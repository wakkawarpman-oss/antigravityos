#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union, List, Dict, Tuple
from services.report_renderer import ReportRenderer, strip_ansi, slug, profile_display_name


ANALYST_ID = "legacy-bridge"
DEFAULT_API_TOKEN = os.getenv("OSINT_API_TOKEN", "legacy-bridge-local-dev-token")


def api_request(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None, api_token: str = DEFAULT_API_TOKEN) -> tuple[int, Any]:
    body = None
    headers = {"Authorization": f"Bearer {api_token}"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base_url.rstrip("/") + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"error": raw}





def canonical_lookup_value(value: str) -> str:
    return " ".join(strip_ansi(value).strip().split()).lower()


def normalize_target_value(profile: str, target: str) -> str:
    cleaned = strip_ansi(target).strip()
    if profile in {"domain", "dnsenum", "whatweb"}:
        match = re.search(r"Ignored\s+invalid\s+OSINT_DOMAIN\s+value:\s*(.+)$", cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
    return cleaned


def tool_name_for_meta(meta: dict[str, Any]) -> str:
    label = strip_ansi(str(meta.get("label") or "")).strip()
    match = re.match(r"dossier_[^_]+_([^_]+)_", label)
    if match:
        return match.group(1)

    profile = str(meta.get("profile") or "").strip().lower()
    fallback = {
        "phone": "phoneinfoga",
        "username": "username",
        "domain": "domain",
        "dnsenum": "dnsenum",
        "whatweb": "whatweb",
        "email": "email",
        "ip": "ip",
    }
    return fallback.get(profile, profile or "legacy")


def supporting_evidence_ids(claim: dict[str, Any], evidence_ids_by_target: dict[str, list[str]]) -> list[str]:
    matches: list[str] = []
    seen_ids: set[str] = set()
    for entity in claim.get("entities", []):
        entity_value = str(entity.get("entity_value") or "")
        lookup = canonical_lookup_value(entity_value)
        for evidence_id in evidence_ids_by_target.get(lookup, []):
            if evidence_id in seen_ids:
                continue
            seen_ids.add(evidence_id)
            matches.append(evidence_id)
    return matches


def parse_phone_log(log_text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "categories": {},
        "urls": [],
        "top_findings": [],
    }
    current_group = None
    for raw_line in log_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith(":") and not line.startswith("URL:"):
            current_group = line[:-1]
            parsed["categories"].setdefault(current_group, [])
            continue
        if line.startswith("URL:"):
            url = line.split("URL:", 1)[1].strip()
            parsed["urls"].append(url)
            if current_group:
                parsed["categories"].setdefault(current_group, []).append(url)
            continue
        match = re.match(r"^(Raw local|Local|E164|International|Country):\s*(.+)$", line)
        if match:
            key = match.group(1).lower().replace(" ", "_")
            parsed[key] = match.group(2).strip()
            parsed["top_findings"].append(line)
            continue
        if line.startswith("Results for "):
            parsed["top_findings"].append(line)
            continue
    return parsed








def infer_entity_type(profile: str, target: str) -> str:
    if profile in {"phone"}:
        return "observable"
    if profile in {"email"}:
        return "identity"
    if profile in {"username"}:
        return "identity"
    if profile in {"domain", "dnsenum", "whatweb"}:
        return "infrastructure"
    if profile == "ip":
        return "infrastructure"
    if "@" in target:
        return "identity"
    if target.startswith("+") or target[:1].isdigit():
        return "observable"
    return "observable"


def ensure_graph(base_url: str, target_label: str, api_token: str) -> str:
    input_node = str(uuid.uuid4())
    processor_node = str(uuid.uuid4())
    status, payload = api_request(
        base_url,
        "POST",
        "/api/v1/graphs",
        {
            "name": f"legacy-phone-dossier-{slug(target_label)}",
            "analyst_id": ANALYST_ID,
            "version": "1",
            "nodes": [
                {
                    "id": input_node,
                    "name": "Legacy Phone Seed",
                    "node_type": "input",
                    "subtype": "phone",
                    "adapter_name": None,
                    "position": {"x": 120, "y": 80},
                    "config": {},
                },
                {
                    "id": processor_node,
                    "name": "PhoneInfoga Legacy Import",
                    "node_type": "processor",
                    "subtype": "phoneinfoga",
                    "adapter_name": "phoneinfoga",
                    "position": {"x": 420, "y": 80},
                    "config": {"source": "legacy-export-bridge"},
                },
            ],
            "edges": [
                {
                    "source_node_id": input_node,
                    "source_port_id": "out",
                    "target_node_id": processor_node,
                    "target_port_id": "in",
                    "observable_type": "phone",
                    "contract_name": "phone->phoneinfoga",
                }
            ],
        },
        api_token=api_token,
    )
    if status != 201:
        raise RuntimeError(f"graph creation failed: {payload}")
    return str(payload["graph_id"])


def create_run(base_url: str, graph_id: str, phone: str, api_token: str) -> str:
    status, payload = api_request(
        base_url,
        "POST",
        "/api/v1/runs",
        {
            "graph_id": graph_id,
            "project_id": "legacy-phone-dossier",
            "analyst_id": ANALYST_ID,
            "seeds": [{"observable_type": "phone", "value": phone}],
        },
        api_token=api_token,
    )
    if status != 201:
        raise RuntimeError(f"run creation failed: {payload}")
    return str(payload["run_id"])


def post_event(base_url: str, run_id: str, node_id: str, api_token: str, message: str) -> None:
    status, payload = api_request(
        base_url,
        "POST",
        f"/api/v1/runs/{run_id}/events",
        {
            "node_id": node_id,
            "status": "succeeded",
            "message": message,
            "progress_percent": 100,
            "payload": {"source": "legacy-export-bridge"},
        },
        api_token=api_token,
    )
    if status != 201:
        raise RuntimeError(f"event creation failed: {payload}")


def intake_evidence(base_url: str, run_id: str, node_id: str, meta: dict[str, Any], log_text: str, api_token: str) -> str:
    status, payload = api_request(
        base_url,
        "POST",
        "/api/v1/evidence/intake",
        {
            "run_id": run_id,
            "node_id": node_id,
            "kind": "execution_log",
            "uri": meta["log_file"],
            "source_uri": meta["log_file"],
            "mime_type": "text/plain",
            "content": log_text,
            "tool_name": tool_name_for_meta(meta),
            "tool_version": "legacy",
            "actor_id": ANALYST_ID,
            "actor_type": "adapter",
            "metadata": {
                "legacy_label": meta.get("label"),
                "legacy_timestamp": meta.get("timestamp"),
                "legacy_profile": meta.get("profile"),
            },
        },
        api_token=api_token,
    )
    if status != 201:
        raise RuntimeError(f"evidence intake failed: {payload}")
    return str(payload["artifact_id"])


def create_claim(base_url: str, run_id: str, statement: str, entities: list[dict[str, Any]], claim_value: dict[str, Any], metadata: dict[str, Any], api_token: str) -> str:
    status, payload = api_request(
        base_url,
        "POST",
        "/api/v1/claims",
        {
            "run_id": run_id,
            "claim_type": "assertion",
            "statement": statement,
            "entities": entities,
            "claim_value": claim_value,
            "status": "active",
            "lifecycle_state": "proposed",
            "event_time": datetime.now(timezone.utc).isoformat(),
            "trust_tier": "medium",
            "metadata": metadata,
            "actor_id": ANALYST_ID,
            "actor_type": "adapter",
        },
        api_token=api_token,
    )
    if status != 201:
        raise RuntimeError(f"claim creation failed: {payload}")
    return str(payload["claim_id"])


def attach_evidence(base_url: str, claim_id: str, evidence_id: str, api_token: str, confidence: float = 0.72) -> None:
    status, payload = api_request(
        base_url,
        "POST",
        f"/api/v1/claims/{claim_id}/evidence",
        {
            "evidence_id": evidence_id,
            "confidence": confidence,
            "extraction_method": "metadata",
            "actor_id": ANALYST_ID,
            "actor_type": "adapter",
        },
        api_token=api_token,
    )
    if status != 201:
        raise RuntimeError(f"attach evidence failed: {payload}")


def assess_claim(base_url: str, claim_id: str, api_token: str) -> None:
    status, payload = api_request(
        base_url,
        "POST",
        f"/api/v1/claims/{claim_id}/assess?actor_id={ANALYST_ID}&actor_type=adapter",
        api_token=api_token,
    )
    if status != 200:
        raise RuntimeError(f"claim assess failed: {payload}")


def fetch_json(base_url: str, path: str, api_token: str) -> Any:
    status, payload = api_request(base_url, "GET", path, api_token=api_token)
    if status != 200:
        raise RuntimeError(f"GET {path} failed: {payload}")
    return payload



def build_phone_claims(parsed: dict[str, Any], target: str) -> list[dict[str, Any]]:
    entities_base = [{"role": "subject", "entity_type": "observable", "entity_value": target}]
    claims: list[dict[str, Any]] = []
    if parsed.get("country"):
        claims.append(
            {
                "statement": f"Phone number {target} is associated with country {parsed['country']}",
                "entities": entities_base + [{"role": "location", "entity_type": "location", "entity_value": parsed["country"]}],
                "claim_value": {"country": parsed["country"], "observable_type": "phone"},
                "metadata": {"source_layer": "phone_osint", "parser": "legacy-bridge", "field": "country"},
                "confidence": 0.81,
            }
        )
    if parsed.get("local"):
        claims.append(
            {
                "statement": f"Phone number {target} has local normalized form {parsed['local']}",
                "entities": entities_base + [{"role": "format", "entity_type": "observable", "entity_value": parsed["local"]}],
                "claim_value": {"local": parsed["local"], "observable_type": "phone"},
                "metadata": {"source_layer": "phone_osint", "parser": "legacy-bridge", "field": "local"},
                "confidence": 0.74,
            }
        )
    if parsed.get("international"):
        claims.append(
            {
                "statement": f"Phone number {target} has international normalized form {parsed['international']}",
                "entities": entities_base + [{"role": "format", "entity_type": "observable", "entity_value": parsed["international"]}],
                "claim_value": {"international": parsed["international"], "observable_type": "phone"},
                "metadata": {"source_layer": "phone_osint", "parser": "legacy-bridge", "field": "international"},
                "confidence": 0.74,
            }
        )
    if parsed.get("categories"):
        claims.append(
            {
                "statement": f"Phone number {target} produced multiple open-source search pivots across phone intelligence categories",
                "entities": entities_base,
                "claim_value": {"categories": {key: len(value) for key, value in parsed['categories'].items()}},
                "metadata": {"source_layer": "phone_osint", "parser": "legacy-bridge", "field": "search_surface"},
                "confidence": 0.68,
            }
        )
    return claims


def build_generic_claim(meta: dict[str, Any]) -> dict[str, Any]:
    profile = str(meta.get("profile") or "legacy")
    target = normalize_target_value(profile, str(meta.get("target") or "unknown"))
    profile = str(meta.get("profile") or "legacy")
    status = str(meta.get("status") or "unknown")
    label = strip_ansi(str(meta.get("label") or profile))
    duration = meta.get("duration_sec")
    lines = meta.get("line_count")
    detail_parts = []
    if duration:
        detail_parts.append(f"{duration}s runtime")
    if lines:
        detail_parts.append(f"{lines} lines collected")
    detail = f" ({', '.join(detail_parts)})" if detail_parts else ""
    return {
        "statement": f"{profile_display_name(profile)} scan of '{target}' completed with status '{status}'{detail}",
        "entities": [{"role": "subject", "entity_type": infer_entity_type(profile, target), "entity_value": target}],
        "claim_value": {
            "profile": profile,
            "status": status,
            "exit_code": meta.get("exit_code"),
            "duration_sec": meta.get("duration_sec"),
            "line_count": meta.get("line_count"),
        },
        "metadata": {"source_layer": "legacy_dossier", "parser": "legacy-bridge", "field": "run_status", "label": meta.get("label")},
        "confidence": 0.66 if status == "success" else 0.35,
    }


def build_cross_entity_claims(metas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create claims that link entities across different profile types."""
    phones: list[str] = []
    identities: list[str] = []
    infra: list[str] = []
    for m in metas:
        profile = str(m.get("profile") or "")
        target = normalize_target_value(profile, str(m.get("target") or ""))
        profile = str(m.get("profile") or "")
        if not target or m.get("status") != "success":
            continue
        if profile == "phone" and target not in phones:
            phones.append(target)
        elif profile == "username" and target not in identities:
            identities.append(target)
        elif profile in ("domain", "whatweb", "dnsenum") and target not in infra:
            infra.append(target)

    claims: list[dict[str, Any]] = []
    # Link each phone to each identity
    for phone in phones:
        for identity in identities:
            claims.append({
                "statement": f"Phone {phone} is associated with identity '{identity}' based on co-occurrence in the same OSINT collection session",
                "entities": [
                    {"role": "subject", "entity_type": "observable", "entity_value": phone},
                    {"role": "owner", "entity_type": "identity", "entity_value": identity},
                ],
                "claim_value": {"link_type": "phone-to-identity", "phone": phone, "identity": identity},
                "metadata": {"source_layer": "cross_entity", "parser": "legacy-bridge", "field": "session_link"},
                "confidence": 0.62,
            })
    # Link each identity to each infrastructure target
    for identity in identities:
        for domain in infra:
            claims.append({
                "statement": f"Identity '{identity}' is linked to web resource '{domain}' based on co-occurrence in the same OSINT collection",
                "entities": [
                    {"role": "subject", "entity_type": "identity", "entity_value": identity},
                    {"role": "resource", "entity_type": "infrastructure", "entity_value": domain},
                ],
                "claim_value": {"link_type": "identity-to-infrastructure", "identity": identity, "resource": domain},
                "metadata": {"source_layer": "cross_entity", "parser": "legacy-bridge", "field": "session_link"},
                "confidence": 0.58,
            })
    # Link phones to infrastructure
    for phone in phones:
        for domain in infra:
            claims.append({
                "statement": f"Phone {phone} is linked to web resource '{domain}' via shared OSINT collection context",
                "entities": [
                    {"role": "subject", "entity_type": "observable", "entity_value": phone},
                    {"role": "resource", "entity_type": "infrastructure", "entity_value": domain},
                ],
                "claim_value": {"link_type": "phone-to-infrastructure", "phone": phone, "resource": domain},
                "metadata": {"source_layer": "cross_entity", "parser": "legacy-bridge", "field": "session_link"},
                "confidence": 0.52,
            })
    # Link multiple phones to each other
    for i, phone_a in enumerate(phones):
        for phone_b in phones[i + 1:]:
            claims.append({
                "statement": f"Phone numbers {phone_a} and {phone_b} are associated with the same target entity",
                "entities": [
                    {"role": "subject", "entity_type": "observable", "entity_value": phone_a},
                    {"role": "alias", "entity_type": "observable", "entity_value": phone_b},
                ],
                "claim_value": {"link_type": "phone-to-phone", "phones": [phone_a, phone_b]},
                "metadata": {"source_layer": "cross_entity", "parser": "legacy-bridge", "field": "multi_phone"},
                "confidence": 0.55,
            })
    return claims


def merge_parsed_results(parsed_results: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {"categories": {}, "urls": [], "top_findings": []}
    for parsed in parsed_results:
        for key in ("e164", "local", "international", "country"):
            if parsed.get(key) and not merged.get(key):
                merged[key] = parsed[key]
        for group_name, urls in parsed.get("categories", {}).items():
            merged["categories"].setdefault(group_name, []).extend(urls)
        merged["urls"].extend(parsed.get("urls", []))
        merged["top_findings"].extend(parsed.get("top_findings", []))
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge legacy dossier exports into the control-plane API and render a connected HTML dossier.")
    parser.add_argument("--meta-json", required=True, nargs="+", help="Path(s) to legacy flat metadata JSON export(s).")
    parser.add_argument("--api-base", default="http://127.0.0.1:8700", help="Control-plane API base URL.")
    parser.add_argument("--api-token", default=DEFAULT_API_TOKEN, help="Bearer token for control-plane API access.")
    parser.add_argument("--output-html", help="Output HTML path. Defaults to runs/exports/html/dossiers/connected_<session>.html")
    args = parser.parse_args()

    meta_paths = [Path(item).expanduser().resolve() for item in args.meta_json]
    metas: list[dict[str, Any]] = []
    parsed_results: list[dict[str, Any]] = []
    log_payloads: list[tuple[dict[str, Any], str, dict[str, Any]]] = []
    for meta_path in meta_paths:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not meta.get("log_file"):
            continue
        if meta.get("target"):
            meta["target"] = normalize_target_value(str(meta.get("profile") or ""), str(meta["target"]))
        if meta.get("label"):
            meta["label"] = strip_ansi(str(meta["label"]))
        log_path = Path(meta["log_file"]).expanduser().resolve()
        if not log_path.exists():
            continue
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_phone_log(log_text) if str(meta.get("profile")) == "phone" else {"categories": {}, "urls": [], "top_findings": []}
        meta["_log_excerpt"] = "\n".join(log_text.splitlines()[:120])
        metas.append(meta)
        parsed_results.append(parsed)
        log_payloads.append((meta, log_text, parsed))

    parsed = merge_parsed_results(parsed_results)
    meta_path = meta_paths[0]

    session_id_match = re.search(r"(\d{8}_\d{6})", meta_path.name)
    session_id = session_id_match.group(1) if session_id_match else datetime.now().strftime("%Y%m%d_%H%M%S")
    target = str(parsed.get("e164") or metas[0].get("target") or "unknown")

    health_status, health_payload = api_request(args.api_base, "GET", "/api/v1/health", api_token=args.api_token)
    if health_status != 200:
        raise RuntimeError(f"control-plane API is not reachable: {health_payload}")

    graph_id = ensure_graph(args.api_base, target, args.api_token)
    status, graph_payload = api_request(args.api_base, "GET", f"/api/v1/graphs/{graph_id}", api_token=args.api_token)
    if status != 200:
        raise RuntimeError(f"failed to fetch graph after creation: {graph_payload}")
    processor_node_id = str(graph_payload["graph_json"]["nodes"][1]["id"])

    run_id = create_run(args.api_base, graph_id, target, args.api_token)
    all_evidence_ids: list[str] = []
    evidence_ids_by_target: dict[str, list[str]] = {}
    for meta, log_text, parsed_item in log_payloads:
        post_event(args.api_base, run_id, processor_node_id, args.api_token, f"legacy dossier imported: {meta.get('label', meta.get('profile', 'unknown'))}")
        evidence_id = intake_evidence(args.api_base, run_id, processor_node_id, meta, log_text, args.api_token)
        all_evidence_ids.append(evidence_id)
        target_key = canonical_lookup_value(str(meta.get("target") or ""))
        if target_key:
            evidence_ids_by_target.setdefault(target_key, []).append(evidence_id)

        claims = [build_generic_claim(meta)]
        if str(meta.get("profile")) == "phone":
            claims.extend(build_phone_claims(parsed_item, str(parsed_item.get("e164") or meta.get("target") or target)))

        for claim in claims:
            claim_id = create_claim(args.api_base, run_id, claim["statement"], claim["entities"], claim["claim_value"], claim["metadata"], args.api_token)
            attach_evidence(args.api_base, claim_id, evidence_id, args.api_token, confidence=claim["confidence"])
            assess_claim(args.api_base, claim_id, args.api_token)

    # Cross-entity linking: connect phones, identities, and infrastructure
    cross_claims = build_cross_entity_claims(metas)
    if cross_claims and all_evidence_ids:
        for claim in cross_claims:
            claim_id = create_claim(args.api_base, run_id, claim["statement"], claim["entities"], claim["claim_value"], claim["metadata"], args.api_token)
            for supporting_id in supporting_evidence_ids(claim, evidence_ids_by_target) or all_evidence_ids[:1]:
                attach_evidence(args.api_base, claim_id, supporting_id, args.api_token, confidence=claim["confidence"])
            assess_claim(args.api_base, claim_id, args.api_token)

    dossier = fetch_json(args.api_base, f"/api/v1/runs/{run_id}/dossier", args.api_token)
    timeline = fetch_json(args.api_base, f"/api/v1/fusion/timeline/{run_id}", args.api_token)
    contradictions = fetch_json(args.api_base, f"/api/v1/fusion/contradictions/{run_id}", args.api_token)

    output_path = Path(args.output_html).expanduser().resolve() if args.output_html else meta_path.parent / "html" / "dossiers" / f"connected_{session_id}.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path = output_path.parent / "latest_dossier.html"
    rendered = ReportRenderer.render_connected_dossier(session_id, metas, parsed, dossier, timeline, contradictions)
    output_path.write_text(rendered, encoding="utf-8")
    latest_path.write_text(rendered, encoding="utf-8")

    print(json.dumps({
        "run_id": run_id,
        "graph_id": graph_id,
        "evidence_id": evidence_id,
        "output_html": str(output_path),
        "latest_html": str(latest_path),
        "claims": len(dossier.get("claims", [])),
        "entities": len(dossier.get("entities", [])),
        "relationships": len(dossier.get("relationships", [])),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()