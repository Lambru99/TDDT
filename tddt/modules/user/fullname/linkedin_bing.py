"""Bing LinkedIn dork module for user full name profiling."""

from __future__ import annotations

import re
from typing import ClassVar, Iterable
from urllib.parse import quote_plus, urlparse

from tddt.core.entity import BaseEntity, FullName, Service
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)


@register_module(
    name="user.fullname.linkedin_bing",
    mode=["user"],
    consumes=[FullName],
    produces=[Service],
    active=False,
    requires_key=None,
)
class FullNameLinkedinBingModule(BaseModule):
    """Searches Bing for LinkedIn profiles matching a person's full name."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, FullName):
                continue

            query = f'site:linkedin.com/in/ "{entity.value}"'
            url = f"https://www.bing.com/search?q={quote_plus(query)}"

            try:
                resp = self.client.get(url)
            except Exception as e:
                _log.warning("HTTP error searching Bing for LinkedIn %s: %s", entity.value, e)
                continue

            if resp.status_code in (403, 429):
                _log.warning("Bing LinkedIn search rate limited / blocked for %s (status %d)", entity.value, resp.status_code)
                continue

            if resp.status_code != 200:
                _log.debug("Bing LinkedIn search returned status %d for %s", resp.status_code, entity.value)
                continue

            seen_urls = set()
            raw_links = re.findall(r'href=["\'](https?://[^"\']+)["\']', resp.text)
            for raw_link in raw_links:
                target_url = raw_link
                parsed = urlparse(target_url)
                netloc = parsed.netloc.lower()
                if "linkedin.com" not in netloc or "/in/" not in parsed.path:
                    continue

                clean_url = f"https://{parsed.netloc}{parsed.path}".rstrip("/")
                if clean_url in seen_urls:
                    continue
                seen_urls.add(clean_url)

                yield Service(
                    value=clean_url,
                    source_module=self.name,
                    confidence=0.85,
                    metadata={"platform": "linkedin", "fullname": entity.value},
                )
