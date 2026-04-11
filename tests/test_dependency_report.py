from __future__ import annotations

from dependency_report import CommandResult, collect_dependency_report, render_markdown


def test_collect_dependency_report_pass_lane_when_no_blockers():
    outputs = {
        "python -m pip list --outdated --format=json": CommandResult(0, "[]", ""),
        "python -m pip check": CommandResult(0, "No broken requirements found.", ""),
        "npm outdated --json": CommandResult(1, "{}", ""),
        "npm audit --omit=dev --audit-level=high --json": CommandResult(
            0,
            '{"metadata": {"vulnerabilities": {"high": 0, "critical": 0}}}',
            "",
        ),
    }

    report = collect_dependency_report(run=lambda command: outputs[command])

    assert report["kpi"]["core_dependency_lane_status"] == "pass"
    assert report["kpi"]["blockers"]["pip_check_failed"] is False


def test_collect_dependency_report_fails_lane_when_high_vulns_or_pip_check_fail():
    outputs = {
        "python -m pip list --outdated --format=json": CommandResult(0, "[]", ""),
        "python -m pip check": CommandResult(1, "", "broken"),
        "npm outdated --json": CommandResult(1, "{}", ""),
        "npm audit --omit=dev --audit-level=high --json": CommandResult(
            1,
            '{"metadata": {"vulnerabilities": {"high": 2, "critical": 1}}}',
            "",
        ),
    }

    report = collect_dependency_report(run=lambda command: outputs[command])

    assert report["kpi"]["core_dependency_lane_status"] == "fail"
    assert report["kpi"]["blockers"]["pip_check_failed"] is True
    assert report["kpi"]["blockers"]["npm_high"] == 2
    assert report["kpi"]["blockers"]["npm_critical"] == 1


def test_render_markdown_contains_core_sections():
    report = {
        "generated_at": "2026-04-11T00:00:00Z",
        "python": {"outdated_count": 1, "pip_check": {"status": "pass"}},
        "node": {"outdated_count": 2},
        "kpi": {
            "core_dependency_lane_status": "pass",
            "policy": "Block release on pip_check fail or npm high/critical vulnerabilities",
            "blockers": {"npm_high": 0, "npm_critical": 0},
        },
    }

    markdown = render_markdown(report)

    assert "Weekly Dependency Report" in markdown
    assert "Core lane status" in markdown
    assert "Python" in markdown
    assert "Node" in markdown
