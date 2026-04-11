import asyncio
from pathlib import Path

from scanners.sql_injection import scan_sql_injection
from scanners.url_analyzer import analyze_url_structure
from scanners.xss_scanner import scan_xss
from utils.helpers import generate_report, log_message, print_progress
from utils.link_checker import check_links


def load_links(file_path: str) -> list[str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Links file not found: {file_path}")

    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def run() -> None:
    user_agent = "HANNA-Scanner/1.0"
    links = load_links("data/links.txt")
    log_message(f"Loaded links: {len(links)}")

    valid_links = await check_links(links)
    log_message(f"Reachable links: {len(valid_links)}")

    results: list[dict] = []
    total = len(valid_links)

    for idx, url in enumerate(valid_links, start=1):
        sql_result = scan_sql_injection(url, user_agent)
        xss_result = scan_xss(url, user_agent)
        structure_result = analyze_url_structure(url)

        merged = {
            "url": url,
            "sql_injection": sql_result.get("sql_injection", False),
            "xss": xss_result.get("xss", False),
            "structure": structure_result.get("structure", {}),
            "details": {
                "sql": sql_result.get("details", ""),
                "xss": xss_result.get("details", ""),
            },
        }
        results.append(merged)
        print_progress("scan", total, idx)

    print()
    generate_report(results, "reports", "scan_report.json")
    log_message("Done")


if __name__ == "__main__":
    asyncio.run(run())
