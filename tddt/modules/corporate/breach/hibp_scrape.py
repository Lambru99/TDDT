"""HaveIBeenPwned breach checking module."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote

from tddt.core.entity import BaseEntity, Breach, Email
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.breach.hibp_scrape",
    mode=["corporate", "user"],
    consumes=[Email],
    produces=[Breach],
    active=False,
    requires_key="hibp_api_key",
)
class HibpScrapeModule(BaseModule):
    """Queries HaveIBeenPwned API for accounts exposed in known data breaches."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Email):
                continue

            email_val = entity.value.strip().lower()
            api_key = getattr(self.settings, "hibp", "") or getattr(
                self.settings, "hibp_api_key", ""
            )
            if not api_key:
                self.log.debug("HIBP API key not configured; skipping %s", email_val)
                continue

            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email_val)}?truncateResponse=false"
            headers = {
                "hibp-api-key": api_key,
                "user-agent": "TDDT-EASM-Scanner",
            }

            try:
                resp = self.client.get(
                    url, headers=headers, host_hint="haveibeenpwned.com", timeout=15
                )
            except Exception:
                self.log.debug("HIBP request failed for %s", email_val, exc_info=True)
                continue

            if resp.status_code == 404:
                self.log.debug("No breaches found on HIBP for %s", email_val)
                continue
            if resp.status_code in (401, 403, 429):
                self.log.warning(
                    "HIBP returned status %d for %s (rate limit / forbidden)",
                    resp.status_code,
                    email_val,
                )
                continue
            if resp.status_code != 200:
                self.log.debug("HIBP returned non-200 status %d for %s", resp.status_code, email_val)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.debug("Failed to decode HIBP JSON for %s", email_val, exc_info=True)
                continue

            if isinstance(data, list):
                for item in data:
                    name = item.get("Name", "Unknown Breach")
                    yield Breach(
                        value=name,
                        parent_id=entity.id,
                        source_module=self.name,
                        metadata={
                            "email": email_val,
                            "title": item.get("Title"),
                            "domain": item.get("Domain"),
                            "breach_date": item.get("BreachDate"),
                            "pwn_count": item.get("PwnCount"),
                            "data_classes": item.get("DataClasses", []),
                        },
                    )
