#!/usr/bin/env bash
NODE_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$NODE_PROJECT_ROOT/.tools/node/bin/node" ]]; then
  export PATH="$NODE_PROJECT_ROOT/.tools/node/bin:$PATH"
fi
