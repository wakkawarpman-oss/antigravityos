from __future__ import annotations

import pytest

from registry import MODULE_PRESETS, resolve_modules


def test_resolve_modules_default_excludes_getcontact_alias():
    resolved = resolve_modules(None)

    assert "ua_phone" in resolved
    assert "getcontact" not in resolved


def test_full_spectrum_preset_excludes_getcontact_alias():
    resolved = resolve_modules(["full-spectrum"])

    assert resolved == MODULE_PRESETS["full-spectrum"]
    assert "ua_phone" in resolved
    assert "getcontact" not in resolved


def test_resolve_modules_raises_for_unknown_module_name():
    with pytest.raises(ValueError, match="Unknown modules/presets"):
        resolve_modules(["definitely-unknown-module"])


def test_resolve_modules_raises_for_unknown_preset_name():
    with pytest.raises(ValueError, match="Unknown modules/presets"):
        resolve_modules(["definitely-unknown-preset"])