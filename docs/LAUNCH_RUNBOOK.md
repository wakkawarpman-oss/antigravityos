# HANNA Launch Runbook

This runbook defines the minimum operator flow before a controlled rollout.

## 1. Environment Freeze

Run from the repository root:

```bash
cd /Users/admin/Desktop/hanna-v3-2-clean
./scripts/setup_hanna.sh
```

Canonical cockpit launch for macOS and the VS Code integrated terminal:

```bash
./scripts/hanna ui --plain
```

Before rollout, freeze these surfaces:

- canonical launcher: `./scripts/hanna`
- legacy compatibility launchers: `python3 run_discovery.py`, `python3 hanna_ui.py`
- export contract: HTML + metadata + STIX + ZIP
- reset semantics: preserve or remove generated runtime state only through `rs`

### Contract Compatibility Rule (Consumers)

External consumers must treat contract provenance as the canonical compatibility gate.

1. Read `adapter_result_schema_version` from runtime summary and metadata payloads.
2. Read `provenance.namespace` and `provenance.contracts` from ZIP `manifest.json`.
3. Read `x_hanna_provenance` from STIX `note` objects.
4. Accept payloads only when namespace is `urn:hanna:contract-provenance:v1` and known schema versions are supported.
5. If namespace is unknown, fail closed (mark artifact as incompatible) rather than guessing field semantics.

## 2. Mandatory Pre-Launch Check

Run the bundled verification workflow:

```bash
./scripts/prelaunch_check.sh
```

This creates a review bundle under `.cache/prelaunch/<timestamp>/` containing:

- root wrapper smoke outputs
- canonical list/preflight JSON
- smart summary smoke output
- focused regression output
- final machine-readable verdict in `final-summary.json`

Canonical output directory variable for prelaunch bundles:

```bash
HANNA_PRELAUNCH_OUTPUT_DIR=/path/to/.cache/prelaunch/release-rc
```

`HANNA_PRELAUNCH_OUT_DIR` may still appear in legacy examples, but `HANNA_PRELAUNCH_OUTPUT_DIR` is the primary variable for release procedures.

For CI or external automation, read only `final-summary.json` through the gate helper:

```bash
./scripts/prelaunch_gate.sh .cache/prelaunch/<timestamp>/final-summary.json
```

If CI must require a successful full rehearsal, not just a passing overall bundle:

```bash
./scripts/prelaunch_gate.sh \
	.cache/prelaunch/<timestamp>/final-summary.json \
	--require-check full_rollout_rehearsal
```

If you prefer `make` in CI:

```bash
make prelaunch-gate \
	SUMMARY=.cache/prelaunch/<timestamp>/final-summary.json \
	ARGS='--require-check full_rollout_rehearsal'
```

### Canonical Verdict Commands

Use one bundle path and run one of these three command variants.

Normal (human-readable output):

```bash
python3 scripts/analyze_release_verdict_with_logs.py \
	.cache/prelaunch/<timestamp>/final-summary.json \
	.cache/prelaunch/<timestamp>/gate-result.json \
	.cache/prelaunch/<timestamp>/pytest.err \
	.cache/prelaunch/<timestamp>/full-rehearsal.err \
	--tor-policy
```

CI mode (`--rc`, exit code only):

```bash
python3 scripts/analyze_release_verdict_with_logs.py \
	.cache/prelaunch/<timestamp>/final-summary.json \
	.cache/prelaunch/<timestamp>/gate-result.json \
	.cache/prelaunch/<timestamp>/pytest.err \
	.cache/prelaunch/<timestamp>/full-rehearsal.err \
	--tor-policy --rc
```

Diagnostics mode (`--dry-run`, never fails process):

```bash
python3 scripts/analyze_release_verdict_with_logs.py \
	.cache/prelaunch/<timestamp>/final-summary.json \
	.cache/prelaunch/<timestamp>/gate-result.json \
	.cache/prelaunch/<timestamp>/pytest.err \
	.cache/prelaunch/<timestamp>/full-rehearsal.err \
	--tor-policy --dry-run
```

### Release Decision Criteria

Treat a run as release-ready only when all of the following are true:

1. `overall_status = pass` in `final-summary.json`.
2. `gate.valid = true` in `gate-result.json`.
3. `required_check_failures = []` in `gate-result.json`.
4. `tor_policy.status = pass` when Tor policy is enabled for the profile.
5. Analyzer returns `exit_code = 0` in CI mode:

```bash
python3 scripts/analyze_release_verdict_with_logs.py \
	.cache/prelaunch/<timestamp>/final-summary.json \
	.cache/prelaunch/<timestamp>/gate-result.json \
	.cache/prelaunch/<timestamp>/pytest.err \
	.cache/prelaunch/<timestamp>/full-rehearsal.err \
	--tor-policy --rc
```

### Deploy Workflow Strict Toggle (Repo Variables)

`Production Deploy` supports an optional strict prelaunch mode controlled by repository variables.

Set these in GitHub repository settings: `Settings -> Secrets and variables -> Actions -> Variables`.

Minimal baseline (default behavior):

1. `HANNA_DEPLOY_REQUIRE_FULL_REHEARSAL=0`
2. Deploy gate requires: `preflight`, `smart_summary`, `focused_regression`, `contract_provenance`.

Strict rollout mode:

1. `HANNA_DEPLOY_REQUIRE_FULL_REHEARSAL=1`
2. `HANNA_FULL_REHEARSAL_TARGET=example.com` (required)
3. `HANNA_FULL_REHEARSAL_MODULES=pd-infra-quick` (optional, defaults to `full-spectrum`)

When strict mode is enabled:

1. Deploy workflow runs prelaunch with `HANNA_RUN_FULL_REHEARSAL=1`.
2. Gate additionally requires `full_rollout_rehearsal`.
3. Missing `HANNA_FULL_REHEARSAL_TARGET` fails deploy gate immediately.

## 3. Optional Live Smoke

To include the no-credential chain smoke used during release QA:

```bash
HANNA_RUN_LIVE_SMOKE=1 ./scripts/prelaunch_check.sh
```

Use this only when you explicitly want a longer operational rehearsal.

To include a full chain rehearsal with artifact verification after HTML/STIX/ZIP generation:

```bash
HANNA_RUN_FULL_REHEARSAL=1 \
HANNA_FULL_REHEARSAL_TARGET="example.com" \
HANNA_FULL_REHEARSAL_MODULES="pd-infra-quick" \
./scripts/prelaunch_check.sh
```

The rehearsal writes:

- `full-rehearsal.runtime.json`
- `full-rehearsal.metadata.json`
- `full-rehearsal.verification.json`

`full-rehearsal.verification.json` is considered passing only if the generated HTML path exists and the exported `json`, `metadata`, `stix`, and `zip` files all exist.

The same verification step now enforces contract provenance compatibility:

1. Metadata and runtime summary must expose supported `adapter_result_schema_version`.
2. ZIP `manifest.json` and STIX `note.x_hanna_provenance` must use `urn:hanna:contract-provenance:v1`.
3. Unknown namespace or unsupported contract versions fail the rehearsal gate (fail closed).

## 4. Pass Criteria

Minimum pass criteria before rollout:

1. `run_discovery.py` root wrapper lists adapters and presets without crashing.
2. `hanna_ui.py` root wrapper exposes `tui` help without crashing.
3. `preflight.json` shows no blocking failures for the intended preset.
4. Focused regression bundle is fully green.
5. ZIP-export path remains intact, including hit-linked artifacts such as persisted EyeWitness output when produced.
6. `final-summary.json` reports overall `pass` for the intended gate.

The documented schema contract for this file is in [docs/PRELAUNCH_SUMMARY_SCHEMA.md](/Users/admin/Desktop/hanna-v3-2-clean/docs/PRELAUNCH_SUMMARY_SCHEMA.md).

## 5. Controlled Rollout Order

Use this order:

1. Internal smoke target.
2. Limited production target set.
3. Full operator rollout.

Do not add features during this window. Treat the first 24-48 hours as a stability observation period.

## 6. Immediate Rollback Conditions

Pause rollout if any of the following appear:

1. Entry-point drift returns and operators need `PYTHONPATH` workarounds.
2. ZIP bundles are missing dossier, metadata, STIX, or expected media artifacts.
3. Runtime summaries show unexpected `worker_crash` or broad timeout spikes.
4. Preflight begins failing on tools that were green at freeze time.

## 7. Post-Launch Observation

Watch these first:

1. `missing_credentials` versus true runtime failures.
2. `missing_binary` growth after environment changes.
3. incomplete artifact bundles.
4. stale or oversized runtime directories under the active runs root.