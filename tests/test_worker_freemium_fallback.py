from __future__ import annotations

from worker import build_tasks


def test_build_tasks_freemium_missing_credentials_adds_baseline_fallback(monkeypatch):
    monkeypatch.delenv("SHODAN_API_KEY", raising=False)

    tasks, errors = build_tasks(
        module_names=["shodan"],
        target_name="example.com",
        known_phones=[],
        known_usernames=[],
        proxy="socks5h://127.0.0.1:9050",
        timeout=5.0,
        leak_dir=None,
    )

    task_names = {task.module_name for task in tasks}
    assert "shodan" not in task_names
    assert {"subfinder", "dnsx", "httpx_probe", "naabu", "nmap", "nuclei"}.issubset(task_names)

    shodan_error = next(err for err in errors if err.get("module") == "shodan")
    assert shodan_error["error_kind"] == "missing_credentials"
    assert shodan_error["degraded"] is True


def test_build_tasks_freemium_with_credentials_keeps_module(monkeypatch):
    monkeypatch.setenv("SHODAN_API_KEY", "test-key")

    tasks, errors = build_tasks(
        module_names=["shodan"],
        target_name="example.com",
        known_phones=[],
        known_usernames=[],
        proxy="socks5h://127.0.0.1:9050",
        timeout=5.0,
        leak_dir=None,
    )

    task_names = {task.module_name for task in tasks}
    assert "shodan" in task_names
    assert all(err.get("module") != "shodan" for err in errors)
