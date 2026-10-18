"""CV / Resume hunter module for user full name."""

from __future__ import annotations

import re
from typing import ClassVar, Iterable
from urllib.parse import parse_qs, quote_plus, urlparse

from tddt.core.entity import BaseEntity, Document, FullName
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)

DOC_EXTENSIONS = (".pdf", ".doc", ".docx")
GOOGLE_DOMAINS = ("google.com", "google.", "gstatic.com", "googleapis.com")


@register_module(
    name="user.fullname.cv_hunter",
    mode=["user"],
    consumes=[FullName],
    produces=[Document],
    active=False,
    requires_key=None,
)
class FullNameCvHunterModule(BaseModule):
    """Searches Google for CVs and Resumes associated with a person's full name."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, FullName):
                continue

            query = f'"{entity.value}" (filetype:pdf OR filetype:doc OR filetype:docx)'
            url = f"https://www.google.com/search?q={quote_plus(query)}"

            try:
                resp = self.client.get(url)
            except Exception as e:
                _log.warning("HTTP error searching CVs for %s: %s", entity.value, e)
                continue

            if resp.status_code in (403, 429):
                _log.warning("Google CV hunter rate limited / blocked for %s (status %d)", entity.value, resp.status_code)
                continue

            if resp.status_code != 200:
                _log.debug("Google CV hunter returned status %d for %s", resp.status_code, entity.value)
                continue

            seen_urls = set()
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

                path_lower = parsed.path.lower()
                matching_ext = next((ext for ext in DOC_EXTENSIONS if path_lower.endswith(ext)), None)
                if not matching_ext:
                    continue

                if target_url in seen_urls:
                    continue
                seen_urls.add(target_url)

                yield Document(
                    value=target_url,
                    source_module=self.name,
                    confidence=0.8,
                    metadata={"fullname": entity.value, "filetype": matching_ext.lstrip(".")},
                )
