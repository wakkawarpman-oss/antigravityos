#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from stix2validator import ValidationError
from stix2validator import validate_string


def _load_json_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"stix bundle not found: {path}") from exc


def _validate_json_structure(raw_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("STIX payload must be a JSON object")
    if payload.get("type") != "bundle":
        raise RuntimeError("STIX payload type must be 'bundle'")
    objects = payload.get("objects")
    if not isinstance(objects, list):
        raise RuntimeError("STIX bundle must include an objects array")
    return payload


def _run_validation(raw_text: str) -> tuple[bool, list[str], list[str]]:
    try:
        result = validate_string(raw_text)
    except ValidationError as exc:
        return False, [str(exc)], []
    except Exception as exc:  # pragma: no cover - defensive boundary for validator runtime
        return False, [f"validator runtime error: {exc}"], []

    errors = [str(item) for item in getattr(result, "errors", [])]
    warnings = [str(item) for item in getattr(result, "warnings", [])]
    return len(errors) == 0, errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate STIX 2.1 bundle with external validator")
    parser.add_argument("stix_file", help="Path to a STIX bundle JSON file")
    parser.add_argument("--json-only", action="store_true", help="Print machine-readable JSON only")
    args = parser.parse_args()

    stix_path = Path(args.stix_file)
    try:
        raw_text = _load_json_text(stix_path)
        payload = _validate_json_structure(raw_text)
        ok, errors, warnings = _run_validation(raw_text)
    except RuntimeError as exc:
        report = {
            "status": "fail",
            "path": str(stix_path),
            "errors": [str(exc)],
            "warnings": [],
            "object_count": 0,
        }
        print(json.dumps(report, ensure_ascii=False, indent=None if args.json_only else 2))
        raise SystemExit(1)

    report = {
        "status": "pass" if ok else "fail",
        "path": str(stix_path),
        "errors": errors,
        "warnings": warnings,
        "object_count": len(payload.get("objects", [])),
    }
    print(json.dumps(report, ensure_ascii=False, indent=None if args.json_only else 2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()