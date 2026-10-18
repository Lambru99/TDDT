"""Personal website discovery module for user full name."""

from __future__ import annotations

import re
from typing import ClassVar, Iterable
from urllib.parse import parse_qs, quote_plus, urlparse

from tddt.core.entity import BaseEntity, Domain, FullName, URL
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)

GOOGLE_DOMAINS = ("google.com", "google.", "gstatic.com", "googleapis.com")


@register_module(
    name="user.fullname.personal_site",
    mode=["user"],
    consumes=[FullName],
    produces=[Domain, URL],
    active=False,
    requires_key=None,
)
class FullNamePersonalSiteModule(BaseModule):
    """Searches Google for personal domains/blogs matching a person's full name."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, FullName):
                continue

            query = f'"{entity.value}" (site:.me OR site:.dev OR site:.bio OR site:.info OR site:.blog OR site:.io)'
            url = f"https://www.google.com/search?q={quote_plus(query)}"

            try:
                resp = self.client.get(url)
            except Exception as e:
                _log.warning("HTTP error searching personal sites for %s: %s", entity.value, e)
                continue

            if resp.status_code in (403, 429):
                _log.warning("Google personal site search rate limited for %s (status %d)", entity.value, resp.status_code)
                continue

            if resp.status_code != 200:
                _log.debug("Google personal site search returned status %d for %s", resp.status_code, entity.value)
                continue

            seen_domains = set()
            raw_links = re.findall(r'href=["\']([^"\']+)["\']', resp.text)
            for raw_link in raw_links:
                target_url = raw_link
                if target_url.startswith("/url?q="):
                    parsed_qs = parse_qs(urlparse(target_url).query)
                    q_vals = parsed_qs.get("q")
                    if q_vals:
                        target_url = q_vals[0]
                elif not target_url.startswith(("http://", "https://")):
                    continue

                parsed = urlparse(target_url)
                netloc = parsed.netloc.lower()
                if not netloc or any(gd in netloc for gd in GOOGLE_DOMAINS):
                    continue

                domain = netloc.split(":")[0]
                if domain.startswith("www."):
                    domain = domain[4:]

                if domain not in seen_domains:
                    seen_domains.add(domain)
                    yield Domain(
                        value=domain,
                        source_module=self.name,
                        confidence=0.75,
                        metadata={"fullname": entity.value, "url": target_url},
                    )

                yield URL(
                    value=target_url,
                    source_module=self.name,
                    confidence=0.6,
                    metadata={"fullname": entity.value},
                )
