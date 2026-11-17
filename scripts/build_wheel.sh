#!/usr/bin/env bash
# Build a self-contained wheel (web interface included) into dist/.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT/scripts/build_web.sh"
cd "$ROOT"
"${PYTHON:-python3}" -m pip install --quiet --upgrade build
rm -rf dist build
"${PYTHON:-python3}" -m build --wheel
ls -1 dist
