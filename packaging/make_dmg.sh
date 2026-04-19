#!/usr/bin/env bash
# Build a distributable .dmg from dist/ShotTrainer.app.
#
# Uses macOS's built-in hdiutil so there's no third-party dependency.
# The result lands at dist/ShotTrainer-macOS.dmg by default; pass an
# alternative path as the first argument.

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "make_dmg.sh only runs on macOS (hdiutil is not available elsewhere)." >&2
    exit 1
fi

here="$(cd "$(dirname "$0")" && pwd)"
project_root="$(cd "$here/.." && pwd)"
app="$project_root/dist/ShotTrainer.app"
out="${1:-$project_root/dist/ShotTrainer-macOS.dmg}"

if [[ ! -d "$app" ]]; then
    echo "$app not found. Run \`make package\` first." >&2
    exit 1
fi

stage="$(mktemp -d -t shottrainer-dmg)"
trap 'rm -rf "$stage"' EXIT

cp -R "$app" "$stage/"
ln -s /Applications "$stage/Applications"

rm -f "$out"
hdiutil create \
    -volname "ShotTrainer" \
    -srcfolder "$stage" \
    -ov \
    -format UDZO \
    "$out"

echo "Wrote $out"
