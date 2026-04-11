from __future__ import annotations

from pathlib import Path

from tools_cleanup import CleanupAction, CommandResult, apply_cleanup_actions, plan_cleanup_actions


def test_plan_cleanup_actions_detects_missing_and_dirty(tmp_path: Path):
    (tmp_path / ".gitmodules").write_text(
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
        "git ls-files --stage -- tools": CommandResult(
            0,
            "160000 abc 0\ttools/EyeWitness\n160000 def 0\ttools/recon-ng\n",
            "",
        ),
        "git submodule status -- tools/EyeWitness": CommandResult(0, "-abc123 tools/EyeWitness\n", ""),
        "git submodule status -- tools/recon-ng": CommandResult(0, " abc123 tools/recon-ng\n", ""),
        "git status --short -- tools/recon-ng": CommandResult(0, " m tools/recon-ng\n", ""),
    }

    actions = plan_cleanup_actions(tmp_path, run=lambda cmd: outputs.get(cmd, CommandResult(0, "", "")))

    assert any(a.kind == "init" and a.tool_path == "tools/EyeWitness" for a in actions)
    reset_action = next(a for a in actions if a.kind == "reset" and a.tool_path == "tools/recon-ng")
    assert "clean -fdx" in reset_action.command


def test_apply_cleanup_actions_respects_allow_destructive_flag(tmp_path: Path):
    actions = [
        CleanupAction(kind="init", tool_path="tools/EyeWitness", command="echo init", reason="missing"),
        CleanupAction(kind="reset", tool_path="tools/recon-ng", command="echo reset", reason="dirty"),
    ]

    result = apply_cleanup_actions(
        actions,
        repo_root=tmp_path,
        run=lambda cmd: CommandResult(0, "ok", ""),
        allow_destructive=False,
    )

    assert result[0]["status"] == "applied"
    assert result[1]["status"] == "skipped"
