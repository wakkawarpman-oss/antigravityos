#!/usr/bin/env python3
"""
HANNALYZER v3.2 - production system audit
Large test: parsing metrics + stability + rudiments + performance.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import psutil


@dataclass
class AuditResult:
    parse_success: float = 0.0
    parse_total: int = 0
    pydantic_coverage: float = 0.0
    adapters_total: int = 0
    stability_score: float = 0.0
    performance_ms: float = 0.0
    rudiments_count: int = 0
    silent_fails: int = 0
    tests_passed: int = 0
    tests_total: int = 0


class HannaAuditor:
    def __init__(self, root_dir: str = "."):
        self.root = Path(root_dir)
        self.results = AuditResult()

    def run_full_audit(self) -> AuditResult:
        print("HANNALYZER v3.2 - start audit")
        start_time = time.time()

        self._test_suite()
        self._parse_metrics()
        self._pydantic_coverage()
        self._find_rudiments()
        self._performance_test()
        self._stability_test()

        self.results.performance_ms = (time.time() - start_time) * 1000
        self._print_detailed_report()
        return self.results

    def _run_pytest(self, args: list[str]) -> tuple[int, int]:
        cmd = ["pytest", "-q", *args]
        result = subprocess.run(cmd, capture_output=True, text=True)

        out = (result.stdout or "") + "\n" + (result.stderr or "")
        # Example: "1 failed, 241 passed in 3.76s" or "242 passed in 3.27s"
        passed = 0
        failed = 0
        for m in re.finditer(r"(\d+)\s+passed", out):
            passed = max(passed, int(m.group(1)))
        for m in re.finditer(r"(\d+)\s+failed", out):
            failed = max(failed, int(m.group(1)))

        total = passed + failed
        if total == 0:
            # fallback for older output formats
            col = re.search(r"collected\s+(\d+)\s+items", out)
            if col:
                total = int(col.group(1))
            passed = total if result.returncode == 0 else 0
        return passed, total

    def _test_suite(self) -> None:
        print("\n1/6 tests")

        passed, total = self._run_pytest(["tests/"])
        self.results.tests_passed = passed
        self.results.tests_total = total
        print(f"pytest: {passed}/{total}")

        p4_passed, p4_total = self._run_pytest(["tests/test_p4_schema_contracts.py"])
        print(f"P4 schema contracts: {p4_passed}/{p4_total}")

    def _parse_metrics(self) -> None:
        print("\n2/6 parsing metrics")

        cache_file = self.root / ".cache/adapter_quality_audit_post_p2p3.json"
        if not cache_file.exists():
            print("cache metric file not found")
            return

        with cache_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        rows = data.get("rows", [])

        self.results.parse_total = len(rows)
        parse_ok = sum(1 for r in rows if float(r.get("parsing_pct", 0)) > 30)
        self.results.parse_success = (parse_ok / len(rows) * 100) if rows else 0.0
        print(f"parse rate: {self.results.parse_success:.1f}% ({parse_ok}/{len(rows)})")

    def _pydantic_coverage(self) -> None:
        print("\n3/6 pydantic coverage")

        adapters = [
            p
            for p in self.root.glob("src/adapters/*.py")
            if p.stem not in {"base", "__init__"}
        ]
        self.results.adapters_total = len(adapters)

        pydantic_files: list[str] = []
        for adapter in adapters:
            content = adapter.read_text(encoding="utf-8", errors="ignore")
            if "model_validate(" in content:
                pydantic_files.append(adapter.stem)

        if self.results.adapters_total:
            self.results.pydantic_coverage = (
                len(pydantic_files) / self.results.adapters_total * 100
            )

        preview = ", ".join(pydantic_files[:8])
        suffix = "..." if len(pydantic_files) > 8 else ""
        print(
            f"pydantic: {len(pydantic_files)}/{self.results.adapters_total} "
            f"({self.results.pydantic_coverage:.1f}%)"
        )
        if preview:
            print(f"covered: {preview}{suffix}")

    def _find_rudiments(self) -> None:
        print("\n4/6 rudiments + silent fails")

        patterns = {
            "print_debug": r"\bprint\s*\(",
            "deprecated_urllib": r"^\s*import\s+urllib\s*$|^\s*from\s+urllib\s+import\s+",
            "silent_continue": r"except[^:]*:\s*\n\s*continue\b",
            "silent_pass": r"except[^:]*:\s*\n\s*pass\b",
        }

        rudiments: list[tuple[str, list[str]]] = []
        silent_fails: list[str] = []

        for adapter in self.root.glob("src/adapters/*.py"):
            content = adapter.read_text(encoding="utf-8", errors="ignore")
            issues = [
                name
                for name, pattern in patterns.items()
                if re.search(pattern, content, re.MULTILINE | re.DOTALL)
            ]
            if issues:
                rudiments.append((adapter.stem, issues))
                self.results.rudiments_count += len(issues)

            if re.search(r"except[^:]*:\s*\n\s*(continue|pass)\b", content, re.MULTILINE):
                silent_fails.append(adapter.stem)

        self.results.silent_fails = len(set(silent_fails))

        print(f"rudiments: {self.results.rudiments_count}")
        for adapter, issues in rudiments[:5]:
            print(f"  {adapter}: {issues}")
        print(f"silent fails: {self.results.silent_fails}")

    def _performance_test(self) -> None:
        print("\n5/6 performance")

        start = time.time()
        cpu_before = psutil.cpu_percent(interval=0.1)
        mem_before = psutil.virtual_memory().percent

        # Lightweight synthetic workload instead of sleeping blindly.
        _ = sum(i * i for i in range(300000))

        cpu_after = psutil.cpu_percent(interval=0.1)
        mem_after = psutil.virtual_memory().percent

        perf_ms = (time.time() - start) * 1000
        self.results.performance_ms = perf_ms

        print(f"mock discovery: {perf_ms:.0f}ms")
        print(
            f"cpu: {cpu_before:.1f}% -> {cpu_after:.1f}% | "
            f"ram: {mem_before:.1f}% -> {mem_after:.1f}%"
        )

    def _stability_test(self) -> None:
        print("\n6/6 stability")

        critical = [
            "src/logging_utils.py",
            "src/schedulers/lanes.py",
            "src/models/api_schemas.py",
        ]

        missing = [f for f in critical if not (self.root / f).exists()]
        if missing:
            self.results.stability_score = 70.0
            print(f"missing P0-P4 files: {missing}")
        else:
            self.results.stability_score = 95.0
            print("P0-P4 files present")

        logging_utils = self.root / "src/logging_utils.py"
        if logging_utils.exists() and "structlog" in logging_utils.read_text(encoding="utf-8", errors="ignore"):
            print("structured logging detected")

    def _is_production_ready(self) -> bool:
        return (
            self.results.parse_success > 60
            and self.results.pydantic_coverage > 20
            and self.results.tests_total > 0
            and self.results.tests_passed == self.results.tests_total
            and self.results.stability_score > 90
        )

    def _print_detailed_report(self) -> None:
        print("\n" + "=" * 72)
        print("HANNALYZER v3.2 - final audit summary")
        print("=" * 72)

        status = "PRODUCTION READY" if self._is_production_ready() else "NEEDS WORK"
        print(f"status: {status}")

        print("\nmetrics:")
        print(f"  parse success:   {self.results.parse_success:.1f}%")
        print(f"  pydantic:        {self.results.pydantic_coverage:.1f}%")
        print(f"  tests:           {self.results.tests_passed}/{self.results.tests_total}")
        print(f"  performance:     {self.results.performance_ms:.0f}ms")
        print(f"  stability:       {self.results.stability_score:.0f}%")

        print("\nissues:")
        print(f"  rudiments:       {self.results.rudiments_count}")
        print(f"  silent fails:    {self.results.silent_fails}")


def main() -> int:
    auditor = HannaAuditor()
    result = auditor.run_full_audit()

    report = asdict(result)
    report["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

    out_file = Path(".cache/audit_report.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\nreport saved: {out_file}")
    return 0 if auditor._is_production_ready() else 1


if __name__ == "__main__":
    raise SystemExit(main())
