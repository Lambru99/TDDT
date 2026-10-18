"""Bing search scraping module for email discovery."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote_plus

from tddt.core.entity import BaseEntity, Domain, Email
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import extract_domain_emails


@register_module(
    name="corporate.email.bing_scrape",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email],
    active=False,
    requires_key=None,
)
class BingScrapeModule(BaseModule):
    """Harvests emails using Bing web search queries."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            queries = [
                f'"@{domain}"',
                f'"{domain}" email OR mail',
            ]
            found: set[str] = set()

            for q in queries:
                url = f"https://www.bing.com/search?q={quote_plus(q)}&first=0"
                try:
                    resp = self.client.get(url, host_hint="www.bing.com", timeout=10)
                except Exception:
                    self.log.debug("Bing query request failed for %s", url, exc_info=True)
                    continue

                if resp.status_code in (403, 429):
                    self.log.warning(
                        "Bing search returned status %d for %s (rate limit / forbidden)",
                        resp.status_code,
                        domain,
                    )
                    continue
                if resp.status_code != 200:
                    self.log.debug(
                        "Bing search returned non-200 status %d for %s", resp.status_code, domain
                    )
                    continue

                extracted = extract_domain_emails(resp.text, domain)
                found.update(extracted)

            for email in sorted(found):
                yield Email(
                    value=email,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "bing", "domain": domain},
                )
