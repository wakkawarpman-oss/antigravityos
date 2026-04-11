"""DNSXAdapter — high-throughput DNS resolving via ProjectDiscovery dnsx."""
from __future__ import annotations

import os
from datetime import datetime

from adapters.base import ReconAdapter, ReconHit
from adapters.cli_common import run_cli


class DNSXAdapter(ReconAdapter):
    """Resolve and validate hostnames discovered by passive enumeration."""

    name = "dnsx"
    region = "global"

    def search(self, target_name: str, known_phones: list[str], known_usernames: list[str]) -> list[ReconHit]:
        hits: list[ReconHit] = []
        for host in self._collect_hosts(target_name, known_usernames)[:50]:
            hits.extend(self._resolve_host(host))
        return hits

    def _collect_hosts(self, target_name: str, known_usernames: list[str]) -> list[str]:
        hosts: list[str] = []
        for value in [target_name] + known_usernames:
            candidate = value.strip().lower()
            if not candidate or "@" in candidate or " " in candidate:
                continue
            if candidate.startswith(("http://", "https://")):
                candidate = candidate.split("://", 1)[1].split("/", 1)[0]
            if "." in candidate:
                hosts.append(candidate)
        return list(dict.fromkeys(hosts))

    def _resolve_host(self, host: str) -> list[ReconHit]:
        dnsx_bin = os.environ.get("DNSX_BIN", "dnsx")
        proc = run_cli(
            [dnsx_bin, "-silent", "-resp", "-a", "-aaaa", "-ptr", host],
            timeout=self.timeout * 6,
            env={"LC_ALL": "C"},
            proxy=self.proxy,
        )
        if not proc or not proc.stdout.strip():
            return []

        hits: list[ReconHit] = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            value = line.split()[0]
            if value != host and not value.endswith(host):
                continue
            hits.append(
                ReconHit(
                    observable_type="infrastructure",
                    value=value,
                    source_module=self.name,
                    source_detail=f"dnsx:resolved:{host}",
                    confidence=0.64,
                    raw_record={"host": host, "line": line},
                    timestamp=datetime.now().isoformat(),
                    cross_refs=[host],
                )
            )
        return hits
