from __future__ import annotations

import pytest

from adapters import cli_common
from adapters.censys_adapter import CensysAdapter
from adapters.getcontact_client import GetContactClient
from adapters.web_search import WebSearchAdapter
from net import proxy_aware_request


def test_run_cli_requires_proxy_when_enforced(monkeypatch):
    monkeypatch.setattr(cli_common, "REQUIRE_PROXY", True)
    with pytest.raises(RuntimeError):
        cli_common.run_cli(["python3", "-c", "print('ok')"], timeout=1.0)


def test_web_search_enforces_proxy_flag(monkeypatch):
    import adapters.web_search as ws_mod

    monkeypatch.setattr(ws_mod, "REQUIRE_PROXY", True)
    with pytest.raises(RuntimeError):
        adapter = WebSearchAdapter(proxy=None, timeout=1.0)
        adapter.search("target", [], [])


def test_proxy_aware_request_requires_proxy(monkeypatch):
    import net as net_mod

    monkeypatch.setattr(net_mod, "REQUIRE_PROXY", True)
    with pytest.raises(RuntimeError):
        proxy_aware_request("https://example.com", method="HEAD", timeout=1.0, proxy=None)


def test_getcontact_client_requires_proxy_when_enforced(monkeypatch):
    import adapters.getcontact_client as gc_mod

    monkeypatch.setattr(gc_mod, "REQUIRE_PROXY", True)
    with pytest.raises(RuntimeError):
        GetContactClient(
            token="token",
            aes_key="00112233445566778899aabbccddeeff",
            timeout=1.0,
            proxy=None,
        )


def test_censys_request_uses_shared_transport(monkeypatch):
    adapter = CensysAdapter(proxy="socks5h://127.0.0.1:9050", timeout=1.0)

    def _fake_post(url, data, headers=None):
        assert url.startswith("https://search.censys.io/api/v2/")
        assert "Authorization" in (headers or {})
        return 200, '{"result":{"hits":[]}}'

    monkeypatch.setattr(adapter, "_post", _fake_post)
    payload = adapter._request("/hosts/search", {"q": "example.com"}, "id", "secret")
    assert payload == {"result": {"hits": []}}
