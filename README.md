# MAX YouTube

A standalone, locally built, customised YouTube APK produced with the MAX Patcher ecosystem. Created by
Umaiz Sufiyan.

**Status: architecture and audit only.** No build exists. Nothing here has been installed on a device.

The original YouTube APK is a local build input: it is never committed, never uploaded as an artifact and
never redistributed, and neither are its proprietary resources.

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | what exists today, the pipeline as it is, what a standalone build needs, reuse, package identity, security boundaries |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | the phased plan, starting with the smallest end-to-end prototype |
| [COMPATIBILITY.md](COMPATIBILITY.md) | the evidence rule, the one analysed APK, and what is not verified |

The engine is not duplicated here. It lives in
[max-patcher](https://github.com/sufiyan-sabeel/max-patcher) and is used at a pinned commit; the patches
live in [max-patches](https://github.com/sufiyan-sabeel/max-patches).
