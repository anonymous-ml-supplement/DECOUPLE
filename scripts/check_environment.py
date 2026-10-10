#!/usr/bin/env python3
"""Report the frozen-data reproduction interpreter and direct package versions.

The default mode accepts Python 3.10 and supported package ranges while clearly
marking builds different from the independently validated lab run. --strict
requires the tested exact interpreter/package versions. Uses standard library only.
"""
import argparse
import sys
from importlib import metadata

EXPECTED = {"numpy": "2.2.6", "matplotlib": "3.10.9"}
LAB_PYTHON = (3, 10, 12)

def major_minor(version):
    parts = version.split(".")
    try:
        return tuple(int(p) for p in parts[:2])
    except (ValueError, IndexError):
        return (-1, -1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="require the tested lab versions exactly")
    args = ap.parse_args()
    py = sys.version_info[:3]
    print("PYTHON_EXECUTABLE=" + sys.executable)
    print("PYTHON_VERSION=" + ".".join(str(p) for p in py))
    problems = []
    for name, expected in EXPECTED.items():
        try:
            v = metadata.version(name)
        except metadata.PackageNotFoundError:
            v = "MISSING"
        print(f"{name.upper()}_VERSION={v}")
        if v == "MISSING":
            problems.append(name + " missing")
        elif args.strict and v != expected:
            problems.append(name + " requires " + expected + " for strict match")
        elif not args.strict:
            mm = major_minor(v)
            if name == "numpy" and not ((1, 24) <= mm < (3, 0)):
                problems.append(name + " outside declared compatibility range")
            if name == "matplotlib" and not ((3, 7) <= mm < (4, 0)):
                problems.append(name + " outside declared compatibility range")
    if args.strict and py != LAB_PYTHON:
        problems.append("Python requires 3.10.12 for strict lab match")
    if not args.strict and sys.version_info[:2] != (3, 10):
        print("WARNING_PYTHON_VERSION=untested interpreter; lab used CPython 3.10.12")
    if problems:
        for p in problems: print("FAIL " + p)
        print("FINAL_ENVIRONMENT_STATUS=FAIL")
        return 1
    match = (py == LAB_PYTHON and all(metadata.version(n) == v for n, v in EXPECTED.items()))
    print("ENVIRONMENT_PROFILE=" + ("MATCHES_TESTED_LAB" if match else "DIFFERS_FROM_TESTED_LAB"))
    print("FINAL_ENVIRONMENT_STATUS=PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
