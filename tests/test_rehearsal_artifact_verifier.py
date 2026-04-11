from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prepare_artifacts(tmp_path: Path, *, namespace: str) -> Path:
    out_dir = tmp_path / "prelaunch"
    out_dir.mkdir(parents=True)

    html_path = out_dir / "full-rehearsal.html"
    json_path = out_dir / "result.json"
    stix_path = out_dir / "result.stix.json"
    zip_path = out_dir / "result.zip"

    html_path.write_text("<html>ok</html>", encoding="utf-8")
    json_path.write_text("{}", encoding="utf-8")

    stix_payload = {
        "type": "bundle",
        "id": "bundle--fixture",
        "objects": [
            {
                "type": "note",
                "id": "note--fixture",
                "x_hanna_provenance": {
                    "namespace": namespace,
                    "contracts": {
                        "run_result_schema_version": 1,
                        "adapter_result_schema_version": 1,
                    },
                },
            }
        ],
    }
    stix_path.write_text(json.dumps(stix_payload), encoding="utf-8")

    manifest = {
        "target_name": "Fixture",
        "mode": "chain",
        "adapter_result_schema_version": 1,
        "provenance": {
            "namespace": namespace,
            "contracts": {
                "run_result_schema_version": 1,
                "adapter_result_schema_version": 1,
            },
        },
        "artifacts": [],
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))

    metadata = {
        "target_name": "Fixture",
        "modules_run": ["ghunt"],
        "adapter_result_schema_version": 1,
        "artifacts": {
            "output_path": str(html_path),
            "exports": {
                "json": str(json_path),
                "stix": str(stix_path),
                "zip": str(zip_path),
            },
        },
    }
    runtime = {
        "target_name": "Fixture",
        "mode": "chain",
        "adapter_result_schema_version": 1,
    }

    (out_dir / "full-rehearsal.metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (out_dir / "full-rehearsal.runtime.json").write_text(json.dumps(runtime), encoding="utf-8")
    return out_dir


def test_rehearsal_artifact_verifier_passes_with_known_namespace(tmp_path):
    module = _load_module(
        Path(__file__).resolve().parents[1] / "scripts" / "verify_rehearsal_artifacts.py",
        "verify_rehearsal_artifacts_pass",
    )
    out_dir = _prepare_artifacts(tmp_path, namespace="urn:hanna:contract-provenance:v1")

    payload = module.build_verification_payload(out_dir)

    assert payload["status"] == "pass"
    assert payload["contract_provenance"]["status"] == "pass"
    assert payload["contract_provenance"]["expected"]["namespace"] == "urn:hanna:contract-provenance:v1"


def test_rehearsal_artifact_verifier_fails_closed_on_unknown_namespace(tmp_path):
    module = _load_module(
        Path(__file__).resolve().parents[1] / "scripts" / "verify_rehearsal_artifacts.py",
        "verify_rehearsal_artifacts_fail",
    )
    out_dir = _prepare_artifacts(tmp_path, namespace="urn:hanna:contract-provenance:v99")

    payload = module.build_verification_payload(out_dir)

    assert payload["status"] == "fail"
    assert payload["contract_provenance"]["status"] == "fail"
    errors = payload["contract_provenance"]["errors"]
    assert any("namespace" in item for item in errors)
