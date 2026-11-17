#!/usr/bin/env bash
# Pull the split set of the installed YouTube from a connected device, then audit it against the base
# APK this project patches. Nothing is installed, modified or uninstalled: it only reads.
#
#   tools/extract_splits.sh YouTube.apk ./splits
#
# The device's own copy is the only source that is guaranteed to match what is installed, and it keeps
# Google's APKs off any third-party site.
set -euo pipefail

BASE="${1:?usage: extract_splits.sh BASE_APK OUTPUT_DIR}"
OUT="${2:?usage: extract_splits.sh BASE_APK OUTPUT_DIR}"
PKG=com.google.android.youtube

command -v adb >/dev/null || { echo "adb is not installed" >&2; exit 2; }
DEVICE=$(adb devices | awk 'NR>1 && $2=="device" {print $1; exit}')
[ -n "${DEVICE:-}" ] || { echo "no device attached" >&2; exit 2; }

echo "device:  $DEVICE"
echo "version: $(adb -s "$DEVICE" shell dumpsys package "$PKG" | grep -m1 versionName | tr -d '\r')"
mkdir -p "$OUT"

echo "paths:"
adb -s "$DEVICE" shell pm path "$PKG" | tr -d '\r' | sed 's/^package://' | tee /tmp/paths.txt | sed 's/^/  /'

while read -r remote; do
  [ -n "$remote" ] || continue
  adb -s "$DEVICE" pull "$remote" "$OUT/" >/dev/null
done < /tmp/paths.txt

echo ""
echo "pulled into $OUT:"
ls -lh "$OUT" | sed 's/^/  /'

echo ""
echo "auditing the set against $BASE"
python3 "$(dirname "$0")/split_audit.py" "$BASE" "$OUT"/*.apk \
  --expect-package "$PKG" --expect-abi arm64-v8a --require-libs
