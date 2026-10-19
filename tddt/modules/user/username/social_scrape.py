"""Social profile scraper using privacy-preserving mirrors (e.g. Nitter)."""

from __future__ import annotations

import re
from collections.abc import Iterable

from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Email, Service, URL, Username
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import EMAIL_REGEX

NITTER_MIRRORS = [
    "nitter.net",
    "nitter.poast.org",
    "nitter.privacydev.net",
]

URL_REGEX = re.compile(r"https?://[^\s\"'<>]+")

# CSS selectors for Nitter profile content zones (bio + pinned tweets).
_PROFILE_SELECTORS = [
    ".profile-bio",
    ".profile-card",
    ".profile-card-extra",
    ".tweet-content",
    ".timeline-item",
]

# Domains/paths belonging to the Nitter project itself, not to any user.
_NITTER_INFRA_PATTERNS = frozenset({
    "liberapay.com/zedeus",
    "patreon.com/nitter",
    "ko-fi.com/zedeus",
    "matrix.to/#/@zedeus",
    "zedeus@",
})


def _is_nitter_infra(value: str) -> bool:
    low = value.lower()
    return any(pat in low for pat in _NITTER_INFRA_PATTERNS)


def _extract_profile_text(html: str) -> str:
    """Return text from profile-specific zones only, or empty if none found."""
    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []
    for sel in _PROFILE_SELECTORS:
        for tag in soup.select(sel):
            parts.append(str(tag))
    return "\n".join(parts)


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
                    if resp.status_code != 200:
                        continue

                    profile_html = _extract_profile_text(resp.text)
                    if not profile_html:
                        self.log.debug(
                            "No profile content found on %s — page may be a notice/splash",
                            url,
                        )
                        break

                    for m in EMAIL_REGEX.findall(profile_html):
                        em = m.strip().lower()
                        if _is_nitter_infra(em):
                            continue
                        yield Email(
                            value=em,
                            parent_id=entity.id,
                            source_module=self.name,
                            confidence=0.8,
                            metadata={"source": f"social_scrape:{mirror}", "username": username},
                        )

                    for link in URL_REGEX.findall(profile_html):
                        clean_link = link.strip().rstrip(".,;)")
                        if mirror in clean_link or "twitter.com" in clean_link:
                            continue
                        if _is_nitter_infra(clean_link):
                            continue
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
