import pytest
import tempfile
from discovery_engine import DiscoveryEngine, Observable

@pytest.fixture
def engine():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        eng = DiscoveryEngine(db_path=tmp.name)
        yield eng

def test_resolve_entities_clusters_same_source(engine):
    # Register observables with same source_file
    engine._classify_and_register("+380501234567", "phoneinfoga", "target1", "run1.log")
    engine._classify_and_register("admin@example.com", "phoneinfoga", "target1", "run1.log")
    
    clusters = engine.resolve_entities()
    
    # We expect one cluster containing both because they share source_file
    assert len(clusters) == 1
    cluster = clusters[0]
    values = {obs.value for obs in cluster.observables}
    assert "+380501234567" in values
    assert "admin@example.com" in values

def test_resolve_entities_no_unwarranted_clustering(engine):
    # Different run logs, no shared observables
    engine._classify_and_register("+380501234567", "phoneinfoga", "target1", "run1.log")
    engine._classify_and_register("other@example.com", "sherlock", "target2", "run2.log")
    
    clusters = engine.resolve_entities()
    
    # Should be separate clusters if they share no anchors
    assert len(clusters) == 2
