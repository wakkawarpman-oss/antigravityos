#!/usr/bin/env python3
"""
Аналізує final-summary.json та gate-result.json і видає release verdict: GREEN / RED / WARNING.
"""

import argparse
import json
import sys
from pathlib import Path


def load_json(path: str) -> dict:
    """Завантажує JSON-файл."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="analyze_release_verdict_multi",
        description="Analyze final-summary.json and gate-result.json to produce a release verdict.",
    )
    parser.add_argument("summary", help="Path to final-summary.json")
    parser.add_argument("gate", help="Path to gate-result.json")
    parser.add_argument(
        "--tor-policy",
        action="store_true",
        help="Enable additional check for tor_policy.status == 'pass' when present.",
    )
    args = parser.parse_args()

    summary_path = args.summary
    gate_path = args.gate
    use_tor_policy = args.tor_policy

    # Load artifacts
    try:
        summary = load_json(summary_path)
        gate = load_json(gate_path)
    except Exception as e:
        print(f"ERROR loading JSON: {e}")
        return 1

    print("ANALYZING RELEASE VERDICT")
    print("  SUMMARY:", summary_path)
    print("  GATE:", gate_path)
    print("-" * 60)

    # 1. Overall runtime status
    overall_status = summary.get("overall_status")
    failure_count = summary.get("failure_count", 0)
    checks = summary.get("checks", {})
    if not isinstance(checks, dict):
        checks = {}
    tor_policy = checks.get("tor_policy", {})
    if not isinstance(tor_policy, dict):
        tor_policy = {}

    # 2. Gate result
    gate_valid = gate.get("valid", False)
    required_failures = gate.get("required_check_failures", [])
    if not isinstance(required_failures, list):
        required_failures = [required_failures]

    # --- Decision logic ---
    is_green = True

    # (a) Gate contract
    if not gate_valid:
        print("GATE INVALID: gate.valid is not True")
        is_green = False

    if required_failures:
        print("Required check failures:")
        for fail in sorted(required_failures, key=lambda x: str(x)):
            print(f"  - {fail}")
        is_green = False

    # (b) Overall prelaunch outcome
    if overall_status != "pass":
        print(f"overall_status = {overall_status}")
        is_green = False

    # (c) tor_policy (optional)
    if use_tor_policy:
        tor_status = tor_policy.get("status")
        if tor_status != "pass" and tor_status is not None:
            print(f"tor_policy.status = {tor_status}")
            is_green = False
        elif tor_status == "pass":
            print("tor_policy.status = pass")

    # (d) Non-critical failures
    try:
        failure_count_int = int(failure_count)
    except Exception:
        failure_count_int = 0

    verdict_label = "GREEN"
    if failure_count_int > 0 and is_green:
        print(
            f"There are {failure_count_int} non-required failure(s) present (status = warning)."
        )
        verdict_label = "WARNING"

    # --- Final verdict ---
    print("-" * 60)
    print("OVERALL STATUS:", overall_status)
    print("GATE VALID:", gate_valid)
    print("REQUIRED FAILURES:", required_failures)
    print("TOR POLICY STATUS:", tor_policy.get("status"))
    print("FAILURE COUNT (non-required):", failure_count)

    print("-" * 60)
    if is_green and verdict_label == "GREEN":
        print("RELEASE VERDICT: GREEN (ready for RC)")
        exit_code = 0
    elif is_green and verdict_label == "WARNING":
        print("RELEASE VERDICT: WARNING (gate-green with non-required failures)")
        exit_code = 0
    else:
        print("RELEASE VERDICT: RED (not ready for RC)")
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
