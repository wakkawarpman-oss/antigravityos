# RELEASE v3.3.0 Execution Plan (Baseline -> Release)

Purpose: lock deterministic delivery from PR #7 baseline to production release v3.3.0 with non-bypassable merge gates.

## Stage 0 - PR #7 Baseline Stabilization

ETC: 2-4 hours

Key tasks:
1. Lock green CI baseline for vertical-slice:
- fixed Node runtime across workflows and local dev;
- deterministic install strategy (npm ci);
- canonical test command for contract slice.
2. Remove workflow drift:
- same Node major in local and CI;
- same contract command in local and CI.

Definition of green:
1. test-vertical-slice is green.
2. baseline npm test in CI is stable (no flaky behavior).

Deliverables:
1. Locked workflow runtime and install strategy.
2. Documented baseline command matrix (local vs CI).

## Stage 1 - Contract

ETC: 4-6 hours

Key tasks:
1. JWT decode contract lock:
- claim set is fixed;
- deterministic 401/403 behavior;
- tenant boundary is enforced.
2. Negative path suite to zero ambiguity:
- malformed token;
- expired token;
- missing authorization;
- tenant mismatch;
- permission denied.

Definition of green:
1. vertical contract package for auth + adapter routes is green.
2. contract checklist is attached to PR and reviewed.

Deliverables:
1. Stable auth/adapter contract tests.
2. Updated Gate1 contract checklist in docs.

## Stage 2 - Core

ETC: 6-10 hours

Key tasks:
1. Complete route migration for users/reports/metrics with deterministic error codes.
2. Align RBAC policy on all new core routes:
- deny-by-default;
- no route-level exceptions.

Definition of green:
1. core routes contract pack is green.
2. route-level rate-limit + auth integration tests are green.

Deliverables:
1. Core route contract pack.
2. RBAC matrix for new route surface.

## Stage 3 - Tests

ETC: 5-8 hours

Key tasks:
1. Build one regression pack for Node + Python boundary.
2. Split flaky/slow tests into separate jobs so merge gate stays deterministic.

Definition of green:
1. npm run test:all is green.
2. critical pytest pack is green (schema/export/runtime-smoke).

Deliverables:
1. Deterministic merge-gate test jobs.
2. Separate slow/non-blocking jobs.

## Stage 4 - Security

ETC: 3-6 hours

Key tasks:
1. Run security policy on auth/jwt/rbac boundary and secret hygiene.
2. Make prelaunch gate mandatory as security + ops barrier.

Definition of green:
1. npm audit has no high/critical blockers.
2. security checks in CI and prelaunch summary gate are green.

Deliverables:
1. Security policy evidence in CI logs.
2. Required prelaunch gate in release path.

## Stage 5 - Deploy -> RELEASE v3.3.0

ETC: 3-5 hours

Key tasks:
1. Dry-run deploy workflow with health/metrics/report artifact verification.
2. Release freeze, v3.3.0 tagging, controlled post-deploy smoke.

Definition of green:
1. deploy workflow is green.
2. production-readiness + prelaunch gate + health endpoint smoke are green.

Deliverables:
1. Release candidate bundle and verification summary.
2. Release tag v3.3.0 and post-deploy smoke report.

## Immediate Blocker-Prevention Step (Right After Green PR #7)

Mandatory Post-PR7 Stabilization commit package:
1. lock CI runtime (Node version + install strategy);
2. lock contract command (single canonical test entrypoint);
3. enable required status checks for merge.

Why this is mandatory:
1. prevents Core-stage failures caused by CI environment drift, not business logic;
2. keeps merge gate deterministic before route surface expansion.

## Branch Protection (GitHub Settings, Not In Repo Files)

This must be configured in repository settings for branch master.

Required status checks (recommended minimum):
1. Node Vertical Slice / test-vertical-slice
2. Quality Gates / coverage-and-regression
3. Production Deploy / deploy (required for release branch or release window)

Policy:
1. Require branch to be up to date before merging.
2. Require pull request reviews.
3. Disallow manual bypass for required checks.
4. Restrict who can push to protected branch.

## Exit Criteria for RELEASE v3.3.0

All must be true:
1. Stages 0-5 are green by definition above.
2. No open high-severity auth/rbac/security findings.
3. Prelaunch final-summary gate is pass.
4. Post-deploy smoke is pass and archived.
