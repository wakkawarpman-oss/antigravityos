#!/usr/bin/env python3
"""Analyze prelaunch artifacts and emit a release verdict.

Inputs:
- final-summary.json
- gate-result.json

Output verdicts:
- GREEN: required gate contract is satisfied.
- RED: required gate contract is not satisfied.
- WARNING: required gate contract is satisfied, but non-required failures exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    """Load JSON from file path."""
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="analyze_release_verdict",
        description="Analyze final-summary.json and gate-result.json to produce a release verdict.",
    )
    parser.add_argument(
        "--summary",
        "-s",
        required=True,
        help="Path to final-summary.json",
    )
    parser.add_argument(
        "--gate",
        "-g",
        required=True,
        help="Path to gate-result.json",
    )
    parser.add_argument(
        "--tor-policy",
        action="store_true",
        help="Require checks.tor_policy.status == 'pass' when present.",
    )
    args = parser.parse_args()

    try:
        summary = load_json(args.summary)
        gate = load_json(args.gate)
    except Exception as exc:
        print(f"ERROR: failed to load input JSON: {exc}")
        return 1

    overall_status = summary.get("overall_status")
    checks = summary.get("checks") or {}
    tor_policy = checks.get("tor_policy") if isinstance(checks, dict) else {}
    if not isinstance(tor_policy, dict):
        tor_policy = {}

    gate_valid = gate.get("valid", False)
    required_failures = gate.get("required_check_failures") or []
    if not isinstance(required_failures, list):
        required_failures = [str(required_failures)]

    failure_count = summary.get("failure_count", 0)
    try:
        failure_count_int = int(failure_count)
    except Exception:
        failure_count_int = 0

    is_green = True
    warning_reasons: list[str] = []
    red_reasons: list[str] = []

    if gate_valid is not True:
        is_green = False
        red_reasons.append("gate.valid is not true")

    if required_failures:
        is_green = False
        red_reasons.append(f"required_check_failures={sorted(required_failures)}")

    if overall_status != "pass":
        is_green = False
        red_reasons.append(f"overall_status={overall_status}")

    if args.tor_policy:
        tor_status = tor_policy.get("status")
        if tor_status is not None and tor_status != "pass":
            is_green = False
            red_reasons.append(f"tor_policy.status={tor_status}")

    if failure_count_int > 0 and is_green:
        warning_reasons.append(f"failure_count={failure_count_int} (non-required checks)")

    print("-" * 60)
    print("SUMMARY PATH:", args.summary)
    print("GATE PATH:", args.gate)
    print("OVERALL STATUS:", overall_status)
    print("GATE VALID:", gate_valid)
    print("REQUIRED FAILURES:", required_failures)
    print("TOR POLICY STATUS:", tor_policy.get("status"))

    if red_reasons:
        print("RED REASONS:")
        for reason in red_reasons:
            print("-", reason)

    if warning_reasons:
        print("WARNING REASONS:")
        for reason in warning_reasons:
            print("-", reason)

    if is_green and warning_reasons:
        print("RELEASE VERDICT: WARNING")
        exit_code = 0
    elif is_green:
        print("RELEASE VERDICT: GREEN")
        exit_code = 0
    else:
        print("RELEASE VERDICT: RED")
        exit_code = 1

    print("=" * 60)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
