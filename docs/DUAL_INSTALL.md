# Dual installation — what the package identity change actually does

MAX YouTube ships as **`app.maxyoutube.client`**, so it installs beside the official
`com.google.android.youtube` instead of replacing it.

## The transformation

| Element | Before | After | Why |
|---|---|---|---|
| `manifest@package` | `com.google.android.youtube` | `app.maxyoutube.client` | the id Android uses to tell two apps apart |
| relative component names | `.UrlActivity` | `com.google.android.youtube.UrlActivity` | a relative name resolves against the **new** id and would find no class — the app would crash at launch |
| provider authorities | `com.google.android.youtube.fileprovider`, `…lifecycle-trojan` | `app.maxyoutube.client.fileprovider`, `…lifecycle-trojan` | two apps may not share an authority |
| declared permissions (4) | `com.google.android.youtube.permission.C2D_MESSAGE`, `…DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` | `app.maxyoutube.client.…` | two apps may not share a permission name |

Deliberately unchanged: component class names, Java package names, dex contents, deep-link schemes and
hosts, and references to other apps. The application id is not the Java package, and renaming a class would
break the app.

## The check that proves the rename is safe

`tools/identity_audit.py` lists every package-dependent element and tests each component name against the
classes actually present in the APK. On the base APK **26 of 147** component names do not resolve, because
they live in feature splits rather than in this base APK.

The invariant that matters is that the rename changes nothing about that:

| | Original | Renamed |
|---|---|---|
| package | `com.google.android.youtube` | `app.maxyoutube.client` |
| components | 147 | 147 |
| providers | 6 | 6 |
| declared permissions | 52 | 52 |
| component names that do not resolve | 26 | **26 — the same 26** |

Newly broken by the rename: **none**.

## What remains unverified

Installing both apps, seeing both in the launcher, launching MAX YouTube, and every behaviour under the new
id: playback, search, subscriptions, navigation, **Google sign-in, notifications, casting, deep links**. Google
services bind identity to package name *and* signing certificate, and neither is Google's here, so those are
expected to be affected. Nothing about them is claimed.

## Installing

```bash
adb install MAX-YouTube-21.45.82-DUAL-TEST.apk
```

No uninstall of YouTube is needed. `INSTALL_FAILED_UPDATE_INCOMPATIBLE` means an older same-package build
(v0.1.0-test.1 or v0.1.0-test.2) is installed — uninstall that, not YouTube.
