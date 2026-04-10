from __future__ import annotations

import json

from adapters.base import ReconHit
from exporters.stix_exporter import build_stix_bundle, export_run_result_stix
from models import AdapterOutcome, RunResult


def _sample_result() -> RunResult:
    hit = ReconHit(
        observable_type="email",
        value="user@example.com",
        source_module="ghunt",
        source_detail="fixture",
        confidence=0.8,
        raw_record={"source": "fixture"},
    )
    return RunResult(
        target_name="Case Target",
        mode="aggregate",
        modules_run=["ghunt"],
        outcomes=[AdapterOutcome(module_name="ghunt", lane="fast", hits=[hit], elapsed_sec=0.1)],
        all_hits=[hit],
        started_at="2026-04-10T12:00:00",
        finished_at="2026-04-10T12:00:01",
    )


def test_stix_bundle_contains_required_object_types():
    bundle = build_stix_bundle(_sample_result())
    types = [obj["type"] for obj in bundle["objects"]]

    assert bundle["type"] == "bundle"
    assert "identity" in types
    assert "observed-data" in types
    assert "relationship" in types
    assert "note" in types


def test_stix_relationships_reference_existing_objects():
    bundle = build_stix_bundle(_sample_result())
    ids = {obj["id"] for obj in bundle["objects"]}
    relationships = [obj for obj in bundle["objects"] if obj["type"] == "relationship"]

    assert relationships
    for rel in relationships:
        assert rel["source_ref"] in ids
        assert rel["target_ref"] in ids


def test_stix_export_writes_valid_bundle_file(tmp_path):
    path = export_run_result_stix(_sample_result(), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.exists()
    assert payload["type"] == "bundle"
    assert isinstance(payload["objects"], list)
    assert payload["objects"]
