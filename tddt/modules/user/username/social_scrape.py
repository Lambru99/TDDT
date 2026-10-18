"""Social profile scraper using privacy-preserving mirrors (e.g. Nitter)."""

from __future__ import annotations

import re
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Email, Service, URL, Username
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import EMAIL_REGEX

NITTER_MIRRORS = [
    "nitter.net",
    "nitter.poast.org",
    "nitter.privacydev.net",
]

URL_REGEX = re.compile(r"https?://[^\s\"'<>]+")


@register_module(
    name="user.username.social_scrape",
    mode=["user"],
    consumes=[Service, Username],
    produces=[URL, Email],
    active=False,
    requires_key=None,
)
class SocialScrapeModule(BaseModule):
    """Scrapes public social media profiles via open mirror proxies to bypass auth walls."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            username = ""
            if isinstance(entity, Service):
                site = str(entity.metadata.get("site", "")).lower()
                if "twitter" not in site and site != "x":
                    continue
                username = entity.metadata.get("username") or entity.value.split(":")[-1]
            elif isinstance(entity, Username):
                username = entity.value.strip()

            if not username:
                continue

            for mirror in NITTER_MIRRORS:
                url = f"https://{mirror}/{username}"
                try:
                    resp = self.client.get(url, timeout=10)
                    if resp.status_code == 200:
                        # Extract emails
                        for m in EMAIL_REGEX.findall(resp.text):
                            em = m.strip().lower()
                            yield Email(
                                value=em,
                                parent_id=entity.id,
                                source_module=self.name,
                                confidence=0.8,
                                metadata={"source": f"social_scrape:{mirror}", "username": username},
                            )

                        # Extract external URLs
                        for link in URL_REGEX.findall(resp.text):
                            clean_link = link.strip().rstrip(".,;)")
                            if mirror not in clean_link and "twitter.com" not in clean_link:
                                yield URL(
                                    value=clean_link,
                                    parent_id=entity.id,
                                    source_module=self.name,
                                    confidence=0.7,
                                    metadata={"source": f"social_scrape:{mirror}", "username": username},
                                )
                        break
                except Exception:
                    self.log.debug("Mirror %s failed for %s", mirror, username, exc_info=True)
                    continue
