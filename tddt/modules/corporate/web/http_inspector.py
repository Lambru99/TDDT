"""HTTP surface inspector module.

Probes target domains/subdomains over HTTPS then HTTP with TLS verification
enabled by default (fixing bug §2.9). Extracts status code, page title,
server headers, and captures the response body and headers in the URL entity's
metadata for downstream reuse (fixing bug §2.secondary).
"""

from __future__ import annotations

from collections.abc import Iterable

from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Domain, URL
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.web.http_inspector",
    mode=["corporate"],
    consumes=[Domain],
    produces=[URL],
    active=False,
    requires_key=None,
)
class HttpInspectorModule(BaseModule):
    """Inspects HTTP/HTTPS services on discovered domains."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            for proto in ("https", "http"):
                url = f"{proto}://{domain}"
                try:
                    resp = self.client.get(url, allow_redirects=True)
                except Exception:
                    self.log.debug("HTTP inspector connection failed for %s", url)
                    continue

                if resp.status_code == 0:
                    continue

                try:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    title = soup.title.string.strip() if soup.title and soup.title.string else ""
                except Exception:
                    self.log.debug("Failed to parse HTML title for %s", url)
                    title = ""

                server = resp.headers.get("Server", "N/A")
                metadata = {
                    "domain": domain,
                    "status_code": resp.status_code,
                    "title": title[:100],
                    "server": server,
                    "headers": dict(resp.headers),
                    "body": resp.text,
                }

                clean_url = resp.url.rstrip("/") if resp.url.endswith("/") and resp.url.count("/") == 3 else resp.url
                yield URL(
                    value=clean_url,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata=metadata,
                )
                # Successful probe on https or http -> move to next domain
                break
