#!/usr/bin/env bash
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$PROJECT_ROOT/.tools/root/usr/bin/qemu-system-aarch64" ]]; then
  export RPI_LAB_QEMU_DATA="$PROJECT_ROOT/.tools/root/usr/share/qemu"
  export QEMU_MODULE_DIR="$PROJECT_ROOT/.tools/root/usr/lib/x86_64-linux-gnu/qemu"
  export PATH="$PROJECT_ROOT/.tools/root/usr/bin:$PATH"
  export LD_LIBRARY_PATH="$PROJECT_ROOT/.tools/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
