from __future__ import annotations

import logging

import run_discovery


def test_run_discovery_list_modules_exits_after_printing_inventory(capsys, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["run_discovery.py", "--list-modules"],
    )

    run_discovery.main()

    out = capsys.readouterr().out
    assert "=== Available Adapters ===" in out
    assert "ua_phone" in out
    assert "=== Presets" in out


def test_run_discovery_emits_legacy_warning_by_default(capsys, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["run_discovery.py", "--list-modules"],
    )

    run_discovery.main()

    err = capsys.readouterr().err
    assert "[legacy]" in err
    assert "./scripts/hanna" in err


def test_run_discovery_can_suppress_legacy_warning(capsys, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["run_discovery.py", "--list-modules", "--no-legacy-warning"],
    )

    run_discovery.main()

    err = capsys.readouterr().err
    assert err == ""


def test_run_discovery_redacts_sensitive_fields_in_deep_recon_logs(monkeypatch, tmp_path, caplog):
    legacy = run_discovery._load_legacy_module()

    class _FakeEngine:
        def __init__(self, db_path):
            self.db_path = db_path

        def get_pivot_queue(self):
            return []

        def get_stats(self):
            return {"ok": True}

        def verify_content(self, max_checks, timeout, proxy=None):
            return {"upgraded": 0}

        def get_profile_stats(self):
            return {"ok": 0}

    monkeypatch.setattr(run_discovery, "_load_legacy_module", lambda: legacy)
    monkeypatch.setattr(legacy, "DiscoveryEngine", _FakeEngine)
    monkeypatch.setattr(legacy, "ingest_metadata_exports", lambda engine, exports: {"ingested": 0, "rejected": 0, "skipped": 0})
    monkeypatch.setattr(legacy, "ingest_confirmed_evidence", lambda engine, files: [])
    monkeypatch.setattr(legacy, "resolve_clusters", lambda engine: [])
    monkeypatch.setattr(
        legacy,
        "run_recon_stage",
        lambda *args, **kwargs: (
            {
                "new_observables": 0,
                "new_phones": ["+380991234567"],
                "known_usernames": ["sensitive_user"],
                "proxy": "socks5h://127.0.0.1:9050",
                "modules_run": [],
                "errors": [],
            },
            None,
        ),
    )
    monkeypatch.setattr(legacy, "run_verification_stage", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        legacy,
        "render_dossier",
        lambda engine, output_path, report_mode: tmp_path.joinpath("dossier.html").write_text("ok", encoding="utf-8"),
    )

    out = tmp_path / "dossier.html"
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_discovery.py",
            "--target",
            "Case",
            "--exports-dir",
            str(tmp_path),
            "--output",
            str(out),
            "--proxy",
            "socks5h://127.0.0.1:9050",
            "--no-legacy-warning",
        ],
    )

    caplog.set_level(logging.INFO, logger="hanna.run_discovery")
    run_discovery.main()

    text = caplog.text
    assert "+380991234567" not in text
    assert "sensitive_user" not in text
    assert "127.0.0.1" not in text
    assert "socks5h://***:9050" in text