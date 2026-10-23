#!/usr/bin/env bash
# Playwright owns a disposable server; never reuse the student's running instance.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/qemu-env.sh
browser_runtime=$(mktemp -d /tmp/rpb-browser-XXXXXX)
browser_server_pid=""
cleanup() {
  if [[ -n "$browser_server_pid" ]]; then
    kill "$browser_server_pid" 2>/dev/null || true
    wait "$browser_server_pid" 2>/dev/null || true
  fi
  .venv/bin/python - "$browser_runtime" <<'PY'
import shutil
import sys
shutil.rmtree(sys.argv[1])
PY
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
RPI_LAB_HOME="$browser_runtime" RPI_LAB_SSH_PORT=2240 RPI_LAB_ORIGINS=http://127.0.0.1:8001 \
  .venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8001 &
browser_server_pid=$!
wait "$browser_server_pid"
