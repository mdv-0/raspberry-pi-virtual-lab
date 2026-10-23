#!/usr/bin/env python3
"""Add real virtio GPU/input and tty1 support without rewriting any disk image."""

import gzip
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare_display(images: Path = ROOT / "images") -> None:
    with tempfile.TemporaryDirectory(prefix="rpb-display-") as work:
        directory = Path(work)
        with (images / "initramfs.gz").open("rb") as source:
            archive = gzip.decompress(source.read())
        subprocess.run(
            ["cpio", "-id", "--quiet"], cwd=directory, input=archive, check=True
        )
        init = directory / "init"
        text = init.read_text()
        text = text.replace(
            "modprobe virtio_net\n",
            "modprobe virtio_net\nmodprobe virtio_gpu\nmodprobe virtio_input\n",
        )
        text = text.replace(
            "umount /proc\n",
            """# Managed lab images get a separate real framebuffer console and login.
# Existing student files and the base disk are preserved.
if [ -f /newroot/etc/lab-boot ] && ! grep -q '^tty1::' /newroot/etc/inittab; then
  cp -p /newroot/etc/inittab /newroot/etc/inittab.before-display
  printf '\\ntty1::respawn:/sbin/getty 38400 tty1 linux\\n' >> /newroot/etc/inittab
fi
umount /proc
""",
        )
        init.write_text(text)
        packed = subprocess.check_output(
            [
                "bash",
                "-c",
                "find . -print0 | cpio --null -o -H newc --quiet --owner=0:0",
            ],
            cwd=directory,
        )
        target = images / "initramfs-display.gz"
        temp = target.with_suffix(".tmp")
        temp.write_bytes(gzip.compress(packed))
        os.replace(temp, target)
        print("Prepared virtio GPU/input initramfs; guest disks preserved.")


if __name__ == "__main__":
    prepare_display()
