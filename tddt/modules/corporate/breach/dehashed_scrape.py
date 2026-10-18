"""DeHashed breach search module."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote_plus

from tddt.core.entity import BaseEntity, Breach, Email
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.breach.dehashed_scrape",
    mode=["corporate", "user"],
    consumes=[Email],
    produces=[Breach],
    active=False,
    requires_key="dehashed_api_key",
)
class DehashedScrapeModule(BaseModule):
    """Searches DeHashed API for breached credentials associated with email."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Email):
                continue

            email_val = entity.value.strip().lower()
            api_key = getattr(self.settings, "dehashed", "") or getattr(
                self.settings, "dehashed_api_key", ""
            )
            if not api_key:
                self.log.debug("DeHashed API key not configured; skipping %s", email_val)
                continue

            query = f"email:{email_val}"
            url = f"https://api.dehashed.com/search?query={quote_plus(query)}"
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            try:
                resp = self.client.get(
                    url, headers=headers, host_hint="api.dehashed.com", timeout=15
                )
            except Exception:
                self.log.debug("DeHashed request failed for %s", email_val, exc_info=True)
                continue

            if resp.status_code in (401, 403, 429):
                self.log.warning(
                    "DeHashed API returned status %d for %s (unauthorized / rate limit)",
                    resp.status_code,
                    email_val,
                )
                continue
            if resp.status_code != 200:
                self.log.debug("DeHashed API returned non-200 status %d for %s", resp.status_code, email_val)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.debug("Failed to decode DeHashed JSON for %s", email_val, exc_info=True)
                continue

            for entry in data.get("entries", []):
                db_name = entry.get("database_name") or "DeHashed Breach"
                yield Breach(
                    value=db_name,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={
                        "email": email_val,
                        "username": entry.get("username"),
                        "source": "dehashed",
                    },
                )
