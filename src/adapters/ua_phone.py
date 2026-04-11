"""UAPhoneAdapter — Reverse phone lookup through UA-specific services."""
from __future__ import annotations

import json
import logging
import os
import asyncio
from typing import Any, Optional, Union, List, Dict, AsyncIterator
from datetime import datetime

from adapters.base import ReconAdapter, ReconHit

log = logging.getLogger("hanna.recon.ua_phone")


class UAPhoneAdapter(ReconAdapter):
    """
    Reverse phone lookup through UA-specific services.
    Checks GetContact tags (with full AES-encrypted API), Telegram phone→account linking.

    Live methods require env vars:
      - TELEGRAM_BOT_TOKEN     → Bot API phone resolution
      - GETCONTACT_TOKEN       → GetContact API token (from rooted device)
      - GETCONTACT_AES_KEY     → GetContact AES key  (from rooted device)
    If env vars are absent, the adapter returns no hits (no pseudo evidence).
    """

    name = "ua_phone"
    region = "ua"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gc_client = None
        token = os.environ.get("GETCONTACT_TOKEN", "").strip()
        aes_key = os.environ.get("GETCONTACT_AES_KEY", "").strip()
        if token and aes_key:
            try:
                from adapters.getcontact_client import GetContactClient
                self._gc_client = GetContactClient(
                    token=token, aes_key=aes_key, timeout=self.timeout, proxy=self.proxy
                )
                log.info("GetContact client initialized (token=%s...)", token[:8])
            except Exception as exc:
                log.warning("GetContact client init failed: %s", exc)

    async def search_async(
        self,
        target_name: str,
        known_phones: List[str],
        known_usernames: List[str],
    ) -> AsyncIterator[ReconHit]:
        """Async phone resolution: Telegram + GetContact."""
        for phone in known_phones:
            # 1) Telegram
            async for hit in self._check_telegram_phone_live_async(phone, target_name):
                yield hit

            # 2) GetContact
            async for hit in self._check_getcontact_phone_async(phone, target_name):
                yield hit

    def search(
        self,
        target_name: str,
        known_phones: List[str],
        known_usernames: List[str],
    ) -> List[ReconHit]:
        # Legacy loop for ProcessPool
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._collect_async_search(target_name, known_phones, known_usernames))
        finally:
            loop.close()

    async def _collect_async_search(self, target_name: str, known_phones: List[str], known_usernames: List[str]) -> List[ReconHit]:
        hits = []
        async for hit in self.search_async(target_name, known_phones, known_usernames):
            hits.append(hit)
        return hits

    # ── Telegram live resolution ─────────────────────────────────

    async def _check_telegram_phone_live_async(
        self, phone: str, target_name: str
    ) -> AsyncIterator[ReconHit]:
        """Async Telegram resolution."""
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            log.debug("TELEGRAM_BOT_TOKEN missing; skipping Telegram live lookup for %s", phone)
            return

        # Use Telegram Bot API — getChat with phone (unofficial but widespread)
        # The reliable method: create a temporary contact and resolve via getContacts
        # Bot API doesn't expose phone→user directly, so we use the
        # phone_number_privacy workaround: try sending a contact to a
        # helper chat and observing the user_id resolution.
        #
        # Simplified approach: call getChat with the phone-derived user search
        # This is a best-effort check.
        url = f"https://api.telegram.org/bot{token}/getChat"
        try:
            status, body = await self._post_async(url, data={"chat_id": phone})
            if status == 200 and body:
                result = json.loads(body).get("result", {})
                username = result.get("username", "")
                first_name = result.get("first_name", "")
                last_name = result.get("last_name", "")
                full_name = f"{first_name} {last_name}".strip().lower()

                # Check name similarity
                name_parts = set(target_name.lower().split())
                name_match = any(p in full_name for p in name_parts if len(p) > 2)

                conf = 0.7 if name_match else 0.3
                if username:
                    yield ReconHit(
                        observable_type="username",
                        value=username,
                        source_module=self.name,
                        source_detail=f"telegram_bot_api:phone={phone}",
                        confidence=conf,
                        timestamp=datetime.now().isoformat(),
                        raw_record=result,
                        cross_refs=[phone],
                    )
                if full_name and name_match:
                    yield ReconHit(
                        observable_type="phone",
                        value=phone,
                        source_module=self.name,
                        source_detail=f"telegram_bot_api:name_confirmed",
                        confidence=0.85,
                        timestamp=datetime.now().isoformat(),
                        raw_record=result,
                        cross_refs=[username] if username else [],
                    )
                return
        except Exception as exc:
            log.warning(
                "ADAPTER_FAIL",
                extra={
                    "adapter": self.name,
                    "target": target_name,
                    "phone": phone,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "stage": "telegram_live_lookup",
                },
            )

        yield ReconHit(
            observable_type="phone",
            value=phone,
            source_module=self.name,
            source_detail="telegram_phone_check:api_error",
            confidence=0.0,
            timestamp=datetime.now().isoformat(),
            raw_record={"action": "api_call_failed", "service": "telegram", "phone": phone},
        )

    def _check_telegram_phone_live(self, phone: str, target_name: str) -> List[ReconHit]:
        # Legacy wrapper for sync execution paths.
        async def _collect() -> List[ReconHit]:
            rows: List[ReconHit] = []
            async for hit in self._check_telegram_phone_live_async(phone, target_name):
                rows.append(hit)
            return rows

        return asyncio.run(_collect())

    # ── GetContact lookup ────────────────────────────────────────

    async def _check_getcontact_phone_async(
        self, phone: str, target_name: str
    ) -> AsyncIterator[ReconHit]:
        """Async GetContact lookup."""
        if not self._gc_client:
            return

        try:
            # gc_client is currently sync, we wrap the call.
            info = await asyncio.to_thread(self._gc_client.get_full_info, phone)
        except Exception as exc:
            log.warning("GetContact lookup failed for %s: %s", phone, exc)
            return

        if not info:
            return

        name_parts = set(target_name.lower().split())

        # Profile match (displayName / name)
        display_name = info.get("displayName") or ""
        full_name = info.get("name") or ""
        combined_name = f"{display_name} {full_name}".lower()
        profile_name_match = any(p in combined_name for p in name_parts if len(p) > 2)

        if display_name and display_name != "Not Found":
            conf = 0.80 if profile_name_match else 0.35
            yield ReconHit(
                observable_type="phone",
                value=phone,
                source_module=self.name,
                source_detail=f"getcontact:profile={display_name[:60]}",
                confidence=min(1.0, conf),
                timestamp=datetime.now().isoformat(),
                raw_record={
                    "displayName": display_name,
                    "name": full_name,
                    "country": info.get("country"),
                    "email": info.get("email"),
                    "is_spam": info.get("is_spam", False),
                    "remaining_searches": info.get("remaining_searches"),
                    "name_match": profile_name_match,
                },
                cross_refs=[],
            )

            # If email found, emit as separate observable
            email = info.get("email")
            if email:
                yield ReconHit(
                    observable_type="email",
                    value=email,
                    source_module=self.name,
                    source_detail="getcontact:profile_email",
                    confidence=min(1.0, 0.75 if profile_name_match else 0.40),
                    timestamp=datetime.now().isoformat(),
                    raw_record={"phone": phone, "displayName": display_name},
                    cross_refs=[phone],
                )

        # Tags (how others saved this number in their contacts)
        tags = info.get("tags", [])
        for tag in tags[:10]:
            tag_lower = tag.lower()
            tag_name_match = any(p in tag_lower for p in name_parts if len(p) > 2)
            conf = 0.75 if tag_name_match else 0.20
            yield ReconHit(
                observable_type="phone",
                value=phone,
                source_module=self.name,
                source_detail=f"getcontact:tag={tag[:50]}",
                confidence=min(1.0, conf),
                timestamp=datetime.now().isoformat(),
                raw_record={"tag": tag, "phone": phone, "name_match": tag_name_match},
                cross_refs=[],
            )

    def _check_getcontact_phone(self, phone: str, target_name: str) -> List[ReconHit]:
        # Legacy wrapper for sync execution paths.
        async def _collect() -> List[ReconHit]:
            rows: List[ReconHit] = []
            async for hit in self._check_getcontact_phone_async(phone, target_name):
                rows.append(hit)
            return rows

        return asyncio.run(_collect())
