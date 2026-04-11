from typing import Any
from urllib.parse import urlparse


def analyze_url_structure(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    path = parsed.path if parsed.path else "/"

    return {
        "structure": {
            "protocol": parsed.scheme or "http",
            "domain": parsed.netloc,
            "path": path,
        }
    }
