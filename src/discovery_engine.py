"""
discovery_engine.py — Recursive Discovery Orchestrator
=====================================================

Middleware between raw OSINT tool outputs and the claim/entity pipeline.
Implements:
  1. Input Validation Layer   — rejects garbage targets, artifact hashes, profile→target mismatches
  2. Observable Extractor     — regex-extracts phones, emails, usernames, domains, URLs from tool logs
  3. Entity Resolution        — multi-source corroboration + session-level linking (NOT day-level)
  4. Discovery Queue (SQLite) — tracks discovered observables and auto-pivot tasks
  5. Verification Layer       — HTTP HEAD check for profile URLs, tiered confidence

v2.0 — Verification-First Architecture
  - NO day-level co-occurrence (was linking unrelated targets from same calendar day)
  - NO default-to-username for unknown strings (was treating SHA hashes as usernames)
  - NO 100% confidence from quantity (was rewarding garbage volume)
  - Multi-source corroboration required for Confirmed tier
  - Profile URL verification via HTTP HEAD (opt-in)
  - Tiered display: Confirmed / Probable / Unverified

Usage:
    engine = DiscoveryEngine(db_path="discovery.db")
    # Ingest all legacy metadata exports
    for meta_path in metadata_json_paths:
        engine.ingest_metadata(meta_path)
    # Resolve entities into identity clusters
    engine.resolve_entities()
    engine.verify_profiles()  # optional, hits network
    html = engine.render_graph_report()
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import logging
import math
import os
import re

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from models.observables import Observable, IdentityCluster, TIER_CONFIRMED, TIER_PROBABLE, TIER_UNVERIFIED
from discovery_repository import DiscoveryRepository
from pipelines.resolution import EntityResolutionPipeline
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union, List, Dict, Tuple
from typing import Any, Union, Optional, List, Dict, Tuple
from urllib.parse import unquote, urlparse

from config import (
    DEFAULT_DB_PATH,
    MAX_BODY_BYTES,
    MAX_DISCOVERY_DEPTH,
    MAX_PROFILE_URLS,
    RUNS_ROOT,
    SCHEMA_VERSION,
    VERIFY_WORKERS,
)
from net import proxy_aware_request
from observable_extractor import ObservableExtractor
from profile_verifier import ProfileVerifier
from report_renderer import ReportRenderer

log = logging.getLogger("hanna.discovery")

# ── Constants ──────────────────────────────────────────────────────

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_PHONE_RE = re.compile(r"\+?\d[\d\-\s]{7,15}\d")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}")
_DOMAIN_RE = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"(?:com|net|org|io|info|ua|de|ru|uk|co|me|tv|xyz|pro|biz|int)\b"
)
_USERNAME_URL_RE = re.compile(
    r"https?://(?:www\.)?"
    r"(?:facebook|instagram|twitter|x|linkedin|github|tiktok|vk|telegram"
    r"|pinterest|reddit|youtube|twitch|snapchat|medium|behance"
    r"|dribbble|flickr|tumblr|soundcloud|spotify|patreon"
    r"|duolingo|kaggle|roblox|opensea)"
    r"\.(?:com|io|tv|gg|me)/(?:@)?([a-zA-Z0-9_.]{2,40})"
)
_SHERLOCK_HIT_RE = re.compile(r"^\[\+\]\s+\S+:\s+(https?://\S+)", re.MULTILINE)
_MAIGRET_HIT_RE = re.compile(r"^\[\+\]\s+\S+.*?:\s+(https?://\S+)", re.MULTILINE)

# Garbage filters — targets matching these are rejected
_GARBAGE_PATTERNS = [
    re.compile(r"Ignored\s+invalid", re.IGNORECASE),
    re.compile(r"^\[FTL\]"),
    re.compile(r"^ERROR\s"),
    re.compile(r"missing.*flag\s+required", re.IGNORECASE),
    re.compile(r"^Unable\s+to\s+parse"),
    re.compile(r"^\s*$"),  # blank
]

MAX_DISCOVERY_DEPTH = MAX_DISCOVERY_DEPTH  # re-exported from config

# ── Phase 1 Constants: Anti-false-positive filters ──────────────

# Placeholder/noise domains — never register as observables
_PLACEHOLDER_DOMAINS = frozenset({
    "example.com", "example.org", "example.net", "test.com",
    "localhost", "invalid", "local",
})

# Username: alphanumeric + limited special chars, 2-40 chars
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.@\- ]{2,40}$")

# Hex-only strings ≥16 chars — SHA/MD5 hashes, NOT usernames
_HEX_ONLY_RE = re.compile(r"^[a-fA-F0-9]{16,}$")

# Entropy threshold: SHA256 ~ 4.0 bits/char; real usernames < 3.5
_ENTROPY_THRESHOLD = 3.8

# ucoz-family domains for platform deduplication
_UCOZ_DOMAINS = frozenset({
    "ucoz.ru", "ucoz.ua", "ucoz.com", "ucoz.net", "ucoz.org",
    "at.ua", "my1.ru", "3dn.ru", "clan.su", "do.am",
    "org.ua", "pp.ua", "net.ua",
})

# Platforms that return HTTP 200 for ANY username — false-positive factories
_FALSE_POSITIVE_PLATFORMS = frozenset({
    "3ddd", "cs-strikez", "duolingo", "kaskus", "listography",
    "livemaster", "mercadolivre", "ucoz", "wordnik",
    "1001mem", "memrise", "colourlovers", "reverbnation",
    "reddit",
})

_REDACTION_MODES = frozenset({"internal", "shareable", "strict"})

# Verification tier constants
TIER_CONFIRMED = "confirmed"     # Multi-source corroboration OR original target
TIER_PROBABLE = "probable"       # Single source, plausible context
TIER_UNVERIFIED = "unverified"   # Single source, no corroboration


def _shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy in bits per character."""
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s.lower():
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _normalize_phone(raw: str) -> Optional[str]:
    digits = re.sub(r"[\s\-\(\)]", "", raw)
    if not re.fullmatch(r"\+?\d{7,15}", digits):
        return None
    if not digits.startswith("+") and len(digits) >= 10:
        digits = "+" + digits
    return digits


def _normalize_domain(raw: str) -> Optional[str]:
    d = raw.lower().strip().rstrip(".")
    if len(d) < 4 or "." not in d:
        return None
    # reject IPs
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", d):
        return None
    return d


def _is_garbage_target(value: str) -> bool:
    cleaned = strip_ansi(value).strip()
    if not cleaned or len(cleaned) < 2:
        return True
    for pat in _GARBAGE_PATTERNS:
        if pat.search(cleaned):
            return True
    return False


# ── Data classes ───────────────────────────────────────────────────




# ── Discovery Engine ──────────────────────────────────────────────

class DiscoveryEngine:
    """
    Recursive discovery orchestrator.

    Workflow:
      1. ingest_metadata()  — load legacy JSON exports, validate, extract observables
      2. resolve_entities() — cluster observables into identity anchors
      3. get_pivot_queue()  — return observables discovered but not yet pivoted
      4. render_graph_report() — generate person-centric HTML dossier
    """

    def __init__(self, db_path: str = ":memory:"):
        self.repo = DiscoveryRepository(db_path)
        self.db = self.repo
        self.clusters: list[IdentityCluster] = []
        self._all_observables: list[Observable] = []
        self._obs_by_value: dict[str, Observable] = {}  # fingerprint -> Observable (dedup + corroboration)
        self._metas: list[dict[str, Any]] = []
        self._tool_stats: dict[str, dict[str, int]] = {}  # tool -> {success, failed, observables}
        self._confirmed_imports: list[dict[str, Any]] = []
        self.extractor = ObservableExtractor({
            "extract_observables": self._extract_observables,
            "classify_and_register": self._classify_and_register,
            "infer_type": self._infer_type,
            "normalize": self._normalize,
            "extract_from_phone_log": self._extract_from_phone_log,
            "extract_from_username_log": self._extract_from_username_log,
            "extract_from_domain_log": self._extract_from_domain_log,
            "extract_generic": self._extract_generic,
            "platform_from_url": self._platform_from_url,
        })
        self.verifier = ProfileVerifier(self, false_positive_platforms=_FALSE_POSITIVE_PLATFORMS)
        self.renderer = ReportRenderer(
            self,
            placeholder_domains=_PLACEHOLDER_DOMAINS,
            redaction_modes=_REDACTION_MODES,
            strip_ansi=strip_ansi,
        )

    def _record_rejected_target(self, source_file: str, raw_target: str, reason: str) -> None:
        self.repo.record_rejected_target(source_file, raw_target, reason)

    # ── 1.  Input Validation + Ingestion ──────────────────────────

    def ingest_metadata(self, meta_path: Union[str, Path]) -> Dict[str, Any]:
        """Load a single legacy metadata JSON, validate, extract observables."""
        meta_path = Path(meta_path)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        raw_target = strip_ansi(str(meta.get("target") or ""))
        profile = str(meta.get("profile") or "unknown")
        status = str(meta.get("status") or "unknown")
        log_file = meta.get("log_file", "")
        file_sha256 = meta.get("sha256", "")

        # Update tool stats
        stats = self._tool_stats.setdefault(profile, {"success": 0, "failed": 0, "observables": 0})
        if status == "success":
            stats["success"] += 1
        else:
            stats["failed"] += 1

        # ── Phase 1: Defense in Depth — Input Validation ────────────

        # 1a. Reject garbage targets (ANSI artifacts, errors, blanks)
        if _is_garbage_target(raw_target):
            self._record_rejected_target(str(meta_path), raw_target, "garbage_target_filter")
            return {"status": "rejected", "reason": "garbage_target", "raw": raw_target}

        # 1b. Reject when target IS the file's SHA256 hash (artifact, not a human identifier)
        if file_sha256 and raw_target == file_sha256:
            self._record_rejected_target(str(meta_path), raw_target, "target_is_file_hash")
            return {"status": "rejected", "reason": "target_is_file_hash", "raw": raw_target}

        # 1c. Reject hex-only targets (SHA hashes used as phoneinfoga / maigret input)
        if _HEX_ONLY_RE.fullmatch(raw_target):
            self._record_rejected_target(str(meta_path), raw_target, "hex_hash_target")
            return {"status": "rejected", "reason": "hex_hash_target", "raw": raw_target}

        # 1d. Entropy check — high-entropy strings are hashes/tokens, not human identifiers
        if len(raw_target) >= 16 and _shannon_entropy(raw_target) > _ENTROPY_THRESHOLD:
            self._record_rejected_target(str(meta_path), raw_target, "high_entropy_target")
            return {"status": "rejected", "reason": "high_entropy_target", "raw": raw_target}

        # 1e. Profile → target type validation
        if profile == "phone" and not _normalize_phone(raw_target):
            self._record_rejected_target(str(meta_path), raw_target, "phone_profile_invalid_target")
            return {"status": "rejected", "reason": "phone_profile_invalid_target", "raw": raw_target}

        if profile == "domain" and raw_target.lower().strip().rstrip(".") in _PLACEHOLDER_DOMAINS:
            self._record_rejected_target(str(meta_path), raw_target, "placeholder_domain")
            return {"status": "rejected", "reason": "placeholder_domain", "raw": raw_target}

        if profile == "health":
            return {"status": "skipped", "reason": "health_check"}

        # Read log file
        if not log_file or not Path(log_file).exists():
            return {"status": "skipped", "reason": "no_log_file"}
        log_text = Path(log_file).read_text(encoding="utf-8", errors="replace")
        log_text = strip_ansi(log_text)

        # Store valid meta
        meta["target"] = raw_target
        meta["_log_text"] = log_text
        meta["_source_file"] = str(meta_path)
        meta["_label"] = meta.get("label", "")
        self._metas.append(meta)

        # Extract observables from the log
        extracted = self._extract_observables(log_text, profile, raw_target, str(meta_path))
        stats["observables"] += len(extracted)

        return {"status": "ingested", "profile": profile, "target": raw_target, "observables": len(extracted)}

    def ingest_confirmed_evidence(self, evidence_path: Union[str, Path]) -> Dict[str, Any]:
        """Ingest analyst-confirmed evidence from a JSON manifest."""
        evidence_path = Path(evidence_path)
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))

        if isinstance(payload, dict):
            entries = payload.get("entries", [])
            default_target = str(payload.get("target") or "")
            default_source = str(payload.get("source_tool") or "confirmed_import")
            batch_label = str(payload.get("label") or evidence_path.stem)
        elif isinstance(payload, list):
            entries = payload
            default_target = ""
            default_source = "confirmed_import"
            batch_label = evidence_path.stem
        else:
            raise ValueError("Confirmed evidence manifest must be a JSON object or list")

        imported = 0
        duplicates = 0
        target_anchor: Optional[Observable] = None
        if default_target:
            seed_obs = self._classify_and_register(
                value=default_target,
                source_tool=default_source,
                source_target=default_target,
                source_file=str(evidence_path),
                depth=0,
                is_original_target=True,
            )
            if seed_obs:
                seed_obs.tier = TIER_CONFIRMED
                target_anchor = seed_obs
                self.repo.register_observable(
                    seed_obs.obs_type, seed_obs.value, seed_obs.raw or seed_obs.value,
                    seed_obs.source_tool, seed_obs.source_target, seed_obs.source_file,
                    seed_obs.depth, seed_obs.is_original_target, tier=TIER_CONFIRMED
                )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            obs_type = str(entry.get("type") or entry.get("obs_type") or "").strip()
            value = str(entry.get("value") or "").strip()
            if not obs_type or not value:
                continue

            source_tool = str(entry.get("source_tool") or default_source or "confirmed_import")
            source_target = str(entry.get("source_target") or default_target or value)
            source_file = str(evidence_path)
            normalized = self._normalize(obs_type, value) if obs_type in {"phone", "domain", "email", "username", "url"} else value.strip()
            if not normalized:
                continue

            fp = f"{obs_type}:{normalized}"
            existing = self._obs_by_value.get(fp)
            if existing:
                existing.source_tools.add(source_tool)
                existing.tier = TIER_CONFIRMED
                self.repo.register_observable(
                    obs_type, normalized, value, source_tool,
                    source_target, source_file, int(entry.get("depth", 1)),
                    bool(entry.get("is_original_target", False)), tier=TIER_CONFIRMED
                )
                duplicates += 1
                continue

            obs = Observable(
                obs_type=obs_type,
                value=normalized,
                source_tool=source_tool,
                source_target=source_target,
                source_file=source_file,
                depth=int(entry.get("depth", 1)),
                raw=value,
                is_original_target=bool(entry.get("is_original_target", False)),
                source_tools={source_tool},
                tier=TIER_CONFIRMED,
            )
            self.repo.register_observable(
                obs.obs_type, obs.value, obs.raw, obs.source_tool,
                obs.source_target, obs.source_file, obs.depth, obs.is_original_target, tier=obs.tier
            )
            self._all_observables.append(obs)
            self._obs_by_value[fp] = obs
            if target_anchor and target_anchor.fingerprint != obs.fingerprint:
                self._link_observables(target_anchor, obs, "confirmed_manifest", 0.95)
            imported += 1

        tool_stats = self._tool_stats.setdefault(default_source, {"success": 0, "failed": 0, "observables": 0})
        tool_stats["success"] += 1
        tool_stats["observables"] += imported
        self._confirmed_imports.append({
            "path": str(evidence_path),
            "label": batch_label,
            "imported": imported,
            "duplicates": duplicates,
        })
        return {
            "status": "ingested",
            "label": batch_label,
            "imported": imported,
            "duplicates": duplicates,
        }

    def _extract_observables(self, log_text: str, profile: str, target: str, source_file: str) -> list[Observable]:
        """Extract all observable types from a tool's log output."""
        found: list[Observable] = []

        # Always register the target itself as an observable (original investigation input)
        seed_obs = self._classify_and_register(target, profile, target, source_file, depth=0, is_original_target=True)
        if seed_obs:
            found.append(seed_obs)

        if profile == "phone":
            found.extend(self._extract_from_phone_log(log_text, target, source_file))
        elif profile in ("username",):
            found.extend(self._extract_from_username_log(log_text, profile, target, source_file))
        elif profile in ("domain", "dnsenum", "whatweb"):
            found.extend(self._extract_from_domain_log(log_text, profile, target, source_file))

        # Generic: extract all emails, phones, domains from any log
        found.extend(self._extract_generic(log_text, profile, target, source_file))

        return found

    def _classify_and_register(self, value: str, source_tool: str, source_target: str, source_file: str, depth: int = 0, is_original_target: bool = False) -> Optional[Observable]:
        """Classify a value, normalize it, and register in DB. Returns None for unrecognizable types."""
        value = value.strip()
        if not value or _is_garbage_target(value):
            return None

        obs_type = self._infer_type(value)
        if obs_type is None:
            return None  # Unknown type — refuse to guess (was defaulting to "username")

        # Block placeholder domains at registration level
        if obs_type == "domain" and value.lower().strip().rstrip(".") in _PLACEHOLDER_DOMAINS:
            return None

        normalized = self._normalize(obs_type, value)
        if not normalized:
            return None

        # Corroboration tracking: if already registered, update source_tools count
        fp = f"{obs_type}:{normalized}"
        existing = self._obs_by_value.get(fp)
        if existing:
            existing.source_tools.add(source_tool)
            self.repo.register_observable(
                obs_type, normalized, value, source_tool,
                source_target, source_file, depth, is_original_target
            )
            return existing

        obs = Observable(
            obs_type=obs_type, value=normalized, source_tool=source_tool,
            source_target=source_target, source_file=source_file, depth=depth, raw=value,
            is_original_target=is_original_target, source_tools={source_tool},
        )

        self.repo.register_observable(
            obs.obs_type, obs.value, obs.raw, obs.source_tool,
            obs.source_target, obs.source_file, obs.depth, is_original_target
        )
        self._all_observables.append(obs)
        self._obs_by_value[fp] = obs
        return obs

    def _infer_type(self, value: str) -> Optional[str]:
        """Classify a string. Returns None if unrecognizable (NO catch-all default)."""
        if _EMAIL_RE.fullmatch(value):
            return "email"
        if _PHONE_RE.fullmatch(re.sub(r"[\s\-\(\)]", "", value)):
            return "phone"
        if re.fullmatch(r"https?://.+", value):
            return "url"
        if "." in value and _DOMAIN_RE.fullmatch(value.lower()):
            return "domain"
        # Explicit username validation — NO catch-all default
        if _HEX_ONLY_RE.fullmatch(value):
            return None  # SHA/MD5 hash, not a username
        if len(value) >= 16 and _shannon_entropy(value) > _ENTROPY_THRESHOLD:
            return None  # High entropy → token/hash, not a human identifier
        if _USERNAME_RE.fullmatch(value) and 2 <= len(value) <= 40:
            return "username"
        return None  # Unknown type — refuse to guess

    def _normalize(self, obs_type: str, value: str) -> Optional[str]:
        if obs_type == "phone":
            return _normalize_phone(value)
        if obs_type == "domain":
            return _normalize_domain(value)
        if obs_type == "email":
            return value.lower().strip()
        if obs_type == "username":
            return value.strip()
        if obs_type == "url":
            return value.strip()
        return value.strip() or None

    def _extract_from_phone_log(self, log_text: str, target: str, source_file: str) -> list[Observable]:
        found: list[Observable] = []
        # Extract E164, local, international from phoneinfoga output
        for label, pattern in [
            ("phone", r"E164:\s*(\+?\d[\d\s\-]{7,15}\d)"),
            ("phone", r"International:\s*(\d{10,15})"),
        ]:
            m = re.search(pattern, log_text)
            if m:
                obs = self._classify_and_register(m.group(1), "phoneinfoga", target, source_file)
                if obs:
                    found.append(obs)
        # Note: Country code (e.g. "UA") is metadata, NOT an observable — don't register it
        return found

    def _extract_from_username_log(self, log_text: str, tool: str, target: str, source_file: str) -> list[Observable]:
        found: list[Observable] = []
        # Extract profile URLs from sherlock/maigret [+] lines
        for m in _SHERLOCK_HIT_RE.finditer(log_text):
            url = m.group(1).rstrip(")")
            self.repo.add_profile_url(target, self._platform_from_url(url), url, tool)
            # Try to extract domain
            parsed = urlparse(url)
            if parsed.hostname:
                dom = _normalize_domain(parsed.hostname)
                if dom and dom not in ("facebook.com", "instagram.com", "twitter.com", "x.com",
                                       "linkedin.com", "github.com", "google.com", "youtube.com",
                                       "reddit.com", "pinterest.com", "vk.com", "tiktok.com"):
                    # Non-social-media domain might be interesting
                    pass  # don't auto-pivot on every social media domain
        return found

    def _extract_from_domain_log(self, log_text: str, tool: str, target: str, source_file: str) -> list[Observable]:
        found: list[Observable] = []
        # Skip placeholder domains
        if target.lower().strip().rstrip(".") in _PLACEHOLDER_DOMAINS:
            return found
        # Extract emails from theHarvester (but not tool-internal emails)
        for email in set(_EMAIL_RE.findall(log_text)):
            # skip tool author emails and noise
            if any(skip in email for skip in ("edge-security", "example.com", "noreply", "localhost")):
                continue
            obs = self._classify_and_register(email, tool, target, source_file, depth=1)
            if obs:
                found.append(obs)
        # Extract subdomains (cap at 20 to avoid noise)
        subdomain_count = 0
        for line in log_text.splitlines():
            line = line.strip()
            if _DOMAIN_RE.fullmatch(line) and line != target:
                obs = self._classify_and_register(line, tool, target, source_file, depth=1)
                if obs:
                    found.append(obs)
                subdomain_count += 1
                if subdomain_count >= 20:
                    break
        return found

    def _extract_generic(self, log_text: str, tool: str, target: str, source_file: str) -> list[Observable]:
        """Fallback: extract emails, phones from any log text. Only for phone/username tools — domain tools have their own extractor."""
        found: list[Observable] = []
        # Only run generic extraction on phone and username tools (domain tools are too noisy)
        if tool not in ("phone", "phoneinfoga", "username", "sherlock", "maigret"):
            return found
        # Skip very large logs
        if len(log_text) > 200_000:
            return found
        # Emails (skip tool-internal ones)
        for email in set(_EMAIL_RE.findall(log_text)):
            if any(skip in email for skip in ("edge-security", "example.com", "noreply", "localhost")):
                continue
            obs = self._classify_and_register(email, tool, target, source_file, depth=1)
            if obs and obs not in found:
                found.append(obs)
        return found

    @staticmethod
    def _platform_from_url(url: str) -> str:
        try:
            host = urlparse(url).hostname or ""
            host_clean = host.replace("www.", "")
            # ucoz-family dedup: all ucoz-hosted sites → single "ucoz" platform
            for ucoz_tld in _UCOZ_DOMAINS:
                if host_clean.endswith("." + ucoz_tld) or host_clean == ucoz_tld:
                    return "ucoz"
            parts = host_clean.split(".")
            return parts[0] if parts else "unknown"
        except Exception:
            return "unknown"

    # ── 2.  Entity Resolution ─────────────────────────────────────







    # ── 3.  Discovery Queue ───────────────────────────────────────




    def resolve_entities(self):
        """Cluster all discovered observables into identity anchors."""
        from pipelines.resolution import EntityResolutionPipeline
        pipeline = EntityResolutionPipeline(self.repo, self._all_observables, self._platform_from_url)
        self.clusters = pipeline.resolve_entities()
        return self.clusters

    def verify_content(self, max_checks: int = 100, timeout: float = 8.0, proxy: Optional[str] = None) -> Dict[str, int]:
        return self.verifier.verify_content(max_checks, timeout, proxy)

    def get_pivot_queue(self) -> list[dict[str, Any]]:
        """Return observables needing further investigation with reasons."""
        existing_targets = {m.get("target", "") for m in self._metas}
        queue: list[dict[str, Any]] = []

        # Unverified observables need cross-tool checks
        for obs in self._all_observables:
            if obs.tier == TIER_UNVERIFIED and obs.value not in existing_targets:
                suggested, reason = self._suggest_tools_with_reason(obs)
                if suggested:
                    queue.append({
                        "obs_type": obs.obs_type,
                        "value": obs.value,
                        "discovered_by": obs.source_tool,
                        "depth": obs.depth,
                        "suggested_tools": suggested,
                        "reason": reason,
                        "tier": obs.tier,
                    })
                    self.repo.enqueue_discovery(obs.obs_type, obs.value, suggested, reason, obs.depth)

        # Suggest reverse-lookup for phones without name confirmation
        for obs in self._all_observables:
            if obs.obs_type == "phone" and obs.is_original_target:
                linked_usernames = [
                    o for o in self._all_observables
                    if o.obs_type == "username" and o.tier == TIER_CONFIRMED
                ]
                if not linked_usernames:
                    queue.append({
                        "obs_type": obs.obs_type,
                        "value": obs.value,
                        "discovered_by": obs.source_tool,
                        "depth": 0,
                        "suggested_tools": ["GetContact", "TrueCaller"],
                        "reason": "Phone has no name confirmation — needs reverse lookup",
                        "tier": obs.tier,
                    })

        return queue

    @staticmethod
    def _suggest_tools_with_reason(obs: Observable) -> tuple[list[str], str]:
        if obs.obs_type == "phone":
            return ["phoneinfoga", "GetContact"], "Phone found by single tool — needs cross-validation"
        if obs.obs_type == "email":
            return ["holehe", "h8mail"], "Email needs breach/registration check"
        if obs.obs_type == "username":
            return ["sherlock", "maigret"], "Username needs profile enumeration"
        if obs.obs_type == "domain":
            return ["theHarvester", "whois"], "Domain needs WHOIS + subdomain enumeration"
        return [], ""

    # ── 4.  Profile Verification ─────────────────────────────────

    def verify_profiles(self, max_checks: int = 50, timeout: float = 5.0, proxy: Optional[str] = None):
        return self.verifier.verify_profiles(max_checks=max_checks, timeout=timeout, proxy=proxy)

    def reverify_expired(self, max_checks: int = 50, timeout: float = 5.0, proxy: Optional[str] = None) -> Dict[str, int]:
        return self.verifier.reverify_expired(max_checks=max_checks, timeout=timeout, proxy=proxy)

    def get_profile_stats(self) -> Dict[str, int]:
        return self.verifier.get_profile_stats()

    # ── 4a. Content Verification ──────────────────────────────────

    def verify_content(self, max_checks: int = 100, timeout: float = 8.0, proxy: Optional[str] = None) -> Dict[str, int]:
        return self.verifier.verify_content(max_checks=max_checks, timeout=timeout, proxy=proxy)


    # ── 4b. Deep Recon Integration ────────────────────────────────

    def run_deep_recon(
        self,
        target_name: Optional[str] = None,
        modules: Optional[List[str]] = None,
        proxy: Optional[str] = None,
        leak_dir: Optional[str] = None,
        known_phones_override: Optional[List[str]] = None,
        known_usernames_override: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], Optional[ReconReport]]:
        """
        Run deep UA+RU recon and feed results back into the observable pipeline.

        Args:
            target_name: Override auto-detected name (from primary cluster label)
            modules: List of module names or preset (e.g. "deep-all")
            proxy: SOCKS5 proxy URL (e.g. "socks5h://127.0.0.1:9050")
            leak_dir: Override default leak scan directory
            known_phones_override: Extra known phones to inject for this run
            known_usernames_override: Extra known usernames to inject for this run

                Returns:
                        Tuple of:
                            - summary dict with counts of new observables added
                            - ReconReport (or None when target is missing)
        """
        from deep_recon import DeepReconRunner, ReconReport

        # Auto-detect target name from primary cluster
        if not target_name and self.clusters:
            target_name = self.clusters[0].label
        if not target_name:
            return ({"error": "No target name — run resolve_entities() first or pass target_name"}, None)

        # Collect known phones and usernames from current state
        known_phones = [
            obs.value for obs in self._all_observables
            if obs.obs_type == "phone"
        ]
        known_usernames = [
            obs.value for obs in self._all_observables
            if obs.obs_type == "username"
        ]

        if known_phones_override:
            known_phones.extend(p.strip() for p in known_phones_override if p and p.strip())
            known_phones = sorted(set(known_phones))
        if known_usernames_override:
            known_usernames.extend(u.strip() for u in known_usernames_override if u and u.strip())
            known_usernames = sorted(set(known_usernames))

        print(f"\n{'='*60}")
        print(f"DEEP RECON: {target_name}")
        print(f"Known phones: {known_phones}")
        print(f"Known usernames: {known_usernames}")
        print(f"Modules: {modules or 'all'}")
        print(f"Proxy: {proxy or 'direct'}")
        if leak_dir:
            print(f"Leak dir: {leak_dir}")
        print(f"{'='*60}\n")

        runner = DeepReconRunner(proxy=proxy, leak_dir=leak_dir)
        report = runner.run(
            target_name=target_name,
            known_phones=known_phones,
            known_usernames=known_usernames,
            modules=modules,
        )

        # Feed hits back into the discovery engine
        new_obs_count = 0
        for hit in report.hits:
            if hit.confidence <= 0:
                continue  # skip manual-check placeholders

            obs = self._classify_and_register(
                value=hit.value,
                source_tool=f"deep_recon:{hit.source_module}",
                source_target=target_name,
                source_file=f"deep_recon:{hit.source_detail}",
                depth=1,
            )
            if obs:
                new_obs_count += 1
                # Add to pivot queue with reason
                self.repo.enqueue_discovery(
                    hit.observable_type,
                    hit.value,
                    ["cross_verify", "getcontact"],
                    f"Found by {hit.source_module} (conf={hit.confidence:.0%}): {hit.source_detail}",
                    1
                )


        # Print summary
        summary = DeepReconRunner.report_summary(report)
        print(summary)

        return ({
            "target": target_name,
            "modules_run": report.modules_run,
            "total_hits": len(report.hits),
            "new_observables": new_obs_count,
            "new_phones": report.new_phones,
            "new_emails": report.new_emails,
            "cross_confirmed": len(report.cross_confirmed),
            "errors": report.errors,
        }, report)

    # ── 5.  Reporting ─────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Summary metrics for the discovery run."""
        stats = self.repo.get_stats()
        obs_count = stats["observables"]
        rejected_count = stats["rejected_targets"]
        link_count = stats["entity_links"]
        url_count = stats["profile_urls"]
        queue_count = stats["pending_queue"]
        confirmed = sum(1 for o in self._all_observables if o.tier == TIER_CONFIRMED)
        probable = sum(1 for o in self._all_observables if o.tier == TIER_PROBABLE)
        unverified = sum(1 for o in self._all_observables if o.tier == TIER_UNVERIFIED)
        profile_stats = self.get_profile_stats()
        return {
            "total_metadata_files": len(self._metas),
            "total_observables": obs_count,
            "confirmed_observables": confirmed,
            "probable_observables": probable,
            "unverified_observables": unverified,
            "rejected_targets": rejected_count,
            "entity_links": link_count,
            "profile_urls": url_count,
            "profile_verification": profile_stats,
            "identity_clusters": len(self.clusters),
            "pending_pivots": queue_count,
            "tool_stats": self._tool_stats,
        }

    def _get_runs_dir(self) -> Path:
        db_file = self.repo.get_database_path()
        if db_file:
            return Path(db_file).resolve().parent
        return RUNS_ROOT

    @staticmethod
    def _get_lane_registry() -> dict[str, str]:
        from registry import MODULE_LANE
        return dict(MODULE_LANE)

    def render_graph_report(self, output_path: Union[str, Path, None] = None, redaction_mode: str = "shareable") -> str:
        return self.renderer.render_graph_report(output_path=output_path, redaction_mode=redaction_mode)


# ── CLI entry point ──────────────────────────────────────────────

def _cli():
    """
    HANNA Discovery Engine — CLI

    Usage:
      python3 discovery_engine.py --verify-all --db discovery.db
      python3 discovery_engine.py --ingest /path/to/exports/*.json --db discovery.db
      python3 discovery_engine.py --report --db discovery.db
      python3 discovery_engine.py --stats --db discovery.db
    """
    import argparse
    import glob

    parser = argparse.ArgumentParser(
        prog="discovery_engine",
        description="HANNA Discovery Engine v2 — verification-first orchestrator",
    )
    parser.add_argument("--db", metavar="PATH", help="SQLite database path (default: config.DEFAULT_DB_PATH)")
    parser.add_argument("--verify-all", action="store_true", help="Run HTTP verification for all unchecked profile URLs")
    parser.add_argument("--verify-content", action="store_true", help="Run content-match verification for soft_match URLs")
    parser.add_argument("--reverify-expired", action="store_true", help="Re-verify profiles whose TTL has expired")
    parser.add_argument("--ingest", nargs="*", metavar="JSON", help="Ingest metadata JSON exports")
    parser.add_argument("--report", metavar="OUT", nargs="?", const="auto", help="Generate HTML dossier report")
    parser.add_argument("--report-mode", choices=["internal", "shareable", "strict"], default="shareable", help="HTML dossier redaction level")
    parser.add_argument("--stats", action="store_true", help="Print observable and profile stats")
    parser.add_argument("--max-checks", type=int, default=200, metavar="N", help="Max URLs to verify (default: 200)")
    parser.add_argument("--timeout", type=float, default=5.0, metavar="SEC", help="Per-request timeout (default: 5)")

    args = parser.parse_args()

    # ── Resolve DB path ──
    db_path = args.db or str(DEFAULT_DB_PATH)
    if not Path(db_path).exists() and not args.ingest:
        print(f"DB not found: {db_path}")
        raise SystemExit(1)

    engine = DiscoveryEngine(db_path=db_path)

    did_something = False

    # ── Ingest ──
    if args.ingest:
        files = []
        for pattern in args.ingest:
            files.extend(glob.glob(pattern))
        if not files:
            print("No files matched ingest patterns.")
        else:
            for fpath in sorted(set(files)):
                print(f"  Ingesting: {fpath}")
                engine.ingest_metadata(fpath)
            engine.resolve_entities()
            print(f"  ✓ Ingested {len(files)} file(s), resolved entities.")
        did_something = True

    # ── Verify profiles ──
    if args.verify_all:
        before = engine.get_profile_stats()
        unchecked = before.get("unchecked", 0)
        if unchecked == 0:
            print("  No unchecked profile URLs to verify.")
        else:
            print(f"  Verifying {min(unchecked, args.max_checks)} profile URLs (timeout={args.timeout}s)...")
            engine.verify_profiles(max_checks=args.max_checks, timeout=args.timeout)
            after = engine.get_profile_stats()
            print(f"  ✓ Profile verification complete:")
            for status, count in sorted(after.items()):
                delta = count - before.get(status, 0)
                tag = f" (+{delta})" if delta > 0 else ""
                print(f"    {status:15s} {count:4d}{tag}")
        did_something = True

    # ── Content verification ──
    if args.verify_content:
        print(f"  Running content verification (max={args.max_checks}, timeout={args.timeout}s)...")
        counts = engine.verify_content(max_checks=args.max_checks, timeout=args.timeout)
        print(f"  ✓ Content verification: upgraded={counts.get('upgraded',0)}, "
              f"killed={counts.get('killed',0)}, unchanged={counts.get('unchanged',0)}, "
              f"errors={counts.get('errors',0)}, blacklisted={counts.get('skipped_blacklisted',0)}")
        did_something = True

    # ── TTL re-verification ──
    if args.reverify_expired:
        print(f"  Re-verifying expired TTL profiles (max={args.max_checks}, timeout={args.timeout}s)...")
        counts = engine.reverify_expired(max_checks=args.max_checks, timeout=args.timeout)
        print(f"  ✓ TTL re-verification: rechecked={counts['rechecked']}, "
              f"upgraded={counts['upgraded']}, downgraded={counts['downgraded']}, "
              f"unchanged={counts['unchanged']}")
        did_something = True

    # ── Stats ──
    if args.stats or not did_something:
        stats = engine.get_stats()
        print(f"\n{'='*50}")
        print(f"  HANNA Discovery Engine — DB Stats")
        print(f"  Database: {db_path}")
        print(f"{'='*50}")
        print(f"\n  Observables (confirmed/probable/unverified):")
        print(f"    Total:           {stats['total_observables']:4d}")
        print(f"    Confirmed:       {stats['confirmed_observables']:4d}")
        print(f"    Probable:        {stats['probable_observables']:4d}")
        print(f"    Unverified:      {stats['unverified_observables']:4d}")
        print(f"\n  Profile URLs:")
        for status, count in sorted(stats['profile_verification'].items()):
            print(f"    {status:15s} {count:4d}")
        print(f"\n  Entity links:      {stats['entity_links']}")
        print(f"  Pending pivots:    {stats['pending_pivots']}")
        did_something = True

    # ── Report ──
    if args.report:
        if args.report == "auto":
            out_path = str(RUNS_ROOT / "dossier.html")
        else:
            out_path = args.report
        engine.render_graph_report(output_path=out_path, redaction_mode=args.report_mode)
        print(f"\n📄 HTML report saved: {out_path}")


if __name__ == "__main__":
    _cli()
