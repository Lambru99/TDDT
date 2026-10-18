"""Social profile scraper module extracting full names, websites, and emails."""

from __future__ import annotations

import re
from typing import ClassVar, Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Email, FullName, Service, Website
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module
from tddt.modules.user.service.avatar_hasher import _resolve_service_url

_log = get_logger(__name__)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
EXCLUDED_NETLOCS = (
    "github.com",
    "gitlab.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
)


@register_module(
    name="user.service.profile_scraper",
    mode=["user"],
    consumes=[Service],
    produces=[FullName, Website, Email],
    active=False,
    requires_key=None,
)
class ServiceProfileScraperModule(BaseModule):
    """Scrapes profile metadata, real name, and outbound personal websites from services."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Service):
                continue

            probe_url = _resolve_service_url(entity)
            if probe_url is None:
                _log.debug("Service %s has no http(s) URL to probe; skipping", entity.value)
                continue

            try:
                resp = self.client.get(probe_url, timeout=15)
            except Exception as e:
                _log.warning("HTTP error scraping profile %s: %s", entity.value, e)
                continue

            if resp.status_code != 200:
                _log.debug("Profile page returned HTTP %d for %s", resp.status_code, entity.value)
                continue

            try:
                soup = BeautifulSoup(resp.text, "html.parser")
            except Exception as e:
                _log.debug("HTML parsing failed for %s: %s", entity.value, e)
                continue

            # Extract FullName
            name_candidates = []
            for sel in [".p-name", ".vcard-fullname", "h1.vcard-names span", "meta[property='og:title']"]:
                tag = soup.select_one(sel)
                if tag:
                    text = tag.get("content") if tag.name == "meta" else tag.get_text()
                    if text and isinstance(text, str):
                        clean = text.strip()
                        if clean and len(clean.split()) >= 2:
                            name_candidates.append(clean)

            if name_candidates:
                yield FullName(
                    value=name_candidates[0],
                    source_module=self.name,
                    confidence=0.85,
                    metadata={"service": entity.value},
                )

            # Extract personal Website
            seen_websites = set()
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if not href.startswith(("http://", "https://")):
                    continue
                parsed = urlparse(href)
                netloc = parsed.netloc.lower()
                if not netloc or any(ex in netloc for ex in EXCLUDED_NETLOCS):
                    continue
                rel = link.get("rel", [])
                rel_str = " ".join(rel) if isinstance(rel, list) else str(rel)
                # Matches rel="me" or profile website selectors
                if "me" in rel_str or link.find_parent(class_=re.compile(r"vcard|profile|bio")):
                    if href not in seen_websites:
                        seen_websites.add(href)
                        yield Website(
                            value=href,
                            source_module=self.name,
                            confidence=0.8,
                            metadata={"service": entity.value, "rel": rel_str},
                        )

            # Extract Emails
            seen_emails = set()
            for match in EMAIL_RE.finditer(resp.text):
                email_val = match.group(0).lower()
                if email_val in seen_emails:
                    continue
                seen_emails.add(email_val)
                yield Email(
                    value=email_val,
                    source_module=self.name,
                    confidence=0.75,
                    metadata={"service": entity.value, "source": "profile_scraper"},
                )
