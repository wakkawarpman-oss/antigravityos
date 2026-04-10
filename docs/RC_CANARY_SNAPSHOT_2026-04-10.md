# RC Canary Snapshot — 2026-04-10

## Scope
- Step: full-pipeline canary rehearsal in strict-by-gate-only mode.
- Revision: `014a913`.
- Mode flag: `HANNA_PRELAUNCH_STRICT_BY_GATE=1`.
- Required checks: `preflight,focused_regression,tor_policy`.

## Profiles Executed

### 1) Tor-on profile
- Output bundle: `.cache/prelaunch/canary-tor-on/`
- Key env:
  - `HANNA_TOR_ENABLED=1`
  - `HANNA_TOR_PROXY_URL=socks5h://127.0.0.1:9050`
  - `HANNA_TOR_REQUIRE_SOCKS5H=1`
  - `HANNA_TOR_CONTROL_ENABLED=1`
  - `HANNA_TOR_CONTROL_PORT=9051`
- Full rehearsal flags:
  - `HANNA_RUN_LIVE_SMOKE=1`
  - `HANNA_RUN_FULL_REHEARSAL=1`
  - `HANNA_FULL_REHEARSAL_MODULES=pd-infra-quick`

Result:
- `final-summary.json` overall_status: `fail`
- `gate-result.json` valid: `true`
- `gate-result.json` required_check_failures:
  - focused_regression: status is `fail`, expected `pass`
- strict-by-gate exit: non-zero (fail)

### 2) Tor-off profile
- Output bundle: `.cache/prelaunch/canary-tor-off/`
- Key env:
  - `HANNA_TOR_ENABLED=0`
  - `HANNA_TOR_PROXY_URL=socks5://127.0.0.1:9050`
  - `HANNA_TOR_REQUIRE_SOCKS5H=1`
- Full rehearsal flags:
  - `HANNA_RUN_LIVE_SMOKE=1`
  - `HANNA_RUN_FULL_REHEARSAL=1`
  - `HANNA_FULL_REHEARSAL_MODULES=pd-infra-quick`

Result:
- `final-summary.json` overall_status: `fail`
- `gate-result.json` valid: `true`
- `gate-result.json` required_check_failures:
  - focused_regression: status is `fail`, expected `pass`
- strict-by-gate exit: non-zero (fail)

## Observed Blockers
1. Focused regression step fails in prelaunch bundles because the venv python used by the script cannot import pytest (`No module named pytest`).
2. Chain rehearsal/live smoke fail due runtime crash in chain runner path (`TypeError: object of type 'NoneType' has no len()` around `len(clusters)` logging).
3. Tor policy gate itself behaves as expected in both profiles:
   - Tor-on: `tor_policy.status=pass`
   - Tor-off: `tor_policy.status=pass` (policy disabled context)

## Rotation Event Evidence
- Targeted verification path passed:
  - `tests/test_tor_policy.py::test_tui_scheduler_event_emits_tor_rotation_messages`
  - `tests/test_scheduler.py::test_scheduler_emits_tor_rotation_events_for_empty_dispatch`
- Result: 2 passed.

## RC Verdict
- Decision: **RED (not ready for RC tag)**.
- Reason: required check `focused_regression` fails in both canary profiles under strict-by-gate contract.

## Required Fixes Before RC
1. Stabilize focused regression execution environment used by prelaunch script (`pytest` availability for selected python runtime).
2. Fix chain runner null-cluster crash path before full rehearsal/live smoke can be considered reliable.
3. Re-run both canary profiles and require empty `required_check_failures` in `gate-result.json`.

## Rerun Update — 2026-04-10

### Strict-by-gate rerun (post-fix)
- Tor-on bundle: `.cache/prelaunch/20260410T200817/`
- Tor-off bundle: `.cache/prelaunch/20260410T200824/`
- Required checks: `preflight,focused_regression,tor_policy`

Result:
- Tor-on `gate-result.json`:
  - `overall_status: pass`
  - `required_check_failures: []`
- Tor-off `gate-result.json`:
  - `overall_status: pass`
  - `required_check_failures: []`
- `final-summary.json`:
  - Tor-on `tor_policy.status: pass` (`tor_enabled: true`)
  - Tor-off `tor_policy.status: pass` (`tor_enabled: false`)

Focused regression verification (targeted suite used by remediation):
- `tests/test_integration_runtime_smokes.py`
- `tests/test_discovery_engine.py`
- `tests/test_chain_runner.py`
- Result: `42 passed`.

## Updated RC Verdict
- Decision: **GREEN under strict-by-gate contract**.
- Evidence: both rerun bundles have `overall_status=pass` and no required-check failures.
- Residual note: Tor policy warns that SOCKS 9050 is host-published; keep only if host access is intentionally required.

## RC Freeze Record
- Commit hash: `014a913`
- Tag: `rc-20260410`
- Archive: `rc-20260410-bundle.tar.gz`

Canonical GREEN bundles:
- `.cache/prelaunch/20260410T200817/`
- `.cache/prelaunch/20260410T200824/`

Required artifacts verified in both bundles:
- `final-summary.json`
- `gate-result.json`
- `full-rehearsal.verification.json`

Final freeze verdict:
- `20260410T200817`: **GREEN**
- `20260410T200824`: **GREEN**

## Post-Freeze Follow-up — Phase 2 Coverage Commit

- Commit hash: `f472bbe`
- Tag: `rc-20260410-p2`
- Strict canary bundle: `.cache/prelaunch/20260410T210327/`
- Analyzer command mode: `scripts/analyze_release_verdict_with_logs.py --tor-policy --rc`
- Analyzer rc exit code: `0`

Result:
- `final-summary.json` + `gate-result.json` satisfy strict gate contract.
- Follow-up freeze verdict for this episode: **GREEN**.
