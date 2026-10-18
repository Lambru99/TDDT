"""DuckDuckGo HTML search scraping module for email discovery."""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, Email
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import extract_domain_emails


@register_module(
    name="corporate.email.ddg_scrape",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email],
    active=False,
    requires_key=None,
)
class DuckDuckGoScrapeModule(BaseModule):
    """Harvests emails using DuckDuckGo HTML endpoint."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            url = "https://html.duckduckgo.com/html/"
            data = {"q": f'"@{domain}"'}

            try:
                resp = self.client.post(url, data=data, host_hint="html.duckduckgo.com", timeout=10)
            except Exception:
                self.log.debug("DuckDuckGo request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code in (403, 429):
                self.log.warning(
                    "DuckDuckGo returned status %d for %s (rate limit / forbidden)",
                    resp.status_code,
                    domain,
                )
                continue
            if resp.status_code != 200:
                self.log.debug(
                    "DuckDuckGo returned non-200 status %d for %s", resp.status_code, domain
                )
                continue

            emails = extract_domain_emails(resp.text, domain)
            for email in sorted(emails):
                yield Email(
                    value=email,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "duckduckgo", "domain": domain},
                )
