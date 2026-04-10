from __future__ import annotations

import ipaddress
import json
import re
import time
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from config import RUNS_ROOT
from registry import resolve_modules
from runners.aggregate import AggregateRunner


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9\-\s()]{6,20}[0-9]$")
_DOMAIN_RE = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$")
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]{2,40}$")
_HASH_RE = re.compile(r"^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{56}$|^[a-fA-F0-9]{64}$|^[a-fA-F0-9]{128}$")


@dataclass
class Target:
    value: str
    type_hint: Optional[str] = None


@dataclass
class Evidence:
    source: str
    field: str
    value: Any
    layer: str
    confidence: float = 0.8
    score: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Dossier:
    target: Target
    evidences: list[Evidence] = field(default_factory=list)
    layers: list[str] = field(default_factory=list)
    extra_notes: list[str] = field(default_factory=list)


@dataclass
class DossierRun:
    dossier: Dossier
    normalized: dict[str, list[str]]
    links: list[dict[str, str]]
    stats: dict[str, Any]
    exports: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "target": asdict(self.dossier.target),
            "layers": list(self.dossier.layers),
            "extra_notes": list(self.dossier.extra_notes),
            "stats": dict(self.stats),
            "normalized": self.normalized,
            "links": self.links,
            "evidences": [asdict(item) for item in self.dossier.evidences],
            "exports": dict(self.exports),
        }


class DossierEngine:
    """One-shot dossier orchestration with three reconnaissance cycles."""

    def __init__(
        self,
        *,
        proxy: Optional[str] = None,
        leak_dir: Optional[str] = None,
        workers: int = 4,
        runner_factory: Callable[..., Any] = AggregateRunner,
    ):
        self.proxy = proxy
        self.leak_dir = leak_dir
        self.workers = workers
        self.runner_factory = runner_factory

    def classify_target(self, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            return "unknown"

        if _EMAIL_RE.match(candidate):
            return "email"

        if _PHONE_RE.match(candidate):
            digits = re.sub(r"\D", "", candidate)
            if 7 <= len(digits) <= 15:
                return "phone"

        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return "url"

        host = parsed.hostname or candidate
        try:
            ipaddress.ip_address(host)
            return "ip"
        except ValueError:
            pass

        if _HASH_RE.match(candidate):
            return "hash"

        if _DOMAIN_RE.match(candidate.lower()):
            return "domain"

        if " " not in candidate and _USERNAME_RE.match(candidate):
            return "username"

        return "unknown"

    def _split_to_layers(
        self,
        target: Target,
        *,
        surface_modules: Optional[list[str]] = None,
        deep_modules: Optional[list[str]] = None,
        pivot_modules: Optional[list[str]] = None,
    ) -> dict[str, list[str]]:
        surface_presets = {
            "email": ["email-chain", "fast-lane"],
            "phone": ["deep-ua", "deep-ru", "person-deep"],
            "username": ["social-deep", "person-deep"],
            "domain": ["recon-auto-quick", "subdomain-full"],
            "ip": ["infra-deep", "port-scan"],
            "url": ["pd-infra-quick", "infra-deep"],
            "hash": ["fast-lane"],
            "unknown": ["fast-lane"],
        }

        deep_presets = {
            "email": ["person-deep", "social-deep"],
            "phone": ["deep-all", "social-deep"],
            "username": ["person-deep", "milint"],
            "domain": ["infra-deep", "pd-full"],
            "ip": ["infra-deep", "pd-full"],
            "url": ["infra-deep", "pd-full"],
            "hash": ["milint"],
            "unknown": ["person-deep", "infra"],
        }

        target_type = target.type_hint or "unknown"
        surface = resolve_modules(surface_modules or surface_presets.get(target_type, ["fast-lane"]))
        deep = resolve_modules(deep_modules or deep_presets.get(target_type, ["person-deep"]))
        pivot = resolve_modules(pivot_modules or ["recon-auto-quick", "social-deep"])

        return {
            "surface": list(dict.fromkeys(surface)),
            "deep": list(dict.fromkeys(deep)),
            "pivot": list(dict.fromkeys(pivot)),
        }

    def _run_cycle(
        self,
        target: Target,
        *,
        cycle_name: str,
        modules: list[str],
        known_phones: Optional[list[str]] = None,
        known_usernames: Optional[list[str]] = None,
    ) -> tuple[list[Evidence], dict[str, Any]]:
        runner = self.runner_factory(proxy=self.proxy, leak_dir=self.leak_dir, max_workers=self.workers)
        result = runner.run(
            target_name=target.value,
            known_phones=known_phones or [],
            known_usernames=known_usernames or [],
            modules=modules,
        )

        evidences: list[Evidence] = []
        for outcome in result.outcomes:
            if outcome.error:
                evidences.append(Evidence(
                    source=f"hanna::{outcome.module_name}",
                    field="error",
                    value=outcome.error,
                    layer=cycle_name,
                    confidence=0.2,
                    score=0.0,
                    details={"error_kind": outcome.error_kind},
                ))
                continue
            for hit in outcome.hits:
                evidences.append(Evidence(
                    source=f"hanna::{outcome.module_name}",
                    field=hit.observable_type,
                    value=hit.value,
                    layer=cycle_name,
                    confidence=float(hit.confidence),
                    score=float(max(0.0, min(1.0, hit.confidence))),
                    details={
                        "source_detail": hit.source_detail,
                        "cross_refs": list(hit.cross_refs),
                        "timestamp": hit.timestamp,
                    },
                ))

        stats = {
            "cycle": cycle_name,
            "modules": list(modules),
            "modules_run": list(result.modules_run),
            "ok": int(result.success_count),
            "errors": int(result.error_count),
            "hits": int(result.total_hits),
            "runtime": result.runtime_summary(),
        }
        return evidences, stats

    def normalize_evidences(self, evidences: list[Evidence]) -> dict[str, list[str]]:
        normalized = {
            "emails": [],
            "phones": [],
            "domains": [],
            "urls": [],
            "ips": [],
            "hashes": [],
            "usernames": [],
            "social_profiles": [],
            "other": [],
        }

        for evidence in evidences:
            if evidence.field == "error" or evidence.value is None:
                continue
            value = str(evidence.value).strip()
            if not value:
                continue
            lowered = value.lower()

            if _EMAIL_RE.match(lowered):
                normalized["emails"].append(lowered)
            elif _PHONE_RE.match(value):
                normalized["phones"].append(re.sub(r"\s+", "", value))
            elif lowered.startswith(("http://", "https://")):
                normalized["urls"].append(value)
                if any(token in lowered for token in ["profile", "user", "@"]):
                    normalized["social_profiles"].append(value)
            else:
                host = value
                if lowered.startswith(("http://", "https://")):
                    host = (urlparse(value).hostname or "").lower()

                added = False
                try:
                    ipaddress.ip_address(host)
                    normalized["ips"].append(host)
                    added = True
                except ValueError:
                    pass

                if not added and _DOMAIN_RE.match(host):
                    normalized["domains"].append(host)
                    added = True

                if not added and _HASH_RE.match(value):
                    normalized["hashes"].append(value.lower())
                    added = True

                if not added and _USERNAME_RE.match(value):
                    normalized["usernames"].append(value)
                    added = True

                if not added:
                    normalized["other"].append(value)

        for key, values in normalized.items():
            normalized[key] = sorted(list(dict.fromkeys(values)))

        return normalized

    def _build_links(self, evidences: list[Evidence]) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        seen: set[tuple[str, str, str, str]] = set()

        for evidence in evidences:
            source = str(evidence.value).strip()
            if not source:
                continue
            refs = evidence.details.get("cross_refs", []) if isinstance(evidence.details, dict) else []
            for ref in refs:
                target = str(ref).strip()
                if not target:
                    continue
                key = (source, target, evidence.layer, evidence.source)
                if key in seen:
                    continue
                seen.add(key)
                links.append({
                    "from": source,
                    "to": target,
                    "type": "cross_ref",
                    "layer": evidence.layer,
                    "source": evidence.source,
                })
        return links

    def _render_text(self, run: DossierRun) -> str:
        lines = [
            "ONE-SHOT DOSSIER",
            f"Target: {run.dossier.target.value}",
            f"Classified as: {run.dossier.target.type_hint}",
            f"Layers: {', '.join(run.dossier.layers)}",
            f"Evidence count: {len(run.dossier.evidences)}",
            "",
            "Normalized entities:",
        ]
        for key, values in run.normalized.items():
            if not values:
                continue
            lines.append(f"- {key} ({len(values)})")
            for item in values[:10]:
                lines.append(f"  - {item}")
            if len(values) > 10:
                lines.append(f"  - ... and {len(values) - 10} more")

        if run.links:
            lines.append("")
            lines.append("Links:")
            for link in run.links[:25]:
                lines.append(f"- [{link['layer']}] {link['from']} -> {link['to']} ({link['source']})")
            if len(run.links) > 25:
                lines.append(f"- ... and {len(run.links) - 25} more")

        return "\n".join(lines) + "\n"

    def _render_html(self, run: DossierRun) -> str:
        cards = []
        for key, values in run.normalized.items():
            if not values:
                continue
            items = "".join(f"<li>{v}</li>" for v in values[:25])
            cards.append(
                "<section class='card'>"
                f"<h3>{key} ({len(values)})</h3>"
                f"<ul>{items}</ul>"
                "</section>"
            )

        link_rows = []
        for link in run.links[:40]:
            link_rows.append(
                f"<tr><td>{link['layer']}</td><td>{link['from']}</td><td>{link['to']}</td><td>{link['source']}</td></tr>"
            )

        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>HANNA One-Shot Dossier</title>"
            "<style>"
            ":root{--bg:#f4efe7;--ink:#1d1c1a;--muted:#6b665e;--card:#fffaf1;--accent:#b1462f;}"
            "body{font-family:ui-monospace,Menlo,monospace;background:radial-gradient(circle at 10% 20%,#fff8e8,#f4efe7);color:var(--ink);margin:0;padding:24px;}"
            "h1{margin:0 0 8px 0;font-size:28px;letter-spacing:.2px;}"
            ".meta{color:var(--muted);margin-bottom:20px;}"
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;}"
            ".card{background:var(--card);border:1px solid #e8dccb;border-radius:14px;padding:12px 14px;box-shadow:0 8px 24px rgba(20,15,8,.05);}" 
            "h3{margin:0 0 8px 0;color:var(--accent)}ul{margin:0;padding-left:18px;}"
            "table{width:100%;border-collapse:collapse;margin-top:18px;background:var(--card);border-radius:12px;overflow:hidden;}"
            "th,td{padding:8px 10px;border-bottom:1px solid #eee1d0;text-align:left;font-size:13px;}"
            "th{background:#f0e4d3;}"
            "@media (max-width: 720px){body{padding:14px;}h1{font-size:22px;}}"
            "</style></head><body>"
            f"<h1>ONE-SHOT Dossier</h1><div class='meta'>Target: {run.dossier.target.value} | Type: {run.dossier.target.type_hint}</div>"
            f"<div class='grid'>{''.join(cards)}</div>"
            "<h2>Evidence Links</h2>"
            "<table><thead><tr><th>Layer</th><th>From</th><th>To</th><th>Source</th></tr></thead>"
            f"<tbody>{''.join(link_rows) or '<tr><td colspan=4>No links</td></tr>'}</tbody></table>"
            "</body></html>"
        )

    def _render_stix(self, run: DossierRun) -> dict[str, Any]:
        created = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        objects: list[dict[str, Any]] = [
            {
                "type": "identity",
                "spec_version": "2.1",
                "id": "identity--00000000-0000-4000-8000-000000000001",
                "created": created,
                "modified": created,
                "name": run.dossier.target.value,
                "identity_class": "individual" if run.dossier.target.type_hint in {"email", "phone", "username"} else "organization",
            }
        ]

        idx = 2
        for evidence in run.dossier.evidences:
            if evidence.field == "error" or evidence.value is None:
                continue
            value = str(evidence.value)
            escaped_value = value.replace("'", "\\'")
            indicator = {
                "type": "indicator",
                "spec_version": "2.1",
                "id": f"indicator--00000000-0000-4000-8000-{idx:012d}",
                "created": created,
                "modified": created,
                "name": f"{evidence.field}:{value}",
                "pattern_type": "stix",
                "pattern": f"[x-hanna:value = '{escaped_value}']",
                "valid_from": created,
                "confidence": int(max(0, min(100, round(evidence.confidence * 100)))),
            }
            objects.append(indicator)
            idx += 1

        return {
            "type": "bundle",
            "id": "bundle--00000000-0000-4000-8000-000000000001",
            "objects": objects,
        }

    def _write_exports(self, run: DossierRun, export_formats: list[str], export_dir: Optional[str]) -> dict[str, str]:
        if not export_formats:
            return {}

        target_dir = Path(export_dir) if export_dir else (RUNS_ROOT / "exports" / "dossiers")
        target_dir.mkdir(parents=True, exist_ok=True)
        timestamp = str(int(time.time()))
        slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", run.dossier.target.value.strip())[:48] or "target"
        base = target_dir / f"dossier_{slug}_{timestamp}"

        outputs: dict[str, str] = {}
        requested = set(export_formats)
        artifact_formats = set(requested)
        artifact_formats.discard("zip")
        if "zip" in requested and not artifact_formats:
            artifact_formats.update({"text", "json"})

        if "text" in artifact_formats:
            text_path = base.with_suffix(".txt")
            text_path.write_text(self._render_text(run), encoding="utf-8")
            outputs["text"] = str(text_path)

        if "json" in artifact_formats:
            json_path = base.with_suffix(".json")
            json_path.write_text(json.dumps(run.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            outputs["json"] = str(json_path)

        if "html" in artifact_formats:
            html_path = base.with_suffix(".html")
            html_path.write_text(self._render_html(run), encoding="utf-8")
            outputs["html"] = str(html_path)

        if "stix" in artifact_formats:
            stix_path = base.with_suffix(".stix.json")
            stix_path.write_text(json.dumps(self._render_stix(run), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            outputs["stix"] = str(stix_path)

        if "zip" in requested:
            zip_path = base.with_suffix(".zip")
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for path in outputs.values():
                    file_path = Path(path)
                    if file_path.exists():
                        zf.write(file_path, arcname=file_path.name)
            outputs["zip"] = str(zip_path)

        return outputs

    def run_one_shot(
        self,
        input_str: str,
        *,
        type_hint: Optional[str] = None,
        surface_modules: Optional[list[str]] = None,
        deep_modules: Optional[list[str]] = None,
        pivot_modules: Optional[list[str]] = None,
        export_formats: Optional[list[str]] = None,
        export_dir: Optional[str] = None,
        interactive_export: bool = False,
    ) -> DossierRun:
        inferred_type = type_hint or self.classify_target(input_str)
        target = Target(value=input_str, type_hint=inferred_type)
        layers = self._split_to_layers(
            target,
            surface_modules=surface_modules,
            deep_modules=deep_modules,
            pivot_modules=pivot_modules,
        )

        cycle_stats: list[dict[str, Any]] = []
        all_evidences: list[Evidence] = []
        known_phones: list[str] = []
        known_usernames: list[str] = []

        for cycle_name in ["surface", "deep", "pivot"]:
            evidences, stats = self._run_cycle(
                target,
                cycle_name=cycle_name,
                modules=layers[cycle_name],
                known_phones=known_phones,
                known_usernames=known_usernames,
            )
            cycle_stats.append(stats)
            all_evidences.extend(evidences)

            normalized = self.normalize_evidences(all_evidences)
            known_phones = normalized["phones"]
            known_usernames = normalized["usernames"]

        normalized = self.normalize_evidences(all_evidences)
        links = self._build_links(all_evidences)

        dossier = Dossier(
            target=target,
            evidences=all_evidences,
            layers=["surface", "deep", "pivot"],
            extra_notes=[
                "Generated by ONE-SHOT Dossier engine (surface/deep/pivot).",
                "Evidence values are adapter-derived and can include low-confidence noise.",
            ],
        )
        run = DossierRun(
            dossier=dossier,
            normalized=normalized,
            links=links,
            stats={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "cycles": cycle_stats,
                "total_evidences": len(all_evidences),
            },
        )

        chosen_formats = list(export_formats or [])
        if interactive_export and not chosen_formats:
            print("Choose export formats: text,json,stix,zip,html")
            print("Press Enter for default: text,json")
            raw = input("Formats: ").strip()
            chosen_formats = [item.strip().lower() for item in raw.split(",") if item.strip()] if raw else ["text", "json"]

        run.exports = self._write_exports(run, chosen_formats, export_dir)
        return run
