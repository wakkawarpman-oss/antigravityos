from __future__ import annotations

import subprocess

from adapters import cli_common


def _timeout_exc_with_pid(pid: int = 4321) -> subprocess.TimeoutExpired:
    exc = subprocess.TimeoutExpired(cmd=["dummy"], timeout=1.0, output="", stderr="err")
    exc.pid = pid  # type: ignore[attr-defined]
    return exc


def test_kill_process_group_updates_success_stats(monkeypatch):
    cli_common.reset_process_lifecycle_stats()

    monkeypatch.setattr(cli_common.os, "getpgid", lambda _pid: 9999)
    monkeypatch.setattr(cli_common.os, "killpg", lambda _pgid, _sig: None)

    ok = cli_common.kill_process_group(_timeout_exc_with_pid())
    stats = cli_common.get_process_lifecycle_stats()

    assert ok is True
    assert stats["kill_attempted"] == 1
    assert stats["kill_succeeded"] == 1
    assert stats["kill_failed"] == 0


def test_kill_process_group_updates_failure_stats(monkeypatch):
    cli_common.reset_process_lifecycle_stats()

    monkeypatch.setattr(cli_common.os, "getpgid", lambda _pid: 9999)

    def _raise(_pgid, _sig):
        raise OSError("denied")

    monkeypatch.setattr(cli_common.os, "killpg", _raise)

    ok = cli_common.kill_process_group(_timeout_exc_with_pid())
    stats = cli_common.get_process_lifecycle_stats()

    assert ok is False
    assert stats["kill_attempted"] == 1
    assert stats["kill_succeeded"] == 0
    assert stats["kill_failed"] == 1


def test_run_cli_timeout_marks_kill_failed(monkeypatch):
    cli_common.reset_process_lifecycle_stats()

    def _fake_run(*_args, **_kwargs):
        raise _timeout_exc_with_pid()

    monkeypatch.setattr(cli_common.subprocess, "run", _fake_run)
    monkeypatch.setattr(cli_common, "_resolve_executable", lambda exe, _path: exe)
    monkeypatch.setattr(cli_common.os, "getpgid", lambda _pid: 9999)

    def _raise(_pgid, _sig):
        raise OSError("denied")

    monkeypatch.setattr(cli_common.os, "killpg", _raise)

    proc = cli_common.run_cli(["dummy"], timeout=0.01, proxy="socks5h://127.0.0.1:9050")
    stats = cli_common.get_process_lifecycle_stats()

    assert proc is not None
    assert proc.returncode == 124
    assert "[timeout][kill_failed]" in (proc.stderr or "")
    assert stats["timeout_events"] == 1
    assert stats["kill_failed"] == 1
