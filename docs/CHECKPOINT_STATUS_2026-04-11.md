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
