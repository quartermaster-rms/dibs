#!/usr/bin/env python
"""Fail unless security-sensitive paths reach 100% line + branch coverage.

Security-sensitive per IMPLEMENTATION-GUIDE §7: authorization decisions,
credential/token handling, and the interlock device port.
"""
import json
import sys
from pathlib import Path

SECURITY_DIRS = ("/dibs/auth/", "/dibs/permissions/", "/dibs/device/")
COVERAGE_JSON = Path("coverage.json")


def is_security_file(path: str) -> bool:
    norm = "/" + path.replace("\\", "/").lstrip("/")
    return any(d in norm for d in SECURITY_DIRS)


def main() -> int:
    if not COVERAGE_JSON.exists():
        print("coverage.json missing; run the tests first", file=sys.stderr)
        return 2
    data = json.loads(COVERAGE_JSON.read_text())
    files = data.get("files", {})
    checked = 0
    failures = []
    for path, info in sorted(files.items()):
        if not is_security_file(path):
            continue
        checked += 1
        s = info["summary"]
        if s["missing_lines"] or s.get("missing_branches", 0) or s.get("num_partial_branches", 0):
            failures.append(
                f"  {path}: missing_lines={s['missing_lines']} "
                f"missing_branches={s.get('missing_branches', 0)} "
                f"partial_branches={s.get('num_partial_branches', 0)} "
                f"missing={info.get('missing_lines')}"
            )
    if checked == 0:
        print("no security-sensitive files matched; refusing to pass vacuously", file=sys.stderr)
        return 2
    if failures:
        print(f"security-path coverage < 100% ({len(failures)}/{checked} files):", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"security-path coverage OK: 100% on {checked} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
