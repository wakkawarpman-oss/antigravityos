import pytest
import tempfile
from pathlib import Path
from discovery_engine import DiscoveryEngine

@pytest.fixture
def test_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        yield tmp.name

@pytest.fixture
def engine(test_db_path):
    eng = DiscoveryEngine(db_path=test_db_path)
    return eng

def test_extract_phone_numbers(engine):
    log_text = "E164: +380501234567\nInternational: 380671234567"
    observables = engine._extract_observables(log_text, "phone", "target", "source")
    
    values = {obs.value for obs in observables}
    assert "+380501234567" in values
    assert "+380671234567" in values

def test_extract_emails(engine):
    log_text = "Contact me at test_user123@example.com for more info or admin@admin.org."
    observables = engine._extract_observables(log_text, "username", "target", "source")
    
    values = {obs.value for obs in observables}
    assert "test_user123@example.com" not in values # example.com is skipped!
    assert "admin@admin.org" in values

def test_do_not_extract_placeholder_domains(engine):
    log_text = "Example on example.com and some site.ucoz.ru."
    observables = engine._extract_observables(log_text, "domain", "target", "source")
    types = {obs.obs_type: obs.value for obs in observables}
    
    # Check that ucoz.ru is not registered if placeholder blocking works
    assert "site.ucoz.ru" not in types.values()
    
def test_entropy_filter(engine):
    import string
    import random
    garbage = "".join(random.choices(string.ascii_letters + string.digits, k=64))
    log_text = f"Token: {garbage}"
    
    observables = engine._extract_observables(log_text, "username", "target", "source")
    values = {obs.value for obs in observables}
    
    # Ensure high-entropy strings aren't mistakenly extracted
    assert garbage not in values
