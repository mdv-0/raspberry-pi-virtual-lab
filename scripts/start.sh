#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/qemu-env.sh
if [[ ! -x .venv/bin/uvicorn || ! -f frontend/dist/index.html ]]; then
  echo 'Run ./scripts/setup-ubuntu.sh first.' >&2; exit 1
fi
check_status=0
.venv/bin/python scripts/check_running.py || check_status=$?
if [[ $check_status == 10 ]]; then
  if [[ "${RPI_LAB_NO_BROWSER:-0}" != 1 ]]; then
    xdg-open http://127.0.0.1:8000 >/dev/null 2>&1 || true
  fi
  exit 0
elif [[ $check_status != 0 ]]; then
  exit "$check_status"
fi
if [[ "${RPI_LAB_NO_BROWSER:-0}" != 1 ]]; then
  (sleep 2; xdg-open http://127.0.0.1:8000 >/dev/null 2>&1 || true) &
fi
exec .venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
