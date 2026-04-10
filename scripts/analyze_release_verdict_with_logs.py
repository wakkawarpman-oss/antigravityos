#!/usr/bin/env python3
"""Analyze release artifacts and emit verdict with first-cause hints from logs.

Inputs:
- final-summary.json
- gate-result.json
Optional inputs:
- pytest.err
- full-rehearsal.err
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    """Load a JSON object from disk."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def read_log(path: str, lines: int = 200) -> str:
    """Read first N lines from a log file; return marker when file is missing."""
    p = Path(path)
    if not p.exists():
        return f"[log {path} missing]"
    with p.open("r", encoding="utf-8", errors="replace") as f:
        return "".join(f.readlines()[:lines])


def get_first_match(text: str, patterns: list[str]) -> str | None:
    """Return first line containing any pattern."""
    for line in text.splitlines():
        for pattern in patterns:
            if pattern in line:
                return line
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="analyze_release_verdict_with_logs",
        description="Analyze final-summary, gate-result, and optional logs.",
    )
    parser.add_argument("summary", help="Path to final-summary.json")
    parser.add_argument("gate", help="Path to gate-result.json")
    parser.add_argument("pytest_err", nargs="?", default=None, help="Optional path to pytest.err")
    parser.add_argument(
        "rehearsal_err",
        nargs="?",
        default=None,
        help="Optional path to full-rehearsal.err",
    )
    parser.add_argument(
        "--tor-policy",
        action="store_true",
        help="Require checks.tor_policy.status == 'pass' when present.",
    )
    parser.add_argument(
        "--rc",
        action="store_true",
        help="CI mode: print nothing and signal verdict via exit code only.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Never fail process; always exit 0 after analysis.",
    )
    args = parser.parse_args()

    def emit(*parts: object) -> None:
        if not args.rc:
            print(*parts)

    try:
        summary = load_json(args.summary)
        gate = load_json(args.gate)
    except Exception as exc:
        emit(f"ERROR loading JSON: {exc}")
        return 0 if args.dry_run else 1

    emit("RELEASE VERDICT + LOG ANALYSIS")
    emit("  SUMMARY:", args.summary)
    emit("  GATE:", args.gate)
    if args.pytest_err:
        emit("  PYTEST:", args.pytest_err)
    if args.rehearsal_err:
        emit("  REHEARSAL:", args.rehearsal_err)
    emit("-" * 60)

    overall_status = summary.get("overall_status")
    failure_count = summary.get("failure_count", 0)
    checks = summary.get("checks", {})
    if not isinstance(checks, dict):
        checks = {}
    tor_policy = checks.get("tor_policy", {})
    if not isinstance(tor_policy, dict):
        tor_policy = {}

    gate_valid = gate.get("valid", False)
    required_failures = gate.get("required_check_failures", [])
    if not isinstance(required_failures, list):
        required_failures = [required_failures]

    is_green = True

    if not gate_valid:
        emit("GATE INVALID: gate.valid is not True")
        is_green = False

    if required_failures:
        emit("Required check failures:")
        for fail in sorted(required_failures, key=lambda x: str(x)):
            emit(f"  - {fail}")
        is_green = False

    if overall_status != "pass":
        emit(f"overall_status = {overall_status}")
        is_green = False

    if args.tor_policy and tor_policy:
        tor_status = tor_policy.get("status")
        if tor_status not in (None, "pass"):
            emit(f"tor_policy.status = {tor_status}")
            is_green = False

    try:
        failure_count_int = int(failure_count)
    except Exception:
        failure_count_int = 0

    if failure_count_int > 0 and is_green:
        emit(f"There are {failure_count_int} non-required failures (warning).")

    if not is_green:
        emit("First cause analysis from logs:")
        patterns = [
            "ModuleNotFoundError:",
            "No module named",
            "TypeError: object of type 'NoneType' has no len()",
            "error:",
            "fatal",
            "crash",
        ]

        if args.pytest_err:
            raw = read_log(args.pytest_err, 100)
            cause = get_first_match(raw, patterns)
            if cause:
                emit("  pytest.err ->", cause.strip())
            else:
                emit("  pytest.err: no obvious cause found")

        if args.rehearsal_err:
            raw = read_log(args.rehearsal_err, 100)
            cause = get_first_match(raw, patterns)
            if cause:
                emit("  rehearsal.err ->", cause.strip())
            else:
                emit("  rehearsal.err: no obvious cause found")

    emit("-" * 60)
    emit("STATUS:", overall_status)
    emit("GATE VALID:", gate_valid)
    emit("REQUIRED FAILURES:", required_failures)
    emit("TOR POLICY STATUS:", tor_policy.get("status"))
    emit("NON-REQ FAIL COUNT:", failure_count)
    emit("-" * 60)

    if is_green:
        emit("RELEASE VERDICT: GREEN (ready for RC)")
        exit_code = 0
    else:
        emit("RELEASE VERDICT: RED (not ready for RC)")
        exit_code = 1

    if args.dry_run:
        return 0
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
