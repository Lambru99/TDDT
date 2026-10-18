"""Wayback Machine CDX archive harvester module.

Queries web.archive.org CDX API for historical URLs associated with target domains.
Identifies potentially sensitive / juicy files (.sql, .env, .bak, .zip, etc.).
"""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, URL
from tddt.core.module import BaseModule, register_module

JUICY_EXTENSIONS = (
    ".bak", ".old", ".backup", ".sql", ".zip", ".rar",
    ".env", ".config", ".xml", ".json", ".git", ".sh",
    ".yaml", ".yml", ".pem", ".key", ".p12", ".pfx",
    ".log", ".dump", ".tar", ".gz", ".7z", ".passwd",
)


def is_juicy(url: str) -> bool:
    low = url.lower()
    return any(low.endswith(ext) or f"{ext}?" in low for ext in JUICY_EXTENSIONS)


@register_module(
    name="corporate.wayback.wayback_machine",
    mode=["corporate"],
    consumes=[Domain],
    produces=[URL],
    active=False,
    requires_key=None,
)
class WaybackMachineModule(BaseModule):
    """Harvests historical URLs from the Wayback Machine."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            url = "https://web.archive.org/cdx/search/cdx"
            params = {
                "url": f"*.{domain}/*",
                "collapse": "urlkey",
                "output": "json",
                "fl": "original",
                "filter": "statuscode:200",
                "limit": 3000,
            }

            try:
                resp = self.client.get(url, params=params, host_hint="web.archive.org")
            except Exception:
                self.log.warning("wayback_machine query failed for %s", domain, exc_info=True)
                continue

            if resp.status_code != 200:
                self.log.debug("wayback_machine returned status %d for %s", resp.status_code, domain)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.debug("wayback_machine invalid JSON for %s", domain)
                continue

            if not isinstance(data, list) or len(data) <= 1:
                continue

            seen: set[str] = set()
            for row in data[1:]:
                if not row or not isinstance(row, list):
                    continue
                u = row[0].strip()
                if u and u not in seen:
                    seen.add(u)
                    yield URL(
                        value=u,
                        parent_id=entity.id,
                        source_module=self.name,
                        metadata={
                            "domain": domain,
                            "source": "wayback",
                            "juicy": is_juicy(u),
                        },
                    )
