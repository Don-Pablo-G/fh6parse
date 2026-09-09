#!/usr/bin/env bash
# Native Linux one-file build (run this script on Linux).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m PyInstaller --noconfirm --clean \
  --distpath dist/linux \
  --workpath build/linux \
  packaging/fh6parse.spec

chmod +x dist/linux/fh6parse
echo "Built dist/linux/fh6parse"
