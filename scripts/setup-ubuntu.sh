#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/qemu-env.sh
source scripts/node-env.sh
missing=0
for tool in qemu-system-aarch64 qemu-img cpio unsquashfs mkfs.ext4 ssh ssh-keygen picocom node npm; do
  command -v "$tool" >/dev/null || missing=1
done
if [[ $missing == 1 ]] || { [[ ! -x .venv/bin/pip ]] && ! python3 -m venv .venv; }; then
  sudo apt-get update
  sudo apt-get install -y python3-venv python3-pip qemu-system-arm qemu-utils cpio squashfs-tools e2fsprogs openssh-client picocom nodejs npm
  python3 -m venv .venv
fi
if ! node -e 'if(Number(process.versions.node.split(".")[0])<20)process.exit(1)'; then
  python3 scripts/install_node.py
  source scripts/node-env.sh
fi
.venv/bin/pip install -r requirements-dev.txt
(cd frontend && npm ci && npm run build)
source scripts/qemu-env.sh
if [[ ! -f images/base.raw ]]; then
  .venv/bin/python scripts/provision.py
elif ! .venv/bin/python -c 'import json; assert json.load(open("images/manifest.json")).get("bootstrap_verified")' 2>/dev/null; then
  if compgen -G 'runtime/media/*.qcow2' >/dev/null; then
    echo 'Unprepared base has existing student overlays. Preserve those files before rebuilding the base.' >&2
    exit 1
  fi
  .venv/bin/python scripts/prepare_guest.py
fi
.venv/bin/python scripts/prepare_display.py
printf '\nReady: ./scripts/start.sh\n'
