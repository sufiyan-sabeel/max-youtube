# Signing, and why this APK cannot update the official YouTube app

## The test key

| Field | Value |
|---|---|
| Alias | `max-youtube-test` |
| Subject | `O=MAX Patcher test, CN=MAX YouTube TEST BUILD - not for release` |
| Valid until | 2036-11-13 |
| Key | RSA 2048 |
| Certificate SHA-256 | `decba51df18ef1111d6182c92521315a9bbeb318eb666f656ff9b803973c7c3b` |
| Where it lives | the machine that generated it, mode `0600`, never in this repository |

`apksigner verify --print-certs` on the published APK reports this exact digest, and that the signature is
scheme **v2** with **one** signer.

## Why it cannot update the official app

Android identifies an installed app by **package name plus signing certificate**. `com.google.android.youtube`
installed from the Play Store is signed with Google's key. Our build keeps the package name and is signed
with the test key, so:

- **`adb install -r` / a normal install of our APK over the official app fails** with
  `INSTALL_FAILED_UPDATE_INCOMPATIBLE` — the platform refuses to replace an app whose signature changed.
- **Uninstalling the official app is the only way to install ours under the same package name**, and that
  deletes its data: sign-in state, downloads, watch history that has not synced.
- **The Play Store will never update our build**, and our build can never update the Play Store's. Any
  update, in either direction, is an uninstall/reinstall.
- Nothing here "bypasses" that check, and nothing should: it is the platform's anti-tampering guarantee.

This is a property of Android, not a limitation of the pipeline.

## Safe testing without uninstalling the official app

Three options, in order of how little they risk:

### 1. A second device or an emulator (recommended, and what is missing today)

No interference at all. This is the only option that tests the real install path without touching the
phone the official app lives on. Everything in this repository is verified the same way; the gap in the
current release is exactly this step.

### 2. A secondary user or a work profile

Android keeps a separate app namespace per user, so the official app in the owner's profile is untouched:

```bash
adb shell pm create-user maxytest        # secondary user (not available on every ROM, and Vivo may hide it)
adb install --user <user-id> MAX-YouTube-21.45.82-TEST.apk
adb shell am start --user <user-id> -n com.google.android.youtube/...
```

A work profile (managed profile) achieves the same isolation and is more widely available. Both share the
device's storage and battery, and the app in the second profile has no access to the first profile's
Google account unless one is added there.

### 3. A distinct package id — not implemented, and not to be assumed

Renaming the package (for example `app.maxyoutube`) makes both apps installable side by side, and is the
only option that keeps them in the same profile. It is **not** a one-line change: the package name appears
in provider authorities, intent filters, deep-link schemes and some DEX references, and Google sign-in and
Play services bind to it. Until that is implemented and tested, this repository makes **no claim** that a
renamed build keeps sign-in, deep links, cast, notifications or account features.

## What is never done

- The test keystore and its password are never committed, uploaded or printed.
- The original YouTube APK is never published.
- A production signature is never produced here: that requires a permanent key the owner controls and an
  explicit approval, as a separate workflow.
