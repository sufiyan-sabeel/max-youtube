# MAX YouTube — compatibility

**Nothing is supported yet.** One APK has been analysed; no build has been produced from it and no
device test has been run. This document exists so that a claim cannot be made without the evidence beside
it.

---

## The evidence rule

A row may say **Supported** only when all of these are recorded against it:

1. the input APK's SHA-256;
2. a recorded build whose report names the engine version and the bundle version;
3. the output APK's SHA-256 and a successful signature verification;
4. for anything that changes runtime behaviour, an install and launch on a named device.

Anything less is **Experimental**. Anything not analysed is **Unsupported**. A row with no evidence is
not a row.

## Analysed inputs

| APK | SHA-256 | package | versionName | versionCode | State |
|---|---|---|---|---|---|
| `YouTube.apk` (also supplied as `YouTube-2.apk`, byte-identical) | `10b51b7075ae0e92e7cba6d3ca393422a2756c214097800ccb89c5c3f01dfb28` | `com.google.android.youtube` | `21.45.82` | `1561310996` | **Experimental** — analysed, never built, never installed |

The two uploads are the same file: one SHA-256 for both. No second version has been supplied, so the
matrix has one row.

### What was verified in that APK

| Finding | Evidence |
|---|---|
| 8 dex files, `resources.arsc` 2,134,488 bytes, compileSdk 37 | read from the APK |
| `drawable/yt_fill_bell_black_24` **absent** | resource table key index |
| five bell drawables present, including `yt_outline_bell_vd_theme_24` = `0x7f081061` | resource table |
| the navigation icon map is built in `Lkms;.<clinit>` as `EnumMap<Lbgrj;>`, one entry per tab, shape `sget enum → const icon → Integer.valueOf → EnumMap.put` | DEX walk with androguard |
| the bell entry in that map is `yt_outline_bell_vd_theme_24` paired with enum `bD` | same |
| the filled bell `0x7f080e1d` is loaded in `Lkmt;.<clinit>`, a different structure | same |

### What is not verified in that APK

- whether the navigation container can be re-laid-out for Liquid Navigation;
- whether a blur surface is reachable without replacing the tab logic;
- insets behaviour under Android 16 gesture navigation;
- anything about Google sign-in, deep links or account features;
- whether any patch currently in MAX Patches applies cleanly to this version other than the navigation
  icon map.

## Matrix

| YouTube version | MAX Patches state | Notes |
|---|---|---|
| **21.45.82** | **Experimental / Unsupported for the eight navigation-hook dependents** | analysed; the 21.45 fingerprint fix is committed but has never been compiled or run |
| 21.44.528 | Unsupported | not analysed here; declared experimental upstream |
| 21.43.523 | Unsupported | not analysed here; declared experimental upstream |
| 21.30.216 | Unsupported | not analysed here |
| 21.28.208 | Unsupported | not analysed here |
| 21.23.492 | Unsupported | not analysed here |
| 20.51.39 | Unsupported | not analysed here |
| 20.26.46 | Unsupported | not analysed here |

The eight navigation-hook dependents are: Navigation buttons, DeArrow, Change form factor, Hide layout
components, Hide horizontal shelves, Hide Shorts components, Open Shorts in regular player, AI channel
filter, and Series tracker (nine files; eight dependents plus `NavigationBarPatch`, which both depends on
the hook and uses it).

## Package identity

| Configuration | Claimed | Not claimed |
|---|---|---|
| `com.google.android.youtube` | nothing until tested | replacement install over Google's build (signature differs), data continuity, Play Store updates |
| distinct id | nothing until tested | Google sign-in, deep links, account features, Chromecast pairing, notifications integration |

Neither configuration can update a Play Store installation. That is a property of Android's signature
checking, not a limitation of this pipeline.

## How a row moves

1. Build against the APK; the build report records input SHA-256, engine version, bundle version, applied
   and skipped patches, warnings, output SHA-256.
2. Verify the output signature and record the certificate fingerprint.
3. Install on a named device; record install, launch, and the specific behaviour the feature changes.
4. Only then change the state to Supported, with the build's commit beside it.

A skipped patch is never counted as applied, and a bundle that loads is never counted as a working build.
