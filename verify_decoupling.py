from src.discovery_engine import DiscoveryEngine
from pathlib import Path
import os
import json
import sys

# Ensure src is in sys.path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

def verify_resolution():
    db_path = "test_resolution.db"
    log_file = "test_tool_output.log"
    if os.path.exists(db_path): os.remove(db_path)
    
    Path(log_file).write_text("Found some data for testuser and +380500000000")
    
    engine = DiscoveryEngine(db_path=db_path)
    
    # Create fake metadata
    meta = {
        "target": "Target1",
        "profile": "test_profile",
        "status": "success",
        "timestamp": "2026-04-10T00:00:00",
        "log_file": log_file,
        "sha256": "fake_sha"
    }
    meta_file = Path("test_meta.json")
    meta_file.write_text(json.dumps(meta))
    
    print("--- Ingesting ---")
    res = engine.ingest_metadata(meta_file)
    print(f"Ingest Result: {res}")
    
    print("--- Resolving Entities ---")
    engine.resolve_entities()
    
    stats = engine.get_stats()
    print(f"Stats: {stats}")
    
    if stats['total_observables'] > 0:
        print("SUCCESS: Observables registered via repository.")
    else:
        print("FAILURE: No observables found.")

    # Cleanup
    for f in [db_path, log_file, str(meta_file)]:
        if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    verify_resolution()
