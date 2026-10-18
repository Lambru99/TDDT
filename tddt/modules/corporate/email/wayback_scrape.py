"""Wayback Machine crawled page scraping module for email discovery."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urlparse

from tddt.core.entity import BaseEntity, Email, URL
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import extract_domain_emails


@register_module(
    name="corporate.email.wayback_scrape",
    mode=["corporate"],
    consumes=[URL],
    produces=[Email],
    active=False,
    requires_key=None,
)
class WaybackScrapeEmailModule(BaseModule):
    """Extracts emails from historical archived URLs."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, URL):
                continue

            target_url = entity.value
            domain = entity.metadata.get("domain", "")
            if not domain:
                # Attempt to parse target domain from wayback URL or URL itself
                # Wayback formats: https://web.archive.org/web/timestamp/http[s]://domain.com/path
                m = re.search(r"https?://web\.archive\.org/web/\d+/(https?://([^/]+))", target_url)
                if m:
                    domain = urlparse(m.group(1)).netloc.lower()
                else:
                    domain = urlparse(target_url).netloc.lower()

            # Fix/feature: zero extra traffic if body is already present in metadata
            body = entity.metadata.get("body")
            if not body:
                try:
                    resp = self.client.get(target_url, timeout=10)
                    if resp.status_code == 200:
                        body = resp.text
                    else:
                        self.log.debug("Wayback URL %s returned status %d", target_url, resp.status_code)
                        continue
                except Exception:
                    self.log.debug("Failed to fetch Wayback URL %s", target_url, exc_info=True)
                    continue

            emails = extract_domain_emails(body, domain)
            for email in sorted(emails):
                yield Email(
                    value=email,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "wayback_scrape", "url": target_url, "domain": domain},
                )
