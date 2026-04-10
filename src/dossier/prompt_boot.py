from __future__ import annotations

import time

from dossier.cyber_boot import play_cyber_ding, play_cyberpunk_melody


CYBERPUNK_ASCII = """
 █████╗ ███████╗ ██████╗  ██████╗  ██████╗  ██╗   ██╗
██╔══██╗╚══███╔╝██╔════╝ ██╔═══██╗██╔═══██╗██║   ██║
███████║  ███╔╝ ██║      ██║   ██║██║   ██║██║   ██║
██╔══██║ ███╔╝  ██║      ██║   ██║██║   ██║╚██╗ ██╔╝
██║  ██║███████╗╚██████╗ ╚██████╔╝╚██████╔╝ ╚████╔╝
╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝  ╚═════╝   ╚═══╝

    H A N N A   |   ONE-SHOT-DOSSIER
            CYBERPUNK BOOT SEQUENCE
"""


def show_cyberpunk_boot(delay: float = 0.25) -> None:
    print("\033[2J\033[H", end="")
    play_cyberpunk_melody()
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
        play_cyber_ding(900 + idx * 70, 35)
        print(f"\033[95mLoading {step:<10} {idx}/{len(steps)}\033[0m")
        time.sleep(delay)
    play_cyber_ding(1200, 120)
    print("\033[92;1mInitialization complete.\033[0m\n")
