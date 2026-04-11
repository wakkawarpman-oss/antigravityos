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

## Master Plan Execution Update (Freemium enrichment fallback lane)
- Added explicit freemium module policy in registry (`shodan`, `censys`) with baseline fallback preset support.
- Worker task build now degrades gracefully on missing freemium credentials and auto-schedules baseline modules without blocking.
- Adapter error model now includes `freemium_degraded`; dispatcher classifies missing-credential/freemium events as non-blocking task skips.
- Runtime summary contract now includes `freemium_degraded` counter and preserves failure semantics for strict blockers only.
- Added focused tests for freemium fallback scheduling, adapter credential gates, and runtime summary compatibility.

## Master Plan Execution Update (Strict module resolution + export parity)
- Module/preset resolution is now fail-fast: unknown module or preset names raise explicit resolver errors instead of silent skips.
- CLI path now surfaces module-resolution errors as parser-level actionable feedback.
- Added resolver regression tests for unknown module/preset handling.
- Added cross-export parity regression test to enforce observed-data consistency between runtime JSON and STIX artifacts inside ZIP evidence packs.

## Master Plan Execution Update (Process lifecycle observability)
- Added process-lifecycle counters for CLI timeout handling: `timeout_events`, `kill_attempted`, `kill_succeeded`, `kill_failed`.
- Timeout cleanup now emits explicit stderr marker when process-group kill fails (`[timeout][kill_failed]`) to improve postmortem visibility.
- Added dedicated regression tests for process-group kill success/failure and timeout marker behavior.

## Master Plan Execution Update (OPSEC proxy propagation hardening)
- Fixed adapter proxy forwarding in `amass`, `subfinder`, and `shodan` CLI paths to prevent strict-mode false failures and potential proxy bypass paths.
- Added dedicated regression tests validating proxy propagation for those adapters via shared `run_cli` helper.

## Master Plan Execution Update (TUI UX acceleration)
- Added high-speed navigation shortcuts for cockpit views (`[` / `]`) and direct export shortcuts (`s` for STIX, `z` for ZIP).
- Expanded command aliases for terminal operators: direct `manual|aggregate|chain`, plus `clear`, `exit`, and `view next|prev`.
- Updated in-cockpit command legend/help text to match new controls.
- Added TUI regression tests for alias execution and view-cycle behavior.

## Master Plan Execution Update (Adapter-wide OPSEC matrix)
- Added registry-wide OPSEC matrix tests to verify all registered adapters enforce proxy requirement when strict policy is enabled.
- Added registry-wide initialization coverage to verify all registered adapters can initialize under strict mode with an explicit proxy.
- This closes the previous gap from spot-check OPSEC tests toward full adapter-surface policy validation.

## Master Plan Execution Update (Timeout burst lifecycle acceptance)
- Added explicit process-lifecycle acceptance evaluator for timeout cleanup invariants and thresholds.
- Added burst regression test (25 timeout events) that validates cleanup metrics: attempts, successes, failures, and success ratio.
- Integrated this burst acceptance check into `tests/test_adapter_capability_matrix.py`, so it runs in the targeted release-guard test pack.

## Master Plan Execution Update (Lifecycle telemetry in runner artifacts)
- Aggregate, chain, and manual runners now reset process-lifecycle counters at run start and attach lifecycle metrics into `RunResult.extra.process_lifecycle`.
- Added regression assertions in runner test suites to ensure lifecycle telemetry is present and shape-stable in result metadata.
- Added integration runtime smoke assertions so lifecycle telemetry visibility is enforced in manual and aggregate execution flows, not only unit-level runner tests.

## Master Plan Execution Update (Plan drift control loop)
- Added automated master-plan drift report (`make plan-drift-report`) that compares `MASTER_PLAN_2000_WORDS.md` against `Master Plan Execution Update` blocks in checkpoint status.
- Added machine-readable and markdown report artifacts (`.cache/reports/plan-drift-report.json`, `.cache/reports/plan-drift-report.md`).
- Synchronized `MASTER_PLAN_2000_WORDS.md` with all currently delivered execution-update blocks to eliminate strategy-vs-reality drift.
- Added blocking `release-guard` check `plan_drift_sync` so release decisioning fails closed on master-plan drift.
- Added scheduled CI workflow `.github/workflows/plan-drift-report.yml` to publish drift artifacts and fail on non-`ok` drift status.
