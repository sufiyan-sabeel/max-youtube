#!/usr/bin/env python3
"""Tests for tools/apk_inspect.py. Runs against a real APK, never a mock.

    MAX_YOUTUBE_TEST_APK=/path/to/YouTube.apk python3 tools/test_apk_inspect.py

Two kinds of assertion:

  * invariants that hold for any YouTube APK — package name, a parseable version, at least one dex, a
    resource table;
  * fixture assertions that only run when the input is the YouTube 21.45.82 build this project has
    analysed (SHA-256 10b51b70…dfb28), where the exact values are known from an independent inspection.

So the suite is meaningful on any input and exact on the one input whose facts are established.
"""
import hashlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apk_inspect  # noqa: E402

FIXTURE_SHA256 = "10b51b7075ae0e92e7cba6d3ca393422a2756c214097800ccb89c5c3f01dfb28"

failures: list[str] = []
passed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
        print("  PASS  %s" % name)
    else:
        failures.append("%s %s" % (name, detail))
        print("  FAIL  %s %s" % (name, detail))


def main() -> int:
    path = os.environ.get("MAX_YOUTUBE_TEST_APK") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not path or not os.path.isfile(path):
        print("set MAX_YOUTUBE_TEST_APK to a YouTube APK", file=sys.stderr)
        return 2

    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    print("input %s" % os.path.basename(path))
    print("sha256 %s" % sha)
    print("fixture %s" % ("YouTube 21.45.82" if sha == FIXTURE_SHA256 else "unknown build"))
    print("")

    report = apk_inspect.inspect(path, deep=False)

    # ---- invariants
    m = report["manifest"]
    check("package is a YouTube package",
          m.get("package") in ("com.google.android.youtube", "app.maxyoutube"),
          "got %r" % m.get("package"))
    check("versionName parsed", isinstance(m.get("versionName"), str) and len(m["versionName"]) > 0,
          "got %r" % m.get("versionName"))
    check("versionCode parsed", isinstance(m.get("versionCode"), int) and m["versionCode"] > 0,
          "got %r" % m.get("versionCode"))
    check("minSdk parsed", isinstance(m.get("minSdkVersion"), int),
          "got %r" % m.get("minSdkVersion"))
    check("resource table present", report["resources"].get("present") is True)
    check("at least one dex", report["dex"]["count"] >= 1, "got %d" % report["dex"]["count"])
    check("every dex parses", all(d.get("valid") for d in report["dex"]["files"]))
    check("classes counted", report["dex"]["totalClasses"] > 0)
    check("signing block present", report["signing"]["apkSigBlock"] is True)
    check("sha256 recorded", report["input"]["sha256"] == sha)

    # ---- fixture assertions, only for the build whose facts are known
    if sha == FIXTURE_SHA256:
        check("version is 21.45.82", m.get("versionName") == "21.45.82",
              "got %r" % m.get("versionName"))
        check("versionCode is 1561310996", m.get("versionCode") == 1561310996,
              "got %r" % m.get("versionCode"))
        check("targetSdk is 37", m.get("targetSdkVersion") == 37,
              "got %r" % m.get("targetSdkVersion"))
        check("resources.arsc is 2134488 bytes",
              report["resources"].get("arscSizeBytes") == 2134488,
              "got %r" % report["resources"].get("arscSizeBytes"))
        check("eight dex files", report["dex"]["count"] == 8, "got %d" % report["dex"]["count"])

    # ---- the report round-trips as JSON
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        import json
        json.dump(report, tmp)
        tmp_path = tmp.name
    try:
        with open(tmp_path) as f:
            reloaded = json.load(f)
        check("report round-trips as JSON", reloaded["input"]["sha256"] == sha)
    finally:
        os.unlink(tmp_path)

    print("")
    print("%d passed, %d failed" % (passed, len(failures)))
    if failures:
        for f in failures:
            print("  - %s" % f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
