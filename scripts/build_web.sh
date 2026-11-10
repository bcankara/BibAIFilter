#!/usr/bin/env bash
# Build the web interface and copy it into the Python package (src/bibaifilter/_web).
# Needed only for development checkouts and for building the wheel; end users install
# the wheel (`pip install bibaifilter`) and do not need Node.js.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/web"
[ -d node_modules ] || npm ci --no-audit --no-fund
BIBAIFILTER_BUILD_MODE=static npx next build
rm -rf "$ROOT/src/bibaifilter/_web"
cp -R out "$ROOT/src/bibaifilter/_web"
echo "Web interface copied to src/bibaifilter/_web"
