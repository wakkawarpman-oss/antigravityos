from __future__ import annotations

from plan_drift_report import collect_plan_drift_report, render_markdown


def test_collect_plan_drift_report_flags_missing_updates(tmp_path):
    master = tmp_path / "MASTER_PLAN_2000_WORDS.md"
    checkpoint = tmp_path / "CHECKPOINT_STATUS_2026-04-11.md"

    master.write_text("# Master Plan\n\n- pre-release governance\n", encoding="utf-8")
    checkpoint.write_text(
        "\n".join(
            [
                "# Checkpoint",
                "## Master Plan Execution Update (Pre-release governance)",
                "## Master Plan Execution Update (Tool health lane)",
            ]
        ),
        encoding="utf-8",
    )

    report = collect_plan_drift_report(str(master), str(checkpoint))

    assert report["drift_status"] == "drift"
    assert report["missing_in_master_plan"] == ["Tool health lane"]


def test_collect_plan_drift_report_ok_when_all_updates_are_present(tmp_path):
    master = tmp_path / "MASTER_PLAN_2000_WORDS.md"
    checkpoint = tmp_path / "CHECKPOINT_STATUS_2026-04-11.md"

    master.write_text("# Master Plan\n\nPre-release governance\nTool health lane\n", encoding="utf-8")
    checkpoint.write_text(
        "\n".join(
            [
                "# Checkpoint",
                "## Master Plan Execution Update (Pre-release governance)",
                "## Master Plan Execution Update (Tool health lane)",
            ]
        ),
        encoding="utf-8",
    )

    report = collect_plan_drift_report(str(master), str(checkpoint))

    assert report["drift_status"] == "ok"
    assert report["missing_in_master_plan"] == []


def test_render_markdown_contains_status_and_sections():
    markdown = render_markdown(
        {
            "generated_at": "2026-04-11T00:00:00Z",
            "drift_status": "drift",
            "checkpoint_updates": ["A", "B"],
            "missing_in_master_plan": ["B"],
        }
    )

    assert "Plan Drift Report" in markdown
    assert "Drift status" in markdown
    assert "Missing In Master Plan" in markdown
    assert "- B" in markdown