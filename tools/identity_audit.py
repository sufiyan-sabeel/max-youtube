#!/usr/bin/env python3
"""Audit everything in an APK's manifest that depends on the package identity.

    python3 tools/identity_audit.py APK [--dex] [--json out.json]

Reports the package, every component and its declared name, providers and their authorities, declared
permissions, deep-link schemes and hosts, and — with --dex — whether each component name resolves to a
class that actually exists in the APK. That last check is what proves a package rename did not leave the
manifest pointing at classes the new id cannot find.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apk_inspect import (ANDROID_NS, RES_STRING_POOL_TYPE, RES_XML_START_TAG,  # noqa: E402
                         RES_XML_TYPE, StringPool)

COMPONENT_TAGS = ("activity", "activity-alias", "service", "receiver", "provider", "application")
IDENTITY_TAGS = ("permission", "permission-group", "uses-permission", "uses-permission-sdk-23")


def walk_manifest(axml: bytes) -> list[dict]:
    """Every start tag with its attributes, in document order."""
    pool = None
    out: list[dict] = []
    offset = struct_header = None
    import struct
    offset = struct.unpack_from("<H", axml, 2)[0]
    while offset + 8 <= len(axml):
        import struct as _s
        chunk_type, _header_size, chunk_size = _s.unpack_from("<HHI", axml, offset)
        if chunk_size < 8:
            break
        if chunk_type == RES_STRING_POOL_TYPE:
            pool = StringPool(axml, offset)
        elif chunk_type == RES_XML_START_TAG and pool is not None:
            ns_idx, name_idx = _s.unpack_from("<iI", axml, offset + 16)
            attr_start, attr_size, attr_count = _s.unpack_from("<HHH", axml, offset + 24)
            attrs = {}
            for i in range(attr_count):
                pos = offset + 16 + attr_start + i * attr_size
                a_ns, a_name = _s.unpack_from("<iI", axml, pos)
                data_type = axml[pos + 15]
                data = _s.unpack_from("<I", axml, pos + 16)[0]
                key = pool.get(a_name)
                ns = pool.get(a_ns) if a_ns >= 0 else ""
                value = pool.get(data) if data_type == 0x03 else data
                attrs[("android:" + key) if ns == ANDROID_NS else key] = value
            out.append({"tag": pool.get(name_idx), "attrs": attrs})
        offset += chunk_size
    return out


def dex_classes(path: str) -> set[str]:
    from androguard.core.dex import DEX
    classes: set[str] = set()
    with zipfile.ZipFile(path) as apk:
        for name in apk.namelist():
            if name.startswith("classes") and name.endswith(".dex"):
                d = DEX(apk.read(name))
                for c in d.get_classes():
                    classes.add(c.get_name())
    return classes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("apk")
    p.add_argument("--dex", action="store_true", help="check component names against the dex classes")
    p.add_argument("--json")
    args = p.parse_args()

    with zipfile.ZipFile(args.apk) as apk:
        axml = apk.read("AndroidManifest.xml")
    elements = walk_manifest(axml)
    package = next((e["attrs"].get("package") for e in elements if e["tag"] == "manifest"), None)

    components, providers, permissions, deep_links = [], [], [], []
    for e in elements:
        tag = e["tag"]
        if tag in COMPONENT_TAGS and e["attrs"].get("android:name"):
            components.append({"tag": tag, "name": e["attrs"]["android:name"],
                               "exported": e["attrs"].get("android:exported")})
        if tag == "provider" and e["attrs"].get("android:authorities"):
            providers.append(e["attrs"]["android:authorities"])
        if tag in IDENTITY_TAGS and e["attrs"].get("android:name"):
            permissions.append({"tag": tag, "name": e["attrs"]["android:name"]})
        if tag == "data":
            scheme = e["attrs"].get("android:scheme")
            host = e["attrs"].get("android:host")
            if scheme or host:
                deep_links.append({"scheme": scheme, "host": host})

    report = {
        "apk": os.path.basename(args.apk),
        "package": package,
        "components": components,
        "providers": providers,
        "permissions": permissions,
        "deepLinks": deep_links[:40],
        "counts": {"components": len(components), "providers": len(providers),
                   "permissions": len(permissions), "deepLinks": len(deep_links)},
    }

    print("package      %s" % package)
    print("components   %d" % len(components))
    print("providers    %d  %s" % (len(providers), providers[:3]))
    print("permissions  %d" % len(permissions))
    print("deep links   %d" % len(deep_links))

    if args.dex:
        try:
            classes = dex_classes(args.apk)
        except ImportError:
            print("dex check    SKIPPED (androguard not installed)")
        else:
            unresolved = []
            for c in components:
                name = c["name"]
                if not name.startswith(".") and "." not in name:
                    continue
                binary = "L" + name.replace(".", "/") + ";"
                if binary not in classes:
                    unresolved.append(name)
            report["dexCheck"] = {"classes": len(classes), "unresolved": unresolved}
            print("dex classes  %d" % len(classes))
            print("unresolved   %d %s" % (len(unresolved), unresolved[:5]))
            if unresolved:
                print("FAIL: the manifest names components that do not exist in the APK")

    if args.json:
        json.dump(report, open(args.json, "w"), indent=2)
    return 1 if report.get("dexCheck", {}).get("unresolved") else 0


if __name__ == "__main__":
    raise SystemExit(main())
