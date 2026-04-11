from __future__ import annotations

from pathlib import Path

from release_guard import _parse_drift_paths, run_release_guard


def test_parse_drift_paths_extracts_porcelain_paths():
    output = " M src/run_discovery.py\n?? tests/new_test.py\n"
    paths = _parse_drift_paths(output)

    assert paths == ["src/run_discovery.py", "tests/new_test.py"]


def test_run_release_guard_passes_for_clean_happy_path(tmp_path: Path):
    result = run_release_guard(
        repo_root=tmp_path,
        targeted_commands=["echo targeted-ok"],
        full_guard_command="echo guard-ok",
        drift_command="printf ''",
        block_commands=[("opsec_policy", "echo opsec-ok"), ("contract_compatibility", "echo contract-ok"), ("export_consistency", "echo export-ok")],
    )

    assert result.ok is True
    assert result.drift_paths == []
    assert all(stage.status == "pass" for stage in result.stages)
    assert result.direct_verdict == "go"
    assert result.asymmetric_verdict == "accept"
    assert result.post_block_decision == "go"
    assert result.selected_method
    assert result.method_scores


def test_run_release_guard_fails_when_drift_detected(tmp_path: Path):
    result = run_release_guard(
        repo_root=tmp_path,
        targeted_commands=["echo targeted-ok"],
        full_guard_command="echo guard-ok",
        drift_command="printf ' M src/registry.py\\n'",
        block_commands=[("opsec_policy", "echo opsec-ok"), ("contract_compatibility", "echo contract-ok"), ("export_consistency", "echo export-ok")],
    )

    assert result.ok is False
    assert "src/registry.py" in result.drift_paths
    assert any(stage.name == "drift_check" and stage.status == "fail" for stage in result.stages)
    assert result.residual_risks
    assert result.direct_verdict == "no-go"
    assert result.post_block_decision == "no-go"


def test_run_release_guard_rejects_unmitigated_high_impact_risk(tmp_path: Path):
    result = run_release_guard(
        repo_root=tmp_path,
        targeted_commands=["echo targeted-ok"],
        full_guard_command="echo guard-ok",
        drift_command="printf ''",
        block_commands=[("opsec_policy", "false"), ("contract_compatibility", "echo contract-ok"), ("export_consistency", "echo export-ok")],
    )

    assert result.ok is False
    assert result.asymmetric_verdict == "reject"
    assert any(risk.category == "opsec" and risk.status == "unmitigated" for risk in result.asymmetric_risks)


def test_run_release_guard_flags_plan_drift_sync_failure(tmp_path: Path):
    result = run_release_guard(
        repo_root=tmp_path,
        targeted_commands=["echo targeted-ok"],
        full_guard_command="echo guard-ok",
        drift_command="printf ''",
        block_commands=[
            ("opsec_policy", "echo opsec-ok"),
            ("contract_compatibility", "echo contract-ok"),
            ("export_consistency", "echo export-ok"),
            ("plan_drift_sync", "false"),
        ],
    )

    assert result.ok is False
    assert result.post_block_decision == "no-go"
    assert any(stage.name == "plan_drift_sync" and stage.status == "fail" for stage in result.stages)
    assert any("Master plan drift check failed" in risk for risk in result.residual_risks)
