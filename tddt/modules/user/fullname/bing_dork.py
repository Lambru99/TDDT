"""Bing dork module for user full name profiling."""

from __future__ import annotations

import re
from typing import ClassVar, Iterable
from urllib.parse import quote_plus, urlparse

from tddt.core.entity import BaseEntity, FullName, Service, URL
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)

SOCIAL_DOMAINS = (
    "github.com",
    "gitlab.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "instagram.com",
    "facebook.com",
    "reddit.com",
    "medium.com",
    "youtube.com",
    "pinterest.com",
)

BING_DOMAINS = (
    "bing.com",
    "bing.net",
    "microsoft.com",
    "live.com",
    "msn.com",
)


@register_module(
    name="user.fullname.bing_dork",
    mode=["user"],
    consumes=[FullName],
    produces=[URL, Service],
    active=False,
    requires_key=None,
)
class FullNameBingDorkModule(BaseModule):
    """Searches Bing for occurrences of a person's full name."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, FullName):
                continue

            query = f'"{entity.value}"'
            url = f"https://www.bing.com/search?q={quote_plus(query)}"

            try:
                resp = self.client.get(url)
            except Exception as e:
                _log.warning("HTTP error searching Bing for name %s: %s", entity.value, e)
                continue

            if resp.status_code in (403, 429):
                _log.warning("Bing search rate limited / blocked for %s (status %d)", entity.value, resp.status_code)
                continue

            if resp.status_code != 200:
                _log.debug("Bing search returned status %d for %s", resp.status_code, entity.value)
                continue

            seen_urls = set()
            raw_links = re.findall(r'href=["\'](https?://[^"\']+)["\']', resp.text)
            for raw_link in raw_links:
                target_url = raw_link
                parsed = urlparse(target_url)
                netloc = parsed.netloc.lower()
                if not netloc or any(bd in netloc for bd in BING_DOMAINS):
                    continue

                if target_url in seen_urls:
                    continue
                seen_urls.add(target_url)

                if any(sd in netloc for sd in SOCIAL_DOMAINS):
                    yield Service(
                        value=target_url,
                        source_module=self.name,
                        confidence=0.7,
                        metadata={"fullname": entity.value},
                    )
                else:
                    yield URL(
                        value=target_url,
                        source_module=self.name,
                        confidence=0.6,
                        metadata={"fullname": entity.value},
                    )
