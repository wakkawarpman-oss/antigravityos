from __future__ import annotations

import pytest

from adapters.base import FreemiumDegradedError, MissingCredentialsError
from adapters.censys_adapter import CensysAdapter
from adapters.shodan_adapter import ShodanAdapter
from models.base import RunResult


def test_shodan_adapter_requires_api_key(monkeypatch):
    monkeypatch.delenv("SHODAN_API_KEY", raising=False)
    adapter = ShodanAdapter(proxy="socks5h://127.0.0.1:9050", timeout=1.0)

    with pytest.raises(MissingCredentialsError):
        adapter.search("example.com", [], [])


def test_censys_adapter_requires_credentials(monkeypatch):
    monkeypatch.delenv("CENSYS_API_ID", raising=False)
    monkeypatch.delenv("CENSYS_API_SECRET", raising=False)
    adapter = CensysAdapter(proxy="socks5h://127.0.0.1:9050", timeout=1.0)

    with pytest.raises(MissingCredentialsError):
        adapter.search("example.com", [], [])


def test_run_result_treats_freemium_degraded_as_non_blocking_failure_kind():
    result = RunResult(
        target_name="case",
        mode="aggregate",
        errors=[{"module": "shodan", "error": "freemium degraded: quota", "error_kind": "freemium_degraded"}],
        started_at="2026-04-08T00:00:00",
        finished_at="2026-04-08T00:00:01",
    )

    summary = result.runtime_summary()

    assert summary["freemium_degraded"] == 1
    assert summary["failed"] == 0


def test_censys_request_raises_freemium_degraded_on_rate_limit(monkeypatch):
    adapter = CensysAdapter(proxy="socks5h://127.0.0.1:9050", timeout=1.0)

    monkeypatch.setattr(
        adapter,
        "_post",
        lambda *_args, **_kwargs: (429, "quota exceeded"),
    )

    with pytest.raises(FreemiumDegradedError):
        adapter._request("/hosts/search", {"q": "example.com"}, "id", "secret")
