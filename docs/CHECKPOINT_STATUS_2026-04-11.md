# Checkpoint Status 2026-04-11

## Production Gate
- Status: PRODUCTION READY

## Audit Snapshot
- Parse success: 63.3% (19/30)
- Tests: 242/242
- Rudiments: 0
- Silent fails: 0
- Stability: 95%

Source: `.cache/audit_report.json`

## Load Snapshot
- Requests: 1000/1000 successful
- Success rate: 100.0%
- Avg response: 166ms
- P95 response: 199ms

Source: `.cache/stress_test_report.json`

## Contract Compatibility Rule (Phase 5)
- Canonical provenance namespace: `urn:hanna:contract-provenance:v1`.
- Contract versions are now explicit in all consumer-facing export surfaces:
	- runtime summary / metadata: `adapter_result_schema_version`
	- ZIP manifest: `provenance.contracts.run_result_schema_version`, `provenance.contracts.adapter_result_schema_version`
	- STIX note: `x_hanna_provenance.contracts.*`
- Consumer policy: if provenance namespace is unknown, treat artifact as incompatible and stop parsing.
- CI guardrail: `quality-gates` workflow runs `python scripts/ci_verify_contract_provenance_smoke.py` to fail fast on provenance contract drift.
- Diagnostic lane: non-blocking negative smoke runs with unknown namespace (`urn:hanna:contract-provenance:v99`) in expect-fail mode to verify fail-closed behavior remains active.
- Deploy gate policy: `Production Deploy` now always requires `contract_provenance`; optional strict mode (`HANNA_DEPLOY_REQUIRE_FULL_REHEARSAL`) also requires `full_rollout_rehearsal`.
- Bridge preflight policy: `legacy_bridge_api_token` is now an always-visible preflight check; it hard-fails only when `HANNA_LEGACY_BRIDGE_ENABLED=1` and `OSINT_API_TOKEN` is missing.
- Prelaunch now runs `Contract provenance smoke` unconditionally and publishes `contract-provenance-smoke.json`; `checks.contract_provenance` is based on this smoke and further tightened by rehearsal provenance when full rehearsal is enabled.

## Master Plan Execution Update (Pre-release governance)
- Mandatory post-block control layer is implemented in `release_guard`.
- Direct logic checks now include: targeted tests, full guard, `opsec_policy`, `contract_compatibility`, `export_consistency`, and drift check.
- Asymmetric risk register and KPI method arbitration are part of guard output and release decisioning.
- CI enforcement updated: quality gates now execute `make release-guard` and workflows are aligned with the active `main` branch.

## Master Plan Execution Update (Dependency reporting)
- Added weekly dependency report automation via GitHub Actions schedule (`dependency-report` workflow).
- Added machine-readable and Markdown dependency snapshots (`.cache/reports/dependency-weekly.json`, `.cache/reports/dependency-weekly.md`).
- Added local operator command `make dependency-report` for on-demand report generation.

## Master Plan Execution Update (Tool health lane)
- Added non-blocking tool-health reporting module for tool/submodule drift visibility.
- Added local command `make tool-health-report` for operator diagnostics.
- Added scheduled CI workflow (`tool-health`) with artifact export, intentionally non-blocking for core release lane.

## Master Plan Execution Update (Tools cleanup lane)
- Added isolated tools-cleanup utility with dry-run plan (`make tools-cleanup-plan`) and apply mode (`make tools-cleanup-apply`).
- Cleanup actions are scoped to tool/submodule drift and intentionally separated from core release lane logic.
- Optional external checkout `tools/tookie-osint` is now ignored in git status to reduce non-core operational noise.
