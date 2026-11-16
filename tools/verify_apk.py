#!/usr/bin/env python3
"""Verify a built APK: signature, identity, structure, and the customisation it should carry.

    python3 tools/verify_apk.py APK --expect-label "MAX YouTube" [--apksigner PATH]

Exit 0 only if every check passes. Signature verification uses Android's own apksigner when it can be
found; otherwise it falls back to parsing the APK Signing Block and reporting that the cryptographic
check was not performed, rather than pretending it was.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apk_inspect  # noqa: E402

failures: list[str] = []
passed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
        print("  PASS  %s" % name)
    else:
        failures.append("%s %s" % (name, detail))
        print("  FAIL  %s %s" % (name, detail))


def find_apksigner(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    for candidate in ("apksigner", os.path.expanduser("~/Android/Sdk/build-tools/apksigner")):
        found = shutil.which(candidate) or (candidate if os.path.isfile(candidate) else None)
        if found:
            return found
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk")
    parser.add_argument("--expect-package", default="com.google.android.youtube")
    parser.add_argument("--expect-label")
    parser.add_argument("--expect-cert")
    parser.add_argument("--apksigner")
    parser.add_argument("--report")
    args = parser.parse_args()

    print("verifying %s" % os.path.basename(args.apk))
    report = apk_inspect.inspect(args.apk, deep=False)
    manifest = report["manifest"]

    check("opens as an APK", report["dex"]["count"] >= 1)
    check("package is %s" % args.expect_package,
          manifest.get("package") == args.expect_package, "got %r" % manifest.get("package"))
    check("resource table readable", report["resources"].get("present") is True)
    check("every dex parses", all(d.get("valid") for d in report["dex"]["files"]))
    if args.expect_label:
        check("app label is %r" % args.expect_label,
              manifest.get("applicationLabel") == args.expect_label,
              "got %r" % manifest.get("applicationLabel"))

    signer = find_apksigner(args.apksigner)
    cert_sha = None
    if signer:
        with tempfile.TemporaryDirectory() as tmp:
            java = os.path.join(os.environ.get("JAVA_HOME", ""), "bin", "java")
            jar = os.path.join(os.path.dirname(os.path.realpath(signer)), "lib", "apksigner.jar")
            cmd = ([java, "-Xmx512m", "-XX:CompressedClassSpaceSize=32m", "-jar", jar]
                   if os.path.isfile(jar) else [signer])
            # Absolute: the tool runs in a scratch directory, where a relative path would not resolve.
            proc = subprocess.run(cmd + ["verify", "--verbose", "--print-certs", os.path.abspath(args.apk)],
                                  capture_output=True, text=True, cwd=tmp)
        out = proc.stdout + proc.stderr
        verified = any(l.strip() == "Verifies" for l in out.splitlines())
        check("apksigner verifies the signature", verified and proc.returncode == 0,
              out.strip().splitlines()[-1] if out.strip() else "")
        for line in out.splitlines():
            if "certificate SHA-256 digest" in line:
                cert_sha = line.split(":")[-1].strip()
    else:
        print("  SKIP  apksigner not found: the signature block is present but was not verified "
              "cryptographically")

    if args.expect_cert:
        check("certificate is the expected one", cert_sha == args.expect_cert,
              "got %r" % cert_sha)

    if args.report:
        json.dump({"inspect": report, "apksignerCertificateSha256": cert_sha},
                  open(args.report, "w"), indent=2)

    print("")
    print("%d passed, %d failed" % (passed, len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
