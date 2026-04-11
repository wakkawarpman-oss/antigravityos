from __future__ import annotations

from urllib.parse import urlparse


def redact_proxy(value: str | None) -> str:
    if not value:
        return "direct"
    raw = value.strip()
    if not raw:
        return "direct"
    parsed = urlparse(raw)
    if parsed.scheme and parsed.hostname:
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://***{port}"
    return "***"


def _redact_phone(value: str) -> str:
    raw = str(value).strip()
    digits = [idx for idx, ch in enumerate(raw) if ch.isdigit()]
    if not digits:
        return "***"
    keep_from = max(len(digits) - 2, 0)
    out = list(raw)
    for pos, idx in enumerate(digits):
        if pos < keep_from:
            out[idx] = "*"
    return "".join(out)


def _redact_username(value: str) -> str:
    raw = str(value).strip()
    if len(raw) <= 2:
        return "*" * len(raw)
    return f"{raw[:1]}***{raw[-1:]}"


def _redact_email(value: str) -> str:
    raw = str(value).strip()
    local, sep, domain = raw.partition("@")
    if not sep:
        return "***"
    if not local:
        return f"***@{domain}"
    return f"{local[:1]}***@{domain}"


def redact_seed_values(values: list[str], value_type: str) -> list[str]:
    if value_type == "phone":
        return [_redact_phone(item) for item in values]
    if value_type == "username":
        return [_redact_username(item) for item in values]
    if value_type == "email":
        return [_redact_email(item) for item in values]
    return ["***" for _ in values]


def seed_summary(values: list[str], value_type: str) -> str:
    if not values:
        return "count=0"
    masked = redact_seed_values(values, value_type)
    preview = masked[:3]
    return f"count={len(values)} sample={preview}"


def redact_runtime_payload(payload: dict) -> dict:
    def _walk(value: object, key_hint: str | None = None) -> object:
        if isinstance(value, dict):
            out: dict = {}
            for key, item in value.items():
                out[key] = _walk(item, str(key))
            return out
        if isinstance(value, list):
            if key_hint in {"new_phones", "known_phones", "phones"}:
                return redact_seed_values([str(item) for item in value], "phone")
            if key_hint in {"known_usernames", "usernames"}:
                return redact_seed_values([str(item) for item in value], "username")
            if key_hint in {"new_emails", "emails"}:
                return redact_seed_values([str(item) for item in value], "email")
            return [_walk(item) for item in value]
        if isinstance(value, str):
            if key_hint == "proxy":
                return redact_proxy(value)
            return value
        return value

    return _walk(payload) if isinstance(payload, dict) else {}
