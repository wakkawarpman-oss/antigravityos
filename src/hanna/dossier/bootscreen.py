from dossier.bootscreen import *  # noqa: F401,F403

if __name__ == "__main__":
    from dossier.bootscreen import show_boot_screen

    raise SystemExit(0 if show_boot_screen() else 1)
