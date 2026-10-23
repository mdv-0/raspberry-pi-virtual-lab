"""Real ARM64 boot, host PTY, persistent root disk, QMP networking, power."""

import asyncio
import shutil

import pytest
import serial

from backend.lab import PROJECT, Lab

pytestmark = pytest.mark.skipif(
    not shutil.which("qemu-system-aarch64")
    or not (PROJECT / "images/base.raw").exists(),
    reason="Provision guest and expose QEMU on PATH; see TESTING.md",
)


async def wait_for(predicate, timeout=180):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.2)


async def guest_ready(lab):
    await wait_for(lambda: b"ARM64 LAB READY" in lab.serial.history)
    # Console ready does not prove sshd started successfully.
    for _ in range(90):
        try:
            if "aarch64" in await lab.ssh("uname -m"):
                return
        except ValueError:
            pass
        await asyncio.sleep(1)
    raise AssertionError("SSH never became ready")


def test_real_guest_full_lifecycle(tmp_path):
    async def scenario():
        lab = Lab(tmp_path)
        lab.ssh_port = 2234
        port = None
        try:
            media = await lab.create_media("Integration student")
            lab.insert(media)
            await lab.start()
            await guest_ready(lab)
            assert b"Linux version" in lab.serial.history
            assert b"login:" in lab.serial.history
            assert lab.power == "RUNNING"
            # Read and write through the actual host-side PTY, not a mocked transport.
            lab.serial.connect("host")
            port = serial.Serial(str(lab.serial.path), 115200, timeout=0.1)

            async def read_until(token, timeout=30):
                output = bytearray()
                async with asyncio.timeout(timeout):
                    while token not in output:
                        output.extend(await asyncio.to_thread(port.read, 4096))
                        await asyncio.sleep(0.05)
                return bytes(output)

            port.write(b"\r")
            await read_until(b"login:")
            port.write(b"student\r")
            await read_until(b"Password:")
            port.write(b"student\r")
            await read_until(b"$")
            port.write(b"printf 'UART_%s\\n' VERIFIED\r")
            assert b"UART_VERIFIED" in await read_until(b"UART_VERIFIED")
            await lab.ssh("echo persistent-arm64 > /home/student/proof; sync")
            assert "10.0.2." in await lab.ssh("ip -4 addr show eth0")
            assert "1" == (await lab.ssh("cat /sys/class/net/eth0/carrier")).strip()
            await lab.set_link(False)
            await asyncio.sleep(1)
            assert (await lab.qmp.execute("query-status"))["running"]
            # UART still works while Ethernet is down; verify real guest link state.
            port.reset_input_buffer()
            port.write(b"cat /sys/class/net/eth0/carrier; echo LINK_CHECK_DONE\r")
            assert b"0\r\n" in await read_until(b"0\r\n")
            with pytest.raises(ValueError):
                await lab.ssh("true")
            await lab.set_link(True)
            for _ in range(20):
                try:
                    assert (
                        await lab.ssh("cat /sys/class/net/eth0/carrier")
                    ).strip() == "1"
                    break
                except ValueError:
                    await asyncio.sleep(1)
            else:
                pytest.fail("Ethernet failed to recover")
            port.close()
            lab.serial.disconnect()
            with pytest.raises(ValueError):
                lab.eject()
            await lab.shutdown()
            await wait_for(lambda: lab.process.returncode is not None, 30)
            assert lab.power == "OFF"
            await lab.start()
            await guest_ready(lab)
            assert "persistent-arm64" in await lab.ssh("cat /home/student/proof")
            await lab.qmp.execute("system_reset")
            await asyncio.sleep(1)
            assert lab.process.returncode is None
            await lab.force_stop()
            assert lab.process.returncode is not None
            assert not lab.serial.path.exists()
            lab.eject()
            assert lab.media()[0]["state"] == "AVAILABLE"
        finally:
            if port is not None:
                port.close()
            await lab.close()

    asyncio.run(scenario())


def test_partitioned_import_with_custom_kernel(tmp_path):
    """Boot a real MBR disk, write inside its root partition, reset to import."""
    import gzip
    import struct
    import subprocess
    import tempfile

    async def scenario():
        with tempfile.TemporaryDirectory(prefix="rpb-part-") as directory:
            work = Path(directory)
            init = work / "initrd"
            init.mkdir()
            await asyncio.to_thread(
                subprocess.run,
                ["cpio", "-id", "--quiet"],
                cwd=init,
                input=gzip.decompress((PROJECT / "images/initramfs.gz").read_bytes()),
                check=True,
            )
            script = init / "init"
            script.write_text(script.read_text().replace("/dev/vda", "/dev/vda1"))
            packed = await asyncio.to_thread(
                subprocess.check_output,
                [
                    "bash",
                    "-c",
                    "find . -print0 | cpio --null -o -H newc --quiet --owner=0:0",
                ],
                cwd=init,
            )
            initrd = work / "partition-initramfs.gz"
            initrd.write_bytes(gzip.compress(packed))
            image = work / "buildroot.sdimg"
            base = PROJECT / "images/base.raw"
            offset = 1024**2
            with image.open("wb") as out, base.open("rb") as source:
                mbr = bytearray(512)
                mbr[450] = 0x83
                struct.pack_into(
                    "<II", mbr, 454, offset // 512, base.stat().st_size // 512
                )
                mbr[510:] = b"\x55\xaa"
                out.write(mbr)
                out.seek(offset)
                shutil.copyfileobj(source, out)
            lab = Lab(work / "lab")
            lab.ssh_port = 2236
            try:
                ident = await lab.import_image(image, "Partition boot test")
                await lab.configure_boot(
                    ident,
                    {
                        "profile": "virt-arm64",
                        "kernel_path": str(PROJECT / "images/vmlinuz"),
                        "initrd_path": str(initrd),
                        "cmdline": "console=ttyAMA0 root=/dev/vda1 rw",
                    },
                )
                lab.insert(ident)
                await lab.start()
                await guest_ready(lab)
                assert "/dev/vda1" in await lab.ssh("mount | head -1")
                await lab.ssh(
                    "echo partition-proof > /home/student/partition-proof; sync"
                )
                await lab.force_stop()
                await lab.start()
                await guest_ready(lab)
                assert "partition-proof" in await lab.ssh(
                    "cat /home/student/partition-proof"
                )
                await lab.force_stop()
                assert await lab.reset_media(ident) == ident
                await lab.start()
                await guest_ready(lab)
                assert "RESET_CLEAN" in await lab.ssh(
                    "test ! -e /home/student/partition-proof && echo RESET_CLEAN"
                )
            finally:
                await lab.close()

    from pathlib import Path

    asyncio.run(scenario())


def test_official_pi_image_boot(tmp_path):
    """Optional real Pi 3B boot; provide a decompressed official ARM64 SD image."""
    import os
    from pathlib import Path

    source = os.environ.get("RPI_LAB_TEST_PI_IMAGE")
    if not source:
        pytest.skip("Set RPI_LAB_TEST_PI_IMAGE to an official Pi OS 64-bit .img")

    async def scenario():
        lab = Lab(tmp_path)
        lab.ssh_port = 2237
        try:
            ident = await lab.import_image(
                Path(source), "Official Raspberry Pi OS", "raspi3b"
            )
            lab.insert(ident)
            assert lab.status()["profile"]["id"] == "raspi3b"
            await lab.start()
            await wait_for(
                lambda: any(
                    token in lab.serial.history
                    for token in (
                        b"login:",
                        b"Please create a user",
                        b"Enter new username",
                    )
                ),
                180,
            )
            assert b"Kernel panic" not in lab.serial.history
            assert lab.process.returncode is None
        finally:
            await lab.close()

    asyncio.run(scenario())
