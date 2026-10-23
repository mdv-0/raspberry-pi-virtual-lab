"""Disk layout validation and persistent imported-media semantics."""

import asyncio
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.lab import Lab
from backend.storage import inspect_raw


def raw_ext4(path, size=4 * 1024**2):
    with path.open("wb") as f:
        f.truncate(size)
        f.seek(1080)
        f.write(b"\x53\xef")
    return path


def mbr_image(path):
    size = 8 * 1024**2
    with path.open("wb") as f:
        f.truncate(size)
        mbr = bytearray(512)
        mbr[450] = 0x83
        struct.pack_into("<II", mbr, 454, 2048, (size - 1024**2) // 512)
        mbr[510:] = b"\x55\xaa"
        f.write(mbr)
        f.seek(1024**2 + 1080)
        f.write(b"\x53\xef")
    return path


def gpt_image(path):
    size = 8 * 1024**2
    entries = bytearray(128 * 128)
    entries[:16] = bytes([1]) * 16
    struct.pack_into("<QQ", entries, 32, 2048, size // 512 - 34)
    header = bytearray(512)
    header[:8] = b"EFI PART"
    struct.pack_into("<II", header, 8, 0x10000, 92)
    struct.pack_into("<QQQQ", header, 24, 1, size // 512 - 1, 34, size // 512 - 34)
    struct.pack_into("<QIII", header, 72, 2, 128, 128, zlib.crc32(entries))
    struct.pack_into("<I", header, 16, zlib.crc32(header[:92]))
    with path.open("wb") as f:
        f.truncate(size)
        f.seek(512)
        f.write(header)
        f.write(entries)
        f.seek(1024**2 + 1080)
        f.write(b"\x53\xef")
    return path


@pytest.mark.parametrize(
    "factory,table", [(raw_ext4, "none"), (mbr_image, "mbr"), (gpt_image, "gpt")]
)
def test_disk_layouts(tmp_path, factory, table):
    layout = inspect_raw(factory(tmp_path / "disk.img"))
    assert layout["table"] == table
    if table != "none":
        assert layout["partitions"][0]["filesystem"] == "ext4"
        assert layout["partitions"][0]["number"] == 1


def test_reject_truncated_partition_and_bad_gpt(tmp_path):
    path = mbr_image(tmp_path / "disk.img")
    with path.open("r+b") as f:
        f.truncate(2 * 1024**2)
    with pytest.raises(ValueError, match="truncated"):
        inspect_raw(path)
    gpt_image(path)
    with path.open("r+b") as f:
        f.seek(512 + 16)
        f.write(bytes(4))
    with pytest.raises(ValueError, match="checksum"):
        inspect_raw(path)


@pytest.mark.skipif(not shutil.which("qemu-img"), reason="QEMU required")
def test_import_reset_boot_config_and_restart(tmp_path):
    async def scenario():
        source = mbr_image(tmp_path / "build.wic")
        original = source.read_bytes()
        home = tmp_path / "runtime"
        lab = Lab(home)
        try:
            ident = await lab.import_image(source, "Buildroot", "virt-arm64")
            lab.insert(ident)
            # Linux virtio partition naming is /dev/vda1, not /dev/vdap1.
            assert "root=/dev/vda1 " in lab.boot_config()["cmdline"]
            with pytest.raises(ValueError, match="kernel"):
                lab.qemu_args(lab.inserted(), lab.boot_config())
            kernel = tmp_path / "Image"
            kernel.write_bytes(b"guest-kernel")
            config = {
                "profile": "virt-arm64",
                "kernel_path": str(kernel),
                "cmdline": "console=ttyAMA0 root=/dev/vda1 rw",
            }
            await lab.configure_boot(ident, config)
            kernel.write_bytes(b"rebuilt")
            assert Path(lab.boot_config()["kernel"]).read_bytes() == b"guest-kernel"
            disk = lab.inserted()
            await asyncio.to_thread(
                subprocess.run,
                ["qemu-io", "-f", "qcow2", "-c", "write -P 0xab 4096 512", str(disk)],
                check=True,
                capture_output=True,
            )
            assert await lab.reset_media(ident) == ident
            restored = tmp_path / "restored.raw"
            await lab.image_command(
                "convert", "-f", "qcow2", "-O", "raw", disk, restored
            )
            assert restored.read_bytes() == original
            assert source.read_bytes() == original
        finally:
            await lab.close()
        lab = Lab(home)
        try:
            assert lab.boot_config()["cmdline"] == config["cmdline"]
            assert lab.media()[0]["layout"]["table"] == "mbr"
        finally:
            await lab.close()

    asyncio.run(scenario())


@pytest.mark.skipif(not shutil.which("qemu-img"), reason="QEMU required")
def test_import_api_and_no_partial_media(tmp_path, monkeypatch):
    monkeypatch.setenv("RPI_LAB_HOME", str(tmp_path / "runtime"))
    image = mbr_image(tmp_path / "disk.wic")
    with TestClient(app) as client:
        for response in (
            client.post(
                "/api/media/import-path",
                json={"path": str(image), "profile": "virt-arm64"},
            ),
            client.post("/api/media/import", content=image.read_bytes()),
        ):
            assert response.status_code == 200, response.text
        assert (
            client.post(
                "/api/media/import-path", json={"path": "/dev/zero"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/media/import?profile=raspi3b", content=image.read_bytes()
            ).status_code
            == 409
        )
        media = client.get("/api/status").json()["media"]
        assert len(media) == 2
        ident = media[0]["id"]
        assert (
            client.get(f"/api/media/{ident}/inspect").json()["layout"]["table"] == "mbr"
        )
        assert (
            client.post(
                f"/api/media/{ident}/boot", json={"cmdline": "console=ttyAMA0"}
            ).status_code
            == 409
        )
        kernel = tmp_path / "Image"
        kernel.write_bytes(b"kernel")
        assert (
            client.post(
                f"/api/media/{ident}/boot",
                json={
                    "kernel_path": str(kernel),
                    "cmdline": "console=ttyAMA0 root=/dev/vda1 rw",
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/media/{ident}/boot",
                json={"kernel_path": str(kernel), "cmdline": "bad\nline"},
            ).status_code
            == 422
        )
        assert len(list((tmp_path / "runtime/media").glob("*.base.qcow2"))) == 2


@pytest.mark.skipif(not shutil.which("qemu-img"), reason="QEMU required")
def test_delete_cleans_import_but_preserves_source_and_other_media(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RPI_LAB_HOME", str(tmp_path / "runtime"))
    source = mbr_image(tmp_path / "source.img")
    original = source.read_bytes()
    kernel = tmp_path / "Image"
    kernel.write_bytes(b"kernel")
    with TestClient(app) as client:
        ident = client.post(
            "/api/media/import-path", json={"path": str(source)}
        ).json()["id"]
        other = client.post(
            "/api/media/import-path", json={"path": str(source)}
        ).json()["id"]
        assert (
            client.post(
                f"/api/media/{ident}/boot",
                json={
                    "kernel_path": str(kernel),
                    "cmdline": "console=ttyAMA0 root=/dev/vda1 rw",
                },
            ).status_code
            == 200
        )
        client.post(f"/api/media/{ident}/insert")
        assert client.delete(f"/api/media/{ident}").status_code == 409
        client.post("/api/media/eject")
        assert client.delete(f"/api/media/{ident}").status_code == 200
        media = client.get("/api/status").json()["media"]
        assert [m["id"] for m in media] == [other]
        files = list((tmp_path / "runtime/media").iterdir())
        assert len(list((tmp_path / "runtime/media").glob("*.base.qcow2"))) == 1
        assert not any(p.suffix == ".kernel" for p in files)
        assert not any(p.name.startswith(".delete-") for p in files)
        assert source.read_bytes() == original
        assert kernel.read_bytes() == b"kernel"
        assert client.delete(f"/api/media/{ident}").status_code == 409


@pytest.mark.skipif(not shutil.which("qemu-img"), reason="QEMU required")
def test_status_during_disk_creation_has_no_incomplete_row(tmp_path):
    async def scenario():
        lab = Lab(tmp_path / "runtime")
        lab.assets = tmp_path / "assets"
        lab.assets.mkdir()
        raw_ext4(lab.assets / "base.raw")
        started, finish = asyncio.Event(), asyncio.Event()
        command = lab.image_command

        async def delayed_command(*args):
            started.set()
            await finish.wait()
            return await command(*args)

        lab.image_command = delayed_command
        task = asyncio.create_task(lab.create_media("Concurrent status"))
        try:
            await started.wait()
            assert lab.status()["media"] == []
            finish.set()
            ident = await task
            assert lab.status()["media"][0]["id"] == ident
        finally:
            finish.set()
            await task
            await lab.close()

    asyncio.run(scenario())


@pytest.mark.skipif(not shutil.which("qemu-img"), reason="QEMU required")
def test_boot_replacement_reclaims_artifacts_and_failed_save_is_atomic(tmp_path):
    async def scenario():
        lab = Lab(tmp_path / "runtime")
        source = mbr_image(tmp_path / "source.img")
        kernel = tmp_path / "Image"
        kernel.write_bytes(b"kernel")
        try:
            ident = await lab.import_image(source, "Build output")
            lab.insert(ident)
            config = {
                "profile": "virt-arm64",
                "kernel_path": str(kernel),
                "cmdline": "console=ttyAMA0 root=/dev/vda1 rw",
            }
            await lab.configure_boot(ident, config)
            first = Path(lab.boot_config()["kernel"])
            await lab.configure_boot(ident, config)
            second = Path(lab.boot_config()["kernel"])
            assert not first.exists()
            assert second.exists()
            before = set(lab.images.iterdir())
            with pytest.raises(ValueError, match="regular file"):
                await lab.configure_boot(
                    ident, dict(config, dtb_path=str(tmp_path / "missing.dtb"))
                )
            assert set(lab.images.iterdir()) == before
            assert Path(lab.boot_config()["kernel"]) == second
        finally:
            await lab.close()

    asyncio.run(scenario())


def test_gpt_partitions_cannot_overlap_partition_metadata(tmp_path):
    path = gpt_image(tmp_path / "invalid.img")
    with path.open("r+b") as image:
        image.seek(1024)
        entries = bytearray(image.read(128 * 128))
        struct.pack_into("<QQ", entries, 32, 2, 10)
        image.seek(1024)
        image.write(entries)
        image.seek(512)
        header = bytearray(image.read(512))
        struct.pack_into("<I", header, 88, zlib.crc32(entries))
        struct.pack_into("<I", header, 16, 0)
        struct.pack_into("<I", header, 16, zlib.crc32(header[:92]))
        image.seek(512)
        image.write(header)
    with pytest.raises(ValueError, match="usable"):
        inspect_raw(path)
