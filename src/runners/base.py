import json
import logging
from datetime import datetime
from pathlib import Path

import asyncio
from adapters.base import ReconHit, ReconReport
from config import RUNS_ROOT
from registry import resolve_modules
from schedulers.lanes import dedup_and_confirm
from schedulers.dispatcher import MultiLaneDispatcher
from worker import build_tasks

log = logging.getLogger("hanna.recon")


class DeepReconRunner:
    """
    Event-Driven OSINT orchestrator with priority-based worker pool.
    """
    def __init__(
        self,
        proxy: str | None = None,
        timeout: float = 10.0,
        leak_dir: str | None = None,
        max_workers: int = 4,
        log_dir: str | None = None,
    ):
        self.proxy = proxy
        self.timeout = timeout
        self.leak_dir = leak_dir
        self.max_workers = max_workers
        self.log_dir = log_dir or str(RUNS_ROOT / "logs")

    def run(
        self,
        target_name: str,
        known_phones: list[str] | None = None,
        known_usernames: list[str] | None = None,
        modules: list[str] | None = None,
    ) -> ReconReport:
        known_phones = known_phones or []
        known_usernames = known_usernames or []
        module_names = resolve_modules(modules)

        tasks, errors = build_tasks(
            module_names, target_name, known_phones, known_usernames,
            self.proxy, self.timeout, self.leak_dir,
        )

        started = datetime.now().isoformat()
        all_hits: list[ReconHit] = []
        modules_run: list[str] = []

        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        # New Async Dispatcher
        dispatcher = MultiLaneDispatcher(
            max_parallel_tasks=self.max_workers,
            event_callback=None  # Can be passed from TUI in future iterations
        )
        
        # Run async dispatcher in a sync bridge
        all_hits = asyncio.run(dispatcher.run_tasks(tasks, label="deep_recon"))
        
        errors.extend(dispatcher.errors)
        modules_run = list(dispatcher.modules_run)

        deduped, cross_confirmed = dedup_and_confirm(all_hits)

        known_set = set(known_phones)
        new_phones = sorted({h.value for h in deduped if h.observable_type == "phone" and h.value not in known_set and h.confidence > 0})
        new_emails = sorted({h.value for h in deduped if h.observable_type == "email" and h.confidence > 0})

        report = ReconReport(
            target_name=target_name,
            modules_run=modules_run,
            hits=deduped,
            errors=errors,
            started_at=started,
            finished_at=datetime.now().isoformat(),
            new_phones=new_phones,
            new_emails=new_emails,
            cross_confirmed=cross_confirmed,
        )
        self._save_report(report)
        return report

    def _save_report(self, report: ReconReport) -> str | None:
        try:
            runs_dir = Path(self.log_dir).resolve().parent
            runs_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = runs_dir / f"deep_recon_{stamp}.json"
            tmp_path = runs_dir / f".{out_path.name}.tmp"

            payload = {
                "target": report.target_name,
                "modules": report.modules_run,
                "hits": [h.to_dict() for h in report.hits],
                "errors": report.errors,
                "started": report.started_at,
                "finished": report.finished_at,
                "new_phones": report.new_phones,
                "new_emails": report.new_emails,
                "cross_confirmed": [h.to_dict() for h in report.cross_confirmed],
            }
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(out_path)
            return str(out_path)
        except OSError:
            return None

    @staticmethod
    def report_summary(report: ReconReport) -> str:
        infra_hits = [h for h in report.hits if h.observable_type == "infrastructure"]
        url_hits = [h for h in report.hits if h.observable_type == "url"]
        coord_hits = [h for h in report.hits if h.observable_type == "coordinates"]
        loc_hits = [h for h in report.hits if h.observable_type == "location"]

        lines = [
            f"=== Deep Recon Report: {report.target_name} ===",
            f"Modules run: {', '.join(report.modules_run)}",
            f"Time: {report.started_at} → {report.finished_at}",
            f"Total hits: {len(report.hits)}",
            f"New phones: {len(report.new_phones)}",
            f"New emails: {len(report.new_emails)}",
            f"Infrastructure: {len(infra_hits)}",
            f"URLs discovered: {len(url_hits)}",
            f"Coordinates: {len(coord_hits)}",
            f"Locations: {len(loc_hits)}",
            f"Cross-confirmed: {len(report.cross_confirmed)}",
        ]

        if report.new_phones:
            lines.append("\nNew Phone Numbers Found:")
            for phone in report.new_phones:
                best = max((h for h in report.hits if h.value == phone), key=lambda h: h.confidence)
                xconf = " CROSS-CONFIRMED" if any(h.fingerprint == best.fingerprint for h in report.cross_confirmed) else ""
                lines.append(f"  {phone}  (conf={best.confidence:.0%}, via {best.source_detail}){xconf}")

        if report.new_emails:
            lines.append("\nNew Emails Found:")
            for email in report.new_emails:
                best = max((h for h in report.hits if h.value == email), key=lambda h: h.confidence)
                lines.append(f"  {email}  (conf={best.confidence:.0%}, via {best.source_detail})")

        if infra_hits:
            lines.append("\nInfrastructure:")
            for h in sorted(infra_hits, key=lambda x: -x.confidence)[:15]:
                lines.append(f"  {h.value}  (conf={h.confidence:.0%}, via {h.source_detail})")

        if coord_hits:
            lines.append("\nGEOINT Coordinates:")
            for h in coord_hits:
                lines.append(f"  {h.value}  (from {h.source_detail})")

        if loc_hits:
            lines.append("\nLocations Resolved:")
            for h in loc_hits:
                lines.append(f"  {h.value[:80]}  (via {h.source_detail})")

        if url_hits:
            lines.append(f"\nURLs Found: {len(url_hits)} (top 10):")
            for h in sorted(url_hits, key=lambda x: -x.confidence)[:10]:
                lines.append(f"  {h.value}  (conf={h.confidence:.0%}, via {h.source_detail})")

        if report.errors:
            lines.append(f"\nErrors: {len(report.errors)}")
            for err in report.errors:
                lines.append(f"  [{err['module']}] {err['error']}")

        return "\n".join(lines)
