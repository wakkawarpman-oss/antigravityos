#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTERS_DIR = REPO_ROOT / "src" / "adapters"

# Canonical transport layer is allowed to use low-level network calls.
ALLOWLIST = {
    Path("src/adapters/base.py"),
}

DISALLOWED_CALLS = {
    "urllib.request.urlopen",
    "requests.get",
    "requests.post",
    "requests.request",
    "httpx.get",
    "httpx.post",
    "httpx.request",
    "aiohttp.ClientSession",
}


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return None


def scan_file(path: Path) -> list[tuple[int, str]]:
    rel = path.relative_to(REPO_ROOT)
    if rel in ALLOWLIST:
        return []

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [(exc.lineno or 1, f"syntax_error:{exc.msg}")]

    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name in DISALLOWED_CALLS:
            violations.append((getattr(node, "lineno", 1), name))
    return violations


def main() -> int:
    files = sorted(ADAPTERS_DIR.glob("*.py"))
    all_violations: list[tuple[Path, int, str]] = []

    for file_path in files:
        for lineno, call_name in scan_file(file_path):
            all_violations.append((file_path.relative_to(REPO_ROOT), lineno, call_name))

    if all_violations:
        print("Direct network guard failed:", file=sys.stderr)
        for rel, lineno, call_name in all_violations:
            print(f"  {rel}:{lineno} -> {call_name}", file=sys.stderr)
        print("Allow direct calls only in canonical transport layer.", file=sys.stderr)
        return 1

    print("No disallowed direct network calls detected in src/adapters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
