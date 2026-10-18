"""Google dork module for user email profiling."""

from __future__ import annotations

import re
from typing import ClassVar, Iterable
from urllib.parse import parse_qs, unquote, urlparse

from tddt.core.entity import BaseEntity, Document, Email, Service, URL
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)

DOC_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".odt",
    ".ods",
    ".rtf",
    ".txt",
)

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

GOOGLE_DOMAINS = (
    "google.com",
    "google.",
    "gstatic.com",
    "googleapis.com",
    "w3.org",
    "schema.org",
)


@register_module(
    name="user.email.google_dork",
    mode=["user"],
    consumes=[Email],
    produces=[URL, Document, Service],
    active=False,
    requires_key=None,
)
class UserGoogleDorkModule(BaseModule):
    """Searches Google for occurrences of the email address."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Email):
                continue

            query = f'"{entity.value}"'
            url = f"https://www.google.com/search?q={query}"

            try:
                resp = self.client.get(url)
            except Exception as e:
                _log.warning("HTTP error searching Google for %s: %s", entity.value, e)
                continue

            if resp.status_code in (403, 429):
                _log.warning(
                    "Google search rate limited / blocked for %s (status %d)",
                    entity.value,
                    resp.status_code,
                )
                continue

            if resp.status_code != 200:
                _log.debug("Google search returned status %d for %s", resp.status_code, entity.value)
                continue

            seen_urls = set()
            # Extract href links from response text
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

                if target_url in seen_urls:
                    continue
                seen_urls.add(target_url)

                path_lower = parsed.path.lower()
                if any(path_lower.endswith(ext) for ext in DOC_EXTENSIONS):
                    yield Document(
                        value=target_url,
                        source_module=self.name,
                        confidence=0.7,
                        metadata={"email": entity.value},
                    )
                elif any(sd in netloc for sd in SOCIAL_DOMAINS):
                    yield Service(
                        value=target_url,
                        source_module=self.name,
                        confidence=0.75,
                        metadata={"email": entity.value},
                    )
                else:
                    yield URL(
                        value=target_url,
                        source_module=self.name,
                        confidence=0.6,
                        metadata={"email": entity.value},
                    )
