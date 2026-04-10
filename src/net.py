"""Network helpers with centralized proxy policy enforcement."""
from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any, Union, Optional, Tuple, Dict

from config import MAX_BODY_BYTES, REQUIRE_PROXY, RETRY_MAX_ATTEMPTS, RETRY_BASE_DELAY, RETRY_MAX_DELAY
import time
import random


def proxy_aware_request(
    url: str,
    method: str = "GET",
    timeout: float = 5.0,
    proxy: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    max_body_bytes: int = MAX_BODY_BYTES,
) -> Tuple[int, Dict[str, str], str]:
    """Execute HTTP request with optional proxy and capped body read, including exponential backoff."""
    if REQUIRE_PROXY and not proxy:
        raise RuntimeError("HANNA_REQUIRE_PROXY=1 but no proxy provided for HTTP request")

    req = urllib.request.Request(url, headers=headers or {}, method=method)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    ) if proxy else urllib.request.build_opener()

    attempts = 0
    while attempts < RETRY_MAX_ATTEMPTS:
        attempts += 1
        try:
            with opener.open(req, timeout=timeout) as resp:
                status = int(getattr(resp, "status", 200) or 200)
                hdrs = {k: v for k, v in resp.headers.items()}
                body = ""
                if method.upper() != "HEAD":
                    body = resp.read(max_body_bytes).decode("utf-8", errors="replace")
                return status, hdrs, body
        except urllib.error.HTTPError as exc:
            # 5xx responses might be retriable, 4xx generally are not
            code = int(exc.code)
            if code < 500 and code != 429:
                return code, {}, ""
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            code = 0
        
        # If this point is reached, the request failed with a retriable error
        if attempts >= RETRY_MAX_ATTEMPTS:
            return getattr(locals(), 'code', 0), {}, ""
            
        delay = min(RETRY_BASE_DELAY * (2 ** (attempts - 1)), RETRY_MAX_DELAY)
        delay += random.uniform(0, 0.5)  # jitter
        time.sleep(delay)
    
    return 0, {}, ""
