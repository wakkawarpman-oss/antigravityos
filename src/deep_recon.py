"""
deep_recon.py — UA + RU Deep Reconnaissance Runner (refactored)
================================================================

Thin orchestration layer.  Adapter implementations live in ``adapters/``,
module registry in ``registry.py``, worker isolation in ``worker.py``.

This file keeps DeepReconRunner and backward-compatible re-exports so
existing callers (discovery_engine.py, run_discovery.py) keep working.
"""
from __future__ import annotations

from adapters.base import ReconAdapter, ReconHit, ReconReport  # re-exported
from translit import transliterate_to_cyrillic as _transliterate_to_cyrillic  # noqa: F401
from runners.base import DeepReconRunner
from runners.cli import _cli

if __name__ == "__main__":
    _cli()
