"""WebSearchAdapter — DuckDuckGo queries + Playwright page scraping."""
from __future__ import annotations

import json
import logging
import os
import random
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Union, Optional, List, Dict, AsyncIterator, Set
import asyncio
from pydantic import ValidationError

from adapters.base import ReconAdapter, ReconHit
from config import REQUIRE_PROXY
from models.api_schemas import WebSearchResultSchema

log = logging.getLogger("hanna.recon")

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:128.0) Gecko/20100101 Firefox/128.0",
]

# Patterns for classifying result URLs
_PLATFORM_PATTERNS: list[tuple[re.Pattern[str], str, str, float]] = [
    (re.compile(r"linkedin\.com/in/([^/?#]+)", re.I), "username", "linkedin_profile", 0.7),
    (re.compile(r"linkedin\.com/company/([^/?#]+)", re.I), "url", "linkedin_company", 0.6),
    (re.compile(r"instagram\.com/([A-Za-z0-9_.]+)/?$", re.I), "username", "instagram_profile", 0.7),
    (re.compile(r"facebook\.com/([A-Za-z0-9_.]+)/?$", re.I), "url", "facebook_profile", 0.65),
    (re.compile(r"vk\.com/([A-Za-z0-9_.]+)/?$", re.I), "username", "vk_profile", 0.65),
    (re.compile(r"ok\.ru/profile/(\d+)", re.I), "url", "ok_profile", 0.6),
    (re.compile(r"twitter\.com/([A-Za-z0-9_]+)/?$", re.I), "username", "twitter_profile", 0.65),
    (re.compile(r"x\.com/([A-Za-z0-9_]+)/?$", re.I), "username", "twitter_profile", 0.65),
    (re.compile(r"t\.me/([A-Za-z0-9_]+)/?$", re.I), "username", "telegram_channel", 0.65),
    (re.compile(r"scholar\.google\.", re.I), "url", "academic_scholar", 0.6),
    (re.compile(r"researchgate\.net/profile/", re.I), "url", "academic_researchgate", 0.6),
    (re.compile(r"\.edu/", re.I), "url", "academic_university", 0.55),
    (re.compile(r"youtube\.com/(c/|channel/|@)([^/?#]+)", re.I), "url", "youtube_channel", 0.55),
]


class WebSearchAdapter(ReconAdapter):
    """
    Web search adapter — DuckDuckGo queries + Playwright page scraping.

    Performs targeted searches for name/phone/usernames across DuckDuckGo,
    scrapes top results with Playwright for JS-rendered pages, and
    classifies results into social/academic/professional profiles.

    No API keys required. Uses public DuckDuckGo HTML search.
    """

    name = "web_search"
    region = "global"

    _DDG_URL = "https://html.duckduckgo.com/html/"
    _SERPAPI_URL = "https://serpapi.com/search.json"

    @property
    def serpapi_key(self) -> Optional[str]:
        return os.environ.get("SERPAPI_API_KEY", "").strip() or None

    async def search_async(
        self,
        target_name: str,
        known_phones: List[str],
        known_usernames: List[str],
    ) -> AsyncIterator[ReconHit]:
        """Perform concurrent web searches and yield hits as they are found."""
        seen_urls: Set[str] = set()
        queries = self._build_queries(target_name, known_phones, known_usernames)

        browser = None
        pw_context = None
        try:
            from playwright.async_api import async_playwright
            pw_context = await async_playwright().start()
            browser = await pw_context.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
                proxy={"server": self.proxy} if self.proxy else None,
            )
        except Exception as exc:
            log.warning("Async Playwright unavailable, falling back: %s", exc)

        try:
            # We process queries sequentially to avoid DDG rate limits, 
            # but we yield results immediately to the UI pipeline.
            for query in queries:
                if self.serpapi_key:
                    results = await self._serpapi_search_async(query)
                else:
                    results = await self._ddg_search_async(query)

                for r in results:
                    url = r.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = r.get("title", "")
                    snippet = r.get("snippet", "")

                    page_meta: Dict[str, Any] = {}
                    if browser and self._should_scrape(url):
                        page_meta = await self._scrape_page_async(browser, url)

                    hit = self._classify_url(
                        url, title, snippet, page_meta, query, target_name,
                    )
                    if hit:
                        yield hit
                
                # Jitter between queries
                await asyncio.sleep(random.uniform(1.0, 3.0))

        finally:
            if browser: await browser.close()
            if pw_context: await pw_context.stop()

    def search(
        self,
        target_name: str,
        known_phones: List[str],
        known_usernames: List[str],
    ) -> List[ReconHit]:
        # Legacy loop for ProcessPool-based execution
        hits: List[ReconHit] = []
        loop = asyncio.new_event_loop()
        try:
            async def collect():
                async for hit in self.search_async(target_name, known_phones, known_usernames):
                    hits.append(hit)
            loop.run_until_complete(collect())
        finally:
            loop.close()
        return hits

    # ── Query builder ──

    def _build_queries(
        self,
        target_name: str,
        known_phones: list[str],
        known_usernames: list[str],
    ) -> list[str]:
        queries: list[str] = []
        name = target_name.strip()
        if name:
            queries.append(f'"{name}"')
            queries.append(f'"{name}" site:linkedin.com')
            queries.append(f'"{name}" site:instagram.com')
            queries.append(f'"{name}" site:facebook.com')
            queries.append(f'"{name}" site:vk.com')
            queries.append(f'"{name}" site:scholar.google.com OR site:researchgate.net')
        for phone in known_phones[:3]:
            queries.append(f'"{phone}" -spam -lookup -reverse')
        for uname in known_usernames[:3]:
            if uname.strip().lower() != name.lower():
                queries.append(f'"{uname}"')
        return queries

    # ── DuckDuckGo HTML search ──

    async def _ddg_search_async(self, query: str, max_results: int = 15) -> List[Dict[str, str]]:
        ua = random.choice(_USER_AGENTS)
        data = urllib.parse.urlencode({"q": query, "kl": ""})
        # Note: _fetch uses urllib internally, we wrap it via asyncio.to_thread in Base
        status, body = await self._fetch_async(
            f"{self._DDG_URL}?{data}",
            headers={"User-Agent": ua}
        )
        if status != 200:
            return []
        return self._parse_ddg_html(body, max_results)

    async def _serpapi_search_async(self, query: str, max_results: int = 15) -> List[Dict[str, str]]:
        params = {"q": query, "api_key": self.serpapi_key, "engine": "google", "num": max_results}
        url = f"{self._SERPAPI_URL}?{urllib.parse.urlencode(params)}"
        status, body = await self._fetch_async(url, headers={"User-Agent": random.choice(_USER_AGENTS)})
        if status != 200:
            return await self._ddg_search_async(query, max_results)
        try:
            data = json.loads(body)
            organic = data.get("organic_results", [])
            rows: List[Dict[str, str]] = []
            for item in organic[:max_results]:
                try:
                    validated = WebSearchResultSchema.model_validate(
                        {
                            "url": item.get("link", ""),
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                        }
                    )
                except ValidationError as exc:
                    log.warning(
                        "INVALID_SCHEMA",
                        extra={
                            "adapter": self.name,
                            "target": query,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                            "stage": "serpapi_item",
                        },
                    )
                    continue
                rows.append(validated.model_dump())
            return rows
        except Exception as exc:
            log.warning(
                "ADAPTER_FAIL",
                extra={
                    "adapter": self.name,
                    "target": query,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "stage": "serpapi_parse",
                },
            )
            return await self._ddg_search_async(query, max_results)

    def _ddg_search(self, query: str, max_results: int = 15) -> List[Dict[str, str]]:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._ddg_search_async(query, max_results))
        finally:
            loop.close()

    def _parse_ddg_html(self, html_text: str, max_results: int) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        # DuckDuckGo HTML results: <a class="result__a" href="...">title</a>
        # and <a class="result__snippet" ...>snippet</a>
        # Use regex to extract — no external HTML parser dependency
        blocks = re.findall(
            r'<a\s+[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            html_text,
            re.DOTALL | re.IGNORECASE,
        )
        snippets = re.findall(
            r'<a\s+[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            html_text,
            re.DOTALL | re.IGNORECASE,
        )
        for i, (raw_url, raw_title) in enumerate(blocks[:max_results]):
            # DDG wraps URLs through redirects — extract actual URL
            url = self._extract_ddg_url(raw_url)
            if not url:
                continue
            title = re.sub(r"<[^>]+>", "", raw_title).strip()
            snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else ""
            try:
                validated = WebSearchResultSchema.model_validate(
                    {"url": url, "title": title, "snippet": snippet}
                )
            except ValidationError as exc:
                log.warning(
                    "INVALID_SCHEMA",
                    extra={
                        "adapter": self.name,
                        "target": "ddg_html",
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                        "stage": "ddg_item",
                    },
                )
                continue
            results.append(validated.model_dump())
        return results

    @staticmethod
    def _extract_ddg_url(raw: str) -> str:
        """Extract actual URL from DuckDuckGo redirect wrapper."""
        raw = raw.strip()
        if raw.startswith("//duckduckgo.com/l/?"):
            parsed = urllib.parse.urlparse("https:" + raw)
            params = urllib.parse.parse_qs(parsed.query)
            uddg = params.get("uddg", [""])[0]
            if uddg:
                return urllib.parse.unquote(uddg)
        if raw.startswith("http"):
            return raw
        return ""

    # ── Playwright page scraper ──

    @staticmethod
    def _should_scrape(url: str) -> bool:
        """Only scrape domains that benefit from JS rendering."""
        js_domains = (
            "linkedin.com", "instagram.com", "facebook.com",
            "vk.com", "twitter.com", "x.com",
        )
        return any(d in url.lower() for d in js_domains)

    @staticmethod
    async def _scrape_page_async(browser: Any, url: str) -> Dict[str, Any]:
        """Scrape a page with Playwright async headless Chromium."""
        meta: Dict[str, Any] = {}
        context = None
        try:
            context = await browser.new_context(
                viewport={"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
                user_agent=random.choice(_USER_AGENTS),
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(random.uniform(0.5, 1.5))

            meta["title"] = await page.title() or ""
            desc_el = await page.query_selector('meta[name="description"]')
            meta["description"] = await desc_el.get_attribute("content") if desc_el else ""

            og_tags: Dict[str, str] = {}
            for og_el in await page.query_selector_all('meta[property^="og:"]'):
                prop = await og_el.get_attribute("property") or ""
                content = await og_el.get_attribute("content") or ""
                if prop and content: og_tags[prop] = content
            meta["og"] = og_tags

            ld_scripts = await page.query_selector_all('script[type="application/ld+json"]')
            ld_data: List[Any] = []
            for script in ld_scripts[:3]:
                try:
                    ld_data.append(json.loads(await script.inner_text()))
                except Exception as exc:
                    log.debug("web_search json-ld parse failed for %s: %s", url, exc)
            meta["json_ld"] = ld_data

            body_text = await page.inner_text("body") or ""
            meta["text_snippet"] = body_text[:2000]

        except Exception as exc:
            log.debug("Async scrape failed for %s: %s", url, exc)
            meta["error"] = str(exc)
        finally:
            if context: await context.close()
        return meta

    @staticmethod
    def _scrape_page(browser: Any, url: str) -> dict[str, Any]:
        """Scrape a page with Playwright headless Chromium."""
        import random

        meta: dict[str, Any] = {}
        context = None
        try:
            context = browser.new_context(
                viewport={"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
                user_agent=random.choice(_USER_AGENTS),
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(random.uniform(0.5, 1.5))

            meta["title"] = page.title() or ""

            # Meta description
            desc_el = page.query_selector('meta[name="description"]')
            meta["description"] = desc_el.get_attribute("content") if desc_el else ""

            # Open Graph tags
            og_tags: dict[str, str] = {}
            for og_el in page.query_selector_all('meta[property^="og:"]'):
                prop = og_el.get_attribute("property") or ""
                content = og_el.get_attribute("content") or ""
                if prop and content:
                    og_tags[prop] = content
            meta["og"] = og_tags

            # JSON-LD structured data
            ld_scripts = page.query_selector_all('script[type="application/ld+json"]')
            ld_data: list[Any] = []
            for script in ld_scripts[:3]:
                try:
                    ld_data.append(json.loads(script.inner_text()))
                except Exception as exc:
                    log.debug("web_search json-ld parse failed for %s: %s", url, exc)
            meta["json_ld"] = ld_data

            # Text snippet (first 2000 chars of visible text)
            body_text = page.inner_text("body") or ""
            meta["text_snippet"] = body_text[:2000]

        except Exception as exc:
            log.debug("Playwright scrape failed for %s: %s", url, exc)
            meta["error"] = str(exc)
        finally:
            if context:
                try:
                    context.close()
                except Exception as exc:
                    log.debug("web_search context close failed for %s: %s", url, exc)
        return meta

    # ── URL classifier ──

    def _classify_url(
        self,
        url: str,
        title: str,
        snippet: str,
        page_meta: dict[str, Any],
        query: str,
        target_name: str,
    ) -> Optional[ReconHit]:
        """Classify a search result URL into a typed ReconHit."""
        obs_type = "url"
        source_detail = "web_mention"
        confidence = 0.5
        value = url

        for pattern, ptype, pdetail, pconf in _PLATFORM_PATTERNS:
            m = pattern.search(url)
            if m:
                obs_type = ptype
                source_detail = pdetail
                confidence = pconf
                if ptype == "username" and m.lastindex and m.lastindex >= 1:
                    value = m.group(1)
                break

        # Boost confidence if target name appears in title/snippet
        name_parts = [p.lower() for p in target_name.split() if len(p) > 2]
        combined_text = f"{title} {snippet} {page_meta.get('description', '')} {page_meta.get('text_snippet', '')}".lower()
        name_matches = sum(1 for p in name_parts if p in combined_text)
        if name_parts and name_matches >= len(name_parts):
            confidence = min(1.0, confidence + 0.1)
        elif name_matches == 0:
            confidence = max(0.2, confidence - 0.15)

        raw_record: dict[str, Any] = {
            "url": url,
            "title": title,
            "snippet": snippet,
            "query": query,
        }
        if page_meta:
            raw_record["page_title"] = page_meta.get("title", "")
            raw_record["page_description"] = page_meta.get("description", "")
            raw_record["og"] = page_meta.get("og", {})
            raw_record["json_ld"] = page_meta.get("json_ld", [])

        return ReconHit(
            observable_type=obs_type,
            value=value,
            source_module=self.name,
            source_detail=source_detail,
            confidence=round(confidence, 2),
            timestamp=datetime.now().isoformat(),
            raw_record=raw_record,
            cross_refs=[target_name],
        )
