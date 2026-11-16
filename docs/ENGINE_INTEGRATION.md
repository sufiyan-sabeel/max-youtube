# Engine integration — verified API surface and the integration design

**Status: designed and verified against source; not yet compiled or run.** The reasons are in §5 and they
are environmental, not conceptual.

Engine commit integrated (pinned): **`max-patcher` `d701ccd4afe3624d4ce0c5e75ecdb60a63321331`**, whose
`engine/` is MAX Engine **2.3.1**.

---

## 1. How the engine is obtained, and why not from a registry

`app.morphe:morphe-patcher` is published only to the Morphe GitHub Packages registry, which answers **401**
without a token, and `app.morphe.patches` — the plugin the *patch collection* needs — is not on Maven
Central or the plugin portal at all (verified: 401, 404, and a portal redirect to Central that 404s).

So this project uses a **source-based integration** at the exact pinned commit, which the brief permits:

```
max-youtube/
├── settings.gradle.kts        includeBuild("vendor/max-patcher/engine") + dependency substitution
├── cli/                       the runner
└── vendor/max-patcher/        git submodule, pinned to d701ccd4
        ├── engine/            MAX Engine 2.3.1 (GPL-3.0, NOTICE preserved)
        └── vendor/            ARSCLib 675bed2d (Apache-2.0), smali bbabf5f (GPL-3.0) — nested submodules
```

```kotlin
// settings.gradle.kts
includeBuild("vendor/max-patcher/engine") {
    dependencySubstitution {
        substitute(module("app.morphe:morphe-patcher")).using(project(":"))
    }
}
```

No credential is used, nothing is bypassed, and the engine's own `NOTICE`, `LICENSE` and
`api/max-engine.api` travel with the submodule unchanged. Its composite build resolves ARSCLib and smali
from the nested submodules exactly as MAX Patcher does.

## 2. The engine calls the runner makes

Read from `max-patcher/engine` at the pinned commit:

```kotlin
val config = PatcherConfig(
    apkFile = inputApk,                       // the input is never written to
    temporaryFilesPath = workDir,
)
Patcher(config).use { patcher ->
    patcher += setOf(maxTestBuildStampPatch)  // the one customisation
    patcher().collect { result ->             // Flow<PatchResult>, one per patch
        if (result.exception != null) fail(result)
    }
    patcher.get().applyTo(outputApk)          // PatcherResult → writes the APK
}
```

Signing, all public API of the same engine:

```kotlin
val keyStore = ApkSigner.readKeyStore(keystore.inputStream(), password)
val pair = ApkSigner.readPrivateKeyCertificatePair(keyStore, alias, entryPassword)
ApkSigner.newApkSigner("max-youtube-test", pair)
    .signApk(outputApk, signedApk, minSdkVersion = 32)
```

`signApk` picks v1/v2/v3 from the APK's minSdk; a v2-only target is signed in place without rewriting
entries.

## 3. The one customisation

Chosen for being verifiable, reversible and harmless: a **manifest edit** that stamps the build, so the
output is self-identifying and nothing about YouTube's behaviour changes.

| Property | How it is met |
|---|---|
| verified target | `AndroidManifest.xml` is present in the APK and parsed by the inspection tool; the attribute it edits is confirmed to exist |
| reversible | the input APK is opened read-only; the output is a new file |
| harmless | no dex edit, no resource-table edit, no behaviour change |
| testable | the output's `versionName` is re-read by `tools/apk_inspect.py` and asserted |

Patch type: `ResourcePatch`, which gives access to the decoded manifest document. The manifest editor is
`app.morphe.patcher.util.Document`, a wrapper over `org.w3c.dom`, and `apk/AndroidManifestHelper.kt`
provides the attribute helpers.

## 4. What the runner validates after patching

1. the patch reported no exception;
2. the output opens as a zip, and its entries are readable;
3. the manifest parses and its package is `com.google.android.youtube`;
4. `resources.arsc` and every dex still parse;
5. the signing certificate verifies and matches the test key's fingerprint;
6. the output SHA-256 is recorded;
7. a JSON report names engine version, patch name, input hash, output hash, certificate fingerprint and
   warnings.

## 5. Why this has not been run yet

Two environmental facts, both measured:

- **The engine does not finish compiling inside this sandbox.** Gradle 9.8.2 runs, ARSCLib and smali
  compile, and `:compileKotlin` — about 200 files — is cut off at the 285-second per-call limit on every
  attempt. It is not an error; it is the pod's ceiling.
- **The input APK cannot go to CI.** By policy it is a local build input and must never be uploaded as an
  artifact, so a CI runner cannot have the file the pipeline needs.

The way through, in order: build the runner jar in CI (uploading MAX's own jar is allowed), then run that
jar here against the APK with the local test keystore, then verify the output with
`tools/apk_inspect.py`. That keeps the APK local and the compile where there is CPU.

## 6. Licensing and attribution

The submodule keeps MAX Engine's `LICENSE` (GPL-3.0), `NOTICE` (GPLv3 section 7 terms) and its ABI dump
untouched. ARSCLib (Apache-2.0) and smali (GPL-3.0) keep theirs. This repository's own code is GPL-3.0 and
its `NOTICE` records the upstream projects it derives from. Nothing is re-licensed and no copyright header
is removed.
