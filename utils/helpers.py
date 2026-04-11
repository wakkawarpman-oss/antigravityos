import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def clear_screen() -> None:
    cmd = ["cmd", "/c", "cls"] if os.name == "nt" else ["clear"]
    subprocess.run(cmd, check=False)


def print_progress(task: str, total: int, current: int) -> None:
    if total <= 0:
        total = 1
    progress = max(0.0, min(100.0, (current / total) * 100.0))
    filled = int(progress // 2)
    bar = "#" * filled + "." * (50 - filled)
    print(f"\r[PROGRESS] {task}: {current}/{total} | {bar} | {progress:.1f}%", end="", flush=True)


def log_message(msg: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


def _build_html_report(report: dict[str, Any]) -> str:
    rows = []
    for finding in report.get("findings", []):
        rows.append(
            "<tr>"
            f"<td>{finding.get('link', '')}</td>"
            f"<td>{'yes' if finding.get('sql_injection') else 'no'}</td>"
            f"<td>{'yes' if finding.get('xss') else 'no'}</td>"
            f"<td>{finding.get('structure', {})}</td>"
            "</tr>"
        )

    return (
        "<!doctype html>"
        "<html><head><meta charset='utf-8'><title>Scan Report</title>"
        "<style>body{font-family:Arial,sans-serif;padding:24px}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ddd;padding:8px;text-align:left}"
        "th{background:#f4f4f4}</style></head><body>"
        f"<h1>Scan Report</h1><p>Total links: {report.get('total_links', 0)}</p>"
        "<table><thead><tr><th>Link</th><th>SQLi</th><th>XSS</th><th>Structure</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></body></html>"
    )


def generate_report(results: list[dict[str, Any]], output_dir: str, report_file: str) -> None:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_links": len(results),
        "findings": [],
        "summary": {
            "sql_injection_hits": 0,
            "xss_hits": 0,
        },
    }

    for result in results:
        finding = {
            "link": result.get("url", ""),
            "sql_injection": bool(result.get("sql_injection", False)),
            "xss": bool(result.get("xss", False)),
            "structure": result.get("structure", {}),
        }
        report["findings"].append(finding)
        if finding["sql_injection"]:
            report["summary"]["sql_injection_hits"] += 1
        if finding["xss"]:
            report["summary"]["xss_hits"] += 1

    json_path = out_dir / report_file
    html_path = out_dir / f"{json_path.stem}.html"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    with html_path.open("w", encoding="utf-8") as f:
        f.write(_build_html_report(report))

    log_message(f"Report saved: {json_path}")
    log_message(f"Report saved: {html_path}")
