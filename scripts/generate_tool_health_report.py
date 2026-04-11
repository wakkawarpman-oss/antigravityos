#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tool_health_report import collect_tool_health_report, render_markdown, to_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate non-blocking tool-health report.")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--markdown", default="", help="Optional Markdown output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parent.parent

    report = collect_tool_health_report(repo_root)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(to_json(report), encoding="utf-8")

    if args.markdown:
        md_path = Path(args.markdown)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")

    print(to_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
