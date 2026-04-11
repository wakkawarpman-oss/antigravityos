from __future__ import annotations

from pathlib import Path

from sprint_guard import _is_in_scope, _scan_placeholder_hits


def test_is_in_scope_matches_glob_patterns():
    scopes = ["src/**", "tests/**", "docs/**", "package*.json"]
    assert _is_in_scope("src/runners/aggregate.py", scopes)
    assert _is_in_scope("tests/test_cli_contracts.py", scopes)
    assert _is_in_scope("docs/SPRINT_START_GUARD.md", scopes)
    assert _is_in_scope("package-lock.json", scopes)
    assert not _is_in_scope("tools/recon-ng/something.py", scopes)


def test_scan_placeholder_hits_detects_blocked_tokens(tmp_path: Path):
    repo = tmp_path
    bad = repo / "src" / "sample.py"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("token = 'REPLACE_ME'\n", encoding="utf-8")

    clean = repo / "src" / "ok.py"
    clean.write_text("print('ok')\n", encoding="utf-8")

    hits = _scan_placeholder_hits(repo, ["src/sample.py", "src/ok.py"])

    assert "src/sample.py" in hits
    assert any("REPLACE_ME" in pattern for pattern in hits["src/sample.py"])
    assert "src/ok.py" not in hits
