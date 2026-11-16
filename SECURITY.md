# Security

## Signing keys

Two kinds of key, never confused:

| Kind | Where it lives | What it signs |
|---|---|---|
| **Test key** | generated on the build machine, mode `0600`, outside any repository | prototype APKs, labelled TEST BUILD |
| **Production key** | a permanent key the project owner controls; a separate workflow with explicit approval | release APKs |

Rules for both:

- The keystore is never committed, never uploaded as a CI artifact, never copied into this repository.
- The password and the private key never appear in logs, build reports, source or artifacts.
- A build report records the certificate **fingerprint** — public by design — and never key material.
- Every APK signed with the test key carries `TEST BUILD` in its filename and in its build report.

### Test key generated for the prototype

| Field | Value |
|---|---|
| Alias | `max-youtube-test` |
| Subject | `O=MAX Patcher test, CN=MAX YouTube TEST BUILD - not for release` |
| Valid until | 2036-11-13 |
| Certificate SHA-256 | `decba51df18ef1111d6182c92521315a9bbeb318eb666f656ff9b803973c7c3b` |
| Location | the machine that generated it, outside this repository |

This key exists to prove the signing step works. It must never sign anything released.

## The input APK

YouTube's APK is proprietary. In this repository it is:

- a **local build input** only;
- never committed;
- never uploaded as a CI artifact;
- never redistributed, and neither are its resources.

`.gitignore` refuses `*.apk`, `*.p12`, `*.jks`, `*.keystore` and `*.password` so this cannot happen by
accident.

## What this project will not do

- Bypass paid access, DRM, account protections or any other access control. The features are interface
  customisation.
- Claim that a build updates a Play Store installation: the signature differs, and Android refuses the
  update.
- Claim Google sign-in, deep links or account features work under a changed package id without testing
  them.
- Print, commit or transmit a token, key or password.

## Reporting

A security issue in this project can be raised through the issue tracker of
[max-patcher-docs](https://github.com/sufiyan-sabeel/max-patcher-docs/issues). Do not include secrets in a
report.
