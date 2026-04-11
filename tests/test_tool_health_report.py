from __future__ import annotations

from pathlib import Path

from tool_health_report import CommandResult, collect_tool_health_report, render_markdown


def test_collect_tool_health_report_marks_dirty_and_missing(tmp_path: Path):
    gitmodules = tmp_path / ".gitmodules"
    gitmodules.write_text(
        """
[submodule \"tools/EyeWitness\"]
\tpath = tools/EyeWitness
[submodule \"tools/recon-ng\"]
\tpath = tools/recon-ng
""".strip()
        + "\n",
        encoding="utf-8",
    )

    outputs = {
        "git submodule status -- tools/EyeWitness": CommandResult(0, "+123abc tools/EyeWitness (heads/main)\n", ""),
        "git status --short -- tools/EyeWitness": CommandResult(0, " m tools/EyeWitness\n", ""),
        "git submodule status -- tools/recon-ng": CommandResult(0, "-123abc tools/recon-ng\n", ""),
        "git status --short -- tools/recon-ng": CommandResult(0, "", ""),
    }

    report = collect_tool_health_report(tmp_path, run=lambda cmd: outputs.get(cmd, CommandResult(0, "", "")))

    assert report["overall_status"] == "degraded"
    eye = next(item for item in report["items"] if item["tool_path"] == "tools/EyeWitness")
    rec = next(item for item in report["items"] if item["tool_path"] == "tools/recon-ng")
    assert eye["state"] == "dirty"
    assert rec["state"] == "missing"


def test_render_markdown_contains_summary_section():
    report = {
        "generated_at": "2026-04-11T00:00:00Z",
        "overall_status": "watch",
        "items": [
            {
                "tool_path": "tools/EyeWitness",
                "state": "dirty",
                "severity": "medium",
                "detail": "worktree has local changes",
                "recommendation": "isolate changes",
            }
        ],
    }

    md = render_markdown(report)
    assert "Tool Health Report" in md
    assert "Overall status" in md
    assert "tools/EyeWitness" in md
