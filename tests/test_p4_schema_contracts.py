from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.api_schemas import GhuntProfile, LeakHit


def test_leak_hit_phone_ua_valid() -> None:
    item = LeakHit.model_validate(
        {
            "phone": "+380991234567",
            "source_file": "nova_poshta_2024.jsonl:L12",
            "confidence": 0.6,
        }
    )
    assert item.phone == "+380991234567"


def test_leak_hit_phone_invalid_rejected() -> None:
    with pytest.raises(ValidationError):
        LeakHit.model_validate(
            {
                "phone": "+390991234567",
                "source_file": "olx.jsonl:L3",
                "confidence": 0.5,
            }
        )


def test_leak_hit_email_invalid_rejected() -> None:
    with pytest.raises(ValidationError):
        LeakHit.model_validate(
            {
                "email": "not-an-email",
                "source_file": "mailru.jsonl:L4",
                "confidence": 0.4,
            }
        )


def test_ghunt_profile_requires_gaia_id() -> None:
    with pytest.raises(ValidationError):
        GhuntProfile.model_validate({"email": "user@gmail.com"})


def test_ghunt_profile_valid() -> None:
    item = GhuntProfile.model_validate(
        {
            "gaia_id": "1234567890123456",
            "email": "user@gmail.com",
            "phone": "+380991234567",
        }
    )
    assert item.gaia_id == "1234567890123456"
