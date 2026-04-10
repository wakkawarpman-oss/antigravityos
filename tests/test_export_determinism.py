from __future__ import annotations

import json
import zipfile

from adapters.base import ReconHit
from exporters.json_exporter import export_run_result_json
from exporters.zip_exporter import export_run_result_zip
from models import AdapterOutcome, RunResult


def _sample_result() -> RunResult:
    hit = ReconHit(
        observable_type="email",
        value="тест+user@example.com",
        source_module="ghunt",
        source_detail="fixture",
        confidence=0.81234,
        raw_record={"source": "fixture"},
    )
    return RunResult(
        target_name="Тестова Ціль",
        mode="manual",
        modules_run=["ghunt"],
        outcomes=[AdapterOutcome(module_name="ghunt", lane="fast", hits=[hit], elapsed_sec=0.1)],
        all_hits=[hit],
        started_at="2026-04-10T12:30:00",
        finished_at="2026-04-10T12:30:01",
    )


def test_json_export_is_stable_for_identical_input(tmp_path):
    result = _sample_result()

    first_path = export_run_result_json(result, tmp_path)
    first_content = first_path.read_text(encoding="utf-8")

    second_path = export_run_result_json(result, tmp_path)
    second_content = second_path.read_text(encoding="utf-8")

    assert first_path == second_path
    assert first_content == second_content


def test_json_export_preserves_utf8_characters(tmp_path):
    path = export_run_result_json(_sample_result(), tmp_path)
    content = path.read_text(encoding="utf-8")

    assert "Тестова Ціль" in content
    assert "тест+user@example.com" in content


def test_zip_manifest_counts_are_consistent(tmp_path):
    result = _sample_result()
    html_path = tmp_path / "dossier.html"
    html_path.write_text("<html>safe</html>", encoding="utf-8")

    path = export_run_result_zip(result, tmp_path, html_path=html_path, report_mode="shareable")

    with zipfile.ZipFile(path) as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        names = set(zf.namelist())

        assert "manifest.json" in names
        assert any(name.endswith(".json") for name in names)
        assert any(name.endswith(".stix.json") for name in names)
        assert manifest["target_name"] == "Тестова Ціль"
        assert manifest["report_mode"] == "shareable"
        assert len(manifest["artifacts"]) >= 3
        for item in manifest["artifacts"]:
            assert len(item["sha256"]) == 64
