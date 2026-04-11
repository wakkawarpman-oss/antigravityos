#!/usr/bin/env python3
from __future__ import annotations

"""
run_discovery.py — Legacy DiscoveryEngine entrypoint.

Usage:
    python3 run_discovery.py [--exports-dir DIR] [--output HTML_PATH] [--db DB_PATH]

Deep recon mode:
    python3 run_discovery.py --target "Hanna Dosenko" --modules "ua_leak,ru_leak,vk_graph" --verify
    python3 run_discovery.py --target "Hanna Dosenko" --mode deep-all --verify

Preferred operator path:
    ./scripts/hanna list
    ./scripts/hanna chain --target "Hanna Dosenko" --modules full-spectrum
"""
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DEFAULT_DB_PATH, RUNS_ROOT, TOR_ENABLED, TOR_PROXY_URL, TOR_REQUIRE_SOCKS5H
from discovery_engine import DiscoveryEngine
from opsec_redaction import redact_runtime_payload, seed_summary
from registry import MODULE_PRESETS, MODULES, MODULE_LANE
from services.orchestration import (
    ingest_confirmed_evidence,
    ingest_metadata_exports,
    render_dossier,
    resolve_clusters,
    run_recon_stage,
    run_verification_stage,
)

log = logging.getLogger("hanna.run_discovery")

LEGACY_WARNING = (
    "[legacy] run_discovery.py is kept for compatibility. "
    "Prefer './scripts/hanna' or 'python3 src/cli.py' for operator workflows."
)


def _resolve_effective_proxy(cli_proxy: str | None) -> str | None:
    if cli_proxy and cli_proxy.strip():
        return cli_proxy.strip()
    if TOR_ENABLED:
        return TOR_PROXY_URL
    return None


def _validate_proxy_policy(proxy: str | None) -> None:
    if not TOR_ENABLED:
        return
    if not proxy:
        raise SystemExit("TOR policy enabled but no proxy is configured. Set --proxy or HANNA_TOR_PROXY_URL.")
    if TOR_REQUIRE_SOCKS5H and not proxy.startswith("socks5h://"):
        raise SystemExit("TOR policy requires socks5h:// proxy URL. Update --proxy or HANNA_TOR_PROXY_URL.")


def _parse_targets_file(path: str) -> list[dict[str, list[str] | str]]:
    """
    Parse batch targets file.

    Format per line:
      target|phone1,phone2|username1,username2

    Lines starting with '#' or empty lines are ignored.
    """
    items: list[dict[str, list[str] | str]] = []
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"targets file not found: {path}")

    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split("|")]
        while len(parts) < 3:
            parts.append("")

        target = parts[0]
        if not target:
            continue

        phones = [p.strip() for p in parts[1].split(",") if p.strip()]
        usernames = [u.strip() for u in parts[2].split(",") if u.strip()]
        items.append({
            "target": target,
            "phones": phones,
            "usernames": usernames,
        })

    return items


def main():
    parser = argparse.ArgumentParser(
        description="Run recursive discovery engine on legacy OSINT exports",
        epilog="Legacy compatibility path. Prefer './scripts/hanna list|chain|aggregate|manual|preflight'.",
    )
    parser.add_argument("--exports-dir", default=str(RUNS_ROOT / "exports"))
    parser.add_argument("--output", default=None, help="Output HTML path")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--list-modules", action="store_true", help="List available adapters and presets, then exit")
    parser.add_argument("--confirmed-file", nargs="*", default=[], help="JSON manifest(s) with analyst-confirmed evidence to inject before entity resolution")

    # Deep recon options
    parser.add_argument("--target", default=None, help="Target name for deep recon (e.g. 'Hanna Dosenko')")
    parser.add_argument("--modules", default=None, help="Comma-separated recon modules (ua_leak,ru_leak,vk_graph,avito,ua_phone)")
    parser.add_argument("--mode", default=None, help="Module preset: deep-ua, deep-ru, deep-all, leaks_all")
    parser.add_argument("--targets-file", default=None, help="Batch target file: target|phone1,phone2|username1,username2")
    parser.add_argument("--verify", action="store_true", help="Run profile verification after discovery")
    parser.add_argument("--verify-all", action="store_true", help="Verify ALL unchecked profiles (no limit)")
    parser.add_argument("--verify-content", action="store_true", help="Content-verify soft_match URLs (full GET + name matching)")
    parser.add_argument("--leaks-dir", default=None, help="Directory with JSONL leak files (default: runs/leaks/)")
    parser.add_argument("--phone-resolve", action="store_true", help="Run live phone resolution for known numbers")
    parser.add_argument("--proxy", default=None, help="SOCKS5 proxy for deep recon (e.g. socks5h://127.0.0.1:9050)")
    parser.add_argument("--report-mode", choices=["internal", "shareable", "strict"], default="shareable", help="HTML dossier redaction level")
    parser.add_argument("--no-legacy-warning", action="store_true", help="Suppress compatibility warning for scripted legacy usage")

    args = parser.parse_args()

    args.proxy = _resolve_effective_proxy(args.proxy)
    _validate_proxy_policy(args.proxy)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if not args.no_legacy_warning:
        print(LEGACY_WARNING, file=sys.stderr)

    if args.list_modules:
        print("\n=== Available Adapters ===")
        print(f"{'Name':<18} {'Lane':<6} Description")
        print("-" * 70)
        for name, adapter_cls in sorted(MODULES.items()):
            doc = (adapter_cls.__doc__ or "").strip().splitlines()[0] if adapter_cls.__doc__ else ""
            print(f"{name:<18} {MODULE_LANE.get(name, 'fast'):<6} {doc[:40]}")

        print(f"\n=== Presets ({len(MODULE_PRESETS)}) ===")
        for name, mods in MODULE_PRESETS.items():
            print(f"  {name:<20} -> {', '.join(mods)}")
        return

    exports = Path(args.exports_dir)
    metadata_files = sorted(exports.glob("*.json"))
    log.info("Found %d metadata files in %s", len(metadata_files), exports)

    # Default output
    if not args.output:
        out_dir = exports / "html" / "dossiers"
        out_dir.mkdir(parents=True, exist_ok=True)
        args.output = str(out_dir / "discovery_dossier.html")

    engine = DiscoveryEngine(db_path=args.db)

    # Ingest all
    results = ingest_metadata_exports(engine, exports)
    confirmed_results = ingest_confirmed_evidence(engine, args.confirmed_file)

    log.info("Ingestion: %d ingested, %d rejected, %d skipped",
             results['ingested'], results['rejected'], results['skipped'])
    if confirmed_results:
        log.info("Confirmed evidence imports:")
        for item in confirmed_results:
            log.info("  %s: %d imported, %d duplicate(s)",
                     item['label'], item['imported'], item['duplicates'])

    # Resolve entities
    clusters = resolve_clusters(engine)
    log.info("Entity resolution: %d identity cluster(s)", len(clusters))
    for i, c in enumerate(clusters[:5]):
        obs_types = {}
        for obs in c.observables:
            obs_types[obs.obs_type] = obs_types.get(obs.obs_type, 0) + 1
        type_summary = ", ".join(f"{k}:{v}" for k, v in sorted(obs_types.items()))
        log.info("  Cluster %d: \"%s\" — %d obs (%s), %d URLs, conf=%.0f%%",
                 i+1, c.label, len(c.observables), type_summary, len(c.profile_urls), c.confidence * 100)

    # Show pivot opportunities
    queue = engine.get_pivot_queue()
    if queue:
        log.info("Auto-pivot queue: %d pending task(s)", len(queue))
        for item in queue[:10]:
            log.info("  [%s] %s → %s", item['obs_type'], item['value'], ', '.join(item['suggested_tools']))

    # ── Deep recon (Phase 5) ──
    deep_recon_result = None
    deep_recon_results: list[dict] = []
    modules = None
    if args.mode:
        modules = [args.mode]  # resolved as preset by DeepReconRunner
    elif args.modules:
        modules = [m.strip() for m in args.modules.split(",") if m.strip()]

    if args.targets_file:
        batch_targets = _parse_targets_file(args.targets_file)
        log.info("Batch deep recon targets: %d", len(batch_targets))
        for i, item in enumerate(batch_targets, start=1):
            target = str(item["target"])
            phones = list(item["phones"])
            usernames = list(item["usernames"])
            log.info("[%d/%d] Deep recon target: %s", i, len(batch_targets), target)
            if phones:
                log.info("  Seed phones: %s", seed_summary(phones, "phone"))
            if usernames:
                log.info("  Seed usernames: %s", seed_summary(usernames, "username"))

            result, _report = run_recon_stage(
                engine,
                target_name=target,
                modules=modules,
                proxy=args.proxy,
                leak_dir=args.leaks_dir,
                known_phones=phones,
                known_usernames=usernames,
            )
            if result is None:
                continue
            deep_recon_results.append(result)
            redacted_result = redact_runtime_payload(result)
            log.info("Deep recon result: %s", json.dumps(redacted_result, indent=2, default=str))

            if result.get("new_observables", 0) > 0:
                log.info("Re-resolving entities with new deep recon data...")
                clusters = resolve_clusters(engine)
                log.info("Updated: %d identity cluster(s)", len(clusters))

        deep_recon_result = deep_recon_results[-1] if deep_recon_results else None
    elif args.target or args.modules or args.mode:
        deep_recon_result, _report = run_recon_stage(
            engine,
            target_name=args.target,
            modules=modules,
            proxy=args.proxy,
            leak_dir=args.leaks_dir,
            known_phones=None,
            known_usernames=None,
        )
        if deep_recon_result is not None:
            deep_recon_results.append(deep_recon_result)
            redacted_result = redact_runtime_payload(deep_recon_result)
            log.info("Deep recon result: %s", json.dumps(redacted_result, indent=2, default=str))

        # Re-resolve entities with new data
        if deep_recon_result.get("new_observables", 0) > 0:
            log.info("Re-resolving entities with new deep recon data...")
            clusters = resolve_clusters(engine)
            log.info("Updated: %d identity cluster(s)", len(clusters))

    # ── Phone resolve shortcut ──
    if args.phone_resolve and not deep_recon_result:
        deep_recon_result, _report = run_recon_stage(
            engine,
            target_name=args.target,
            modules=["ua_phone"],
            proxy=args.proxy,
            leak_dir=args.leaks_dir,
            known_phones=None,
            known_usernames=None,
        )
        if deep_recon_result is not None:
            redacted_result = redact_runtime_payload(deep_recon_result)
            log.info("Phone resolve result: %s", json.dumps(redacted_result, indent=2, default=str))
            if deep_recon_result.get("new_observables", 0) > 0:
                clusters = resolve_clusters(engine)
                log.info("Updated: %d cluster(s)", len(clusters))

    # ── Profile verification ──
    if args.verify or args.verify_all:
        max_checks = 999999 if args.verify_all else 200
        log.info("Running profile verification (max %d)...", max_checks)
        run_verification_stage(
            engine,
            verify=True,
            verify_all=args.verify_all,
            verify_content=False,
            proxy=args.proxy,
        )
        pstats = engine.get_profile_stats()
        log.info("Profile stats: %s", pstats)

    # ── Content verification (Phase 6A) ──
    if args.verify_content:
        log.info("Running content verification on soft_match URLs...")
        cv_result = engine.verify_content(max_checks=200, timeout=8.0, proxy=args.proxy)
        log.info("Content verify: %s", cv_result)
        pstats = engine.get_profile_stats()
        log.info("Profile stats after content verify: %s", pstats)

    # Stats
    stats = engine.get_stats()
    log.info("Stats: %s", json.dumps(stats, indent=2, default=str))

    # Render report
    render_dossier(engine, output_path=args.output, report_mode=args.report_mode)
    log.info("Graph-centric dossier written to: %s", args.output)

    # Also create a latest symlink
    latest = Path(args.output).parent / "latest_discovery.html"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(Path(args.output).name)
    log.info("Latest link: %s", latest)


if __name__ == "__main__":
    main()
