# MAX YouTube — implementation plan

**Rule for the whole plan:** no feature starts before the APK in hand shows a reliable target for it, and
no compatibility claim is made before a recorded build — and, for runtime behaviour, a device test.

The plan is ordered so that the **smallest end-to-end prototype proves the pipeline** before any
customisation is written. Everything before phase 2 can be built and tested against an APK alone, with no
patch bundle at all, which matters because the bundle is currently blocked (see ARCHITECTURE §9).

---

## Phase 0 — audit (done)

| Deliverable | State |
|---|---|
| `ARCHITECTURE.md` | written, from source |
| `IMPLEMENTATION_PLAN.md` | this document |
| `COMPATIBILITY.md` | written, seeded with the one APK that has been analysed |
| Reuse and gap analysis | in ARCHITECTURE §3–§4 |

**Exit criteria:** met. The three documents exist and every claim in them is traceable to a file or an
APK inspection.

## Phase 1 — the runner, with no patches

Build `max-youtube-cli`: a JVM program that takes an APK path and does everything except patching.

1. Read the APK: package, versionName, versionCode, minSdk, target SDK, ABI set, split detection, signing
   certificate fingerprint, presence of `resources.arsc` and dex files.
2. Compute and print the SHA-256.
3. Write an inspection report as JSON.
4. Exit non-zero on anything that makes patching impossible, with the reason.

**Exit criteria:** run against the supplied YouTube 21.45.82 APK
(`10b51b7075ae0e92e7cba6d3ca393422a2756c214097800ccb89c5c3f01dfb28`) and reproduce the identity already
established by hand: package `com.google.android.youtube`, versionName `21.45.82`, versionCode
`1561310996`, compileSdk 37, eight dex files, a 2,134,488-byte `resources.arsc`.

## Phase 2 — the prototype: one harmless, verified customisation

The smallest thing that proves patch → sign → install works end to end.

- Pick a customisation whose target is **already verified** in the supplied APK, so the fingerprint is
  grounded rather than guessed. The candidate that is ready today is the notification-tab filled icon in
  the navigation icon map: the map was located in `Lkms;.<clinit>` and its bell entry resolved to
  `yt_outline_bell_vd_theme_24` (`0x7f081061`).
- Run the patch through MAX Engine, sign with a **test** keystore generated for this purpose, validate the
  output, and install it on a device.
- Record: input SHA-256, engine version, patch bundle version, output SHA-256, and the install result.

**Exit criteria:** the APK installs, launches, and the single customisation is visible. Any failure is
recorded as a failure.

## Phase 3 — bundle pinning and verification

- Pin a MAX Patches bundle by version **and** SHA-256 in a lock file.
- Verify its Ed25519 signature before use; refuse a mismatch.
- Record the bundle's version in every build report.

**Blocked by:** `GHP_PACKAGES_TOKEN` in `max-patches`. Until it exists, no bundle can be built, and phase
2 must use a locally built one.

**Exit criteria:** the runner refuses a tampered bundle and names the reason.

## Phase 4 — output validation

Zip integrity, resource table readable, dex verifies, signature verifies with the expected certificate,
zipalign status, and an install dry-run via `adb` where a device is attached.

**Exit criteria:** a deliberately corrupted output is rejected with a specific message.

## Phase 5 — Liquid Navigation

The first real feature, and the one with the most unknowns. It must change the navigation experience
itself — a floating translucent surface, rounded glass container, restrained blur, an animated selected
indicator, optional labels, dark/light/AMOLED variants, correct gesture insets, accessible touch targets
— **not** a decorative overlay above the existing bar.

Prerequisites, each an investigation before code:

1. The container that owns the bottom navigation and its layout parameters, from the APK.
2. Whether a blur surface is reachable from the app's own code or requires a new drawable hierarchy.
3. The selected-indicator mechanism, and whether it can be animated without replacing the tab logic.
4. Insets handling on Android 16 with gesture navigation.

**Exit criteria:** a build that installs, navigates, keeps every original navigation action, and passes
the back-gesture test. Until then the feature is declared unsupported.

## Phase 6 — Interface Studio, Player Studio, MAX Settings

Independent modules, each with its own fingerprints, settings category and compatibility row. They are
sequenced after Liquid Navigation because they share its settings infrastructure.

## Phase 7 — release quality

- Reproducible build documented; the APK's checksum recorded per release.
- SBOM and licence inventory for anything MAX ships (not for YouTube's own code, which is not shipped).
- Signing documented: key fingerprint in the report, key never in the repository.
- A `BUILDING.md` that a second person can follow to produce the same APK from the same inputs.

---

## Delivery checklist (from the brief)

| Item | Phase |
|---|---|
| `ARCHITECTURE.md` | 0 — done |
| `IMPLEMENTATION_PLAN.md` | 0 — done |
| `COMPATIBILITY.md` | 0 — done |
| `BUILDING.md` | 7 (stub earlier, once the runner exists) |
| `SECURITY.md` | 7 (the boundaries are already stated in ARCHITECTURE §6) |
| Reproducible local build workflow | 1 + 7 |
| Standalone signed APK | 2 (prototype), then each feature |
| SHA-256 checksum | 2 onward |
| Validation report | 2 onward |

## What is not in this plan, deliberately

- No new patch engine, no fork of MAX Engine, no change to the manager.
- No feature written against a version that has not been inspected.
- No claim that a changed package id keeps Google sign-in, deep links or Play Store updates working.
