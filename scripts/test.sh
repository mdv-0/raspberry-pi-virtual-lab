#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/qemu-env.sh
.venv/bin/pytest -v "$@"
