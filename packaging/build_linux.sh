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
STAMP="$(python3 -c "from fh6parse._version import package_stamp; print(package_stamp())")"
mkdir -p dist/packages
cp -a dist/linux/fh6parse "dist/packages/fh6parse-${STAMP}-linux-x86_64"
echo "Built dist/linux/fh6parse"
echo "Packaged dist/packages/fh6parse-${STAMP}-linux-x86_64"
