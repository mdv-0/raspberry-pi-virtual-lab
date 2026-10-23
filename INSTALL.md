# Installation

Recommended host: Ubuntu 24.04 LTS or newer supported Ubuntu, x86_64; Python 3.12+, Node 20+ or Node 22, 4 GiB free disk. Runtime works without root. Development was exercised on Ubuntu 24.10 with Python 3.12.7 and a user-owned QEMU 9.0.2; that Ubuntu release uses archived repositories.

`./scripts/setup-ubuntu.sh` installs dependencies as needed (and an official, checksummed user-owned Node 22 build if Ubuntu provides Node older than 20), creates a virtual environment, builds the frontend and provisions the guest. Run `./scripts/start.sh` to serve on 127.0.0.1:8000 and open a browser. Running `./scripts/start.sh` again reuses a healthy server for the same runtime directory and opens its browser page; it does not launch another copy. A busy runtime without a verified server produces a short diagnostic. A leftover lock file after shutdown is harmless: the operating system releases the lock when its owner exits. Do not delete a live instance lock. Ctrl-C in the original server terminal stops the server and its guest. Server exit forces guest shutdown; shut down from the UI first to flush filesystems.

Manual setup:

```bash
sudo apt-get install python3-venv qemu-system-arm qemu-utils cpio squashfs-tools e2fsprogs openssh-client picocom nodejs npm
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/provision.py
cd frontend
npm ci
npm run build
cd ..
./scripts/start.sh
```

Development: run `.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000` and `cd frontend && npm run dev` separately. Source `scripts/qemu-env.sh` first if using the isolated project QEMU installation.

Environment settings: `RPI_LAB_HOME` (runtime directory, default project `runtime/`), `RPI_LAB_IMAGES` (guest assets, default project `images/`), `RPI_LAB_SSH_PORT` (default 2222), `RPI_LAB_NO_BROWSER=1` (suppress browser launch), `RPI_LAB_ORIGINS` (comma-separated exact browser origins). Paths must not contain commas because QEMU drive syntax uses them. Keep sockets on a short local path (Unix socket paths have a platform length limit).

Guest provisioning uses Alpine 3.23 minirootfs 3.23.0 and the maintained 3.23 netboot kernel/module bundle. Rootfs checksum is checked against the official HTTPS checksum; downloaded SHA-256 hashes, sources, kernel version and direct-boot status are saved in `images/manifest.json`. The netboot URLs and APK repository are rolling within that release branch. Archive the manifest and assets to reproduce an exact installed lab; rerunning later can obtain updated packages. Setup boots a temporary guest, installs SSH and the student account, verifies AArch64 SSH access, gracefully shuts down, and seals the prepared filesystem as the base image. The guest reports installed versions with `uname -r`, `cat /etc/alpine-release`, and `apk list --installed`. Version output and a prepared base hash are recorded in the manifest. Provisioning refuses to overwrite an existing base disk.

`images/base.raw` is the read-only template. Every student works in a separate `runtime/media/*.qcow2` overlay. Reset creates a fresh overlay, discarding that student's changes. Do not move the base image while overlays reference it. Keep `images/lab_key` private; it is the root management SSH key. The student account is unprivileged. SSH and HTTP bind only to loopback.

Offline image editing: power OFF, eject the disk, and stop the app to prevent another session inserting it. Install libguestfs tools separately if desired. Inspect using `virt-filesystems -a runtime/media/<disk>.qcow2 --all --long`; open `guestfish --rw -a runtime/media/<disk>.qcow2 -m /dev/sda`. This guest uses whole-disk ext4, not partitions. Never mount the same writable image in the guest and host. The app does not offer a host mount operation, so HOST_MOUNTED is not an implemented state. Import supports raw ext4 and primary MBR/GPT disk images up to 64 GiB, with per-disk kernel/initramfs/DTB and command-line settings. See [image import and Pi OS compatibility](docs/IMAGES.md). qcow2 imports and backing chains are rejected by accepting raw input only. For a partitioned disk, inspect its actual layout and use the appropriate partition when editing offline.
