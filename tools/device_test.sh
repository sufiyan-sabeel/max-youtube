#!/usr/bin/env bash
# Device validation for MAX YouTube. Runs every check it can and reports PENDING for anything that needs
# hardware it does not have. Nothing here is claimed to pass unless it printed PASS.
#
#   tools/device_test.sh path/to/MAX-YouTube-...-DUAL-TEST.apk [split.apk ...]
#
# With split APKs it installs the whole set with `install-multiple`; without them it explains why a
# base-only install cannot work on a modern device.
set -uo pipefail

APK="${1:?usage: device_test.sh APK [split.apk ...]}"
shift || true
SPLITS=("$@")

PKG=app.maxyoutube.client
OFFICIAL=com.google.android.youtube
pass=0; fail=0; pending=0

say()  { printf '%s\n' "$*"; }
ok()   { pass=$((pass+1));    say "  PASS     $*"; }
bad()  { fail=$((fail+1));    say "  FAIL     $*"; }
wait() { pending=$((pending+1)); say "  PENDING  $*"; }

say "MAX YouTube device validation"
say "apk:    $APK"
say "splits: ${#SPLITS[@]}"
say ""

if ! command -v adb >/dev/null 2>&1; then
  say "adb is not installed: every device check is PENDING."
  say "Install platform-tools, then run this again."
  exit 2
fi

DEVICE=$(adb devices | awk 'NR>1 && $2=="device" {print $1; exit}')
if [ -z "${DEVICE:-}" ]; then
  say "no device attached: every device check is PENDING."
  say "Connect the Vivo Y31 5G with USB debugging on, authorise the prompt, then run this again."
  exit 2
fi

say "device: $DEVICE"
say "android: $(adb -s "$DEVICE" shell getprop ro.build.version.release | tr -d '\r')  sdk $(adb -s "$DEVICE" shell getprop ro.build.version.sdk | tr -d '\r')  abi $(adb -s "$DEVICE" shell getprop ro.product.cpu.abi | tr -d '\r')"
say ""

say "1. the official app is present and will not be touched"
if adb -s "$DEVICE" shell pm list packages "$OFFICIAL" | grep -q "$OFFICIAL"; then
  ok "official YouTube is installed; this procedure never uninstalls or replaces it"
  adb -s "$DEVICE" shell dumpsys package "$OFFICIAL" | grep -m1 versionName | sed 's/^/           /'
else
  wait "official YouTube is not installed on this device"
fi

say ""
say "2. install"
if [ "${#SPLITS[@]}" -gt 0 ]; then
  # Every APK in a split set must carry the same signature, so the splits have to be re-signed with the
  # same key as the base. Otherwise the install fails with INSTALL_FAILED_INVALID_APK / signature mismatch.
  if adb -s "$DEVICE" install-multiple -r "$APK" "${SPLITS[@]}" 2>&1 | tee /tmp/install.log | grep -q Success; then
    ok "installed base plus ${#SPLITS[@]} splits"
  else
    bad "install-multiple failed: $(tail -2 /tmp/install.log | tr '\n' ' ')"
  fi
else
  say "  note     the base APK declares requiredSplitTypes=base__abi,base__density and ships no lib/,"
  say "           so a base-only install is expected to fail with INSTALL_FAILED_MISSING_SPLIT."
  if adb -s "$DEVICE" install -r "$APK" 2>&1 | tee /tmp/install.log | grep -q Success; then
    ok "base installed on its own (unexpected: the device accepted a split-requiring base)"
  else
    bad "base-only install refused: $(tail -2 /tmp/install.log | tr '\n' ' ')"
  fi
fi

say ""
say "3. both packages coexist"
for p in "$OFFICIAL" "$PKG"; do
  if adb -s "$DEVICE" shell pm list packages "$p" | grep -q "^package:$p$"; then
    ok "$p is installed"
  else
    bad "$p is not installed"
  fi
done

say ""
say "4. both appear in the launcher"
for p in "$OFFICIAL" "$PKG"; do
  label=$(adb -s "$DEVICE" shell cmd package resolve-activity --brief -c android.intent.category.LAUNCHER "$p" 2>/dev/null | tail -1 | tr -d '\r')
  if [ -n "$label" ]; then ok "$p resolves a launcher activity: $label"; else bad "$p resolves no launcher activity"; fi
done

say ""
say "5. cold launch"
adb -s "$DEVICE" shell am force-stop "$PKG"
adb -s "$DEVICE" logcat -c
if adb -s "$DEVICE" shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; then
  ok "launcher intent accepted"
else
  bad "the launcher intent was rejected"
fi
sleep 8
if adb -s "$DEVICE" shell pidof "$PKG" >/dev/null 2>&1; then
  ok "process is running after launch"
else
  bad "no process: the app crashed or never started"
fi
adb -s "$DEVICE" logcat -d > /tmp/maxyoutube-logcat.txt
say "  logcat   /tmp/maxyoutube-logcat.txt ($(wc -l < /tmp/maxyoutube-logcat.txt) lines)"
grep -E "FATAL EXCEPTION|AndroidRuntime.*(E |F )" /tmp/maxyoutube-logcat.txt | head -5 | sed 's/^/           /' || true

say ""
say "6. crash check after 30 seconds of use"
say "  manual   open MAX YouTube, play a video, search, open a channel, then press back"
say "  manual   afterwards run: adb logcat -d | grep -E 'FATAL|ANR'"
wait "navigation, playback and UI need a human on the device; results are not claimed here"

say ""
say "7. features expected to be affected by the new package id"
for f in "Google sign-in" "notifications" "deep links" "casting"; do
  wait "$f — unverified under app.maxyoutube.client"
done

say ""
say "$pass passed, $fail failed, $pending pending"
[ "$fail" -eq 0 ] || exit 1
