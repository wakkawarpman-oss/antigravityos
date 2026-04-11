from __future__ import annotations

from discovery_repository import DiscoveryRepository


def test_register_observable_promotes_probable_on_second_corroboration(tmp_path):
    repo = DiscoveryRepository(tmp_path / "discovery.db")
    try:
        repo.register_observable(
            obs_type="email",
            value="person@example.com",
            raw="person@example.com",
            source_tool="source_a",
            source_target="target_a",
            source_file="a.log",
            depth=0,
            is_original_target=False,
        )
        repo.register_observable(
            obs_type="email",
            value="person@example.com",
            raw="person@example.com",
            source_tool="source_b",
            source_target="target_b",
            source_file="b.log",
            depth=0,
            is_original_target=False,
        )

        row = repo.db.execute(
            "SELECT corroboration_count, tier FROM observables WHERE obs_type = ? AND value = ?",
            ("email", "person@example.com"),
        ).fetchone()

        assert row is not None
        assert int(row["corroboration_count"]) == 2
        assert str(row["tier"]) == "probable"
    finally:
        repo.close()
