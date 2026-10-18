"""Truecaller lookup module for phone owner name resolution."""

from __future__ import annotations

from typing import ClassVar, Iterable
from urllib.parse import quote_plus

from tddt.core.entity import BaseEntity, FullName, Phone
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)


@register_module(
    name="user.phone.truecaller_scrape",
    mode=["user"],
    consumes=[Phone],
    produces=[FullName],
    active=False,
    requires_key="truecaller",
)
class PhoneTruecallerScrapeModule(BaseModule):
    """Resolves phone number ownership details via Truecaller API."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        token = getattr(self.settings, "truecaller", None)
        if not token:
            _log.debug("Truecaller auth token missing, skipping")
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Truecaller/11.75.5 (Android;10)",
        }

        for entity in entities:
            if not isinstance(entity, Phone):
                continue

            query = entity.value.strip()
            url = f"https://search5-noneu.truecaller.com/v2/search?q={quote_plus(query)}"

            try:
                resp = self.client.get(url, headers=headers, host_hint="search5-noneu.truecaller.com")
            except Exception as e:
                _log.warning("HTTP error querying Truecaller for %s: %s", entity.value, e)
                continue

            if resp.status_code in (401, 403):
                _log.warning("Truecaller authentication failed / expired (status %d)", resp.status_code)
                continue

            if resp.status_code == 429:
                _log.warning("Truecaller rate limited for %s (status 429)", entity.value)
                continue

            if resp.status_code != 200:
                _log.debug("Truecaller returned status %d for %s", resp.status_code, entity.value)
                continue

            try:
                data = resp.json()
            except Exception as e:
                _log.debug("Truecaller returned invalid JSON for %s: %s", entity.value, e)
                continue

            entries = data.get("data", []) if isinstance(data, dict) else []
            seen_names = set()
            for item in entries:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("altName")
                if not name or not isinstance(name, str):
                    continue
                clean_name = name.strip()
                if not clean_name or clean_name in seen_names:
                    continue
                seen_names.add(clean_name)

                yield FullName(
                    value=clean_name,
                    source_module=self.name,
                    confidence=0.85,
                    metadata={"phone": entity.value, "source": "truecaller"},
                )
