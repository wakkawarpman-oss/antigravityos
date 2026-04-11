"""NmapAdapter — service fingerprinting via nmap XML output."""
from __future__ import annotations

import os
from datetime import datetime

from defusedxml import ElementTree as ET
from pydantic import ValidationError

from adapters.base import ReconAdapter, ReconHit
from adapters.cli_common import run_cli
from logging_utils import get_logger
from models.api_schemas import NmapServiceSchema

log = get_logger("hanna.recon.nmap")


class NmapAdapter(ReconAdapter):
    """Top-ports scan with service/version detection."""

    name = "nmap"
    region = "global"

    def search(self, target_name: str, known_phones: list[str], known_usernames: list[str]) -> list[ReconHit]:
        hits: list[ReconHit] = []
        for target in self._collect_targets(target_name, known_usernames)[:5]:
            hits.extend(self._run_nmap(target))
        return hits

    def _collect_targets(self, target_name: str, known_usernames: list[str]) -> list[str]:
        targets: list[str] = []
        for value in [target_name] + known_usernames:
            value = value.strip()
            if not value or "@" in value or " " in value:
                continue
            if value.startswith(("http://", "https://")):
                value = value.split("://", 1)[1].split("/", 1)[0]
            if "." in value or value.replace(".", "").isdigit():
                targets.append(value)
        return list(dict.fromkeys(targets))

    def _run_nmap(self, target: str) -> list[ReconHit]:
        nmap_bin = os.environ.get("NMAP_BIN", "nmap")
        proc = run_cli(
            [nmap_bin, "-sV", "-T4", "--top-ports", "1000", "-oX", "-", target],
            timeout=self.timeout * 20,
        )
        if not proc or not proc.stdout.strip():
            return []
        try:
            root = ET.fromstring(proc.stdout)
        except ET.ParseError:
            return []

        hits: list[ReconHit] = []
        for host in root.findall("host"):
            address = target
            for address_node in host.findall("address"):
                if address_node.attrib.get("addrtype") == "ipv4":
                    address = address_node.attrib.get("addr", target)
                    break
                address = address_node.attrib.get("addr", address)
            for port in host.findall("ports/port"):
                state = port.find("state")
                if state is None or state.attrib.get("state") != "open":
                    continue
                portid = port.attrib.get("portid", "?")
                service = port.find("service")
                product = service.attrib.get("product", "") if service is not None else ""
                version = service.attrib.get("version", "") if service is not None else ""
                try:
                    validated = NmapServiceSchema.model_validate(
                        {
                            "address": address,
                            "port": int(portid),
                            "product": product,
                            "version": version,
                        }
                    )
                except (ValidationError, ValueError) as exc:
                    log.warning(
                        "INVALID_SCHEMA",
                        adapter=self.name,
                        target=target,
                        error=str(exc),
                        stage="nmap_service_record",
                    )
                    continue
                extra = " ".join(v for v in [product, version] if v).strip()
                hits.append(ReconHit(
                    observable_type="infrastructure",
                    value=f"{validated.address}:{validated.port} {extra}".strip(),
                    source_module=self.name,
                    source_detail=f"nmap:service:{validated.port}",
                    confidence=0.82,
                    raw_record={"target": target, "port": validated.port, "product": validated.product, "version": validated.version},
                    timestamp=datetime.now().isoformat(),
                    cross_refs=[target],
                ))
        return hits
