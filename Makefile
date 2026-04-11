.PHONY: prelaunch-gate sprint-phase-guard release-guard dependency-report plan-drift-report tool-health-report tools-cleanup-plan tools-cleanup-apply perf-install perf-unit perf-load perf-load-wrk perf-load-k6 perf-memory perf-stress perf-endurance perf-cpu perf-all perf-report perf-clean perf-files tookie tookie-help grafana-up grafana-down grafana-logs grafana-open osint-tools-install parse-test-full nifi-up nifi-down nifi-logs nifi-open spiderfoot-up spiderfoot-down spiderfoot-logs spiderfoot-local-up spiderfoot-local-down spiderfoot-local-scan spiderfoot-local-batch ci-guard-dryrun

PERF_DIR := perf
PERF_STUB_HOST ?= 127.0.0.1
PERF_STUB_PORT ?= 8000
PERF_STUB_URL := http://$(PERF_STUB_HOST):$(PERF_STUB_PORT)
PYTHONPATH_SRC := PYTHONPATH=src

prelaunch-gate:
	@if [ -z "$(SUMMARY)" ]; then \
		echo "usage: make prelaunch-gate SUMMARY=.cache/prelaunch/<timestamp>/final-summary.json [ARGS='--require-check full_rollout_rehearsal']"; \
		exit 2; \
	fi
	@./scripts/prelaunch_gate.sh "$(SUMMARY)" $(ARGS)

sprint-phase-guard:
	@python3 ./scripts/sprint_guard.py \
		--scope 'src/**' \
		--scope 'tests/**' \
		--scope 'scripts/**' \
		--scope 'docs/**' \
		--scope '.github/workflows/**' \
		--scope '*.md' \
		--scope '.gitignore' \
		--scope 'Makefile' \
		--scope 'package*.json' \
		--scope 'requirements*.txt' \
		--ignore 'tools/*' \
		--check-command 'python3 -m pip check' \
		--check-command 'npm audit --omit=dev --audit-level=high' \
		--check-command 'python3 -m pytest -q tests/test_cli_contracts.py tests/test_legacy_entrypoints.py tests/test_integration_runtime_smokes.py'

release-guard:
	@python3 ./scripts/release_guard.py

dependency-report:
	@python3 ./scripts/generate_dependency_report.py \
		--output .cache/reports/dependency-weekly.json \
		--markdown .cache/reports/dependency-weekly.md

plan-drift-report:
	@python3 ./scripts/generate_plan_drift_report.py \
		--master-plan MASTER_PLAN_2000_WORDS.md \
		--checkpoint docs/CHECKPOINT_STATUS_2026-04-11.md \
		--output .cache/reports/plan-drift-report.json \
		--markdown .cache/reports/plan-drift-report.md

tool-health-report:
	@python3 ./scripts/generate_tool_health_report.py \
		--output .cache/reports/tool-health.json \
		--markdown .cache/reports/tool-health.md

tools-cleanup-plan:
	@python3 ./scripts/tools_cleanup.py --output .cache/reports/tools-cleanup-plan.json

tools-cleanup-apply:
	@python3 ./scripts/tools_cleanup.py --apply --allow-destructive --output .cache/reports/tools-cleanup-apply.json

tookie:
	@./scripts/tookie.sh $(ARGS)

tookie-help:
	@./scripts/tookie.sh --help

grafana-up:
	@docker compose -f docker-compose.grafana.yml up -d
	@echo "Grafana: http://localhost:3000 (admin/admin)"

grafana-down:
	@docker compose -f docker-compose.grafana.yml down

grafana-logs:
	@docker compose -f docker-compose.grafana.yml logs -f --tail=100

grafana-open:
	@open http://localhost:3000

osint-tools-install:
	@python3 -m pip install -r requirements.osint-extra.txt

parse-test-full:
	@bash ./scripts/full_parse_test.sh

nifi-up:
	@mkdir -p monitoring/nifi/logs
	@docker compose -f docker-compose.nifi.yml up -d
	@echo "NiFi: http://localhost:8080/nifi"
	@echo "Grafana: http://localhost:3001 (admin/admin)"

nifi-down:
	@docker compose -f docker-compose.nifi.yml down

nifi-logs:
	@docker compose -f docker-compose.nifi.yml logs -f --tail=120

nifi-open:
	@open http://localhost:8080/nifi

spiderfoot-up:
	@docker compose -f docker-compose.spiderfoot.yml up -d
	@echo "SpiderFoot (via Nginx auth): http://localhost:5001"
	@echo "Default credentials: admin / hanna"

spiderfoot-down:
	@docker compose -f docker-compose.spiderfoot.yml down

spiderfoot-logs:
	@docker compose -f docker-compose.spiderfoot.yml logs -f --tail=120

spiderfoot-local-up:
	@mkdir -p monitoring/spiderfoot/local-data
	@docker compose -f docker-compose.spiderfoot.local.yml up -d
	@echo "SpiderFoot local CLI container is running (no published ports)."

spiderfoot-local-down:
	@docker compose -f docker-compose.spiderfoot.local.yml down

spiderfoot-local-scan:
	@TARGET="$(TARGET)" TARGETS="$(TARGETS)" MODULES="$(MODULES)" THREADS="$(THREADS)" OUT_FILE="$(OUT)" DATA_DIR="$(PWD)/monitoring/spiderfoot/local-data" bash ./scripts/spiderfoot_local_scan.sh

spiderfoot-local-batch:
	@if [ -z "$(TARGETS)" ]; then \
		echo "usage: make spiderfoot-local-batch TARGETS='example.com 8.8.8.8'"; \
		exit 2; \
	fi
	@for target in $(TARGETS); do \
		echo "[SpiderFoot batch] $$target"; \
		TARGETS="" TARGET="$$target" MODULES="$(MODULES)" THREADS="$(THREADS)" OUT_FILE="$$target.json" DATA_DIR="$(PWD)/monitoring/spiderfoot/local-data" bash ./scripts/spiderfoot_local_scan.sh; \
	done

# ========================================
# PERFORMANCE TOOLS SETUP
# ========================================
perf-install:
	@echo "Installing performance tools..."
	@command -v apt-get >/dev/null 2>&1 && sudo apt-get update && sudo apt-get install -y wrk siege apache2-utils || true
	@command -v brew >/dev/null 2>&1 && brew install wrk k6 hyperfine || true
	@python3 -m pip install --upgrade pip >/dev/null 2>&1 || true
	@python3 -m pip install locust memory-profiler psutil matplotlib seaborn >/dev/null 2>&1 || true
	@echo "Performance tools setup completed."

# ========================================
# CLI BENCHMARKS (hyperfine)
# ========================================
perf-unit:
	@echo "CLI benchmarks (hyperfine)"
	@mkdir -p $(PERF_DIR) .cache/perf-unit
	@if command -v hyperfine >/dev/null 2>&1; then \
		hyperfine \
			--warmup 3 \
			--min-runs 10 \
			--export-json $(PERF_DIR)/perf-results-unit.json \
			'$(PYTHONPATH_SRC) python3 -m hanna.dossier.cli user@example.com text --export-dir .cache/perf-unit' \
			'$(PYTHONPATH_SRC) python3 -m hanna.dossier.cli +380671234567 text --export-dir .cache/perf-unit' \
			'$(PYTHONPATH_SRC) python3 -m hanna.dossier.cli example.com text --export-dir .cache/perf-unit'; \
	else \
		echo "hyperfine not installed, skipping perf-unit"; \
		printf '{"skipped":"hyperfine not installed"}\n' > $(PERF_DIR)/perf-results-unit.json; \
	fi

# ========================================
# HTTP LOAD TESTING (wrk + k6)
# ========================================
perf-load: perf-load-wrk perf-load-k6

perf-load-wrk:
	@echo "HTTP load test (wrk)"
	@mkdir -p $(PERF_DIR)
	@python3 $(PERF_DIR)/http_stub.py --host $(PERF_STUB_HOST) --port $(PERF_STUB_PORT) > $(PERF_DIR)/stub.log 2>&1 & echo $$! > $(PERF_DIR)/stub.pid
	@sleep 1
	@if command -v wrk >/dev/null 2>&1; then \
		wrk -t4 -c64 -d20s --latency -s $(PERF_DIR)/wrk_post.lua $(PERF_STUB_URL)/api/dossier > $(PERF_DIR)/wrk-results.txt; \
	else \
		echo "wrk not installed, skipped" > $(PERF_DIR)/wrk-results.txt; \
	fi
	@kill `cat $(PERF_DIR)/stub.pid` >/dev/null 2>&1 || true
	@rm -f $(PERF_DIR)/stub.pid
	@tail -n 8 $(PERF_DIR)/wrk-results.txt || true

perf-load-k6:
	@echo "Advanced load test (k6)"
	@mkdir -p $(PERF_DIR)
	@python3 $(PERF_DIR)/http_stub.py --host $(PERF_STUB_HOST) --port $(PERF_STUB_PORT) > $(PERF_DIR)/stub.log 2>&1 & echo $$! > $(PERF_DIR)/stub.pid
	@sleep 1
	@if command -v k6 >/dev/null 2>&1; then \
		k6 run -e BASE_URL=$(PERF_STUB_URL) $(PERF_DIR)/k6_dossier_test.js; \
	else \
		echo "k6 not installed, skipping perf-load-k6"; \
	fi
	@kill `cat $(PERF_DIR)/stub.pid` >/dev/null 2>&1 || true
	@rm -f $(PERF_DIR)/stub.pid

# ========================================
# MEMORY PROFILING
# ========================================
perf-memory:
	@echo "Memory usage test"
	@mkdir -p $(PERF_DIR)
	@if $(PYTHONPATH_SRC) python3 -c "import memory_profiler" >/dev/null 2>&1; then \
		$(PYTHONPATH_SRC) python3 -m memory_profiler $(PERF_DIR)/mem_test.py > $(PERF_DIR)/memory-report.txt; \
	else \
		echo "memory_profiler not installed, skipped" > $(PERF_DIR)/memory-report.txt; \
	fi
	@tail -n 12 $(PERF_DIR)/memory-report.txt || true

# ========================================
# STRESS + ENDURANCE
# ========================================
perf-stress:
	@echo "Stress test"
	@mkdir -p $(PERF_DIR)
	@python3 $(PERF_DIR)/http_stub.py --host $(PERF_STUB_HOST) --port $(PERF_STUB_PORT) > $(PERF_DIR)/stub.log 2>&1 & echo $$! > $(PERF_DIR)/stub.pid
	@sleep 1
	@command -v hey >/dev/null 2>&1 && hey -n 10000 -c 100 -timeout 30s $(PERF_STUB_URL)/api/dossier > $(PERF_DIR)/hey-results.txt || echo "hey not installed, skipped" > $(PERF_DIR)/hey-results.txt
	@command -v siege >/dev/null 2>&1 && siege -c 50 -t 30S $(PERF_STUB_URL)/api/dossier -q > $(PERF_DIR)/siege-results.txt 2>&1 || echo "siege not installed, skipped" > $(PERF_DIR)/siege-results.txt
	@kill `cat $(PERF_DIR)/stub.pid` >/dev/null 2>&1 || true
	@rm -f $(PERF_DIR)/stub.pid

perf-endurance:
	@echo "Endurance test"
	@mkdir -p $(PERF_DIR) .cache/perf-endurance
	@if command -v hyperfine >/dev/null 2>&1; then \
		hyperfine --warmup 2 --runs 30 --export-json $(PERF_DIR)/perf-results-endurance.json '$(PYTHONPATH_SRC) python3 -m hanna.dossier.cli test@example.com text --export-dir .cache/perf-endurance'; \
	else \
		echo "hyperfine not installed, skipping perf-endurance"; \
		printf '{"skipped":"hyperfine not installed"}\n' > $(PERF_DIR)/perf-results-endurance.json; \
	fi

# ========================================
# CPU + SYSTEM METRICS
# ========================================
perf-cpu:
	@echo "CPU usage test"
	@mkdir -p $(PERF_DIR)
	@$(PYTHONPATH_SRC) python3 $(PERF_DIR)/cpu_test.py > $(PERF_DIR)/cpu-report.txt
	@cat $(PERF_DIR)/cpu-report.txt

# ========================================
# FULL PERFORMANCE SUITE
# ========================================
perf-all: perf-unit perf-load perf-memory perf-stress perf-cpu perf-report

# ========================================
# REPORTING
# ========================================
perf-report:
	@echo "Performance report"
	@python3 $(PERF_DIR)/generate_report.py

# ========================================
# CLEANUP
# ========================================
perf-clean:
	@echo "Cleaning performance artifacts..."
	@rm -rf $(PERF_DIR)/*.json $(PERF_DIR)/*.txt $(PERF_DIR)/*.log $(PERF_DIR)/*.pid .cache/perf-unit .cache/perf-endurance

# ========================================
# REQUIRED FILES
# ========================================
perf-files:
	@echo "Required files:"
	@echo "perf/wrk_post.lua"
	@echo "perf/k6_dossier_test.js"
	@echo "perf/mem_test.py"
	@echo "perf/cpu_test.py"
	@echo "perf/generate_report.py"
	@echo "perf/http_stub.py"

ci-guard-dryrun:
	@python3 scripts/network_guard.py