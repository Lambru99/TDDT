"""Pastebin dork module for leaked email discovery."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote_plus

from tddt.core.entity import BaseEntity, Domain, Email
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import extract_domain_emails


@register_module(
    name="corporate.email.pastebin_dork",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email],
    active=False,
    requires_key=None,
)
class PastebinDorkEmailModule(BaseModule):
    """Harvests emails from Pastebin via search dorks."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            query = f'site:pastebin.com "@{domain}"'
            url = f"https://www.bing.com/search?q={quote_plus(query)}&first=0"

            try:
                resp = self.client.get(url, host_hint="www.bing.com", timeout=10)
            except Exception:
                self.log.debug("Pastebin dork request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code in (403, 429):
                self.log.warning(
                    "Pastebin search dork returned status %d for %s (forbidden / rate limit)",
                    resp.status_code,
                    domain,
                )
                continue
            if resp.status_code != 200:
                self.log.debug(
                    "Pastebin search dork returned status %d for %s", resp.status_code, domain
                )
                continue

            emails = extract_domain_emails(resp.text, domain)
            for email in sorted(emails):
                yield Email(
                    value=email,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "pastebin_dork", "domain": domain},
                )
