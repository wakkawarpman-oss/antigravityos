from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from dossier.engine import Dossier, DossierEngine as _Engine, Evidence, Target


class DossierEngine(_Engine):
    """Compatibility API for ONE-SHOT dossier operations."""

    tools = [
        "run",
        "sherlock",
        "maigret",
        "phoneinfoga",
        "amass",
        "spiderfoot",
    ]

    def run_one_shot(self, input_str: str, **kwargs):
        run = super().run_one_shot(input_str, **kwargs)
        return run.dossier, run.normalized

    def run_one_shot_full(self, input_str: str, **kwargs):
        return super().run_one_shot(input_str, **kwargs)

    def export_dossier(self, dossier: Dossier, normalized: dict[str, Any], fmt: str, path: Path) -> Path:
        fmt_norm = fmt.strip().lower()
        if fmt_norm not in {"text", "json"}:
            raise NotImplementedError(f"Format {fmt_norm} not implemented.")

        out_path = Path(path)
        if out_path.suffix == "":
            out_path = out_path.with_suffix(".txt" if fmt_norm == "text" else ".json")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if fmt_norm == "text":
            lines = [
                f"Dossier for {dossier.target.value}",
                f"Type: {dossier.target.type_hint}",
                "",
                "Norm",
            ]
            for key, values in normalized.items():
                if values:
                    for value in values:
                        lines.append(f"  {key}: {value}")
            out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return out_path

        payload = asdict(dossier)
        payload["normalized"] = normalized
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return out_path
