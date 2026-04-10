from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dossier.core import DossierEngine


def run_cli_dossier(target_str: str, export_format: str = "text", export_dir: str | None = None) -> int:
    engine = DossierEngine()
    dossier, normalized = engine.run_one_shot(target_str)

    fmt = export_format.strip().lower()
    now = str(int(time.time()))
    base_name = f"dossier_{now}_{fmt}"
    base_dir = Path(export_dir) if export_dir else Path.cwd()
    base_dir.mkdir(parents=True, exist_ok=True)
    out_path = base_dir / base_name

    path = engine.export_dossier(dossier, normalized, fmt, out_path)
    print(f"Saved dossier to {path}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dossier.cli", description="ONE-SHOT dossier CLI")
    parser.add_argument("target", nargs="+", help="Target string for one-shot dossier generation")
    parser.add_argument("format", nargs="?", default="text", choices=["text", "json"], help="Export format")
    parser.add_argument("--export-dir", default=None, help="Directory where dossier file will be saved")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    target = " ".join(args.target).strip()
    return run_cli_dossier(target, args.format, args.export_dir)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
