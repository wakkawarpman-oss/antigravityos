#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p .cache
REPORT_FILE=".cache/full_parse_test_report.txt"
: > "$REPORT_FILE"

run_step() {
  local title="$1"
  local cmd="$2"
  {
    echo "==== $title ===="
    echo "CMD: $cmd"
    echo
  } | tee -a "$REPORT_FILE"

  if eval "$cmd" 2>&1 | tee -a "$REPORT_FILE"; then
    echo "[OK] $title" | tee -a "$REPORT_FILE"
  else
    echo "[FAIL] $title" | tee -a "$REPORT_FILE"
    return 1
  fi
  echo | tee -a "$REPORT_FILE"
}

run_step "Schema and adapter parse contracts" "pytest -q tests/test_p4_schema_contracts.py tests/test_adapter_result_schema.py"
run_step "Discovery parsing and normalization" "pytest -q tests/test_discovery_engine.py tests/test_extractors.py tests/test_bc_filtering_validation.py tests/test_profile_verifier.py"
run_step "Pipeline parsing regressions" "pytest -q tests/test_chain_runner.py tests/test_run_discovery.py tests/test_opsec.py"
run_step "Full project regression" "pytest -q"

echo "Full parse test report saved to $REPORT_FILE"
