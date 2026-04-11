from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_METHODS: dict[str, dict[str, float]] = {
    "conservative_patch": {
        "reliability_gain": 0.85,
        "security_gain": 0.85,
        "regression_safety": 0.9,
        "time_efficiency": 0.45,
        "rollback_simplicity": 0.9,
        "observability_gain": 0.7,
    },
    "standard_patch": {
        "reliability_gain": 0.75,
        "security_gain": 0.75,
        "regression_safety": 0.75,
        "time_efficiency": 0.7,
        "rollback_simplicity": 0.75,
        "observability_gain": 0.75,
    },
    "aggressive_refactor": {
        "reliability_gain": 0.7,
        "security_gain": 0.7,
        "regression_safety": 0.45,
        "time_efficiency": 0.5,
        "rollback_simplicity": 0.4,
        "observability_gain": 0.85,
    },
}

DEFAULT_WEIGHTS: dict[str, float] = {
    "reliability_gain": 0.24,
    "security_gain": 0.24,
    "regression_safety": 0.2,
    "time_efficiency": 0.1,
    "rollback_simplicity": 0.12,
    "observability_gain": 0.1,
}

RELEASE_KPI_THRESHOLD = 0.72

DEFAULT_BLOCK_COMMANDS: list[tuple[str, str]] = [
    ("opsec_policy", "pytest -q tests/test_opsec.py tests/test_opsec_redaction.py"),
    (
        "contract_compatibility",
        "pytest -q tests/test_cli_contracts.py tests/test_adapter_result_schema.py tests/test_p4_schema_contracts.py",
    ),
    (
        "export_consistency",
        "pytest -q tests/test_exporters.py tests/test_stix_bundle_completeness.py tests/test_rehearsal_artifact_verifier.py",
    ),
]


@dataclass
class StageResult:
    name: str
    command: str
    status: str
    exit_code: int
    output_tail: str = ""


@dataclass
class MethodScore:
    name: str
    score: float
    weighted_components: dict[str, float] = field(default_factory=dict)
    penalties: float = 0.0


@dataclass
class AsymmetricRisk:
    risk_id: str
    category: str
    impact: str
    likelihood: str
    detectability: str
    mitigation_cost: str
    status: str
    detail: str


@dataclass
class ReleaseGuardResult:
    ok: bool
    stages: list[StageResult] = field(default_factory=list)
    drift_paths: list[str] = field(default_factory=list)
    residual_risks: list[str] = field(default_factory=list)
    direct_verdict: str = "no-go"
    asymmetric_verdict: str = "reject"
    kpi_threshold: float = RELEASE_KPI_THRESHOLD
    method_scores: list[MethodScore] = field(default_factory=list)
    selected_method: str = ""
    selected_method_score: float = 0.0
    post_block_decision: str = "no-go"
    asymmetric_risks: list[AsymmetricRisk] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "stages": [
                {
                    "name": stage.name,
                    "command": stage.command,
                    "status": stage.status,
                    "exit_code": stage.exit_code,
                    "output_tail": stage.output_tail,
                }
                for stage in self.stages
            ],
            "drift_paths": self.drift_paths,
            "residual_risks": self.residual_risks,
            "post_block_analysis": {
                "direct_verdict": self.direct_verdict,
                "asymmetric_verdict": self.asymmetric_verdict,
                "kpi_threshold": self.kpi_threshold,
                "selected_method": self.selected_method,
                "selected_method_score": self.selected_method_score,
                "post_block_decision": self.post_block_decision,
                "asymmetric_risk_register": [
                    {
                        "risk_id": risk.risk_id,
                        "category": risk.category,
                        "impact": risk.impact,
                        "likelihood": risk.likelihood,
                        "detectability": risk.detectability,
                        "mitigation_cost": risk.mitigation_cost,
                        "status": risk.status,
                        "detail": risk.detail,
                    }
                    for risk in self.asymmetric_risks
                ],
                "method_ranking": [
                    {
                        "name": score.name,
                        "score": score.score,
                        "penalties": score.penalties,
                        "weighted_components": score.weighted_components,
                    }
                    for score in self.method_scores
                ],
            },
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
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def _parse_drift_paths(status_output: str) -> list[str]:
    paths: list[str] = []
    for line in status_output.splitlines():
        if not line.strip():
            continue
        # porcelain lines usually look like "XY path" or "X path".
        if len(line) >= 3 and line[2] == " ":
            paths.append(line[3:].strip())
        elif len(line) >= 2 and line[1] == " ":
            paths.append(line[2:].strip())
        else:
            paths.append(line.strip())
    return [path for path in paths if path]


def _score_methods(risk_penalty: float) -> list[MethodScore]:
    scores: list[MethodScore] = []
    for method_name, components in DEFAULT_METHODS.items():
        weighted_components: dict[str, float] = {}
        for key, value in components.items():
            weighted_components[key] = value * DEFAULT_WEIGHTS[key]
        penalty_multiplier = 1.0
        if method_name == "aggressive_refactor":
            penalty_multiplier = 1.4
        elif method_name == "standard_patch":
            penalty_multiplier = 1.1
        penalties = risk_penalty * penalty_multiplier
        score = round(sum(weighted_components.values()) - penalties, 4)
        scores.append(
            MethodScore(
                name=method_name,
                score=score,
                weighted_components={key: round(value, 4) for key, value in weighted_components.items()},
                penalties=round(penalties, 4),
            )
        )
    scores.sort(key=lambda item: item.score, reverse=True)
    return scores


def _calculate_risk_penalty(stages: list[StageResult], residual_risks: list[str]) -> float:
    penalty = 0.0
    failing = [stage for stage in stages if stage.status != "pass"]
    for stage in failing:
        if stage.name in {"full_guard", "contract_compatibility", "opsec_policy", "export_consistency"}:
            penalty += 0.35
        elif stage.name == "drift_check":
            penalty += 0.25
        else:
            penalty += 0.2
    penalty += min(len(residual_risks) * 0.05, 0.2)
    return round(min(penalty, 0.95), 4)


def _build_asymmetric_risk_register(stages: list[StageResult], residual_risks: list[str]) -> list[AsymmetricRisk]:
    by_name = {stage.name: stage for stage in stages}
    register: list[AsymmetricRisk] = []

    def _status(name: str) -> str:
        stage = by_name.get(name)
        if not stage:
            return "unknown"
        return "mitigated" if stage.status == "pass" else "unmitigated"

    register.append(
        AsymmetricRisk(
            risk_id="R-OPSEC-001",
            category="opsec",
            impact="high",
            likelihood="medium",
            detectability="high",
            mitigation_cost="medium",
            status=_status("opsec_policy"),
            detail="False-green is unacceptable for OPSEC; leaks have asymmetric operational damage.",
        )
    )
    register.append(
        AsymmetricRisk(
            risk_id="R-CONTRACT-001",
            category="contract",
            impact="high",
            likelihood="medium",
            detectability="high",
            mitigation_cost="low",
            status=_status("contract_compatibility"),
            detail="Contract drift breaks downstream consumers and evidence parsing compatibility.",
        )
    )
    register.append(
        AsymmetricRisk(
            risk_id="R-EXPORT-001",
            category="data_integrity",
            impact="high",
            likelihood="medium",
            detectability="medium",
            mitigation_cost="medium",
            status=_status("export_consistency"),
            detail="Export inconsistency corrupts release evidence and can invalidate pre-release bundle trust.",
        )
    )
    register.append(
        AsymmetricRisk(
            risk_id="R-DRIFT-001",
            category="release_control",
            impact="medium",
            likelihood="high",
            detectability="high",
            mitigation_cost="low",
            status=_status("drift_check"),
            detail="Workspace drift increases probability of partial/accidental push and rollback complexity.",
        )
    )

    if residual_risks:
        register.append(
            AsymmetricRisk(
                risk_id="R-RESIDUAL-001",
                category="execution",
                impact="medium",
                likelihood="medium",
                detectability="high",
                mitigation_cost="low",
                status="unmitigated",
                detail="; ".join(residual_risks),
            )
        )
    return register


def run_release_guard(
    repo_root: Path,
    targeted_commands: list[str],
    full_guard_command: str,
    drift_command: str,
    block_commands: list[tuple[str, str]],
) -> ReleaseGuardResult:
    stages: list[StageResult] = []
    residual_risks: list[str] = []

    for idx, command in enumerate(targeted_commands, start=1):
        code, output = _run(command, repo_root)
        status = "pass" if code == 0 else "fail"
        stages.append(
            StageResult(
                name=f"targeted_tests_{idx}",
                command=command,
                status=status,
                exit_code=code,
                output_tail=output[-4000:],
            )
        )
        if code != 0:
            residual_risks.append("Targeted regression checks failed; pushing now can ship module-level regressions.")

    guard_code, guard_output = _run(full_guard_command, repo_root)
    guard_status = "pass" if guard_code == 0 else "fail"
    stages.append(
        StageResult(
            name="full_guard",
            command=full_guard_command,
            status=guard_status,
            exit_code=guard_code,
            output_tail=guard_output[-4000:],
        )
    )
    if guard_code != 0:
        residual_risks.append("System guard failed; contract, dependency, or workflow drift may reach release.")

    for check_name, command in block_commands:
        code, output = _run(command, repo_root)
        status = "pass" if code == 0 else "fail"
        stages.append(
            StageResult(
                name=check_name,
                command=command,
                status=status,
                exit_code=code,
                output_tail=output[-4000:],
            )
        )
        if code != 0:
            if check_name == "opsec_policy":
                residual_risks.append("OPSEC policy compliance failed; potential leak paths are not fully controlled.")
            elif check_name == "contract_compatibility":
                residual_risks.append("Contract compatibility failed; consumer-facing schemas may be broken.")
            elif check_name == "export_consistency":
                residual_risks.append("Export consistency failed; evidence pack integrity is not guaranteed.")
            else:
                residual_risks.append(f"Blocking check failed: {check_name}.")

    drift_code, drift_output = _run(drift_command, repo_root)
    drift_paths = _parse_drift_paths(drift_output) if drift_code == 0 else []
    drift_ok = drift_code == 0 and not drift_paths
    stages.append(
        StageResult(
            name="drift_check",
            command=drift_command,
            status="pass" if drift_ok else "fail",
            exit_code=drift_code,
            output_tail=drift_output[-4000:],
        )
    )
    if not drift_ok:
        residual_risks.append("Core workspace drift detected; push may include uncontrolled or partial changes.")

    direct_verdict = "go" if all(stage.status == "pass" for stage in stages) else "no-go"

    high_impact_risk = any(
        stage.name in {"full_guard", "drift_check", "opsec_policy", "contract_compatibility", "export_consistency"}
        and stage.status != "pass"
        for stage in stages
    )
    asymmetric_risks = _build_asymmetric_risk_register(stages=stages, residual_risks=residual_risks)
    asymmetric_verdict = "accept" if not any(risk.status == "unmitigated" and risk.impact == "high" for risk in asymmetric_risks) else "reject"

    risk_penalty = _calculate_risk_penalty(stages, residual_risks)
    method_scores = _score_methods(risk_penalty=risk_penalty)
    selected = method_scores[0] if method_scores else MethodScore(name="", score=0.0)
    selected_method = selected.name
    selected_method_score = selected.score

    post_block_decision = "go" if (
        direct_verdict == "go"
        and asymmetric_verdict == "accept"
        and selected_method_score >= RELEASE_KPI_THRESHOLD
    ) else "no-go"

    ok = post_block_decision == "go"
    return ReleaseGuardResult(
        ok=ok,
        stages=stages,
        drift_paths=drift_paths,
        residual_risks=residual_risks,
        direct_verdict=direct_verdict,
        asymmetric_verdict=asymmetric_verdict,
        kpi_threshold=RELEASE_KPI_THRESHOLD,
        method_scores=method_scores,
        selected_method=selected_method,
        selected_method_score=selected_method_score,
        post_block_decision=post_block_decision,
        asymmetric_risks=asymmetric_risks,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Unified release guard: targeted tests -> full guard -> drift check. "
            "Use this before any push."
        )
    )
    parser.add_argument(
        "--targeted-command",
        action="append",
        default=[],
        help="Repeatable targeted test command. If omitted, a default focused test pack is used.",
    )
    parser.add_argument(
        "--full-guard-command",
        default="make sprint-phase-guard",
        help="Full system guard command.",
    )
    parser.add_argument(
        "--drift-command",
        default="git status --porcelain --untracked-files=all -- . ':(exclude)tools/**'",
        help="Command that must return no output when core workspace has no drift.",
    )
    parser.add_argument(
        "--block-command",
        action="append",
        default=[],
        help="Repeatable blocking check in form name=command.",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional report path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    targeted_commands = args.targeted_command or [
        "pytest -q tests/test_dnsx_gau_adapters.py tests/test_adapter_capability_matrix.py tests/test_preflight.py"
    ]
    block_commands: list[tuple[str, str]] = []
    if args.block_command:
        for raw in args.block_command:
            if "=" not in raw:
                raise SystemExit(f"invalid --block-command format: {raw}. expected name=command")
            name, command = raw.split("=", 1)
            block_commands.append((name.strip(), command.strip()))
    else:
        block_commands = list(DEFAULT_BLOCK_COMMANDS)

    result = run_release_guard(
        repo_root=repo_root,
        targeted_commands=targeted_commands,
        full_guard_command=args.full_guard_command,
        drift_command=args.drift_command,
        block_commands=block_commands,
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
