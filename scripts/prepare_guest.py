#!/usr/bin/env python3
"""Validate the initial rootfs in QEMU, install SSH, then seal a clean base."""

import asyncio
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.lab import PROJECT, Lab


async def prepare():
    assets = PROJECT / "images"
    with tempfile.TemporaryDirectory(prefix="rpb-") as work:
        lab = Lab(Path(work))
        lab.assets = assets
        lab.ssh_port = 2235
        try:
            ident = await lab.create_media("Base preparation")
            lab.insert(ident)
            for attempt in range(3):
                print(
                    f"Validating and preparing ARM64 guest ({attempt + 1}/3)…",
                    flush=True,
                )
                await lab.start()
                async with asyncio.timeout(180):
                    while (
                        b"ARM64 LAB READY" not in lab.serial.history
                        and b"LAB BOOT ERROR" not in lab.serial.history
                    ):
                        if lab.process.returncode is not None:
                            raise RuntimeError("QEMU stopped during provisioning")
                        await asyncio.sleep(0.5)
                if b"ARM64 LAB READY" in lab.serial.history:
                    break
                print(
                    bytes(lab.serial.history).decode(errors="replace")[-2000:],
                    flush=True,
                )
                await lab.force_stop()
            else:
                raise RuntimeError(
                    "Guest bootstrap failed; inspect Alpine network access and rerun setup"
                )
            versions = await lab.ssh(
                "uname -r; cat /etc/alpine-release; apk list --installed openssh busybox"
            )
            await lab.ssh("sync")
            await lab.shutdown()
            async with asyncio.timeout(30):
                while lab.process.returncode is None:
                    await asyncio.sleep(0.2)
            if lab.watcher:
                await lab.watcher
            disk = lab.inserted()
            prepared = assets / "base.prepared.raw"
            proc = await asyncio.create_subprocess_exec(
                "qemu-img",
                "convert",
                "-f",
                "qcow2",
                "-O",
                "raw",
                str(disk),
                str(prepared),
            )
            if await proc.wait():
                raise RuntimeError("Cannot seal prepared base")
            os.replace(prepared, assets / "base.raw")
            os.chmod(assets / "base.raw", 0o444)
            manifest_path = assets / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["prepared_guest_versions"] = versions.splitlines()
            manifest["base_sha256"] = hashlib.file_digest(
                (assets / "base.raw").open("rb"), "sha256"
            ).hexdigest()
            manifest["bootstrap_verified"] = True
            manifest_path.write_text(json.dumps(manifest, indent=2))
            print(
                "Prepared base boots real Linux and accepts SSH:\n" + versions,
                flush=True,
            )
        finally:
            await lab.close()


if __name__ == "__main__":
    asyncio.run(prepare())
