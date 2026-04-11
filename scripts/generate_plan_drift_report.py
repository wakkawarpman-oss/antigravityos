#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from plan_drift_report import collect_plan_drift_report, render_json, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate master-plan vs checkpoint drift report.")
    parser.add_argument("--master-plan", required=True, help="Path to MASTER_PLAN markdown file")
    parser.add_argument("--checkpoint", required=True, help="Path to checkpoint status markdown file")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--markdown", default="", help="Optional markdown summary path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = collect_plan_drift_report(master_plan_path=args.master_plan, checkpoint_path=args.checkpoint)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_json(report), encoding="utf-8")

    if args.markdown:
        markdown_path = Path(args.markdown)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")

    print(render_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())