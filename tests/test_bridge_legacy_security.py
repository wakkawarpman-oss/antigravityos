from __future__ import annotations

import pytest

import bridge_legacy_phone_dossier as bridge_mod


def test_resolve_api_token_requires_non_empty_token():
    with pytest.raises(ValueError):
        bridge_mod._resolve_api_token("")


def test_resolve_api_token_rejects_insecure_default_value():
    with pytest.raises(ValueError):
        bridge_mod._resolve_api_token("legacy-bridge-local-dev-token")


def test_resolve_api_token_accepts_non_placeholder_value():
    token = bridge_mod._resolve_api_token("real-token-123")
    assert token == "real-token-123"
