# Device validation — procedure, and the blocker that has to be cleared first

Target: **Vivo Y31 5G, Android 16**, package `app.maxyoutube.client`, beside the official YouTube.

## The blocker: the published APK is not standalone-installable

This was checked, not assumed. The base APK declares:

```
manifest@android:requiredSplitTypes = "base__abi,base__density"
meta-data com.android.vending.splits.required = 4294967295
lib/ entries: none
```

YouTube ships as an app bundle. The base APK carries the code and resources but **no native libraries** —
`librive-android.so` and the rest live in the ABI split — and it explicitly requires an ABI split and a
density split. On a modern Android device a base-only install is refused with
`INSTALL_FAILED_MISSING_SPLIT`, and if it were accepted the app would fail as soon as it loads a native
library.

So device validation cannot begin with the APK alone. It needs the **whole split set**, and there is a
second constraint that is easy to miss:

> Every APK in a split set must carry the **same signature**. Google's splits are signed by Google. Mixing
> our patched, test-signed base with Google-signed splits fails signature verification. All of them have to
> be re-signed with the same key as the base.

### Two ways through, both needing the splits

1. **Re-sign the set and install it as a set**
   ```bash
   for f in split_config.*.apk; do
     apksigner sign --ks max-youtube-test.p12 --ks-pass env:KS_PASS --out "signed-$f" "$f"
   done
   adb install-multiple -r MAX-YouTube-21.45.82-DUAL-TEST.apk signed-split_config.*.apk
   ```
2. **Merge into one standalone APK.** MAX Engine has `ApkMerger`, which is what the manager uses for split
   sets; merging base plus splits and signing the result once gives a single installable file. Not yet
   wired into this repository's CLI.

Either way the split APKs have to come from a source the user controls — extracted from an installed
YouTube with a bundle-extraction tool, or downloaded as a bundle archive. They are not in this repository,
and the original APK never will be.

## What is verified today, offline

| Check | Result |
|---|---|
| the Application class resolves | **yes** — `com.google.android.apps.youtube.app.YouTubeTikTokRoot_Application` exists in the dex |
| launcher targets resolve | **yes** — `Shell_HomeActivity` and the alias targets exist |
| component names after the rename | **unchanged** — the set that does not resolve is identical before and after |
| signature | **verifies** — v2, one signer, Android Build Tools r35 |
| the base alone is installable | **no** — requiredSplitTypes and no `lib/` |

### The 26 → 4 correction

An earlier audit reported 26 manifest components whose class does not exist. That was wrong, and the tool
was wrong: an `<activity-alias>` is a **name the launcher can use**, not a class. What must resolve is its
`android:targetActivity`. Checking the alias name flagged 22 harmless entries.

Corrected, four remain, and none of them is on the start path:

| Component | What it is | Required for normal use? |
|---|---|---|
| `androidx.car.app.connection.provider` | Android for Cars connection provider | no — only when projected to a car |
| `com.google.android.libraries.youtube.edit.gallery.GalleryActivity` | gallery/edit activity | no — a split or an optional feature |
| `com.google.android.libraries.mediaprovenance.service.MediaProvenanceService` | C2PA media provenance | no — optional service |
| `android.net.http.MetaDataHolder` | metadata holder declared as a service | no — declared but unused in this build |

## The procedure

`tools/device_test.sh` runs every check that can be automated and prints **PENDING** for anything needing a
human or hardware:

```bash
tools/device_test.sh MAX-YouTube-21.45.82-DUAL-TEST.apk [signed-split_config.*.apk]
```

It checks, in order:

1. the official app is installed and untouched — the script never uninstalls or replaces it;
2. install (base alone, or the full set with `install-multiple`), capturing the exact error if it fails;
3. both package ids coexist;
4. both resolve a launcher activity;
5. cold launch, then whether the process survives, with logcat captured to `/tmp/maxyoutube-logcat.txt`
   and any `FATAL EXCEPTION` printed;
6. navigation, playback and UI — **PENDING by design**, because they need a human on the device;
7. sign-in, notifications, deep links and casting — **PENDING**, because Google services bind identity to
   package name and certificate and neither is Google's here.

Run without a device it prints `adb is not installed: every device check is PENDING` and exits 2. That is
the current state of this repository, and the report says so rather than implying a test happened.

## What to capture when it does run

- the exact `adb install` output, including any `INSTALL_FAILED_*` code;
- `adb shell dumpsys package app.maxyoutube.client | head -40` (signatures, splits, versionName);
- `adb logcat -d > logcat.txt` after a cold launch, and again after using the app for a minute;
- a screenshot of the launcher showing both apps;
- for each of sign-in, notifications and deep links: what was tried and what happened.
