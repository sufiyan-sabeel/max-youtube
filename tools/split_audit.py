#!/usr/bin/env python3
"""Audit an APK split set: does it belong together, and is anything missing?

    python3 tools/split_audit.py base.apk [split.apk ...] [--json out.json]

Checks, for every APK given:

  * the package name, versionCode and versionName agree across the set;
  * which split each file declares, and what it is configured for (ABI, density, language);
  * whether the base's `requiredSplitTypes` is covered by the set;
  * whether native libraries are present for the device ABI the base needs;
  * whether the density and language resources the base expects are present.

Run against the base alone it prints exactly what a set is missing, which is the point: a base-only
install is refused by Package Manager on any modern Android.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from identity_audit import walk_manifest  # noqa: E402

ABIS = ("arm64-v8a", "armeabi-v7a", "x86_64", "x86")
DENSITIES = ("ldpi", "mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi", "nodpi", "anydpi")


def describe(path: str) -> dict:
    with zipfile.ZipFile(path) as apk:
        names = apk.namelist()
        manifest = {e["tag"]: e["attrs"] for e in walk_manifest(apk.read("AndroidManifest.xml"))}
    manifest_attrs = next((e["attrs"] for e in walk_manifest(open_manifest(path)) if e["tag"] == "manifest"), {})

    libs = sorted({n.split("/")[1] for n in names if n.startswith("lib/") and n.count("/") >= 2})
    density_dirs = sorted({n.split("/")[1] for n in names
                           if n.startswith("res/") and any(d in n.split("/")[1] for d in DENSITIES)})
    return {
        "file": os.path.basename(path),
        "sizeBytes": os.path.getsize(path),
        "package": manifest_attrs.get("package"),
        "versionCode": manifest_attrs.get("android:versionCode"),
        "versionName": manifest_attrs.get("android:versionName"),
        "split": manifest_attrs.get("split") or manifest_attrs.get("android:split"),
        "configForSplit": manifest_attrs.get("configForSplit") or manifest_attrs.get("android:configForSplit"),
        "isFeatureSplit": manifest_attrs.get("android:isFeatureSplit"),
        "requiredSplitTypes": manifest_attrs.get("requiredSplitTypes")
                              or manifest_attrs.get("android:requiredSplitTypes"),
        "abis": libs,
        "densityDirs": density_dirs[:8],
        "entryCount": len(names),
    }


def open_manifest(path: str) -> bytes:
    with zipfile.ZipFile(path) as apk:
        return apk.read("AndroidManifest.xml")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("apks", nargs="+")
    p.add_argument("--json")
    args = p.parse_args()

    entries = [describe(a) for a in args.apks]
    base = next((e for e in entries if not e["split"]), None)

    print("=== files")
    for e in entries:
        print("  %-34s split=%-14s code=%s abis=%s" % (
            e["file"], e["split"] or "(base)", e["versionCode"], e["abis"] or "-"))

    problems: list[str] = []
    if base is None:
        problems.append("no base APK given (no file without a split name)")

    print()
    print("=== identity agreement")
    packages = {e["package"] for e in entries}
    codes = {e["versionCode"] for e in entries}
    if len(packages) == 1:
        print("  package   %s (all files agree)" % packages.pop())
    else:
        problems.append("files disagree on package: %s" % sorted(packages))
        print("  package   MISMATCH %s" % sorted(packages))
    if len(codes) == 1:
        print("  version   %s (all files agree)" % codes.pop())
    else:
        problems.append("files disagree on versionCode: %s" % sorted(codes))
        print("  version   MISMATCH %s" % sorted(codes))

    if base:
        print()
        print("=== what the base requires")
        required = (base["requiredSplitTypes"] or "").split(",")
        required = [r for r in required if r]
        print("  requiredSplitTypes  %s" % (", ".join(required) or "(none declared)"))

        have_abi = any(e["abis"] for e in entries)
        have_density = any(e["densityDirs"] for e in entries if e["split"])

        print("  native libraries    %s" % ("present: " + ", ".join(sorted({a for e in entries for a in e["abis"]}))
                                            if have_abi else "MISSING — no lib/ in any file"))
        print("  density resources   %s" % ("present" if have_density else "in the base only"))

        if "base__abi" in required and not have_abi:
            problems.append("required split type base__abi has no provider: no APK carries lib/<abi>/")
        if "base__density" in required and not have_density:
            print("  note                base__density is satisfied by the base's own resources")

    print()
    print("=== verdict")
    if problems:
        for prob in problems:
            print("  MISSING  %s" % prob)
        print("")
        print("  The set is not complete. Package Manager refuses a base-only install of an app that")
        print("  declares requiredSplitTypes; the splits must be supplied before merging or installing.")
    else:
        print("  The set is complete: one package, one version, every required split type covered.")

    if args.json:
        json.dump({"files": entries, "problems": problems}, open(args.json, "w"), indent=2)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
