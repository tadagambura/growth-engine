#!/usr/bin/env bash
# Copy the FluidStick engine and Kaos's costumes from the master repo into render/vendor.
# Master is the source of truth for how Kaos looks; never edit render/vendor by hand.
#   scripts/sync_render_vendor.sh "/path/to/App Portfolio"
set -euo pipefail
MASTER="${1:?path to the master App Portfolio repo}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cp "$MASTER/site/src/assets/fluidstick.js" "$HERE/render/vendor/fluidstick.js"
cp "$MASTER/site/src/assets/costumes.js"   "$HERE/render/vendor/costumes.js"
for f in fluidstick costumes; do sed -i "1i // VENDORED from the master App Portfolio repo (scripts/sync_render_vendor.sh). Do not edit here." "$HERE/render/vendor/$f.js"; done
cp "$MASTER/site/src/assets/logo-mark.svg" "$HERE/render/vendor/logo-mark.svg"
mkdir -p "$HERE/render/vendor/fonts"
cp "$MASTER/site/src/assets/fonts/bagel-fat-one-latin.woff2" "$HERE/render/vendor/fonts/"
echo "synced $(wc -c < "$HERE/render/vendor/fluidstick.js") bytes of fluidstick.js from $MASTER"
