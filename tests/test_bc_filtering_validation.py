from __future__ import annotations

import json
from pathlib import Path

from discovery_engine import DiscoveryEngine


def _write_meta(tmp_path: Path, *, target: str, profile: str, sha256: str = "", log_name: str = "scan.log") -> Path:
    log_path = tmp_path / log_name
    log_path.write_text("[ok] fixture log", encoding="utf-8")
    meta = {
        "target": target,
        "profile": profile,
        "status": "success",
        "log_file": str(log_path),
        "sha256": sha256,
        "label": "fixture",
    }
    meta_path = tmp_path / f"{profile}.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return meta_path


def test_ingest_rejects_target_equal_to_file_hash(tmp_path, tmp_db):
    engine = DiscoveryEngine(db_path=tmp_db)
    meta_path = _write_meta(tmp_path, target="abc123", profile="username", sha256="abc123")

    result = engine.ingest_metadata(meta_path)

    assert result["status"] == "rejected"
    assert result["reason"] == "target_is_file_hash"


def test_ingest_rejects_hex_hash_target(tmp_path, tmp_db):
    engine = DiscoveryEngine(db_path=tmp_db)
    meta_path = _write_meta(tmp_path, target="a" * 32, profile="username")

    result = engine.ingest_metadata(meta_path)

    assert result["status"] == "rejected"
    assert result["reason"] == "hex_hash_target"


def test_ingest_rejects_high_entropy_target(tmp_path, tmp_db):
    engine = DiscoveryEngine(db_path=tmp_db)
    meta_path = _write_meta(tmp_path, target="xK9zQ2wR5tY8uI3o", profile="username")

    result = engine.ingest_metadata(meta_path)

    assert result["status"] == "rejected"
    assert result["reason"] == "high_entropy_target"


def test_ingest_rejects_invalid_phone_for_phone_profile(tmp_path, tmp_db):
    engine = DiscoveryEngine(db_path=tmp_db)
    meta_path = _write_meta(tmp_path, target="not-a-phone", profile="phone")

    result = engine.ingest_metadata(meta_path)

    assert result["status"] == "rejected"
    assert result["reason"] == "phone_profile_invalid_target"


def test_ingest_rejects_placeholder_domain_for_domain_profile(tmp_path, tmp_db):
    engine = DiscoveryEngine(db_path=tmp_db)
    meta_path = _write_meta(tmp_path, target="example.com", profile="domain")

    result = engine.ingest_metadata(meta_path)

    assert result["status"] == "rejected"
    assert result["reason"] == "placeholder_domain"
