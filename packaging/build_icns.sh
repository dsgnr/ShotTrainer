#!/usr/bin/env bash
# Build packaging/icon.icns from the PNG icons under
# src/shottrainer/ui/assets/. macOS only; uses the system iconutil.
#
# Run this once before `make package` on macOS. The output is ignored by
# git (see .gitignore) so each build produces a fresh icon set.

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "build_icns.sh only runs on macOS (iconutil is not available elsewhere)." >&2
    exit 1
fi

here="$(cd "$(dirname "$0")" && pwd)"
project_root="$(cd "$here/.." && pwd)"
assets="$project_root/src/shottrainer/ui/assets"
out="$here/icon.icns"

work="$(mktemp -d -t shottrainer-icns)"
iconset="$work/icon.iconset"
mkdir -p "$iconset"
trap 'rm -rf "$work"' EXIT

# iconutil expects canonical names. The table maps each source size
# to the icns entries it should populate. Pairs are
# "<source-size>:<dest-name>".
mappings=(
    "16:icon_16x16.png"
    "32:icon_32x32.png"
    "32:icon_16x16@2x.png"
    "64:icon_32x32@2x.png"
    "128:icon_128x128.png"
    "256:icon_128x128@2x.png"
    "256:icon_256x256.png"
    "512:icon_256x256@2x.png"
    "512:icon_512x512.png"
)

for entry in "${mappings[@]}"; do
    size="${entry%%:*}"
    name="${entry##*:}"
    src="$assets/icon_${size}.png"
    if [[ ! -f "$src" ]]; then
        echo "Missing source: $src" >&2
        exit 1
    fi
    cp "$src" "$iconset/$name"
done

iconutil -c icns "$iconset" -o "$out"
echo "Wrote $out"
