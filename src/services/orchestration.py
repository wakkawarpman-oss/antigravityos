from __future__ import annotations

from pathlib import Path
from typing import Any


def ingest_metadata_exports(engine: Any, exports_root: Path) -> dict[str, int]:
    """Ingest JSON metadata exports and return status counters."""
    ing = {"ingested": 0, "rejected": 0, "skipped": 0}
    for meta_path in sorted(exports_root.glob("*.json")):
        res = engine.ingest_metadata(meta_path)
        status = str(res.get("status", "unknown"))
        if status == "ingested":
            ing["ingested"] += 1
        elif status == "rejected":
            ing["rejected"] += 1
        else:
            ing["skipped"] += 1
    return ing


def ingest_confirmed_evidence(engine: Any, verified_files: list[str] | None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for confirmed_file in verified_files or []:
        result = engine.ingest_confirmed_evidence(confirmed_file)
        if isinstance(result, dict):
            results.append(result)
    return results


def resolve_clusters(engine: Any) -> list[Any]:
    return engine.resolve_entities() or []


def run_recon_stage(
    engine: Any,
    *,
    target_name: str | None,
    modules: list[str] | None,
    proxy: str | None,
    leak_dir: str | None,
    known_phones: list[str] | None,
    known_usernames: list[str] | None,
) -> tuple[dict | None, Any | None]:
    if not (target_name or modules):
        return None, None
    return engine.run_deep_recon(
        target_name=target_name,
        modules=modules,
        proxy=proxy,
        leak_dir=leak_dir,
        known_phones_override=known_phones,
        known_usernames_override=known_usernames,
    )


def run_verification_stage(
    engine: Any,
    *,
    verify: bool,
    verify_all: bool,
    verify_content: bool,
    proxy: str | None,
) -> None:
    if verify or verify_all:
        max_checks = 999_999 if verify_all else 200
        engine.verify_profiles(max_checks=max_checks, timeout=4.0, proxy=proxy)
    if verify_content:
        engine.verify_content(max_checks=200, timeout=8.0, proxy=proxy)


def render_dossier(engine: Any, *, output_path: str, report_mode: str) -> None:
    engine.render_graph_report(output_path=output_path, redaction_mode=report_mode)
