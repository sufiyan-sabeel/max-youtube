# MAX YouTube — architecture

**Audit date:** 16 November 2026. Every claim about existing code below was read from the repositories,
not assumed. Nothing here is implemented yet: this is the audit and the design the implementation
follows.

---

## 1. What exists today

| Repository | Head | What it is |
|---|---|---|
| `max-patcher` | `d701ccd4afe3` | The Android manager **and** the engine: Kotlin/Compose app plus `engine/` as an included build |
| `max-patches` | `e24822cbe56f` | The patch collection: 3,047 files, 363 `*Patch.kt`, 1,162 Java extension files |
| `max-patcher-docs` | `9b6c6ae45e61` | Installation, device testing and compatibility documentation |

**MAX Engine** is `max-patcher/engine`, version **2.3.1**, forked from Morphe Patcher 2.3.0 with the
public ABI byte-identical (`api/max-engine.api`). It is a plain JVM library — no Android dependency —
and its two vendored inputs are `vendor/ARSCLib` (Apache-2.0, pinned `675bed2d`) and `vendor/smali`
(GPL-3.0, pinned `bbabf5f`). Both are composite builds, so the app resolves no patch engine from a
registry.

**MAX Patches** builds a `.mpp` bundle: a zip carrying the compiled patch classes, the extension dexes,
`patches-list.json`, and a signature in the zip comment.

## 2. The pipeline as it exists, source-verified

```
user picks APK ─► manager (Compose)
                    │  OriginalApkRepository / LocalApkSources / split preparation
                    │  PatchSelectionRepository + PatchOptionsRepository
                    ▼
                 patcher-core (Android)
                    │  AIDL IPatcherService → EmbeddedJvm (isolated process)
                    ▼
                 MAX Engine (JVM)
                    Patcher(PatcherConfig) · plusAssign(patches) · execute(): Flow<PatchResult>
                    ▼
                 output APK ─► ApkSigner.signApk(input, output, minSdk)   [BouncyCastle]
                    ▼
                 SessionInstaller / RootInstaller / ShizukuInstaller
```

Points that matter for a standalone build, each verified in source:

| Concern | Where it lives | Note |
|---|---|---|
| APK input and split merge | `patcher/split/*` in the app, `engine/apk/ApkMerger.kt` | the merger is in the engine and reusable; the *orchestration* around it is Android-side |
| Patch execution | `engine/Patcher.kt` | `plusAssign(patches)` derives resource and bytecode mode from the patch types; `execute()` returns a flow of `PatchResult` |
| Signing | `engine/apk/ApkSigner.kt` | `signApk(input, output, minSdkVersion)`, v1/v2/v3 chosen from the APK's minSdk |
| Bundle format | `engine/patch/PatchBundleSignature.kt` | zip comment `MorpheSig1 <public key> <signature>`, Ed25519 over the archive |
| Keystore | app `domain/manager/KeystoreManager.kt` | Android-only (app-private storage); a CLI needs its own |
| Resource table access | `vendor/ARSCLib` | in-process, no Android APIs |

## 3. What a standalone pipeline needs that does not exist yet

1. **A headless runner.** The engine runs on a desktop JVM; the *orchestration* does not. `patcher-core`
   is Android-specific (AIDL, WorkManager, embedded JVM in an isolated process). A CLI must reimplement
   that orchestration — about the order of: read APK → verify identity → load bundle → run patches →
   sign → validate → report — while calling the engine for everything that touches an APK.
2. **An APK inspection layer.** Package name, versionName/versionCode, minSdk, ABI set, split detection,
   signing certificate, resource table presence. ARSCLib is already available in-process; nothing in the
   engine exposes this as a single API today.
3. **A compatibility gate before patching.** Compare the APK against the bundle's declared targets and
   refuse *before* running anything, instead of failing mid-patch.
4. **Output validation.** Zip integrity, resource table readable, dex verifies, signature verifies,
   zipalign status.
5. **A build report.** Source SHA-256, bundle version, engine version, applied patches, skipped patches,
   warnings, output SHA-256 — as JSON, written next to the APK.
6. **Keystore provisioning** from a file or environment, never committed, never printed.

## 4. Reuse, exactly

| Component | Reuse | How |
|---|---|---|
| MAX Engine | **direct, pinned** | dependency at the same commit the manager uses; never a copy |
| ARSCLib, smali | **direct** | transitive of the engine's composite build |
| `ApkMerger`, `ApkSigner`, `PatchBundleSignature`, `Patcher` | **direct** | engine public API |
| `.mpp` format and its Ed25519 signature | **direct** | unchanged |
| Patch collection | **direct** | a pinned, verified bundle; features are added as patches |
| `patcher-core` orchestration | **reimplemented** | Android-bound; its order of operations is the reference |
| Manager UI | **not used** | the standalone build has no UI |

## 5. Package identity

Two supported configurations, with consequences stated rather than assumed:

| Configuration | Consequence |
|---|---|
| Keep `com.google.android.youtube` | installs **over** an existing YouTube only if signed with the same key, which it is not; a replacement install therefore requires uninstalling the original. Shares its data directory only if the signature matched, so in practice it does not. |
| A distinct id (e.g. `app.maxyoutube`) | installs alongside the original. **Google sign-in, deep links and Google-account features are not claimed to work** until tested; several of them bind to the package name and the signing certificate. |

In both cases the build **cannot update a Play Store installation**: the signature differs from
Google's, and Android refuses the update. That is a property of Android, not a limitation to be worked
around.

## 6. Security and legal boundaries

- The original YouTube APK is a **local build input**. It is never committed, never uploaded as an
  artifact, and never redistributed, and neither are its proprietary resources.
- No bypassing of paid access, DRM, account protections or other access controls. The features are
  interface customisation.
- Signing keys are user-supplied, read from a path or environment variable, never printed and never
  committed. The build report records a key **fingerprint**, not key material.
- The bundle is verified before it is used; an unsigned or wrongly-signed bundle is refused for a
  release build and accepted only when the operator explicitly allows it for a test build.

## 7. Feature modules

Each is a patch (or a small set) in the MAX Patches collection, with its own fingerprints, settings
category and compatibility declaration. None is implemented until the supplied APK shows a reliable
target for it.

| Module | Depends on | Status |
|---|---|---|
| Liquid Navigation | the navigation bar's icon map and its container (the same area the 21.45 fix touches) | not started |
| Interface Studio | layout and appearance resources | not started |
| Player Studio | player control containers | not started |
| MAX Settings | the patches' own settings injection | not started |

Visual direction, fixed here so it is not re-litigated per feature: graphite and AMOLED surfaces, muted
cyan/teal accents, restrained translucency with subtle borders and reflections, no neon or cyberpunk
styling, and no redesign of screens the feature does not own.

## 8. Non-goals

- A new patch engine. The engine stays canonical and pinned.
- A new manager. The existing app remains how a user patches on-device.
- Distributing YouTube, or any APK built from it, as a repository artifact.
- Claiming compatibility for any version without a recorded build and, where the claim concerns runtime
  behaviour, a device test.

## 9. What is blocked, and by what

| Blocker | Effect on this project |
|---|---|
| `GHP_PACKAGES_TOKEN` missing in `max-patches` (401, verified) | the collection has never compiled; no bundle exists to pin |
| No MAX Patches signing key | a bundle can be built unsigned for testing, not for release |
| No device test of the 21.45 fix | the eight navigation-dependent patches stay unsupported on 21.45.82 |

The first of those gates the whole of phase 1 below, and the architecture is written so that nothing
else has to wait for it: the runner, the inspection layer and the report can be built and tested against
an APK with no bundle at all.
