from __future__ import annotations

from discovery_engine import DiscoveryEngine


def test_verify_profiles_uses_proxy_aware_request(monkeypatch, tmp_db):
    import discovery_engine as de_mod

    engine = DiscoveryEngine(db_path=tmp_db)
    engine.db.execute(
        "INSERT INTO profile_urls (username, platform, url, source_tool, status) VALUES (?, ?, ?, ?, ?)",
        ("alice", "github", "https://example.com/alice", "sherlock", "unchecked"),
    )
    engine.db.commit()

    calls: list[dict] = []

    def _fake_req(url, method="GET", timeout=5.0, proxy=None, headers=None, max_body_bytes=0):
        calls.append({"url": url, "method": method, "proxy": proxy})
        return 200, {"Content-Length": "1000"}, ""

    monkeypatch.setattr(de_mod, "proxy_aware_request", _fake_req)
    engine.verify_profiles(max_checks=10, timeout=1.0, proxy="socks5h://127.0.0.1:9050")

    status, checked_at, last_checked_at, ttl_hours = engine.db.execute(
        """
        SELECT status, checked_at, last_checked_at,
               CAST(ROUND((julianday(valid_until) - julianday(checked_at)) * 24.0) AS INTEGER)
        FROM profile_urls
        """
    ).fetchone()
    assert status == "verified"
    assert checked_at is not None
    assert last_checked_at is not None
    assert ttl_hours == 24
    assert calls and calls[0]["method"] == "HEAD"
    assert calls[0]["proxy"] == "socks5h://127.0.0.1:9050"


def test_verify_content_soft_match_sets_shorter_ttl(monkeypatch, tmp_db):
    import discovery_engine as de_mod

    engine = DiscoveryEngine(db_path=tmp_db)
    engine.db.execute(
        "INSERT INTO profile_urls (username, platform, url, source_tool, status) VALUES (?, ?, ?, ?, ?)",
        ("alice", "github", "https://example.com/alice", "sherlock", "soft_match"),
    )
    engine.db.commit()

    def _fake_req(url, method="GET", timeout=8.0, proxy=None, headers=None, max_body_bytes=0):
        return 200, {"Content-Length": "1200"}, "generic profile content"

    monkeypatch.setattr(de_mod, "proxy_aware_request", _fake_req)

    result = engine.verify_content(max_checks=10, timeout=1.0, proxy="socks5h://127.0.0.1:9050")

    status, checked_at, ttl_hours = engine.db.execute(
        """
        SELECT status, checked_at,
               CAST(ROUND((julianday(valid_until) - julianday(checked_at)) * 24.0) AS INTEGER)
        FROM profile_urls
        """
    ).fetchone()

    assert result["unchanged"] == 1
    assert status == "soft_match"
    assert checked_at is not None
    assert ttl_hours == 12
