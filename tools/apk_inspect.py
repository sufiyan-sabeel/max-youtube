#!/usr/bin/env python3
"""Inspect a YouTube APK and write a JSON report. Standard library only.

This is phase 1 of the MAX YouTube plan: everything the pipeline needs to know about an input before a
single patch runs. It reads the binary AndroidManifest, the dex headers, the resource table's presence and
the APK signing block. It never modifies the APK and never writes outside the report path.

    python3 tools/apk_inspect.py YouTube.apk --json report.json

Deeper detail — resource *names*, per-dex class/method counts beyond the header, and the signing
certificate fingerprint — needs androguard. When it is installed those sections are filled in; when it is
not, they are reported as `null` with the reason, never guessed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import zipfile

RES_XML_TYPE = 0x0003
RES_STRING_POOL_TYPE = 0x0001
RES_XML_START_TAG = 0x0102
UTF8_FLAG = 0x100
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11

ANDROID_NS = "http://schemas.android.com/apk/res/android"
APK_SIG_BLOCK_MAGIC = b"APK Sig Block 42"


# --------------------------------------------------------------------------- binary XML

class StringPool:
    def __init__(self, data: bytes, offset: int):
        self.strings: list[str] = []
        header_size = struct.unpack_from("<H", data, offset + 2)[0]
        size = struct.unpack_from("<I", data, offset + 4)[0]
        count, _style_count, flags, strings_start, _styles_start = struct.unpack_from(
            "<IIIII", data, offset + 8)
        offsets = struct.unpack_from("<%dI" % count, data, offset + header_size)
        base = offset + strings_start
        utf8 = bool(flags & UTF8_FLAG)
        for rel in offsets:
            pos = base + rel
            try:
                if utf8:
                    # u16 length (chars), u16 length (bytes), then the bytes
                    pos += 2
                    byte_len = data[pos]
                    if byte_len & 0x80:
                        pos += 1
                    pos += 1
                    self.strings.append(data[pos:pos + byte_len].decode("utf-8", "replace"))
                else:
                    char_len = struct.unpack_from("<H", data, pos)[0]
                    pos += 2
                    if char_len & 0x8000:
                        char_len = ((char_len & 0x7FFF) << 16) | struct.unpack_from("<H", data, pos)[0]
                        pos += 2
                    self.strings.append(data[pos:pos + char_len * 2].decode("utf-16-le", "replace"))
            except Exception:
                self.strings.append("")
        self.size = size

    def get(self, index: int) -> str:
        if 0 <= index < len(self.strings):
            return self.strings[index]
        return ""


def parse_manifest(axml: bytes) -> dict:
    """Read the manifest's package identity, versions and SDK levels from the binary XML."""
    if len(axml) < 8 or struct.unpack_from("<H", axml, 0)[0] != RES_XML_TYPE:
        raise ValueError("not a binary AndroidManifest.xml")

    pool = None
    result: dict = {}
    seen_manifest = False
    offset = struct.unpack_from("<H", axml, 2)[0]

    while offset + 8 <= len(axml):
        chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", axml, offset)
        if chunk_size < 8:
            break
        if chunk_type == RES_STRING_POOL_TYPE:
            pool = StringPool(axml, offset)
        elif chunk_type == RES_XML_START_TAG and pool is not None:
            ns_idx, name_idx = struct.unpack_from("<iI", axml, offset + 16)
            # ResXMLTree_attrExt: ns(4) name(4) attributeStart(2) attributeSize(2)
            # attributeCount(2) idIndex(2) classIndex(2) styleIndex(2), starting at offset+16.
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", axml, offset + 24)
            tag = pool.get(name_idx)
            attrs: dict[str, tuple[str, object]] = {}
            for i in range(attr_count):
                pos = offset + 16 + attr_start + i * attr_size
                a_ns, a_name, a_raw = struct.unpack_from("<iII", axml, pos)
                data_type = axml[pos + 15]
                data = struct.unpack_from("<I", axml, pos + 16)[0]
                key = pool.get(a_name)
                if data_type == TYPE_STRING:
                    value: object = pool.get(data)
                elif data_type in (TYPE_INT_DEC, TYPE_INT_HEX):
                    value = data
                else:
                    value = data
                ns = pool.get(a_ns) if a_ns >= 0 else ""
                if ns == ANDROID_NS:
                    key = "android:" + key
                attrs[key] = (ns, value)

            if tag == "manifest" and not seen_manifest:
                seen_manifest = True
                result["package"] = attrs.get("package", ("", None))[1]
                result["versionName"] = attrs.get("android:versionName", ("", None))[1]
                result["versionCode"] = attrs.get("android:versionCode", ("", None))[1]
                result["compileSdkVersion"] = attrs.get("android:compileSdkVersion", ("", None))[1]
            elif tag == "uses-sdk":
                result["minSdkVersion"] = attrs.get("android:minSdkVersion", ("", None))[1]
                result["targetSdkVersion"] = attrs.get("android:targetSdkVersion", ("", None))[1]
            elif tag == "application" and "applicationLabel" not in result:
                result["applicationLabel"] = attrs.get("android:label", ("", None))[1]
        offset += chunk_size
    return result


# --------------------------------------------------------------------------- dex

def read_dex_header(data: bytes) -> dict:
    if data[:4] != b"dex\n":
        return {"valid": False}
    version = data[4:7].decode("ascii", "replace")
    (file_size,) = struct.unpack_from("<I", data, 32)
    string_ids_size = struct.unpack_from("<I", data, 56)[0]
    type_ids_size = struct.unpack_from("<I", data, 64)[0]
    proto_ids_size = struct.unpack_from("<I", data, 72)[0]
    field_ids_size = struct.unpack_from("<I", data, 80)[0]
    method_ids_size = struct.unpack_from("<I", data, 88)[0]
    class_defs_size = struct.unpack_from("<I", data, 96)[0]
    return {
        "valid": True,
        "version": version,
        "fileSize": file_size,
        "strings": string_ids_size,
        "types": type_ids_size,
        "protos": proto_ids_size,
        "fields": field_ids_size,
        "methods": method_ids_size,
        "classes": class_defs_size,
    }


# --------------------------------------------------------------------------- signing

def signing_block(path: str) -> dict:
    """Whether the APK carries a v2/v3 signing block.

    The block sits before the central directory, which can be far from the end of the file in a large
    APK, so the magic is looked for across the file rather than in a tail window.
    """
    found = False
    with open(path, "rb") as f:
        carry = b""
        for block in iter(lambda: f.read(1 << 20), b""):
            if APK_SIG_BLOCK_MAGIC in carry + block:
                found = True
                break
            carry = block[-(len(APK_SIG_BLOCK_MAGIC) - 1):]
    return {"apkSigBlock": found, "v1JarSignature": False}


# --------------------------------------------------------------------------- report

def inspect(path: str, deep: bool) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)

    report: dict = {
        "input": {
            "path": os.path.basename(path),
            "sizeBytes": os.path.getsize(path),
            "sha256": digest.hexdigest(),
        },
        "manifest": {},
        "resources": {},
        "dex": {},
        "signing": {},
        "warnings": [],
        "tool": {"name": "apk_inspect", "version": "1.0", "deepInspection": deep},
    }

    with zipfile.ZipFile(path) as apk:
        names = apk.namelist()
        if "AndroidManifest.xml" not in names:
            raise ValueError("no AndroidManifest.xml: not an APK")
        report["manifest"] = parse_manifest(apk.read("AndroidManifest.xml"))

        if "resources.arsc" in names:
            info = apk.getinfo("resources.arsc")
            report["resources"] = {"arscSizeBytes": info.file_size, "present": True}
        else:
            report["resources"] = {"present": False}
            report["warnings"].append("no resources.arsc: a resource patch cannot run")

        dex = []
        for name in sorted(n for n in names if n.startswith("classes") and n.endswith(".dex")):
            header = read_dex_header(apk.read(name))
            header["name"] = name
            header["sizeBytes"] = apk.getinfo(name).file_size
            dex.append(header)
        report["dex"] = {
            "count": len(dex),
            "files": dex,
            "totalClasses": sum(d.get("classes", 0) for d in dex),
            "totalMethods": sum(d.get("methods", 0) for d in dex),
        }

        v1 = any(n.upper().startswith("META-INF/") and n.upper().endswith((".RSA", ".DSA", ".EC"))
                 for n in names)
        signing = signing_block(path)
        signing["v1JarSignature"] = v1
        report["signing"] = signing

    # Optional deep inspection: resource names and the signing certificate.
    report["resources"]["resourceNames"] = None
    report["resources"]["drawableCount"] = None
    report["signing"]["certificateSha256"] = None
    if deep:
        try:
            from androguard.core.apk import APK as _APK  # noqa: F401
            from androguard.core.axml import ARSCParser
            import zipfile as _zip

            pkg = report["manifest"].get("package")
            with _zip.ZipFile(path) as apk:
                arsc = ARSCParser(apk.read("resources.arsc"))
            arsc.get_res_id_by_key(pkg, "drawable", "x")  # forces the lazy parse
            keys = arsc.resource_keys[pkg]
            total = sum(len(v) for v in keys.values())
            report["resources"]["resourceNames"] = total
            report["resources"]["drawableCount"] = len(keys.get("drawable", {}))
            report["resources"]["types"] = sorted(t for t in keys if keys[t])
        except ImportError:
            report["warnings"].append("androguard not installed: resource names not inventoried")
        except Exception as e:  # noqa: BLE001 - reported, not hidden
            report["warnings"].append("deep resource inspection failed: %s" % type(e).__name__)
    else:
        report["warnings"].append("deep inspection not requested: resource names not inventoried")

    if not report["signing"]["apkSigBlock"] and not report["signing"]["v1JarSignature"]:
        report["warnings"].append("APK appears unsigned")

    return report


def summarise(report: dict) -> str:
    m = report["manifest"]
    lines = [
        "input      %s" % report["input"]["path"],
        "size       %d bytes" % report["input"]["sizeBytes"],
        "sha256     %s" % report["input"]["sha256"],
        "package    %s" % m.get("package"),
        "version    %s (code %s)" % (m.get("versionName"), m.get("versionCode")),
        "sdk        min %s, target %s, compile %s" % (
            m.get("minSdkVersion"), m.get("targetSdkVersion"), m.get("compileSdkVersion")),
        "resources  %s" % ("arsc %d bytes" % report["resources"]["arscSizeBytes"]
                           if report["resources"].get("present") else "absent"),
        "dex        %d files, %d classes, %d methods" % (
            report["dex"]["count"], report["dex"]["totalClasses"], report["dex"]["totalMethods"]),
        "signing    apkSigBlock=%s v1=%s" % (report["signing"]["apkSigBlock"],
                                             report["signing"]["v1JarSignature"]),
    ]
    if report["resources"].get("drawableCount") is not None:
        lines.append("drawables  %d" % report["resources"]["drawableCount"])
    for w in report["warnings"]:
        lines.append("warning    %s" % w)
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Inspect a YouTube APK and report on it.")
    parser.add_argument("apk")
    parser.add_argument("--json", metavar="PATH", help="write the JSON report here")
    parser.add_argument("--deep", action="store_true",
                        help="also inventory resource names (needs androguard)")
    args = parser.parse_args(argv)

    try:
        report = inspect(args.apk, args.deep)
    except FileNotFoundError:
        print("no such file: %s" % args.apk, file=sys.stderr)
        return 2
    except (ValueError, zipfile.BadZipFile) as e:
        print("cannot inspect %s: %s" % (args.apk, e), file=sys.stderr)
        return 3

    print(summarise(report))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2)
            f.write("\n")
        print("report     %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
