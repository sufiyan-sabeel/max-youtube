# Split sets: what MAX Engine's ApkMerger actually does, and what is missing

## The investigation

`engine/apk/ApkMerger.kt` (219 lines, from REAndroid's APKEditor, Apache-2.0) was read before deciding
anything.

`merge(inputFile, outputFile, validateModules = true, resDirName, validateResDir, extractNativeLibs, cleanMetaInf)`

| Step | What it does |
|---|---|
| input | a **directory** of APKs, or an **archive** (`.apkm`, `.xapk`) — it extracts every `*.apk` entry itself |
| load | ARSCLib `ApkBundle.loadApkDirectory` → `mergeModules(validateModules = true)`, which validates that the modules belong together |
| resources | merges resource tables, optionally renames the resources root, then `validateResourcesDir()` |
| native libraries | keeps `lib/<abi>/` and sets `extractNativeLibs` to what the base declared |
| **manifest sanitising** | removes `requiredSplitTypes`, `splitTypes`, `isSplitRequired`, and the `com.android.vending.splits` meta-data, and drops the splits table entry |
| output | writes an **aligned** APK; META-INF is kept, so the signature block survives |

That sanitising step is the whole point: it is what turns a base that Package Manager refuses into a
standalone APK that installs on its own.

## Decision: merge, not re-sign the set

Two ways to get an installable artefact, and the difference is not cosmetic:

| Approach | Result |
|---|---|
| **Re-sign the set and `install-multiple`** | every APK must carry the *same* signature, so Google's splits have to be re-signed with the MAX test key — and the installed app remains a split installation, fragile against any later `adb install -r` of one file |
| **Merge, then sign once** | one APK, one signature, `requiredSplitTypes` gone, native libraries inside it. Installs with a plain `adb install`, updates with a plain `adb install -r` |

**Merging is the choice**, and the runner implements it: `--split-dir` merges base plus splits with the
engine's own `ApkMerger`, then patches and signs the merged APK.

One caveat, stated rather than hidden: `ApkMerger` merges every module it is given. Feature splits that are
not part of the set are simply absent, and their components stay unresolvable — which is already true of
this base APK (see `docs/DEVICE_VALIDATION.md`: four components, none on the start path).

## What is missing — exactly

`tools/split_audit.py` against the base APK alone:

```
=== files
  YouTube.apk        split=(base)   code=1561310996   abis=-

=== identity agreement
  package   com.google.android.youtube (all files agree)
  version   1561310996 (all files agree)

=== what the base requires
  requiredSplitTypes  base__abi, base__density
  native libraries    MISSING — no lib/ in any file
  density resources   in the base only

=== verdict
  MISSING  required split type base__abi has no provider: no APK carries lib/<abi>/
```

So, concretely:

| Needed | Status | Why |
|---|---|---|
| **`split_config.arm64_v8a.apk`** | **missing, and required** | provides `lib/arm64-v8a/*.so`; the base declares `base__abi` and carries no native library at all |
| `split_config.xxhdpi.apk` (or similar) | optional | `base__density` is satisfied by the base's own resources |
| language splits (`split_config.en.apk`, `hi.apk`, …) | optional | Play delivers these per locale; the app runs without them, in the base's default locale |
| feature splits (car, gallery, provenance) | optional | their four components are already unresolvable in this base and are not on the start path |

**Minimum viable set: the base plus the arm64-v8a ABI split.** Everything else improves completeness but is
not required for install or launch.

## What the runner does with a set

```bash
java -jar max-youtube-cli-all.jar \
  --apk YouTube.apk --split-dir ./splits \
  --out ./out --keystore max-youtube-test.p12 --alias max-youtube-test \
  --password-env KS_PASS --stamp 21.45.82-MAX-DUAL-TEST --label "MAX YouTube" \
  --package app.maxyoutube.client --name MAX-YouTube-21.45.82-DUAL-TEST.apk
```

It merges, applies the package identity and the label to the merged manifest, signs once, and records
`mergedFrom` in the build report.

## Rules that do not change

- The original installed YouTube is never modified, and Google's APKs and splits are never published.
- `minSdk` is never lowered; the merged APK keeps whatever the base declares (32 here).
- A set is only used when `tools/split_audit.py` says it is complete: one package, one versionCode, every
  required split type covered.
