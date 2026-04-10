from __future__ import annotations
import html
import re
import urllib.parse
from datetime import datetime
from typing import Any, Union, Optional, List, Dict, Set, Tuple

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

def strip_ansi(text: str) -> str:
    """Removes ANSI escape sequences from strings."""
    return _ANSI_RE.sub('', text)

def slug(value: str) -> str:
    """Creates a URL-friendly slug from a string."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower() or "legacy"

def decode_search_pivot(url: str) -> str:
    """Extracts the 'q' parameter from a search URL."""
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
    return urllib.parse.unquote_plus(query).strip() or url

def profile_display_name(profile: str) -> str:
    """Returns a human-readable name for a tool profile."""
    names = {
        "phone": "Phone Intelligence",
        "email": "Email Intelligence",
        "username": "Username Intelligence",
        "domain": "Domain Intelligence",
        "dnsenum": "DNS Enumeration",
        "whatweb": "Web Fingerprint",
        "ip": "IP Intelligence",
    }
    return names.get(profile, profile.replace("_", " ").title())

class ReportRenderer:
    """Service dedicated to rendering analytical reports and dossiers."""

    @staticmethod
    def render_connected_dossier(
        session_id: str,
        metas: List[Dict[str, Any]],
        parsed: Dict[str, Any],
        dossier: Dict[str, Any],
        timeline: Dict[str, Any],
        contradictions: Dict[str, Any]
    ) -> str:
        """Renders the HTML Dossier for a fused intelligence session."""
        meta = metas[0] if metas else {}
        entities = dossier.get("entities", [])
        relationships = dossier.get("relationships", [])
        claims = dossier.get("claims", [])
        timeline_items = timeline.get("items", [])
        contradiction_items = contradictions.get("items", [])

        # -- Build executive summary --
        unique_targets: Dict[str, Set[str]] = {}
        profile_stats: Dict[str, Dict[str, int]] = {}
        for m in metas:
            profile = str(m.get("profile") or "unknown")
            target = strip_ansi(str(m.get("target") or ""))
            status = str(m.get("status") or "unknown")
            unique_targets.setdefault(profile, set()).add(target)
            stats = profile_stats.setdefault(profile, {"success": 0, "failed": 0})
            if status == "success":
                stats["success"] += 1
            else:
                stats["failed"] += 1

        phones = sorted(unique_targets.get("phone", set()))
        usernames = sorted(unique_targets.get("username", set()))
        domains = sorted(unique_targets.get("domain", set()) | unique_targets.get("whatweb", set()) | unique_targets.get("dnsenum", set()))

        summary_lines: List[str] = []
        if phones:
            summary_lines.append(f"<strong>Phone numbers investigated:</strong> {', '.join(html.escape(p) for p in phones)}")
        if usernames:
            summary_lines.append(f"<strong>Identities / usernames:</strong> {', '.join(html.escape(u) for u in usernames)}")
        if domains:
            summary_lines.append(f"<strong>Web infrastructure:</strong> {', '.join(html.escape(d) for d in domains)}")
        
        if phones and usernames:
            summary_lines.append("Co-occurrence link: phone(s) and username(s) were collected in the same OSINT session, suggesting they belong to the same individual.")
        
        if usernames and domains:
            summary_lines.append("Identity-to-infrastructure link: the website/domain results are likely associated with the username target(s).")
        
        if parsed.get("country"):
            summary_lines.append(f"<strong>Phone country:</strong> {html.escape(parsed['country'])}")
        
        if parsed.get("e164"):
            summary_lines.append(f"<strong>E.164 format:</strong> <code>{html.escape(parsed['e164'])}</code>")

        # Source coverage
        coverage_lines: List[str] = []
        for profile, stats in sorted(profile_stats.items()):
            total = stats["success"] + stats["failed"]
            coverage_lines.append(f"<span class='badge badge-{profile}'>{html.escape(profile)}: {stats['success']}/{total} OK</span>")

        # -- Separate link claims from collection claims --
        link_claims: List[Dict[str, Any]] = []
        intel_claims: List[Dict[str, Any]] = []
        collection_claims: List[Dict[str, Any]] = []
        for c in claims:
            stmt = strip_ansi(c.get("statement") or "")
            if "collected legacy evidence" in stmt:
                collection_claims.append(c)
            elif any(kw in stmt for kw in ("associated with", "is linked to", "Phone numbers")):
                link_claims.append(c)
            else:
                intel_claims.append(c)

        # -- Group entities by type --
        entities_by_type: Dict[str, List[Dict[str, Any]]] = {}
        for e in entities:
            etype = e.get("entity_type") or "unknown"
            entities_by_type.setdefault(etype, []).append(e)

        entity_labels = {
            "observable": "Observables (phones, IDs)",
            "identity": "Identities (persons, usernames)",
            "infrastructure": "Infrastructure (domains, websites)",
            "location": "Locations"
        }

        entity_sections_html = ""
        for etype in ("observable", "identity", "infrastructure", "location"):
            group = entities_by_type.get(etype, [])
            if not group:
                continue
            row_parts = []
            for item in group:
                disp = html.escape(strip_ansi(item.get('display_name') or item.get('canonical_value') or ''))
                conf = item.get('confidence_score', 0)
                tier = item.get('trust_tier') or 'unknown'
                tier_display = html.escape(item.get('trust_tier') or 'n/a')
                row_parts.append(f"<tr><td>{disp}</td><td>{conf:.2f}</td><td><span class='trust-{html.escape(tier)}'>{tier_display}</span></td></tr>")
            
            label = entity_labels.get(etype, etype.title())
            entity_sections_html += (
                f"<h3 class='etype-header'>{html.escape(label)} ({len(group)})</h3>"
                f"<table><tr><th>Value</th><th>Confidence</th><th>Trust</th></tr>{''.join(row_parts)}</table>"
            )
        
        if not entity_sections_html:
            entity_sections_html = "<p>No entities detected.</p>"

        relationship_rows = "".join(
            f"<tr><td>{html.escape(strip_ansi(item.get('source_display_name') or item.get('source_entity_id') or ''))}</td><td class='rel-type'>{html.escape(item.get('relationship_type') or '')}</td><td>{html.escape(strip_ansi(item.get('target_display_name') or item.get('target_entity_id') or ''))}</td><td>{item.get('confidence_score', 0):.2f}</td></tr>"
            for item in relationships
        ) or "<tr><td colspan='4'>No relationships</td></tr>"

        link_rows = "".join(
            f"<tr><td>{html.escape(strip_ansi(item.get('statement') or ''))}</td><td>{item.get('confidence_score', 0):.2f}</td><td><span class='status-{html.escape(item.get('status', 'unknown'))}'>{html.escape(item.get('status', 'unknown'))}</span></td></tr>"
            for item in link_claims
        ) or "<tr><td colspan='3'>No cross-entity links</td></tr>"

        intel_rows = "".join(
            f"<tr><td>{html.escape(strip_ansi(item.get('statement') or ''))}</td><td>{html.escape(item.get('status') or '')}</td><td>{item.get('confidence_score', 0):.2f}</td></tr>"
            for item in intel_claims
        ) or "<tr><td colspan='3'>No intelligence claims</td></tr>"

        timeline_rows = "".join(
            f"<tr><td class='mono'>{html.escape(item.get('timeline_time', '')[:19])}</td><td>{html.escape(strip_ansi(item.get('statement', '')))}</td><td>{item.get('confidence_score', 0):.2f}</td></tr>"
            for item in timeline_items
        ) or "<tr><td colspan='3'>No timeline items</td></tr>"

        contradiction_rows = "".join(
            f"<tr><td>{html.escape(strip_ansi(item.get('claim_statement', '')))}</td><td>{html.escape(strip_ansi(item.get('conflicting_claim_statement', '')))}</td><td>{html.escape(item.get('conflict_type', ''))}</td></tr>"
            for item in contradiction_items
        ) or "<tr><td colspan='3'>No contradictions detected</td></tr>"

        url_groups = []
        for group_name, urls in parsed.get("categories", {}).items():
            if not urls:
                continue
            items = ""
            for url in urls[:12]:
                query_text = decode_search_pivot(url)
                if "google.com/search" in url:
                    items += f"<li><strong>Pivot</strong>: <span class='mono'>{html.escape(query_text)}</span> <span class='hint'>(search pivot, not evidence)</span></li>"
                else:
                    items += f"<li><a href='{html.escape(url)}'>{html.escape(url)}</a></li>"
            url_groups.append(f"<details><summary>{html.escape(group_name)} ({len(urls)})</summary><ul>{items}</ul></details>")
        
        collection_summary_rows = "".join(
            f"<tr><td>{html.escape(strip_ansi(item.get('statement', '')))}</td><td>{html.escape(item.get('status', ''))}</td></tr>"
            for item in collection_claims
        )

        finding_items = "".join(f"<li>{html.escape(item)}</li>" for item in parsed.get("top_findings", [])[:10]) or "<li>No parsed findings</li>"

        # -- Final Assembly --
        return f"""<!doctype html>
<html lang='uk'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>OSINT Dossier — {html.escape(session_id)}</title>
  <style>
    :root {{ --bg: #f3f5f4; --card: #fff; --border: #d6ddd8; --accent: #1f6d5b; --accent2: #112b45; --text: #17212b; --muted: #5c6e64; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: 'Segoe UI', 'Noto Sans', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.55; }}
    .wrap {{ max-width: 1300px; margin: 0 auto; padding: 24px 20px 60px; }}
    .hero {{ background: linear-gradient(135deg, var(--accent2), var(--accent) 70%, #99622d); color: #fff; border-radius: 18px; padding: 28px 24px; }}
    .hero h1 {{ margin: 0; font-size: 26px; letter-spacing: .5px; }}
    .hero-sub {{ opacity: .85; margin: 6px 0 0; font-size: 14px; }}
    .hero-meta {{ text-align: right; font-size: 13px; opacity: .85; }}
    .hero-grid {{ display: grid; grid-template-columns: 1.4fr .6fr; gap: 18px; align-items: start; }}
    .cards {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-top: 18px; }}
    .card {{ background: rgba(255,255,255,.13); border: 1px solid rgba(255,255,255,.18); border-radius: 12px; padding: 12px; text-align: center; }}
    .card .k {{ font-size: 11px; text-transform: uppercase; opacity: .75; }}
    .card .v {{ font-size: 28px; font-weight: 800; margin-top: 2px; }}
    .section {{ background: var(--card); border: 1px solid var(--border); border-radius: 14px; margin-top: 16px; overflow: hidden; }}
    .section h2 {{ margin: 0; padding: 13px 16px; background: #ecf3ef; border-bottom: 1px solid var(--border); font-size: 14px; text-transform: uppercase; letter-spacing:.4px; color: var(--accent2); }}
    .pad {{ padding: 16px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 7px 10px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }}
    th {{ background: #f4f7f5; font-weight: 600; font-size: 12px; text-transform: uppercase; color: var(--muted); }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; word-break: break-all; }}
    code {{ background: #e8ecea; padding: 2px 5px; border-radius: 4px; font-size: 12px; }}
    details {{ margin-bottom: 8px; }}
    summary {{ cursor: pointer; font-weight: 600; padding: 4px 0; }}
    pre {{ white-space: pre-wrap; background: #161b18; color: #d5e1da; padding: 14px; border-radius: 10px; overflow: auto; font-size: 12px; }}
    a {{ color: var(--accent); }}
    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 8px; font-size: 12px; font-weight: 600; margin: 2px 4px 2px 0; background: #e0ede7; color: var(--accent2); }}
    .badge-phone {{ background: #dde8f7; }}
    .badge-username {{ background: #f0e6fa; }}
    .badge-domain, .badge-whatweb, .badge-dnsenum {{ background: #fce6d5; }}
    .exec-summary {{ font-size: 14px; line-height: 1.65; }}
    .exec-summary p {{ margin: 6px 0; }}
    .hint {{ color: var(--muted); font-size: 12px; }}
    .etype-header {{ margin: 18px 0 6px; font-size: 13px; text-transform: uppercase; color: var(--accent); border-bottom: 2px solid var(--accent); padding-bottom: 4px; }}
    .kv {{ display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; font-size: 14px; }}
    .kv dt {{ font-weight: 600; color: var(--muted); }}
    .kv dd {{ margin: 0; }}
    @media (max-width: 980px) {{ .hero-grid, .cards, .split, .tri {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class='wrap'>
    <div class='hero'>
      <div class='hero-grid'>
        <div>
          <h1>OSINT INTELLIGENCE DOSSIER</h1>
          <p class='hero-sub'>Multi-source intelligence report — legacy collection data fused through claim/entity pipeline.</p>
        </div>
        <div class='hero-meta'>Generated: {html.escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}<br>Session: {html.escape(session_id)}</div>
      </div>
      <div class='cards'>
        <div class='card'><div class='k'>Sources</div><div class='v'>{len(metas)}</div></div>
        <div class='card'><div class='k'>Entities</div><div class='v'>{len(entities)}</div></div>
        <div class='card'><div class='k'>Links</div><div class='v'>{len(link_claims) + len(relationships)}</div></div>
        <div class='card'><div class='k'>Intel Claims</div><div class='v'>{len(intel_claims)}</div></div>
        <div class='card'><div class='k'>Contradictions</div><div class='v'>{len(contradiction_items)}</div></div>
      </div>
    </div>

    <section class='section'><h2>📋 Executive Summary / Аналітичне зведення</h2><div class='pad exec-summary'>
      {"".join(f"<p>{line}</p>" for line in summary_lines)}
      <p style='margin-top:12px;'><strong>Source coverage:</strong> {"  ".join(coverage_lines)}</p>
    </div></section>

    <section class='section'><h2>🔗 Cross-entity Link Analysis</h2><div class='pad'>
      <table><tr><th>Link Statement</th><th>Confidence</th><th>Status</th></tr>{link_rows}</table>
    </div></section>

    <section class='section'><h2>🎯 Entity Inventory</h2><div class='pad'>{entity_sections_html}</div></section>

    <section class='section'><h2>↔ Semantic Relationships</h2><div class='pad'>
      <table><tr><th>Source</th><th>Relation</th><th>Target</th><th>Confidence</th></tr>{relationship_rows}</table>
    </div></section>

    <section class='section'><h2>🔎 Search Pivots</h2><div class='pad'>{"".join(url_groups) or "<p>No URL groups parsed.</p>"}</div></section>

    <section class='section'><h2>📞 Phone Intelligence</h2><div class='pad'>
        <dl class='kv'>
          <dt>E.164</dt><dd><code>{html.escape(parsed.get('e164', 'n/a'))}</code></dd>
          <dt>Country</dt><dd>{html.escape(parsed.get('country', 'n/a'))}</dd>
        </dl>
        <ul style='margin-top:10px;'>{finding_items}</ul>
    </div></section>

    <section class='section'><h2>📂 Collection Log</h2><div class='pad'>
      <details><summary class='hint'>Show {len(collection_claims)} entries</summary>
        <table><tr><th>Statement</th><th>Status</th></tr>{collection_summary_rows}</table>
      </details>
    </div></section>
  </div>
</body>
</html>"""
