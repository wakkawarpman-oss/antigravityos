import argparse
import sys
from pathlib import Path
from datetime import datetime
import json

from config import RUNS_ROOT
from registry import MODULES, MODULE_PRESETS, ModuleResolutionError, resolve_modules
from runners.base import DeepReconRunner

def _cli():
    parser = argparse.ArgumentParser(
        prog="deep_recon",
        description="HANNA Deep Recon — UA/RU OSINT multi-adapter runner",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--module", metavar="NAME")
    group.add_argument("--mode", metavar="PRESET")
    group.add_argument("--list-modules", action="store_true")
    parser.add_argument("--target", metavar="NAME")
    parser.add_argument("--phones", nargs="*", default=[])
    parser.add_argument("--usernames", nargs="*", default=[])
    parser.add_argument("--proxy", metavar="URL")
    parser.add_argument("--leak-dir", metavar="PATH")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output-dir", metavar="DIR")
    args = parser.parse_args()

    if args.list_modules:
        print("Available modules:")
        for name, cls in MODULES.items():
            doc = (cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else ""
            print(f"  {name:20s}  [{cls.region.upper():6s}]  {doc}")
        print("\nPresets:")
        for preset, mods in MODULE_PRESETS.items():
            print(f"  {preset:20s}  → {', '.join(mods)}")
        return

    if not args.target:
        parser.error("--target required (use --list-modules to browse)")

    try:
        if args.module:
            mods = [args.module]
        elif args.mode:
            mods = resolve_modules([args.mode])
        else:
            mods = resolve_modules(["full-spectrum"])
    except ModuleResolutionError as exc:
        parser.error(str(exc))

    runner = DeepReconRunner(proxy=args.proxy, timeout=args.timeout, leak_dir=args.leak_dir)

    print(f"\n{'='*60}")
    print(f"  HANNA Deep Recon — {args.target}")
    print(f"  Modules: {', '.join(mods)}")
    print(f"{'='*60}\n")

    report = runner.run(
        target_name=args.target,
        known_phones=args.phones,
        known_usernames=args.usernames,
        modules=mods,
    )

    print(f"\n{DeepReconRunner.report_summary(report)}")

    out_dir = Path(args.output_dir) if args.output_dir else RUNS_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rp = out_dir / f"deep_recon_{ts}.json"
    rp.write_text(json.dumps({
        "target": report.target_name,
        "modules": report.modules_run,
        "started": report.started_at,
        "finished": report.finished_at,
        "total_hits": len(report.hits),
        "new_phones": report.new_phones,
        "new_emails": report.new_emails,
        "cross_confirmed": len(report.cross_confirmed),
        "hits": [
            {"type": h.observable_type, "value": h.value, "source": h.source_module,
             "detail": h.source_detail, "confidence": h.confidence, "cross_refs": h.cross_refs}
            for h in report.hits
        ],
        "errors": report.errors,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport saved: {rp}")

if __name__ == "__main__":
    _cli()
