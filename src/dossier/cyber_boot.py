#!/usr/bin/env python3
"""HANNA Cyberpunk boot screen for ONE-SHOT Dossier."""

from __future__ import annotations

import os
import platform
import random
import shutil
import subprocess  # nosec B404
import sys
import time


_RNG = random.SystemRandom()


def _run_quiet(cmd: list[str]) -> bool:
    try:
        subprocess.run(  # nosec B603
            cmd,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def play_cyber_ding(frequency: int = 1000, duration_ms: int = 80) -> None:
    """Play a short cross-platform boot ding with safe fallbacks."""
    if os.getenv("HANNA_CYBER_JINGLE", "1") not in {"1", "true", "TRUE", "yes", "on"}:
        return
    if not sys.stdout.isatty():
        return

    system = platform.system().lower()
    try:
        if system == "windows":
            import winsound

            winsound.Beep(int(frequency), int(duration_ms))
            return
        if system == "linux" and shutil.which("beep"):
            if _run_quiet(["beep", "-f", str(int(frequency)), "-l", str(int(duration_ms))]):
                return
        if system == "darwin":
            if shutil.which("afplay") and _run_quiet(["afplay", "/System/Library/Sounds/Glass.aiff"]):
                return
            if shutil.which("osascript") and _run_quiet(["osascript", "-e", "beep 1"]):
                return
    except Exception:
        print("\a", end="", flush=True)
        return

    # Terminal bell fallback for minimal portability.
    print("\a", end="", flush=True)


def play_cyberpunk_melody() -> None:
    notes = [
        (1200, 60),
        (1450, 70),
        (1700, 90),
    ]
    for freq, duration in notes:
        play_cyber_ding(freq, duration)
        time.sleep(duration / 1000)


class HANNACyberBoot:
    """Neon-style terminal boot banner with ASCII HANNA."""

    COLORS = {
        "hanna_logo": "\033[38;5;45m\033[1m",
        "version": "\033[38;5;99m\033[1m",
        "progress": "\033[38;5;47m",
        "security": "\033[38;5;197m\033[1m",
        "gauge": "\033[38;5;227m",
        "network": "\033[38;5;39m",
        "key_findings": "\033[38;5;208m\033[1m",
        "ready": "\033[38;5;47m\033[1m",
        "reset": "\033[0m",
    }

    # Correctly spelled HANNA banner.
    ASCII_HANNA = """\
██╗  ██╗ █████╗ ███╗   ██╗███╗   ██╗ █████╗
██║  ██║██╔══██╗████╗  ██║████╗  ██║██╔══██╗
███████║███████║██╔██╗ ██║██╔██╗ ██║███████║
██╔══██║██╔══██║██║╚██╗██║██║╚██╗██║██╔══██║
██║  ██║██║  ██║██║ ╚████║██║ ╚████║██║  ██║
╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝╚═╝  ╚═╝
"""

    def __init__(self) -> None:
        self.width = shutil.get_terminal_size(fallback=(100, 30)).columns

    def clear_screen(self) -> None:
        print("\033[2J\033[H", end="")

    def progress_bar(self, current: int, total: int, label: str) -> str:
        percent = min(100, int((current / max(total, 1)) * 100))
        filled = int(40 * percent / 100)
        bar = "█" * filled + "░" * (40 - filled)
        return f"{label:<28} [{bar}] {percent:3d}%"

    def security_gauge(self, score: int = 92) -> str:
        segments = 20
        filled = int(segments * max(0, min(score, 100)) / 100)
        gauge = "█" * filled + "░" * (segments - filled)
        return f"SEC [{gauge}] {score:3d}/100"

    def network_graph(self) -> str:
        graph = _RNG.choice([
            "●──●──●──●──●──●",
            "●──●  ●──●──●  ●",
            " ●──●──●──●──● ",
        ])
        return f"NET {graph} ({_RNG.randint(6, 12)} nodes)"

    def boot_sequence(self) -> None:
        self.clear_screen()
        play_cyberpunk_melody()
        print(self.COLORS["hanna_logo"], end="")
        for line in self.ASCII_HANNA.splitlines():
            print(line.center(self.width))
        print(self.COLORS["reset"], end="")
        print(
            f"{self.COLORS['version']}"
            "HANNA v1.0.0 | NETWORK INTELLIGENCE | (HANNA CORP)"
            f"{self.COLORS['reset']}"
        )
        print()

        phases = [
            ("LOADING CORE MODULES...", 25),
            ("INITIALIZING AI-PROBES...", 50),
            ("SYNCING STIX SCHEMAS...", 70),
            ("BUILDING ADAPTER MATRIX...", 85),
            ("TOR-ROTATION WARMUP...", 95),
            ("ONE-SHOT-DOSSIER READY", 100),
        ]

        for idx, (msg, progress) in enumerate(phases):
            play_cyber_ding(900 + idx * 70, 40)
            security_score = _RNG.randint(88, 97)
            line = (
                f"{self.COLORS['progress']}"
                f"{self.progress_bar(progress, 100, msg)} | "
                f"{self.security_gauge(security_score)} | "
                f"{self.network_graph()}"
                f"{self.COLORS['reset']}"
            )
            print(f"\r{line:<{self.width}}", end="")
            sys.stdout.flush()
            time.sleep(0.35)

        print(
            f"\n{self.COLORS['key_findings']}"
            "KEY FINDINGS: OUTDATED WEB SERVER | STRICT FIREWALL DETECTED"
            f"{self.COLORS['reset']}"
        )
        play_cyber_ding(1200, 140)
        print(f"{self.COLORS['ready']}HANNA CYBERPUNK MODE ACTIVATED{self.COLORS['reset']}")
        print()
        time.sleep(0.8)
        self.clear_screen()


def run_cyber_boot() -> int:
    boot = HANNACyberBoot()
    boot.boot_sequence()
    print(f"{boot.COLORS['ready']}Welcome to HANNA ONE-SHOT-DOSSIER{boot.COLORS['reset']}")
    print("Commands: dossier <target>, tui, history, exit\n")
    return 0


def main() -> None:
    raise SystemExit(run_cyber_boot())


if __name__ == "__main__":
    main()
