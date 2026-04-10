from __future__ import annotations

import time

from dossier.bootscreen import CYBERPUNK_ASCII


def show_cyberpunk_boot(delay: float = 0.25) -> None:
    print("\033[2J\033[H", end="")
    print("\033[96;1m" + CYBERPUNK_ASCII + "\033[0m")
    print("\033[95mInitializing ONE-SHOT-Dossier engine...\033[0m")
    steps = [
        "core",
        "adapters",
        "normalizer",
        "stix",
        "menu",
    ]
    for idx, step in enumerate(steps, start=1):
        print(f"\033[95mLoading {step:<10} {idx}/{len(steps)}\033[0m")
        time.sleep(delay)
    print("\033[92;1mInitialization complete.\033[0m\n")
