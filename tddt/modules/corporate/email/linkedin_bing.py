"""LinkedIn employee profiling and email discovery via Bing search."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Domain, Email, FullName
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import extract_domain_emails


@register_module(
    name="corporate.email.linkedin_bing",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email, FullName],
    active=False,
    requires_key=None,
)
class LinkedInBingModule(BaseModule):
    """Harvests LinkedIn employee profiles and emails using Bing search."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            query = f'site:linkedin.com/in/ "{domain}"'
            url = f"https://www.bing.com/search?q={quote_plus(query)}&first=0"

            try:
                resp = self.client.get(url, host_hint="www.bing.com", timeout=10)
            except Exception:
                self.log.debug("LinkedIn Bing scraping failed for %s", domain, exc_info=True)
                continue

            if resp.status_code in (403, 429):
                self.log.warning(
                    "LinkedIn Bing search returned status %d for %s (forbidden / rate limit)",
                    resp.status_code,
                    domain,
                )
                continue
            if resp.status_code != 200:
                self.log.debug(
                    "LinkedIn Bing search returned status %d for %s", resp.status_code, domain
                )
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            names: set[str] = set()

            for link in soup.find_all("a"):
                href = link.get("href", "")
                if "linkedin.com/in/" in href:
                    raw_text = link.get_text().strip()
                    parts = re.split(r"\s+[-|–—]\s+", raw_text)
                    if parts:
                        candidate_name = parts[0].strip()
                        words = candidate_name.split()
                        if 1 < len(words) <= 4 and all(w.replace(".", "").isalpha() for w in words):
                            names.add(candidate_name)

            for name in sorted(names):
                yield FullName(
                    value=name,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "linkedin_bing", "domain": domain},
                )

            emails = extract_domain_emails(resp.text, domain)
            for email in sorted(emails):
                yield Email(
                    value=email,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "linkedin_bing", "domain": domain},
                )
