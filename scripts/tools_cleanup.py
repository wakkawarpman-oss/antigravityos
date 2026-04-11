#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tools_cleanup import apply_cleanup_actions, plan_cleanup_actions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tools cleanup helper isolated from core lane.")
    parser.add_argument("--apply", action="store_true", help="Apply planned actions. Default is dry-run.")
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Allow destructive actions like resetting dirty submodules or removing optional checkout.",
    )
    parser.add_argument("--include-tookie", action="store_true", help="Include tools/tookie-osint cleanup action.")
    parser.add_argument("--output", default="", help="Optional JSON report path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parent.parent

    actions = plan_cleanup_actions(repo_root=repo_root, include_tookie=bool(args.include_tookie))
    payload: dict = {
        "mode": "apply" if args.apply else "dry-run",
        "allow_destructive": bool(args.allow_destructive),
        "actions": [action.__dict__ for action in actions],
    }

    if args.apply:
        payload["results"] = apply_cleanup_actions(
            actions=actions,
            repo_root=repo_root,
            allow_destructive=bool(args.allow_destructive),
        )

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
