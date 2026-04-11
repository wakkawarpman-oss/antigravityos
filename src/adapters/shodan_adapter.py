"""ShodanAdapter — internet-exposed host enrichment via shodan CLI."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pydantic import ValidationError

from adapters.base import ReconAdapter, ReconHit, MissingCredentialsError, FreemiumDegradedError
from adapters.cli_common import run_cli
from logging_utils import get_logger
from models.api_schemas import ShodanResponseSchema

log = get_logger("hanna.recon.shodan")


class ShodanAdapter(ReconAdapter):
    """Query Shodan for internet-facing service banners and vulnerabilities."""

    name = "shodan"
    region = "global"

    def search(self, target_name: str, known_phones: list[str], known_usernames: list[str]) -> list[ReconHit]:
        if not os.environ.get("SHODAN_API_KEY", "").strip():
            raise MissingCredentialsError("SHODAN_API_KEY")
        hits: list[ReconHit] = []
        for target in self._collect_targets(target_name, known_usernames)[:5]:
            hits.extend(self._run_shodan(target))
        return hits

    def _collect_targets(self, target_name: str, known_usernames: list[str]) -> list[str]:
        targets: list[str] = []
        for value in [target_name] + known_usernames:
            value = value.strip()
            if not value or "@" in value or " " in value:
                continue
            if value.startswith(("http://", "https://")):
                value = value.split("://", 1)[1].split("/", 1)[0]
            targets.append(value)
        return list(dict.fromkeys(targets))

    def _run_shodan(self, target: str) -> list[ReconHit]:
        shodan_bin = os.environ.get("SHODAN_BIN", "shodan")
        proc = run_cli(
            [shodan_bin, "host", target, "--format", "json"],
            timeout=self.timeout * 8,
            proxy=self.proxy,
        )
        if not proc:
            return []
        stderr_l = (proc.stderr or "").lower()
        stdout_l = (proc.stdout or "").lower()
        if proc.returncode != 0:
            if any(token in stderr_l for token in ("rate limit", "quota", "payment required")):
                raise FreemiumDegradedError("shodan quota or rate limit reached")
            if any(token in stderr_l for token in ("api key", "unauthorized", "forbidden", "401", "403")):
                raise FreemiumDegradedError("shodan auth/plan access denied")
            return []
        if "rate limit" in stdout_l or "quota" in stdout_l:
            raise FreemiumDegradedError("shodan quota or rate limit reached")
        output = (proc.stdout or "").strip()
        if not output:
            return []
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []
        try:
            parsed = ShodanResponseSchema.model_validate(data)
        except ValidationError as exc:
            log.warning(
                "INVALID_SCHEMA",
                adapter=self.name,
                target=target,
                error=str(exc),
                stage="shodan_response",
            )
            return []

        hits: list[ReconHit] = []
        for item in parsed.data:
            if item.port is None:
                continue
            product = item.product or item.shodan_meta.get("module", "")
            vulns = item.vulns or []
            raw_record = item.model_dump(by_alias=True)
            hits.append(ReconHit(
                observable_type="infrastructure",
                value=f"{target}:{item.port} {product}".strip(),
                source_module=self.name,
                source_detail=f"shodan:port:{item.port}",
                confidence=0.75,
                raw_record=raw_record,
                timestamp=datetime.now().isoformat(),
                cross_refs=[target] + list(vulns)[:5],
            ))
        return hits
