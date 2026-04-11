from typing import Any

import requests


def scan_xss(url: str, user_agent: str) -> dict[str, Any]:
    payload = "<script>alert('XSS')</script>"
    test_payload = f"{url}?q={requests.utils.quote(payload, safe='')}"

    try:
        res = requests.get(test_payload, headers={"User-Agent": user_agent}, timeout=10)
        text = res.text.lower()
        if "<script>" in text or "alert('xss')" in text:
            return {
                "xss": True,
                "url": url,
                "details": "Potential reflected XSS pattern detected",
            }
    except requests.RequestException as exc:
        return {
            "xss": False,
            "url": url,
            "details": f"Request error: {exc}",
        }

    return {
        "xss": False,
        "url": url,
        "details": "No reflected XSS pattern detected",
    }
