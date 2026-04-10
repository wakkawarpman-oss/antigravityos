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

## Branch Protection Confirmation (GitHub Settings)

Confirm explicitly before sprint execution:
1. protected branch policy is active on master;
2. required status checks are configured;
3. merge without required checks is blocked.

## Done Signal for Sprint Start

Sprint can start only when all blocks above are confirmed.
