from __future__ import annotations

from dossier.core import DossierEngine
from dossier.prompt_boot import show_cyberpunk_boot

try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import WordCompleter
except Exception:  # pragma: no cover - optional dependency
    pt_prompt = None
    WordCompleter = None


def run_interactive_shell(show_boot: bool = True) -> int:
    engine = DossierEngine()
    commands = ["help", "exit", "quit", "save-json", "save-text"]
    completer = WordCompleter(commands) if WordCompleter else None

    if show_boot:
        show_cyberpunk_boot(delay=0.15)

    print("ONE-SHOT-Dossier INTERACTIVE SHELL")
    print("Enter a target (email, phone, username, domain, URL, text).")
    print("Commands: help, exit, quit")

    while True:
        try:
            line = pt_prompt("dossier> ", completer=completer) if pt_prompt else input("dossier> ")
        except (KeyboardInterrupt, EOFError):
            print("\nBye")
            return 0

        user_input = (line or "").strip()
        if not user_input:
            continue
        if user_input in {"exit", "quit"}:
            print("Bye")
            return 0
        if user_input == "help":
            print("Type any target string to run one-shot dossier.")
            print("Examples:")
            print("  user@example.com")
            print("  +380501112233")
            print("  example.com")
            continue

        dossier, normalized = engine.run_one_shot(user_input)
        print(f"\nDOSSIER for {dossier.target.value} ({dossier.target.type_hint})")
        for key, values in normalized.items():
            if not values:
                continue
            print(f"{key}:")
            for value in values[:5]:
                print(f"  - {value}")
            if len(values) > 5:
                print(f"  - ... and {len(values) - 5} more")


if __name__ == "__main__":
    raise SystemExit(run_interactive_shell())
