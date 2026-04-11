from __future__ import annotations

from opsec_redaction import redact_proxy, redact_runtime_payload, seed_summary


def test_redact_proxy_masks_host_and_preserves_scheme_port():
    assert redact_proxy("socks5h://127.0.0.1:9050") == "socks5h://***:9050"


def test_seed_summary_masks_phone_values():
    summary = seed_summary(["+380991234567"], "phone")
    assert "count=1" in summary
    assert "+380991234567" not in summary


def test_seed_summary_masks_username_values():
    summary = seed_summary(["sensitive_user"], "username")
    assert "count=1" in summary
    assert "sensitive_user" not in summary


def test_redact_runtime_payload_masks_sensitive_fields():
    payload = {
        "proxy": "socks5h://127.0.0.1:9050",
        "new_phones": ["+380991234567"],
        "known_usernames": ["sensitive_user"],
        "new_emails": ["operator@example.com"],
    }

    redacted = redact_runtime_payload(payload)

    assert redacted["proxy"] == "socks5h://***:9050"
    assert redacted["new_phones"][0] != "+380991234567"
    assert redacted["known_usernames"][0] != "sensitive_user"
    assert redacted["new_emails"][0] != "operator@example.com"
