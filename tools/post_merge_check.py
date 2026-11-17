#!/usr/bin/env python3
"""Checks a merged MAX YouTube APK is actually standalone and installable.

    python3 tools/post_merge_check.py APK --expect-package app.maxyoutube.client [--expect-abi arm64-v8a]

Every check that fails is printed with what was found, and the exit code is non-zero. Run it on a
non-merged build to see the failures it is meant to catch.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from identity_audit import walk_manifest  # noqa: E402

SPLIT_ATTRS = ("requiredSplitTypes", "android:requiredSplitTypes", "splitTypes", "android:splitTypes",
               "android:isSplitRequired", "split", "android:split", "configForSplit",
               "android:configForSplit")

passed = 0
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
        print("  PASS  %s" % name)
    else:
        failures.append(name)
        print("  FAIL  %s %s" % (name, detail))


def find_apksigner() -> str | None:
    for c in ("apksigner", os.path.expanduser("~/Android/Sdk/build-tools/apksigner")):
        f = shutil.which(c) or (c if os.path.isfile(c) else None)
        if f:
            return f
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("apk")
    p.add_argument("--expect-package", default="app.maxyoutube.client")
    p.add_argument("--expect-abi", default="arm64-v8a")
    p.add_argument("--apksigner")
    args = p.parse_args()

    print("checking %s" % os.path.basename(args.apk))
    with zipfile.ZipFile(args.apk) as apk:
        names = apk.namelist()
        bad = apk.testzip()
        elements = walk_manifest(apk.read("AndroidManifest.xml"))

    manifest = next((e["attrs"] for e in elements if e["tag"] == "manifest"), {})
    application = next((e["attrs"] for e in elements if e["tag"] == "application"), {})
    meta = [e["attrs"].get("android:name", "") for e in elements if e["tag"] == "meta-data"]

    # 1. manifest inspected
    check("manifest parses and declares a package", bool(manifest.get("package")),
          "got %r" % manifest.get("package"))

    # 2. no split declarations survive
    leftover = [a for a in SPLIT_ATTRS if a in manifest or a in application]
    split_meta = [m for m in meta if m.startswith("com.android.vending.splits")]
    check("no required split declarations remain", not leftover and not split_meta,
          "found %s" % (leftover + split_meta))

    # 3. native libraries present
    libs = sorted({n.split("/")[1] for n in names if n.startswith("lib/") and n.count("/") >= 2})
    check("native libraries present for %s" % args.expect_abi, args.expect_abi in libs,
          "found %s" % (libs or "none"))

    # 4. package id
    check("package id is %s" % args.expect_package,
          manifest.get("package") == args.expect_package, "got %r" % manifest.get("package"))

    # 5. signature
    signer = args.apksigner or find_apksigner()
    if signer:
        java = os.path.join(os.environ.get("JAVA_HOME", ""), "bin", "java")
        jar = os.path.join(os.path.dirname(os.path.realpath(signer)), "lib", "apksigner.jar")
        cmd = ([java, "-Xmx512m", "-XX:CompressedClassSpaceSize=32m", "-jar", jar]
               if os.path.isfile(jar) else [signer])
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(cmd + ["verify", "--verbose", os.path.abspath(args.apk)],
                                  capture_output=True, text=True, cwd=tmp)
        out = proc.stdout + proc.stderr
        check("apksigner verifies the signature",
              proc.returncode == 0 and any(l.strip() == "Verifies" for l in out.splitlines()),
              out.strip().splitlines()[-1] if out.strip() else "")
    else:
        print("  SKIP  apksigner not found: signature not verified cryptographically")

    # 6. integrity
    check("zip is intact", bad is None, "first bad entry: %s" % bad)
    dex = [n for n in names if n.startswith("classes") and n.endswith(".dex")]
    check("dex files present", len(dex) >= 1, "found %d" % len(dex))
    check("resource table present", "resources.arsc" in names)

    print("")
    print("%d passed, %d failed" % (passed, len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
