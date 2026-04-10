.PHONY: prelaunch-gate perf-install perf-unit perf-load perf-load-wrk perf-load-k6 perf-memory perf-stress perf-endurance perf-cpu perf-all perf-report perf-clean perf-files

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