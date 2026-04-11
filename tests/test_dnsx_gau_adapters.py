from __future__ import annotations

from adapters.dnsx_adapter import DNSXAdapter
from adapters.gau_adapter import GAUAdapter


def test_dnsx_adapter_parses_resolved_hosts(monkeypatch):
    adapter = DNSXAdapter(proxy="socks5h://127.0.0.1:9050", timeout=1.0)

    class _Proc:
        returncode = 0
        stdout = "example.com A 93.184.216.34\nsub.example.com A 93.184.216.35\n"

    monkeypatch.setattr("adapters.dnsx_adapter.run_cli", lambda *args, **kwargs: _Proc())
    hits = adapter.search("example.com", [], [])

    assert hits
    assert all(hit.source_module == "dnsx" for hit in hits)
    values = {hit.value for hit in hits}
    assert "example.com" in values


def test_gau_adapter_parses_unique_urls(monkeypatch):
    adapter = GAUAdapter(proxy="socks5h://127.0.0.1:9050", timeout=1.0)

    class _Proc:
        returncode = 0
        stdout = "https://example.com/a\nhttps://example.com/a\nhttp://example.com/b\n"

    monkeypatch.setattr("adapters.gau_adapter.run_cli", lambda *args, **kwargs: _Proc())
    hits = adapter.search("example.com", [], [])

    assert len(hits) == 2
    assert all(hit.observable_type == "url" for hit in hits)
    assert all(hit.source_module == "gau" for hit in hits)
