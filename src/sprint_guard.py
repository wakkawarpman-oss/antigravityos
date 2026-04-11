from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"<your_[^>]+>", re.IGNORECASE),
    re.compile(r"\bYOUR_API_KEY\b", re.IGNORECASE),
    re.compile(r"\bREPLACE_ME\b", re.IGNORECASE),
    re.compile(r"TODO:\s*implement", re.IGNORECASE),
    re.compile(r"FIXME:\s*implement", re.IGNORECASE),
)

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".json",
    ".yml",
    ".yaml",
    ".sh",
}


@dataclass
class GuardResult:
    ok: bool
    changed_files: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    placeholder_hits: dict[str, list[str]] = field(default_factory=dict)
    command_failures: list[dict[str, str | int]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "changed_files": self.changed_files,
            "out_of_scope": self.out_of_scope,
            "placeholder_hits": self.placeholder_hits,
            "command_failures": self.command_failures,
        }


def _run(command: str, cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        command,
        shell=True,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def _git_changed_files(repo_root: Path, include_untracked: bool) -> list[str]:
    files: set[str] = set()
    for cmd in (
        "git diff --name-only --diff-filter=ACMRTUXB",
        "git diff --name-only --cached --diff-filter=ACMRTUXB",
    ):
        code, output = _run(cmd, repo_root)
        if code == 0 and output:
            files.update(line.strip() for line in output.splitlines() if line.strip())

    if include_untracked:
        code, output = _run("git ls-files --others --exclude-standard", repo_root)
        if code == 0 and output:
            files.update(line.strip() for line in output.splitlines() if line.strip())

    return sorted(files)


def _is_in_scope(path: str, scopes: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, scope) for scope in scopes)


def _is_ignored(path: str, ignore_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in ignore_globs)


def _scan_placeholder_hits(repo_root: Path, files: list[str]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for rel in files:
        path = repo_root / rel
        if not path.exists() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matched = [pattern.pattern for pattern in PLACEHOLDER_PATTERNS if pattern.search(content)]
        if matched:
            hits[rel] = matched
    return hits


def _default_audit_commands(repo_root: Path) -> list[str]:
    commands = ["python3 -m pip check"]
    if (repo_root / "package.json").exists():
        commands.append("npm audit --omit=dev --audit-level=high")
    return commands


def run_guard(
    repo_root: Path,
    scopes: list[str],
    ignore_globs: list[str],
    include_untracked: bool,
    scan_placeholders: bool,
    check_commands: list[str],
) -> GuardResult:
    all_changed = _git_changed_files(repo_root, include_untracked=include_untracked)
    changed_files = [path for path in all_changed if not _is_ignored(path, ignore_globs)]

    out_of_scope = [path for path in changed_files if not _is_in_scope(path, scopes)]
    placeholder_hits = _scan_placeholder_hits(repo_root, changed_files) if scan_placeholders else {}

    command_failures: list[dict[str, str | int]] = []
    for command in check_commands:
        code, output = _run(command, repo_root)
        if code != 0:
            command_failures.append({
                "command": command,
                "exit_code": code,
                "output": output[-4000:],
            })

    ok = not out_of_scope and not placeholder_hits and not command_failures
    return GuardResult(
        ok=ok,
        changed_files=changed_files,
        out_of_scope=out_of_scope,
        placeholder_hits=placeholder_hits,
        command_failures=command_failures,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint anti-hallucination guard: enforces project scope, blocks placeholder artifacts, "
            "and runs dependency/system audits."
        )
    )
    parser.add_argument(
        "--scope",
        action="append",
        default=[],
        help="Allowed glob for changed files. Repeatable, e.g. --scope 'src/**'",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Ignore changed files matching glob. Repeatable, e.g. --ignore 'tools/*'",
    )
    parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="Include untracked files in scope checks.",
    )
    parser.add_argument(
        "--no-placeholder-scan",
        action="store_true",
        help="Disable placeholder token scan.",
    )
    parser.add_argument(
        "--check-command",
        action="append",
        default=[],
        help="Command to run as mandatory post-phase check. Repeatable.",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path for machine-readable report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    scopes = args.scope or ["src/**", "tests/**", "scripts/**", "docs/**", "*.md", "*.json", "*.txt", "package*.json", "requirements*.txt"]
    check_commands = args.check_command or _default_audit_commands(repo_root)

    result = run_guard(
        repo_root=repo_root,
        scopes=scopes,
        ignore_globs=list(args.ignore or []),
        include_untracked=bool(args.include_untracked),
        scan_placeholders=not bool(args.no_placeholder_scan),
        check_commands=check_commands,
    )

    payload = result.to_dict()
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
