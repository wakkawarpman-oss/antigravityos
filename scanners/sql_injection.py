from typing import Any

import requests


SQL_ERRORS = [
    "you have an error in your sql syntax",
    "warning: mysql",
    "unclosed quotation mark",
    "quoted string not properly terminated",
]


def scan_sql_injection(url: str, user_agent: str) -> dict[str, Any]:
    payload_url = f"{url}%27"
    try:
        res = requests.get(payload_url, headers={"User-Agent": user_agent}, timeout=10)
        body = res.text.lower()
        if any(err in body for err in SQL_ERRORS):
            return {
                "sql_injection": True,
                "url": url,
                "details": "Potential SQL injection error pattern detected",
            }
    except requests.RequestException as exc:
        return {
            "sql_injection": False,
            "url": url,
            "details": f"Request error: {exc}",
        }

    return {
        "sql_injection": False,
        "url": url,
        "details": "No SQL injection error pattern detected",
    }
