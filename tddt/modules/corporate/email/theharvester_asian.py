"""theHarvester-style Asian search engine harvester (Baidu)."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote_plus

from tddt.core.entity import BaseEntity, Domain, Email
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import extract_domain_emails


@register_module(
    name="corporate.email.theharvester_asian",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email],
    active=False,
    requires_key=None,
)
class TheHarvesterAsianModule(BaseModule):
    """Harvests emails from Asian search engine (Baidu)."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            url = f"https://www.baidu.com/s?wd={quote_plus(f'@{domain}')}"

            try:
                resp = self.client.get(url, host_hint="www.baidu.com", timeout=10)
            except Exception:
                self.log.debug("Baidu search query failed for %s", domain, exc_info=True)
                continue

            if resp.status_code in (403, 429):
                self.log.warning(
                    "Baidu search returned status %d for %s (blocked / rate limit)",
                    resp.status_code,
                    domain,
                )
                continue
            if resp.status_code != 200:
                self.log.debug("Baidu search returned status %d for %s", resp.status_code, domain)
                continue

            emails = extract_domain_emails(resp.text, domain)
            for email in sorted(emails):
                yield Email(
                    value=email,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "theharvester_asian", "engine": "baidu", "domain": domain},
                )
