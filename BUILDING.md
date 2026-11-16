# Building and testing

Everything here runs on a desktop with Python 3.10+. The inspection tool has **no third-party
dependencies**; the optional deep mode needs `androguard` for resource-name inventory.

## Inspect an APK

```bash
python3 tools/apk_inspect.py YouTube.apk --json report.json
```

Prints a summary and writes the JSON report:

```
input      YouTube.apk
size       67589212 bytes
sha256     10b51b70…dfb28
package    com.google.android.youtube
version    21.45.82 (code 1561310996)
sdk        min 32, target 37, compile 37
resources  arsc 2134488 bytes
dex        8 files, 57974 classes, 457090 methods
signing    apkSigBlock=True v1=False
```

Add `--deep` to inventory resource names as well (needs `pip install androguard`). Without it those
fields are `null` and a warning says why — they are never guessed.

Exit codes: `0` inspected, `2` no such file, `3` not an APK.

## Run the tests

```bash
MAX_YOUTUBE_TEST_APK=/path/to/YouTube.apk python3 tools/test_apk_inspect.py
```

The suite asserts invariants that hold for any YouTube APK, and exact values when the input is the build
this project has analysed (SHA-256 `10b51b70…dfb28`). Against that build it runs 16 assertions; against
any other build it runs 10, because the fixture-specific ones would be claims about a file nobody has
inspected.

## Test keystore

Prototype builds are signed with a **throwaway** key generated on the machine that builds them:

```bash
python3 tools/make_test_keystore.py ~/keystores/max-youtube-test.p12
```

It prints the certificate's SHA-256 and nothing else. The keystore and its password file are written with
mode `0600` outside any repository.

**Rules that are not negotiable:**

- the keystore is never committed, never uploaded as a CI artifact, and never copied into this repository;
- the password and the private key never appear in logs, reports or source;
- every APK signed with it is a **TEST BUILD** and must be labelled as one, in the filename and in the
  report;
- production signing is a **separate** workflow that requires an explicit approval and a permanent,
  user-controlled key. Nothing in this repository produces a production signature.

The fingerprint of the key generated for the prototype on 16 November 2026 is recorded in
[SECURITY.md](SECURITY.md). That is public information; the key is not.

## What does not work yet

The patch bundle. `max-patches` cannot compile until `GHP_PACKAGES_TOKEN` exists in that repository (the
patch Gradle plugin is registry-only; the registry answers 401 without it). Phases 1 and 2 of
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) do not depend on it.
