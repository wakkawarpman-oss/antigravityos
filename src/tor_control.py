"""Tor ControlPort rotation helpers with policy and cooldown guards."""
from __future__ import annotations

import logging
import socket
import threading
import time
from typing import Dict, Any

from config import (
    TOR_CONTROL_ENABLED,
    TOR_CONTROL_HOST,
    TOR_CONTROL_PORT,
    TOR_ENABLED,
    TOR_ROTATION_COOLDOWN_SEC,
    TOR_ROTATION_POLICY,
)

log = logging.getLogger("hanna.tor_control")

_ROTATION_LOCK = threading.Lock()
_LAST_ROTATION_TS = 0.0


def _policy_allows(reason: str, policy: str) -> bool:
    p = (policy or "").strip().lower()
    if p in {"", "disabled", "off", "never"}:
        return False
    if p in {"always", "on"}:
        return True
    if p in {"batch_on_error", "on_error"}:
        return reason in {"task_timeout", "task_error", "task_crashed"}
    return False


def _send_newnym(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(b'AUTHENTICATE\r\n')
        auth_resp = sock.recv(1024).decode("utf-8", errors="replace")
        if not auth_resp.startswith("250"):
            return False, f"authenticate_failed:{auth_resp.strip()}"

        sock.sendall(b'SIGNAL NEWNYM\r\n')
        signal_resp = sock.recv(1024).decode("utf-8", errors="replace")
        if not signal_resp.startswith("250"):
            return False, f"signal_failed:{signal_resp.strip()}"

        sock.sendall(b'QUIT\r\n')
        return True, "newnym_ok"


def request_tor_rotation(reason: str, module: str | None = None) -> Dict[str, Any]:
    """Attempt Tor circuit rotation via ControlPort under policy and cooldown."""
    if not TOR_ENABLED:
        return {"status": "skipped", "reason": "tor_disabled"}
    if not TOR_CONTROL_ENABLED:
        return {"status": "skipped", "reason": "control_disabled"}
    if not _policy_allows(reason, TOR_ROTATION_POLICY):
        return {"status": "skipped", "reason": "policy_skip", "policy": TOR_ROTATION_POLICY}

    now = time.monotonic()
    with _ROTATION_LOCK:
        global _LAST_ROTATION_TS
        remaining = float(TOR_ROTATION_COOLDOWN_SEC) - (now - _LAST_ROTATION_TS)
        if remaining > 0:
            return {
                "status": "skipped",
                "reason": "cooldown",
                "cooldown_remaining_sec": round(remaining, 2),
                "policy": TOR_ROTATION_POLICY,
            }

        ok, detail = _send_newnym(TOR_CONTROL_HOST, int(TOR_CONTROL_PORT))
        if ok:
            _LAST_ROTATION_TS = time.monotonic()
            payload = {
                "status": "rotated",
                "reason": reason,
                "module": module,
                "policy": TOR_ROTATION_POLICY,
                "cooldown_sec": TOR_ROTATION_COOLDOWN_SEC,
                "detail": detail,
            }
            log.info("TOR rotation succeeded: %s", payload)
            return payload

        payload = {
            "status": "error",
            "reason": reason,
            "module": module,
            "policy": TOR_ROTATION_POLICY,
            "cooldown_sec": TOR_ROTATION_COOLDOWN_SEC,
            "detail": detail,
        }
        log.warning("TOR rotation failed: %s", payload)
        return payload
