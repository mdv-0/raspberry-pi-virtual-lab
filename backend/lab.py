"""Single-board lifecycle, persistent media metadata, and unprivileged QEMU."""

import asyncio
import json
import logging
import os
import shlex
import shutil
import sqlite3
import uuid
from enum import StrEnum
from pathlib import Path

from backend.storage import extract_pi_boot, inspect_raw, regular_file
from emulator.profiles import PROFILES, peripherals
from emulator.qmp import QMP
from emulator.serial import SerialBroker

log = logging.getLogger(__name__)
PROJECT = Path(__file__).resolve().parents[1]


class Power(StrEnum):
    OFF = "OFF"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


class Lab:
    def __init__(self, home: Path | None = None):
        self.home = (
            home or Path(os.environ.get("RPI_LAB_HOME", PROJECT / "runtime"))
        ).resolve()
        if "," in str(self.home) or len(str(self.home / "serial.sock").encode()) > 100:
            raise ValueError(
                "Runtime path must be short and contain no commas (QEMU/Unix socket constraint)"
            )
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.home, 0o700)
        self.images = self.home / "media"
        self.images.mkdir(exist_ok=True)
        self.assets = Path(
            os.environ.get("RPI_LAB_IMAGES", PROJECT / "images")
        ).resolve()
        if "," in str(self.assets):
            raise ValueError("Guest asset path must not contain commas")
        self.db = sqlite3.connect(self.home / "lab.sqlite3")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS media (id INTEGER PRIMARY KEY, name TEXT, filename TEXT, inserted INTEGER DEFAULT 0)"
        )
        columns = {r[1] for r in self.db.execute("PRAGMA table_info(media)")}
        for name, definition in (
            ("boot", "TEXT DEFAULT '{}'"),
            ("layout", "TEXT DEFAULT '{}'"),
            ("baseline", "TEXT"),
        ):
            if name not in columns:
                self.db.execute(f"ALTER TABLE media ADD COLUMN {name} {definition}")
        self.db.commit()
        self.power = Power.OFF
        self.error = None
        self.process = None
        self.lock = asyncio.Lock()
        self.qmp = QMP()
        self.serial = SerialBroker(self.home)
        self.tasks = []
        self.watcher = None
        self.link = True
        self.ssh_port = int(os.environ.get("RPI_LAB_SSH_PORT", "2222"))
        self.log_path = self.home / "qemu.log"
        self.serial_path = self.home / "serial.sock"
        self.qmp_path = self.home / "qmp.sock"
        self.vnc_path = self.home / "vnc.sock"
        self.events = []

    def record(self, message):
        log.info(message)
        self.events.append(message)
        self.events = self.events[-100:]

    def media(self):
        return [
            {
                "id": r[0],
                "name": r[1],
                "size_bytes": (self.images / r[2]).stat().st_size,
                "boot": json.loads(r[4] or "{}"),
                "layout": json.loads(r[5] or "{}"),
                "state": (
                    "GUEST_RUNNING"
                    if self.power in (Power.RUNNING, Power.STARTING, Power.STOPPING)
                    else "INSERTED"
                )
                if r[3]
                else "AVAILABLE",
            }
            for r in self.db.execute("SELECT * FROM media")
        ]

    def inserted(self):
        row = self.db.execute("SELECT filename FROM media WHERE inserted=1").fetchone()
        return self.images / row[0] if row else None

    def require_off(self):
        if self.process and self.process.returncode is None:
            raise ValueError("Power OFF before changing boot media")

    async def create_media(self, name):
        self.require_off()
        base = self.assets / "base.raw"
        if not base.exists():
            raise ValueError(
                "Provision images first: .venv/bin/python scripts/provision.py"
            )
        filename = f"{uuid.uuid4().hex}.qcow2"
        try:
            await self.image_command(
                "create", "-f", "qcow2", "-F", "raw", "-b", base, self.images / filename
            )
            cursor = self.db.execute(
                "INSERT INTO media(name,filename) VALUES (?,?)", (name, filename)
            )
            self.db.commit()
            return cursor.lastrowid
        except BaseException:
            self.db.rollback()
            (self.images / filename).unlink(missing_ok=True)
            raise

    async def image_command(self, *args):
        proc = await asyncio.create_subprocess_exec(
            "qemu-img",
            *map(str, args),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await proc.communicate()
        except BaseException:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            raise
        if proc.returncode:
            raise ValueError(err.decode(errors="replace"))
        return out

    def boot_config(self):
        row = self.db.execute("SELECT boot FROM media WHERE inserted=1").fetchone()
        return json.loads(row[0] or "{}") if row else {}

    async def import_image(self, source, name, profile="virt-arm64"):
        self.require_off()
        if profile not in ("virt-arm64", "raspi3b"):
            raise ValueError("Unknown board profile")
        layout = await asyncio.to_thread(inspect_raw, source)
        token = uuid.uuid4().hex
        artifacts = self.images / f"{token}.boot"
        baseline = self.images / f"{token}.base.qcow2"
        overlay = self.images / f"{token}.qcow2"
        artifacts.mkdir()
        try:
            if profile == "raspi3b":
                boot = await asyncio.to_thread(
                    extract_pi_boot, source, layout, artifacts
                )
            else:
                root = next(
                    (
                        p["number"]
                        for p in layout["partitions"]
                        if p["filesystem"] == "ext4"
                    ),
                    None,
                )
                boot = {
                    "profile": profile,
                    "kernel": "",
                    "initrd": "",
                    "dtb": "",
                    "cmdline": f"console=ttyAMA0,115200 root=/dev/vda{str(root) if root else ''} rootwait rw",
                    "managed": False,
                }
            await self.image_command(
                "convert", "-f", "raw", "-O", "qcow2", source, baseline
            )
            if profile == "raspi3b":
                # QEMU SD cards require a power-of-two capacity.
                capacity = 1 << (layout["size_bytes"] - 1).bit_length()
                await self.image_command("resize", baseline, capacity)
            baseline.chmod(0o444)
            await self.image_command(
                "create", "-f", "qcow2", "-F", "qcow2", "-b", baseline, overlay
            )
            cursor = self.db.execute(
                "INSERT INTO media(name,filename,boot,layout,baseline) VALUES (?,?,?,?,?)",
                (
                    name[:80],
                    overlay.name,
                    json.dumps(boot),
                    json.dumps(layout),
                    baseline.name,
                ),
            )
            self.db.commit()
            return cursor.lastrowid
        except BaseException:
            self.db.rollback()
            baseline.unlink(missing_ok=True)
            overlay.unlink(missing_ok=True)
            shutil.rmtree(artifacts)
            raise

    async def configure_boot(self, ident, config):
        self.require_off()
        row = self.db.execute("SELECT boot FROM media WHERE id=?", (ident,)).fetchone()
        if not row:
            raise ValueError("Unknown media")
        previous = json.loads(row[0] or "{}")
        profile = config["profile"]
        if profile != previous.get("profile", "virt-arm64"):
            raise ValueError("Board profile is selected when importing the disk")
        boot = dict(previous, profile=profile, cmdline=config["cmdline"], managed=False)
        copied = []
        try:
            for key in ("kernel", "initrd", "dtb"):
                value = config.get(key + "_path", "").strip()
                # Empty field preserves current artifact; explicit removal is separate.
                if value:
                    source = regular_file(value)
                    if source.stat().st_size > 256 * 1024**2:
                        raise ValueError("Boot artifact exceeds 256 MiB")
                    dest = self.images / (uuid.uuid4().hex + "." + key)
                    copied.append(dest)
                    await asyncio.to_thread(shutil.copyfile, source, dest)
                    boot[key] = str(dest)
                elif config.get("clear_" + key):
                    boot[key] = ""
            if not boot.get("kernel"):
                raise ValueError("Specify a kernel path on the host")
            if profile == "raspi3b" and not boot.get("dtb"):
                raise ValueError("Raspberry Pi 3B requires a matching DTB")
            self.db.execute(
                "UPDATE media SET boot=? WHERE id=?", (json.dumps(boot), ident)
            )
            self.db.commit()
        except BaseException:
            self.db.rollback()
            for path in copied:
                path.unlink(missing_ok=True)
            raise
        self.remove_unused_artifacts(
            previous[key] for key in ("kernel", "initrd", "dtb") if previous.get(key)
        )

    def remove_unused_artifacts(self, paths):
        referenced = set()
        for (config,) in self.db.execute("SELECT boot FROM media"):
            boot = json.loads(config or "{}")
            referenced.update(
                Path(boot[key]).resolve()
                for key in ("kernel", "initrd", "dtb")
                if boot.get(key)
            )
        for path in paths:
            path = Path(path).resolve()
            if path.is_relative_to(self.images) and path not in referenced:
                path.unlink(missing_ok=True)
                if (
                    path.parent != self.images
                    and path.parent.is_dir()
                    and not any(path.parent.iterdir())
                ):
                    path.parent.rmdir()

    def insert(self, ident: int):
        self.require_off()
        if not self.db.execute("SELECT 1 FROM media WHERE id=?", (ident,)).fetchone():
            raise ValueError("Unknown media")
        self.db.execute("UPDATE media SET inserted=0")
        self.db.execute("UPDATE media SET inserted=1 WHERE id=?", (ident,))
        self.db.commit()

    def eject(self):
        self.require_off()
        self.db.execute("UPDATE media SET inserted=0")
        self.db.commit()

    async def reset_media(self, ident):
        self.require_off()
        row = self.db.execute(
            "SELECT name, filename, inserted FROM media WHERE id=?", (ident,)
        ).fetchone()
        if not row:
            raise ValueError("Unknown media")
        baseline = self.db.execute(
            "SELECT baseline FROM media WHERE id=?", (ident,)
        ).fetchone()[0]
        if baseline:
            replacement = self.images / (uuid.uuid4().hex + ".qcow2")
            try:
                await self.image_command(
                    "create",
                    "-f",
                    "qcow2",
                    "-F",
                    "qcow2",
                    "-b",
                    self.images / baseline,
                    replacement,
                )
                replacement.replace(self.images / row[1])
            finally:
                replacement.unlink(missing_ok=True)
            return ident
        # Prepare replacement before discarding the old overlay.
        new = await self.create_media(row[0])
        previous_boot = self.db.execute(
            "SELECT boot FROM media WHERE id=?", (ident,)
        ).fetchone()[0]
        self.db.execute("UPDATE media SET boot=? WHERE id=?", (previous_boot, new))
        if row[2]:
            self.insert(new)
        self.db.execute("DELETE FROM media WHERE id=?", (ident,))
        self.db.commit()
        (self.images / row[1]).unlink()
        return new

    def delete_media(self, ident):
        self.require_off()
        row = self.db.execute(
            "SELECT filename,baseline,boot,inserted FROM media WHERE id=?", (ident,)
        ).fetchone()
        if not row:
            raise ValueError("Unknown media")
        if row[3]:
            raise ValueError("Eject this image before deleting it")

        def files(record):
            filename, baseline, config = record[:3]
            paths = {self.images / value for value in (filename, baseline) if value}
            boot = json.loads(config or "{}")
            paths.update(
                Path(boot[key]) for key in ("kernel", "initrd", "dtb") if boot.get(key)
            )
            return {
                path.resolve()
                for path in paths
                if path.resolve().is_relative_to(self.images)
            }

        protected = set()
        for other in self.db.execute(
            "SELECT filename,baseline,boot FROM media WHERE id != ?", (ident,)
        ):
            protected.update(files(other))
        candidates = files(row) - protected
        staging = self.images / (".delete-" + uuid.uuid4().hex)
        staging.mkdir()
        moved = []
        try:
            for path in candidates:
                if path.is_file():
                    temporary = staging / str(len(moved))
                    path.rename(temporary)
                    moved.append((path, temporary))
            self.db.execute("DELETE FROM media WHERE id=?", (ident,))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            for path, temporary in reversed(moved):
                temporary.rename(path)
            staging.rmdir()
            raise
        shutil.rmtree(staging)
        artifact_directory = self.images / (Path(row[0]).stem + ".boot")
        for parent in {path.parent for path in candidates} | {artifact_directory}:
            if parent != self.images and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        self.record("Storage image deleted")

    def qemu_args(self, disk, boot):
        pi = boot.get("profile") == "raspi3b"
        custom = bool(boot)
        kernel = Path(boot.get("kernel") or self.assets / "vmlinuz")
        initrd = (
            boot.get("initrd", "")
            if custom
            else str(
                self.assets
                / (
                    "initramfs-display.gz"
                    if (self.assets / "initramfs-display.gz").exists()
                    else "initramfs.gz"
                )
            )
        )
        if custom and not boot.get("kernel"):
            raise ValueError("Configure this disk's kernel before powering on")
        for path in (
            kernel,
            *([Path(initrd)] if initrd else []),
            *([Path(boot["dtb"])] if boot.get("dtb") else []),
        ):
            if not path.is_file():
                raise ValueError(f"Missing boot artifact: {path}")
        args = [
            "qemu-system-aarch64",
            "-machine",
            "raspi3b" if pi else "virt",
            "-accel",
            "tcg",
            "-m",
            "1024" if pi else "512",
            "-smp",
            "4" if pi else "2",
            "-display",
            "none",
            "-monitor",
            "none",
            "-kernel",
            str(kernel),
            "-append",
            boot.get("cmdline", "console=tty0 console=ttyAMA0 root=/dev/vda rw"),
            "-drive",
            f"file={disk},format=qcow2,if={'sd' if pi else 'virtio'}",
            "-netdev",
            f"user,id=net0,hostfwd=tcp:127.0.0.1:{self.ssh_port}-:22",
            "-device",
            ("usb-net" if pi else "virtio-net-pci")
            + ",netdev=net0,id=nic0,mac=52:54:00:12:34:56"
            + ("" if pi else ",romfile="),
            "-chardev",
            f"socket,id=uart,path={self.serial_path},server=on,wait=off",
            "-serial",
            "chardev:uart",
            "-qmp",
            f"unix:{self.qmp_path},server=on,wait=off",
        ]
        if not pi:
            args.extend(["-cpu", "cortex-a53"])
        if initrd:
            args.extend(["-initrd", initrd])
        if boot.get("dtb"):
            args.extend(["-dtb", boot["dtb"]])
        if os.environ.get("RPI_LAB_QEMU_DATA"):
            args.extend(["-L", os.environ["RPI_LAB_QEMU_DATA"]])
        if (
            not pi
            and (not custom or boot.get("graphics", False))
            and (self.assets / "initramfs-display.gz").exists()
        ):
            args.extend(
                [
                    "-device",
                    "virtio-gpu-pci,id=gpu0,xres=1024,yres=768",
                    "-device",
                    "virtio-keyboard-pci,id=kbd0,display=gpu0",
                    "-vnc",
                    f"unix:{self.vnc_path},share=allow-exclusive",
                ]
            )
        return args

    async def start(self):
        self.require_off()
        if self.watcher:
            await self.watcher
        await self.qmp.close()
        disk = self.inserted()
        if not disk:
            raise ValueError("Insert boot media first")
        boot = self.boot_config()
        args = self.qemu_args(disk, boot)
        self.error = None
        self.power = Power.STARTING
        self.serial.history.clear()
        self.qmp = QMP()
        for path in (self.serial_path, self.qmp_path, self.vnc_path):
            path.unlink(missing_ok=True)
        try:
            with self.log_path.open("wb") as logfile:
                self.process = await asyncio.create_subprocess_exec(
                    *args, stdout=logfile, stderr=logfile
                )
            self.tasks = [task for task in self.tasks if not task.done()]
            self.watcher = asyncio.create_task(self.watch(self.process))
            self.tasks.append(self.watcher)
            self.tasks.append(asyncio.create_task(self.serial.attach(self.serial_path)))
            await self.qmp.connect(self.qmp_path)
            await self.qmp.execute("set_link", {"name": "nic0", "up": self.link})
            self.power = Power.RUNNING
            self.record("QEMU running; serial output reports guest boot progress.")
        except Exception as exc:
            await self.force_stop()
            self.error = str(exc)
            self.power = Power.ERROR
            raise ValueError(self.error) from exc

    async def watch(self, process):
        code = await process.wait()
        expected = self.power == Power.STOPPING
        self.power = Power.OFF if expected or code == 0 else Power.ERROR
        if code != 0 and not expected:
            self.error = f"QEMU exited ({code}); see diagnostics"
        await self.serial.close()
        self.record(f"QEMU exited with status {code}")

    async def force_stop(self):
        if self.process and self.process.returncode is None:
            self.power = Power.STOPPING
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        await self.serial.close()
        await self.qmp.close()
        self.power = Power.OFF
        self.record("Power off; forced interruption can damage the writable overlay.")

    async def ssh(self, command):
        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-i",
            str(self.assets / "lab_key"),
            "-p",
            str(self.ssh_port),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={self.home / 'known_hosts'}",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "BatchMode=yes",
            "root@127.0.0.1",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), 15)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise ValueError("Guest SSH timed out")
        if proc.returncode:
            raise ValueError(err.decode())
        return out.decode()

    async def shutdown(self):
        if self.power != Power.RUNNING:
            raise ValueError("Guest is not running")
        # ACPI power-button handling is not configured in this minimal guest.
        # Authenticated SSH invokes actual guest poweroff; never silently force off.
        if self.boot_config() and not self.boot_config().get("managed"):
            raise ValueError(
                "Custom image: run sudo poweroff in the VS Code UART/SSH terminal; management SSH is not provisioned"
            )
        await self.ssh('nohup sh -c "sleep 1; poweroff" >/dev/null 2>&1 </dev/null &')
        self.power = Power.STOPPING
        self.record("Guest graceful poweroff requested via management SSH.")

    async def set_link(self, up):
        if self.power == Power.RUNNING:
            await self.qmp.execute("set_link", {"name": "nic0", "up": up})
        self.link = up
        self.record(f"Ethernet link {'connected' if up else 'disconnected'}")

    def log_tail(self, size=8000):
        if not self.log_path.exists():
            return ""
        with self.log_path.open("rb") as source:
            source.seek(0, 2)
            source.seek(max(0, source.tell() - size))
            return source.read(size).decode(errors="replace")

    def status(self):
        manifest = self.assets / "manifest.json"
        boot = self.boot_config()
        pi = boot.get("profile") == "raspi3b"
        devices = peripherals()
        if pi:
            for device in devices:
                if device["id"] == "boot0":
                    device.update(
                        display_name="SD card", connector="SD/MMC", driver="QEMU SDHCI"
                    )
                elif device["id"] == "net0":
                    device.update(
                        display_name="USB Ethernet",
                        connector="USB",
                        driver="QEMU usb-net",
                        limitation="Emulated USB Ethernet adapter. Guest kernel needs USB networking drivers. Native Pi Ethernet and Wi-Fi are not emulated.",
                    )
                elif device["id"] == "display0":
                    device.update(
                        limitation="Pi framebuffer hardware is emulated; this application exposes terminal access only. Desktop and GPU acceleration are not validated."
                    )
        return {
            "power": self.power,
            "error": self.error,
            "pid": self.process.pid
            if self.process and self.process.returncode is None
            else None,
            "profile": next(
                p
                for p in PROFILES
                if p["id"] == self.boot_config().get("profile", "virt-arm64")
            ),
            "profiles": PROFILES,
            "peripherals": peripherals(),
            "media": self.media(),
            "uart": {
                "mode": self.serial.mode,
                "endpoint": str(self.serial.path)
                if self.serial.mode == "host"
                else None,
                "dropped_bytes": self.serial.dropped_host_bytes,
                "policy": "One host terminal at a time. Use the flock command in your VS Code terminal. Browser consoles are disabled.",
            },
            "display": {
                "supported": (self.assets / "initramfs-display.gz").exists(),
                "available": self.power == Power.RUNNING and self.vnc_path.exists(),
                "viewer_connected": False,
                "viewer_supported": False,
                "backend": "QEMU virtio-gpu / VNC",
                "resolution": "1024 × 768",
                "keyboard": "virtio keyboard",
                "limitation": "Real Linux framebuffer console; no desktop installed. Closing the viewer does not unplug the GPU. Browser viewer and keyboard access are disabled by application policy.",
            },
            "network": {
                "link": self.link,
                "backend": "QEMU user-mode NAT",
                "mac": "52:54:00:12:34:56",
                "guest_ip": None,
                "ssh": f"ssh -p {self.ssh_port} student@127.0.0.1",
            },
            "commands": {
                "uart": shlex.join(
                    [
                        "flock",
                        "-n",
                        str(self.home / "uart.lock"),
                        "picocom",
                        "-b",
                        "115200",
                        str(self.serial.path),
                    ]
                ),
                "logs": shlex.join(["tail", "-f", str(self.home / "qemu.log")]),
            },
            "events": self.events,
            "qmp_events": self.qmp.events[-20:],
            "guest": json.loads(manifest.read_text()) if manifest.exists() else None,
            "diagnostics": self.log_tail(),
        }

    async def close(self):
        await self.force_stop()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.db.close()
