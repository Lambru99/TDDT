"""Reverse WHOIS module by registrant full name via ViewDNS."""

from __future__ import annotations

import re
from typing import ClassVar, Iterable
from urllib.parse import quote_plus

from tddt.core.entity import BaseEntity, Domain, FullName
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)

DOMAIN_RE = re.compile(r"\b([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,})\b")
EXCLUDED_DOMAINS = ("viewdns.info", "schema.org", "w3.org", "google.com")


@register_module(
    name="user.fullname.reverse_whois",
    mode=["user"],
    consumes=[FullName],
    produces=[Domain],
    active=False,
    requires_key=None,
)
class FullNameReverseWhoisModule(BaseModule):
    """Discovers registered domains for a full name via ViewDNS reverse WHOIS."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, FullName):
                continue

            query = entity.value.strip()
            url = f"https://viewdns.info/reversewhois/?q={quote_plus(query)}"

            try:
                resp = self.client.get(url, host_hint="viewdns.info")
            except Exception as e:
                _log.warning("HTTP error querying ViewDNS reverse WHOIS for %s: %s", entity.value, e)
                continue

            if resp.status_code in (403, 429):
                _log.warning("ViewDNS rate limited for %s (status %d)", entity.value, resp.status_code)
                continue

            if resp.status_code != 200:
                _log.debug("ViewDNS returned status %d for %s", resp.status_code, entity.value)
                continue

            seen_domains = set()
            for match in DOMAIN_RE.finditer(resp.text):
                domain = match.group(1).lower()
                if any(ex in domain for ex in EXCLUDED_DOMAINS):
                    continue
                if domain in seen_domains:
                    continue
                seen_domains.add(domain)

                yield Domain(
                    value=domain,
                    source_module=self.name,
                    confidence=0.7,
                    metadata={"registrant": entity.value, "source": "viewdns"},
                )
