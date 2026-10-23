#!/usr/bin/env python3
"""Build a direct-boot Alpine ARM64 ext4 guest without root privileges."""

import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IM = ROOT / "images"
TOOLS = ROOT / ".tools"


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def download(url, path):
    if not path.exists():
        print("Downloading", url, flush=True)
        urllib.request.urlretrieve(url, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    IM.mkdir(exist_ok=True)
    TOOLS.mkdir(exist_ok=True)
    if (IM / "base.raw").exists():
        raise RuntimeError(
            "base.raw exists; refusing to overwrite assets used by student overlays"
        )
    base = "https://dl-cdn.alpinelinux.org/alpine/v3.23/releases/aarch64/"
    sources = {
        "vmlinuz": "netboot/vmlinuz-virt",
        "alpine-initramfs": "netboot/initramfs-virt",
        "modloop-virt": "netboot/modloop-virt",
        "minirootfs.tar.gz": "alpine-minirootfs-3.23.0-aarch64.tar.gz",
    }
    manifest = {}
    for name, remote in sources.items():
        digest = download(base + remote, IM / name)
        # Verify published distribution checksum for the rootfs; netboot hashes are recorded.
        if name == "minirootfs.tar.gz":
            checksum = (
                urllib.request.urlopen(base + remote + ".sha256", timeout=60)
                .read()
                .decode()
                .split()[0]
            )
            if digest != checksum:
                raise RuntimeError("Alpine rootfs checksum mismatch")
        manifest[name] = {"url": base + remote, "sha256": digest}
    stage = TOOLS / "guest-root"
    init = TOOLS / "guest-init"
    for p in (stage, init):
        if p.exists():
            shutil.rmtree(p)
        p.mkdir()
    with tarfile.open(IM / "minirootfs.tar.gz") as archive:
        archive.extractall(stage, filter="tar")
    run(
        "bash",
        "-c",
        'gzip -dc "$1" | cpio -id --quiet',
        "extract",
        str(IM / "alpine-initramfs"),
        cwd=init,
    )
    modules = TOOLS / "modules-unpacked"
    if modules.exists():
        shutil.rmtree(modules)
    run(
        "unsquashfs",
        "-d",
        str(modules),
        str(IM / "modloop-virt"),
        stdout=subprocess.DEVNULL,
    )
    shutil.copytree(
        modules / "modules", init / "lib/modules", dirs_exist_ok=True, symlinks=True
    )
    shutil.copytree(
        modules / "modules", stage / "lib/modules", dirs_exist_ok=True, symlinks=True
    )
    (init / "init").write_text("""#!/bin/sh
export PATH=/sbin:/bin:/usr/sbin:/usr/bin
/bin/busybox --install -s
mount -t devtmpfs devtmpfs /dev
mount -t proc proc /proc
mount -t sysfs sysfs /sys
modprobe virtio_pci
modprobe virtio_blk
modprobe virtio_net
modprobe ext4
mkdir -p /newroot
for i in $(seq 1 30); do [ -b /dev/vda ] && break; sleep 1; done
mount -t ext4 /dev/vda /newroot || exec sh
umount /proc
umount /sys
exec switch_root /newroot /sbin/init
""")
    (init / "init").chmod(0o755)
    packed = subprocess.check_output(
        ["bash", "-c", "find . -print0 | cpio --null -o -H newc --quiet --owner=0:0"],
        cwd=init,
    )
    (IM / "initramfs.gz").write_bytes(gzip.compress(packed))
    key = IM / "lab_key"
    if not key.exists():
        run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key))
    (stage / "root/.ssh").mkdir(parents=True)
    (stage / "root/.ssh/authorized_keys").write_text(
        key.with_suffix(".pub").read_text()
    )
    (stage / "root/.ssh").chmod(0o700)
    (stage / "etc/hostname").write_text("arm64-lab\n")
    (stage / "etc/resolv.conf").write_text("nameserver 10.0.2.3\n")
    (stage / "etc/apk/repositories").write_text(
        "https://dl-cdn.alpinelinux.org/alpine/v3.23/main\nhttps://dl-cdn.alpinelinux.org/alpine/v3.23/community\n"
    )
    (stage / "etc/inittab").write_text("""::sysinit:/etc/lab-boot
ttyAMA0::respawn:/sbin/getty -L 115200 ttyAMA0 vt100
::ctrlaltdel:/sbin/reboot
::shutdown:/bin/umount -a -r
""")
    (stage / "etc/lab-boot").write_text("""#!/bin/sh
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mkdir -p /dev/pts /run /tmp
mount -t devpts devpts /dev/pts
mount -t tmpfs tmpfs /run
hostname arm64-lab
if [ ! -e /etc/lab-ownership-ready ]; then
  chown 0:0 /
  chown -R 0:0 /bin /sbin /lib /usr /etc /var /root /home
  chmod 700 /root/.ssh
  chmod 600 /root/.ssh/authorized_keys
  touch /etc/lab-ownership-ready
fi
ip link set lo up
ip link set eth0 up
udhcpc -i eth0 -b -s /usr/share/udhcpc/default.script
if [ ! -x /usr/sbin/sshd ]; then
  echo 'Preparing SSH on first boot (requires outbound network)...'
  apk add openssh e2fsprogs || { echo "LAB BOOT ERROR: package installation failed"; exit 1; }
  adduser -D student
  echo 'student:student' | chpasswd
  mkdir -p /etc/ssh/sshd_config.d
  printf 'PermitRootLogin prohibit-password\\nPasswordAuthentication yes\\n' > /etc/ssh/sshd_config.d/lab.conf
fi
ssh-keygen -A
/usr/sbin/sshd || { echo "LAB BOOT ERROR: sshd failed"; exit 1; }
printf '\\nARM64 LAB READY — login student / student\\n'
""")
    (stage / "etc/lab-boot").chmod(0o755)
    # Lock root password; root SSH uses the private local management key only.
    shadow = stage / "etc/shadow"
    shadow.write_text(shadow.read_text().replace("root::", "root:*:"))
    disk = IM / "base.raw"
    if disk.exists():
        raise RuntimeError("base.raw exists; refusing to overwrite")
    with disk.open("wb") as f:
        f.truncate(1024**3)
    run("mkfs.ext4", "-q", "-F", "-d", str(stage), str(disk))
    # e2fsprogs preserves source ownership; normalize it inside the guest first boot.
    manifest["kernel_modules"] = [
        p.name for p in (init / "lib/modules").iterdir() if p.name != "firmware"
    ]
    manifest["bootloader"] = "none: QEMU direct kernel boot"
    (IM / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("Provisioned initial filesystem", disk, flush=True)
    run(sys.executable, str(ROOT / "scripts/prepare_display.py"))
    run(sys.executable, str(ROOT / "scripts/prepare_guest.py"))


if __name__ == "__main__":
    main()
