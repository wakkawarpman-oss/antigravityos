"""GAUAdapter — URL history enrichment via getallurls (gau)."""
from __future__ import annotations

import os
from datetime import datetime

from adapters.base import ReconAdapter, ReconHit
from adapters.cli_common import run_cli


class GAUAdapter(ReconAdapter):
    """Collect historical URLs for a domain and emit web-surface observables."""

    name = "gau"
    region = "global"

    def search(self, target_name: str, known_phones: list[str], known_usernames: list[str]) -> list[ReconHit]:
        hits: list[ReconHit] = []
        for domain in self._collect_domains(target_name, known_usernames)[:5]:
            hits.extend(self._run_gau(domain))
        return hits

    def _collect_domains(self, target_name: str, known_usernames: list[str]) -> list[str]:
        domains: list[str] = []
        for value in [target_name] + known_usernames:
            value = value.strip().lower()
            if not value or "@" in value or " " in value:
                continue
            if value.startswith(("http://", "https://")):
                value = value.split("://", 1)[1].split("/", 1)[0]
            if "." in value:
                domains.append(value)
        return list(dict.fromkeys(domains))

    def _run_gau(self, domain: str) -> list[ReconHit]:
        gau_bin = os.environ.get("GAU_BIN", "gau")
        proc = run_cli([gau_bin, "--threads", "5", domain], timeout=self.timeout * 8, proxy=self.proxy)
        if not proc or not proc.stdout.strip():
            return []

        hits: list[ReconHit] = []
        seen: set[str] = set()
        for line in proc.stdout.splitlines():
            url = line.strip()
            if not url or not url.startswith(("http://", "https://")):
                continue
            if url in seen:
                continue
            seen.add(url)
            hits.append(
                ReconHit(
                    observable_type="url",
                    value=url,
                    source_module=self.name,
                    source_detail=f"gau:{domain}",
                    confidence=0.5,
                    raw_record={"domain": domain, "url": url},
                    timestamp=datetime.now().isoformat(),
                    cross_refs=[domain],
                )
            )
            if len(hits) >= 500:
                break
        return hits
