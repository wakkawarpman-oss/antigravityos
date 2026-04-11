# SPRINT START GUARD

Use this at the beginning of every sprint and attach to each release-critical PR.

## Merge Gate

1. PR contains one behavior slice only.
2. No mixed refactor + behavior scope in one PR.
3. Required checks are enabled and cannot be manually bypassed.

## CI Gate

1. test-vertical-slice is green on a clean runner.
2. test:all is green.
3. Contract smoke is isolated from coverage gate.

## Test Contract Gate

JWT contract suite must be green for:
1. malformed token;
2. expired token;
3. missing auth;
4. tenant mismatch;
5. permission denied.

## Security and Ops Gate

1. npm audit has no high/critical blockers.
2. prelaunch summary gate is pass.
3. health endpoint smoke is pass.

## AI Focus and Hallucination Guard

Run this guard before each sprint phase close and before merge:

```bash
python3 scripts/sprint_guard.py \
	--scope 'src/**' \
	--scope 'tests/**' \
	--scope 'scripts/**' \
	--scope 'docs/**' \
	--scope 'package*.json' \
	--scope 'requirements*.txt' \
	--check-command 'python3 -m pip check' \
	--check-command 'npm audit --omit=dev --audit-level=high' \
	--check-command 'python3 -m pytest -q tests/test_cli_contracts.py tests/test_legacy_entrypoints.py tests/test_integration_runtime_smokes.py'
```

Guard enforces:
1. changed files stay in sprint scope;
2. placeholder/hallucination markers are blocked (`<your_...>`, `YOUR_API_KEY`, `REPLACE_ME`, `TODO: implement`);
3. post-phase dependency/system audits are mandatory.

## Branch Protection Confirmation (GitHub Settings)

Confirm explicitly before sprint execution:
1. protected branch policy is active on master;
2. required status checks are configured;
3. merge without required checks is blocked.

## Done Signal for Sprint Start

Sprint can start only when all blocks above are confirmed.
