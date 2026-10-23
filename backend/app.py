import asyncio
import fcntl
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.lab import PROJECT, Lab
from backend.storage import MAX_IMAGE, regular_file

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
lab: Lab


def trusted_origin(origin):
    return not origin or origin in os.environ.get(
        "RPI_LAB_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")


@asynccontextmanager
async def lifespan(app):
    global lab
    lab = Lab()
    instance = (lab.home / "instance.lock").open("a+")
    try:
        fcntl.flock(instance, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        instance.close()
        lab.db.close()
        raise RuntimeError("Another lab instance owns this runtime directory")
    instance.seek(0)
    instance.truncate()
    instance.write(str(os.getpid()) + "\n")
    instance.flush()
    try:
        yield
    finally:
        await lab.close()
        instance.close()


app = FastAPI(title="Raspberry Pi Virtual Lab", lifespan=lifespan)


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]
    if host not in ("127.0.0.1", "localhost", "testserver") or not trusted_origin(
        request.headers.get("origin")
    ):
        return JSONResponse({"detail": "Local origin required"}, status_code=403)
    return await call_next(request)


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(RuntimeError)
async def runtime_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=503)


class MediaName(BaseModel):
    name: str = Field(default="Student workspace", min_length=1, max_length=80)


class UARTMode(BaseModel):
    mode: str = Field(pattern="^(host|disconnected)$")


class Link(BaseModel):
    up: bool


@app.get("/api/instance")
async def instance_identity():
    return {
        "application": "raspberry-pi-virtual-lab",
        "runtime_directory": str(lab.home),
        "pid": os.getpid(),
    }


@app.get("/api/status")
async def status():
    return lab.status()


@app.post("/api/power/{action}")
async def power(action: str):
    async with lab.lock:
        if action == "on":
            await lab.start()
        elif action == "off":
            await lab.force_stop()
        elif action == "shutdown":
            await lab.shutdown()
        elif action == "reset":
            if lab.power != "RUNNING":
                raise ValueError("Guest is not running")
            await lab.qmp.execute("system_reset")
            lab.record("Hardware reset; unflushed data may be lost.")
        else:
            raise HTTPException(404, "Unknown power action")
    return lab.status()


@app.post("/api/media")
async def create_media(body: MediaName):
    async with lab.lock:
        ident = await lab.create_media(body.name)
    return {"id": ident}


@app.post("/api/media/{ident}/insert")
async def insert(ident: int):
    async with lab.lock:
        lab.insert(ident)
    return lab.status()


@app.post("/api/media/eject")
async def eject():
    async with lab.lock:
        lab.eject()
    return lab.status()


@app.post("/api/media/{ident}/reset")
async def reset_media(ident: int):
    async with lab.lock:
        ident = await lab.reset_media(ident)
    return {"id": ident}


@app.delete("/api/media/{ident}")
async def delete_media(ident: int):
    async with lab.lock:
        lab.delete_media(ident)
    return lab.status()


@app.get("/api/media/{ident}/inspect")
async def inspect(ident: int):
    async with lab.lock:
        row = lab.db.execute(
            "SELECT filename FROM media WHERE id=?", (ident,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Unknown media")
        proc = await asyncio.create_subprocess_exec(
            "qemu-img",
            "info",
            "--output=json",
            str(lab.images / row[0]),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode:
            raise ValueError(err.decode())
        return {
            "image": json.loads(out),
            "layout": json.loads(
                lab.db.execute(
                    "SELECT layout FROM media WHERE id=?", (ident,)
                ).fetchone()[0]
                or "{}"
            ),
            "boot": json.loads(
                lab.db.execute(
                    "SELECT boot FROM media WHERE id=?", (ident,)
                ).fetchone()[0]
                or "{}"
            ),
            "host_mount": "Power off and eject before offline editing. Original imports are never modified.",
        }


class LocalImage(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    profile: str = Field(default="virt-arm64", pattern="^(virt-arm64|raspi3b)$")


class BootConfig(BaseModel):
    profile: str = Field(default="virt-arm64", pattern="^(virt-arm64|raspi3b)$")
    kernel_path: str = Field(default="", max_length=4096)
    initrd_path: str = Field(default="", max_length=4096)
    dtb_path: str = Field(default="", max_length=4096)
    clear_initrd: bool = False
    clear_dtb: bool = False
    cmdline: str = Field(min_length=1, max_length=4096, pattern=r"^[^\x00\r\n]+$")


@app.post("/api/media/import-path")
async def import_local_image(body: LocalImage):
    async with lab.lock:
        lab.require_off()
        source = regular_file(body.path)
        ident = await lab.import_image(source, source.name, body.profile)
    return {"id": ident}


@app.post("/api/media/{ident}/boot")
async def configure_boot(ident: int, body: BootConfig):
    async with lab.lock:
        await lab.configure_boot(ident, body.model_dump())
    return lab.status()


@app.post("/api/media/import")
async def import_media(
    request: Request, profile: str = "virt-arm64", name: str = "Imported disk image"
):
    async with lab.lock:
        lab.require_off()
        temp = lab.images / "upload.part"
        size = 0
        try:
            with temp.open("wb") as file:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_IMAGE:
                        raise ValueError("Maximum import size is 64 GiB")
                    file.write(chunk)
            ident = await lab.import_image(temp, name, profile)
            return {"id": ident}
        finally:
            temp.unlink(missing_ok=True)


@app.post("/api/uart")
async def uart(body: UARTMode):
    async with lab.lock:
        if body.mode == "disconnected":
            lab.serial.disconnect()
        else:
            lab.serial.connect(body.mode)
    return lab.status()


@app.post("/api/network")
async def network(body: Link):
    async with lab.lock:
        await lab.set_link(body.up)
    return lab.status()


@app.websocket("/api/serial")
@app.websocket("/api/display")
async def browser_console_disabled(ws: WebSocket):
    await ws.close(
        code=1008, reason="Console access is available through host terminals only"
    )


static = PROJECT / "frontend/dist"
if static.exists():
    app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
