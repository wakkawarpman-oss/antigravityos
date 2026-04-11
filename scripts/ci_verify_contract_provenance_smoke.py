#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import ADAPTER_RESULT_SCHEMA_VERSION, CONTRACT_PROVENANCE_NAMESPACE, RUN_RESULT_SCHEMA_VERSION


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="CI smoke for contract provenance verifier")
    parser.add_argument("--namespace", default=CONTRACT_PROVENANCE_NAMESPACE, help="Namespace to embed into fixture artifacts")
    parser.add_argument(
        "--expect-fail",
        action="store_true",
        help="Treat verifier failure as expected (negative diagnostic mode)",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="hanna-contract-smoke-") as tmp:
        out_dir = Path(tmp)
        html_path = out_dir / "full-rehearsal.html"
        metadata_path = out_dir / "full-rehearsal.metadata.json"
        runtime_path = out_dir / "full-rehearsal.runtime.json"
        json_path = out_dir / "result.json"
        stix_path = out_dir / "result.stix.json"
        zip_path = out_dir / "result.zip"

        html_path.write_text("<html>ok</html>", encoding="utf-8")
        json_path.write_text("{}", encoding="utf-8")

        provenance = {
            "namespace": args.namespace,
            "contracts": {
                "run_result_schema_version": RUN_RESULT_SCHEMA_VERSION,
                "adapter_result_schema_version": ADAPTER_RESULT_SCHEMA_VERSION,
            },
        }

        _write_json(
            stix_path,
            {
                "type": "bundle",
                "id": "bundle--ci-smoke",
                "objects": [
                    {
                        "type": "note",
                        "id": "note--ci-smoke",
                        "x_hanna_provenance": provenance,
                    }
                ],
            },
        )

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "target_name": "CI Smoke",
                        "mode": "chain",
                        "adapter_result_schema_version": ADAPTER_RESULT_SCHEMA_VERSION,
                        "provenance": provenance,
                        "artifacts": [],
                    }
                ),
            )

        _write_json(
            metadata_path,
            {
                "target_name": "CI Smoke",
                "modules_run": ["ghunt"],
                "adapter_result_schema_version": ADAPTER_RESULT_SCHEMA_VERSION,
                "artifacts": {
                    "output_path": str(html_path),
                    "exports": {
                        "json": str(json_path),
                        "stix": str(stix_path),
                        "zip": str(zip_path),
                    },
                },
            },
        )

        _write_json(
            runtime_path,
            {
                "target_name": "CI Smoke",
                "mode": "chain",
                "adapter_result_schema_version": ADAPTER_RESULT_SCHEMA_VERSION,
            },
        )

        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "verify_rehearsal_artifacts.py"),
                str(out_dir),
                "--json-only",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PYTHONPATH": f"{SRC}:{os.environ.get('PYTHONPATH', '')}"},
        )

        if proc.returncode != 0:
            if args.expect_fail:
                print(
                    json.dumps(
                        {
                            "status": "pass",
                            "check": "contract-provenance-negative-smoke",
                            "expected_failure": True,
                            "namespace": args.namespace,
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            if proc.stdout:
                print(proc.stdout.strip())
            if proc.stderr:
                print(proc.stderr.strip(), file=sys.stderr)
            return proc.returncode

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            print("verifier did not emit JSON", file=sys.stderr)
            return 1

        if payload.get("status") != "pass":
            print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
            return 1

        if args.expect_fail:
            print(
                json.dumps(
                    {
                        "status": "fail",
                        "check": "contract-provenance-negative-smoke",
                        "reason": "verifier unexpectedly passed in negative mode",
                        "namespace": args.namespace,
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 1

    print(
        json.dumps(
            {
                "status": "pass",
                "check": "contract-provenance-smoke",
                "namespace": args.namespace,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
