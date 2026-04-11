from __future__ import annotations

import subprocess

from adapters.amass_adapter import AmassAdapter
from adapters.shodan_adapter import ShodanAdapter
from adapters.subfinder_adapter import SubfinderAdapter


def _empty_proc() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["stub"], returncode=0, stdout="", stderr="")


def test_amass_forwards_proxy_to_run_cli(monkeypatch):
    captured = {}

    def _fake_run_cli(_cmd, timeout, proxy=None, **_kwargs):
        captured["proxy"] = proxy
        captured["timeout"] = timeout
        return _empty_proc()

    import adapters.amass_adapter as mod

    monkeypatch.setattr(mod, "run_cli", _fake_run_cli)

    adapter = AmassAdapter(proxy="socks5h://127.0.0.1:9050", timeout=1.0)
    assert adapter.search("example.com", [], []) == []
    assert captured["proxy"] == "socks5h://127.0.0.1:9050"


def test_subfinder_forwards_proxy_to_run_cli(monkeypatch):
    captured = {}

    def _fake_run_cli(_cmd, timeout, proxy=None, **_kwargs):
        captured["proxy"] = proxy
        captured["timeout"] = timeout
        return _empty_proc()

    import adapters.subfinder_adapter as mod

    monkeypatch.setattr(mod, "run_cli", _fake_run_cli)

    adapter = SubfinderAdapter(proxy="socks5h://127.0.0.1:9050", timeout=1.0)
    assert adapter.search("example.com", [], []) == []
    assert captured["proxy"] == "socks5h://127.0.0.1:9050"


def test_shodan_forwards_proxy_to_run_cli(monkeypatch):
    captured = {}

    def _fake_run_cli(_cmd, timeout, proxy=None, **_kwargs):
        captured["proxy"] = proxy
        captured["timeout"] = timeout
        return _empty_proc()

    import adapters.shodan_adapter as mod

    monkeypatch.setattr(mod, "run_cli", _fake_run_cli)
    monkeypatch.setenv("SHODAN_API_KEY", "dummy")

    adapter = ShodanAdapter(proxy="socks5h://127.0.0.1:9050", timeout=1.0)
    assert adapter.search("example.com", [], []) == []
    assert captured["proxy"] == "socks5h://127.0.0.1:9050"
