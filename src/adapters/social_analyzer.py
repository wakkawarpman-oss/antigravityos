"""SocialAnalyzerAdapter — 1000+ social network username search."""
from __future__ import annotations

import json
import os
import re
import asyncio
import urllib.parse
from datetime import datetime
from typing import Optional, List, Dict, AsyncIterator
import logging

from adapters.base import DependencyUnavailableError, MissingBinaryError, ReconAdapter, ReconHit
from adapters.cli_common import run_cli

log = logging.getLogger("hanna.recon.social_analyzer")


class SocialAnalyzerAdapter(ReconAdapter):
    """
    Social-Analyzer — 1000+ social network username search.

    More aggressive than Maigret/Sherlock. Checks:
      - 1000+ social platforms simultaneously
      - Returns profile URL, name, existence confidence
      - CLI + JSON output mode

    Requires: pip install social-analyzer
    Env vars:
      SOCIAL_ANALYZER_BIN — path to executable (default: "social-analyzer")
    """

    name = "social_analyzer"
    region = "global"

    async def search_async(
        self,
        target_name: str,
        known_phones: List[str],
        known_usernames: List[str],
    ) -> AsyncIterator[ReconHit]:
        """Perform concurrent social analysis and yield hits."""
        for username in known_usernames:
            # 1) Try CLI (Heavy, isolated)
            results = await asyncio.to_thread(self._run_social_analyzer, username)
            if results:
                for hit in results: yield hit
            
            # 2) Parallel direct checks (High concurrency)
            async for hit in self._fallback_platform_checks_async(username):
                yield hit

    def search(
        self,
        target_name: str,
        known_phones: List[str],
        known_usernames: List[str],
    ) -> List[ReconHit]:
        # Legacy loop for ProcessPool
        return asyncio.run(self._collect_async_search(target_name, known_phones, known_usernames))

    async def _collect_async_search(self, target_name: str, known_phones: List[str], known_usernames: List[str]) -> List[ReconHit]:
        hits = []
        async for hit in self.search_async(target_name, known_phones, known_usernames):
            hits.append(hit)
        return hits

    def _run_social_analyzer(self, username: str) -> Optional[list[ReconHit]]:
        """Run social-analyzer CLI for a username."""
        sa_bin = os.environ.get("SOCIAL_ANALYZER_BIN", "social-analyzer")
        cmd = [
            sa_bin,
            "--username", username,
            "--metadata",
            "--output", "json",
        ]
        try:
            proc = run_cli(cmd, timeout=self.timeout * 10, proxy=self.proxy)
        except (MissingBinaryError, DependencyUnavailableError):
            return None
        if proc and proc.returncode == 0 and proc.stdout.strip():
            return self._parse_sa_output(username, proc.stdout.strip())
        return None

    def _parse_sa_output(self, username: str, output: str) -> list[ReconHit]:
        """Parse social-analyzer JSON output."""
        hits: list[ReconHit] = []
        try:
            data = json.loads(output)
            profiles = data if isinstance(data, list) else data.get("detected", data.get("results", []))
            for profile in profiles:
                if isinstance(profile, dict):
                    url = profile.get("link", profile.get("url", ""))
                    site = profile.get("site", profile.get("source", ""))
                    status = profile.get("status", "")
                    if url and url.startswith("http") and "not found" not in status.lower():
                        conf = 0.55 if status.lower() in ("found", "claimed", "available") else 0.3
                        hits.append(ReconHit(
                            observable_type="url",
                            value=url,
                            source_module=self.name,
                            source_detail=f"social_analyzer:{site or 'unknown'}",
                            confidence=conf,
                            timestamp=datetime.now().isoformat(),
                            raw_record=profile,
                            cross_refs=[username],
                        ))
        except (json.JSONDecodeError, TypeError) as exc:
            log.warning(
                "ADAPTER_FAIL",
                extra={
                    "adapter": self.name,
                    "target": username,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "stage": "parse_sa_output",
                },
            )
        return hits[:50]

    async def _fallback_platform_checks_async(self, username: str) -> AsyncIterator[ReconHit]:
        """Direct async HTTP checks on popular platforms using parallelism."""
        platforms = {
            "tiktok": f"https://www.tiktok.com/@{urllib.parse.quote(username, safe='')}",
            "pinterest": f"https://www.pinterest.com/{urllib.parse.quote(username, safe='')}/",
            "reddit": f"https://www.reddit.com/user/{urllib.parse.quote(username, safe='')}",
            "medium": f"https://medium.com/@{urllib.parse.quote(username, safe='')}",
            "deviantart": f"https://www.deviantart.com/{urllib.parse.quote(username, safe='')}",
            "soundcloud": f"https://soundcloud.com/{urllib.parse.quote(username, safe='')}",
            "twitch": f"https://www.twitch.tv/{urllib.parse.quote(username, safe='')}",
            "vimeo": f"https://vimeo.com/{urllib.parse.quote(username, safe='')}",
            "flickr": f"https://www.flickr.com/people/{urllib.parse.quote(username, safe='')}/",
            "ok.ru": f"https://ok.ru/{urllib.parse.quote(username, safe='')}",
            "habr": f"https://habr.com/ru/users/{urllib.parse.quote(username, safe='')}/",
            "pikabu": f"https://pikabu.ru/@{urllib.parse.quote(username, safe='')}",
        }

        async def check_one(platform: str, url: str) -> Optional[ReconHit]:
            try:
                if platform == "reddit":
                    api_url = url.rstrip("/") + "/about.json"
                    status, _ = await self._fetch_async(api_url)
                    if status != 200: return None
                
                status, body = await self._fetch_async(url)
                if status == 200 and body:
                    body_l = body.lower()
                    if any(x in body_l for x in ("page not found", "user not found", "404")):
                        return None
                    return ReconHit(
                        observable_type="url", value=url,
                        source_module=self.name, source_detail=f"direct_check:{platform}",
                        confidence=0.35, timestamp=datetime.now().isoformat(),
                        raw_record={"username": username, "platform": platform},
                        cross_refs=[username],
                    )
            except Exception as exc:
                log.warning(
                    "ADAPTER_FAIL",
                    extra={
                        "adapter": self.name,
                        "target": username,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                        "stage": f"direct_check:{platform}",
                    },
                )
            return None

        # Execute all checks concurrently
        tasks = [check_one(p, u) for p, u in platforms.items()]
        results = await asyncio.gather(*tasks)
        for res in results:
            if res: yield res

    def _fallback_platform_checks(self, username: str) -> list[ReconHit]:
        return asyncio.run(self._collect_fallback_async(username))

    async def _collect_fallback_async(self, username: str) -> List[ReconHit]:
        hits = []
        async for hit in self._fallback_platform_checks_async(username):
            hits.append(hit)
        return hits
