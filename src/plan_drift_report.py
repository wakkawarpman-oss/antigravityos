from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


UPDATE_HEADER_RE = re.compile(r"^##\s+Master Plan Execution Update\s*\((.+)\)\s*$")


@dataclass
class PlanDriftReport:
    generated_at: str
    checkpoint_updates: list[str]
    missing_in_master_plan: list[str]
    drift_status: str

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "checkpoint_updates": self.checkpoint_updates,
            "missing_in_master_plan": self.missing_in_master_plan,
            "drift_status": self.drift_status,
        }


def _extract_checkpoint_updates(checkpoint_text: str) -> list[str]:
    updates: list[str] = []
    for raw_line in checkpoint_text.splitlines():
        line = raw_line.strip()
        match = UPDATE_HEADER_RE.match(line)
        if not match:
            continue
        name = match.group(1).strip()
        if name and name not in updates:
            updates.append(name)
    return updates


def collect_plan_drift_report(master_plan_path: str, checkpoint_path: str) -> dict:
    master_text = Path(master_plan_path).read_text(encoding="utf-8")
    checkpoint_text = Path(checkpoint_path).read_text(encoding="utf-8")

    updates = _extract_checkpoint_updates(checkpoint_text)
    master_text_lower = master_text.lower()
    missing = [name for name in updates if name.lower() not in master_text_lower]

    report = PlanDriftReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        checkpoint_updates=updates,
        missing_in_master_plan=missing,
        drift_status="ok" if not missing else "drift",
    )
    return report.to_dict()


def render_markdown(report: dict) -> str:
    missing = report.get("missing_in_master_plan", [])
    status = report.get("drift_status", "unknown")
    updates = report.get("checkpoint_updates", [])

    lines = [
        "# Plan Drift Report",
        "",
        f"- Generated: {report.get('generated_at', 'unknown')}",
        f"- Drift status: **{status}**",
        f"- Checkpoint execution updates discovered: {len(updates)}",
        f"- Missing updates in master plan: {len(missing)}",
        "",
        "## Missing In Master Plan",
    ]

    if missing:
        lines.extend([f"- {name}" for name in missing])
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Checkpoint Update Names")
    if updates:
        lines.extend([f"- {name}" for name in updates])
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def render_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)