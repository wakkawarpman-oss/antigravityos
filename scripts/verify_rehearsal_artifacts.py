#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import ADAPTER_RESULT_SCHEMA_VERSION, CONTRACT_PROVENANCE_NAMESPACE, RUN_RESULT_SCHEMA_VERSION


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON file: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object in {path}")
    return payload


def _extract_stix_note_provenances(stix_payload: dict[str, Any]) -> list[dict[str, Any]]:
    objects = stix_payload.get("objects")
    if not isinstance(objects, list):
        return []
    provenances: list[dict[str, Any]] = []
    for obj in objects:
        if not isinstance(obj, dict) or obj.get("type") != "note":
            continue
        provenance = obj.get("x_hanna_provenance")
        if isinstance(provenance, dict):
            provenances.append(provenance)
    return provenances


def _extract_zip_manifest(zip_path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            try:
                raw = zf.read("manifest.json").decode("utf-8")
            except KeyError as exc:
                raise RuntimeError("ZIP missing manifest.json") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing ZIP artifact: {zip_path}") from exc
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"invalid ZIP artifact: {zip_path}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON in ZIP manifest: {zip_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("ZIP manifest must be a JSON object")
    return payload


def build_verification_payload(out_dir: Path) -> dict[str, Any]:
    metadata_path = out_dir / "full-rehearsal.metadata.json"
    runtime_path = out_dir / "full-rehearsal.runtime.json"

    if not metadata_path.exists():
        raise RuntimeError("missing rehearsal metadata export")
    if not runtime_path.exists():
        raise RuntimeError("missing rehearsal runtime summary")

    metadata = _load_json(metadata_path)
    runtime = _load_json(runtime_path)

    artifacts = metadata.get("artifacts", {}) if isinstance(metadata, dict) else {}
    exports = artifacts.get("exports", {}) if isinstance(artifacts, dict) else {}
    output_path = artifacts.get("output_path") if isinstance(artifacts, dict) else None

    required_export_keys = ["json", "stix", "zip"]
    missing_keys = [key for key in required_export_keys if key not in exports]
    existing = {key: Path(value).exists() for key, value in exports.items() if isinstance(value, str)}
    html_exists = bool(output_path and Path(output_path).exists())

    provenance_errors: list[str] = []
    expected_provenance = {
        "namespace": CONTRACT_PROVENANCE_NAMESPACE,
        "contracts": {
            "run_result_schema_version": RUN_RESULT_SCHEMA_VERSION,
            "adapter_result_schema_version": ADAPTER_RESULT_SCHEMA_VERSION,
        },
    }

    metadata_adapter_version = metadata.get("adapter_result_schema_version")
    runtime_adapter_version = runtime.get("adapter_result_schema_version")

    if metadata_adapter_version != ADAPTER_RESULT_SCHEMA_VERSION:
        provenance_errors.append(
            f"metadata.adapter_result_schema_version={metadata_adapter_version!r} expected {ADAPTER_RESULT_SCHEMA_VERSION}"
        )
    if runtime_adapter_version != ADAPTER_RESULT_SCHEMA_VERSION:
        provenance_errors.append(
            f"runtime.adapter_result_schema_version={runtime_adapter_version!r} expected {ADAPTER_RESULT_SCHEMA_VERSION}"
        )

    manifest_provenance: dict[str, Any] | None = None
    stix_note_provenances: list[dict[str, Any]] = []
    zip_manifest_adapter_version: Any = None

    stix_raw = exports.get("stix")
    zip_raw = exports.get("zip")

    if isinstance(stix_raw, str) and Path(stix_raw).exists():
        stix_payload = _load_json(Path(stix_raw))
        stix_note_provenances = _extract_stix_note_provenances(stix_payload)
    else:
        provenance_errors.append("missing STIX artifact for provenance checks")

    if isinstance(zip_raw, str) and Path(zip_raw).exists():
        manifest = _extract_zip_manifest(Path(zip_raw))
        manifest_provenance = manifest.get("provenance") if isinstance(manifest.get("provenance"), dict) else None
        zip_manifest_adapter_version = manifest.get("adapter_result_schema_version")
    else:
        provenance_errors.append("missing ZIP artifact for provenance checks")

    if zip_manifest_adapter_version != ADAPTER_RESULT_SCHEMA_VERSION:
        provenance_errors.append(
            "manifest.adapter_result_schema_version="
            f"{zip_manifest_adapter_version!r} expected {ADAPTER_RESULT_SCHEMA_VERSION}"
        )

    if not stix_note_provenances:
        provenance_errors.append("stix_note.provenance missing")

    for source_name, provenance in (("manifest", manifest_provenance),):
        if not isinstance(provenance, dict):
            provenance_errors.append(f"{source_name}.provenance missing")
            continue
        namespace = provenance.get("namespace")
        contracts = provenance.get("contracts") if isinstance(provenance.get("contracts"), dict) else {}
        run_result_version = contracts.get("run_result_schema_version")
        adapter_result_version = contracts.get("adapter_result_schema_version")

        if namespace != CONTRACT_PROVENANCE_NAMESPACE:
            provenance_errors.append(
                f"{source_name}.namespace={namespace!r} expected {CONTRACT_PROVENANCE_NAMESPACE!r}"
            )
        if run_result_version != RUN_RESULT_SCHEMA_VERSION:
            provenance_errors.append(
                f"{source_name}.contracts.run_result_schema_version={run_result_version!r} expected {RUN_RESULT_SCHEMA_VERSION}"
            )
        if adapter_result_version != ADAPTER_RESULT_SCHEMA_VERSION:
            provenance_errors.append(
                f"{source_name}.contracts.adapter_result_schema_version={adapter_result_version!r} expected {ADAPTER_RESULT_SCHEMA_VERSION}"
            )

    for idx, provenance in enumerate(stix_note_provenances):
        source_name = f"stix_note[{idx}]"
        namespace = provenance.get("namespace")
        contracts = provenance.get("contracts") if isinstance(provenance.get("contracts"), dict) else {}
        run_result_version = contracts.get("run_result_schema_version")
        adapter_result_version = contracts.get("adapter_result_schema_version")

        if namespace != CONTRACT_PROVENANCE_NAMESPACE:
            provenance_errors.append(
                f"{source_name}.namespace={namespace!r} expected {CONTRACT_PROVENANCE_NAMESPACE!r}"
            )
        if run_result_version != RUN_RESULT_SCHEMA_VERSION:
            provenance_errors.append(
                f"{source_name}.contracts.run_result_schema_version={run_result_version!r} expected {RUN_RESULT_SCHEMA_VERSION}"
            )
        if adapter_result_version != ADAPTER_RESULT_SCHEMA_VERSION:
            provenance_errors.append(
                f"{source_name}.contracts.adapter_result_schema_version={adapter_result_version!r} expected {ADAPTER_RESULT_SCHEMA_VERSION}"
            )

    artifacts_ok = not missing_keys and all(existing.values()) and html_exists
    provenance_ok = len(provenance_errors) == 0

    payload = {
        "status": "pass" if artifacts_ok and provenance_ok else "fail",
        "target_name": metadata.get("target_name"),
        "modules_run": metadata.get("modules_run", []),
        "runtime_summary": runtime,
        "artifacts": {
            "metadata_path": str(metadata_path),
            "metadata_path_exists": metadata_path.exists(),
            "output_path": output_path,
            "output_path_exists": html_exists,
            "exports": exports,
            "existing": existing,
            "missing_export_keys": missing_keys,
        },
        "contract_provenance": {
            "status": "pass" if provenance_ok else "fail",
            "expected": expected_provenance,
            "observed": {
                "metadata_adapter_result_schema_version": metadata_adapter_version,
                "runtime_adapter_result_schema_version": runtime_adapter_version,
                "manifest_provenance": manifest_provenance,
                "stix_note_provenances": stix_note_provenances,
                "manifest_adapter_result_schema_version": zip_manifest_adapter_version,
            },
            "errors": provenance_errors,
        },
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify rehearsal artifacts and contract provenance")
    parser.add_argument("out_dir", help="Path to prelaunch output directory")
    parser.add_argument("--json-only", action="store_true", help="Print compact JSON")
    args = parser.parse_args()

    payload = build_verification_payload(Path(args.out_dir))
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.json_only else 2))
    if payload.get("status") != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
