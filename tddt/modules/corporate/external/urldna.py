"""urlDNA.io deep web and technology intelligence module."""

from __future__ import annotations

import time
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, Finding, Technology
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.external.urldna",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Technology, Finding],
    active=False,
    requires_key="urldna_api_key",
)
class UrlDnaModule(BaseModule):
    """Integrates with urlDNA API for deep technology detection and verdict analysis."""

    def _analyze_with_client(
        self,
        entity: Domain,
        client: object,
        poll_sleep: float = 5.0,
        max_poll: int = 12,
    ) -> Iterable[BaseEntity]:
        domain = entity.value.strip().lower()
        target_url = f"https://{domain}"

        scan_id = None
        try:
            search_results = getattr(client, "search")(domain)
            if search_results and len(search_results) > 0:
                scan_id = getattr(search_results[0], "id", None)
        except Exception:
            self.log.debug("urlDNA search error for %s", domain, exc_info=True)

        if not scan_id:
            try:
                scan_result = getattr(client, "create_scan")(target_url)
                scan_id = getattr(getattr(scan_result, "scan", None), "id", None)
            except Exception:
                self.log.debug("urlDNA create_scan error for %s", domain, exc_info=True)
                return

        if not scan_id:
            return

        # Bug §2.11 fix: Polling loop with max_poll=12 x 5s instead of static sleep(5)
        data = None
        for _ in range(max_poll):
            try:
                data = getattr(client, "get_scan")(scan_id)
                # If technologies or classification ready, break
                if (hasattr(data, "technologies") and getattr(data, "technologies")) or (
                    hasattr(data, "classification") and getattr(data, "classification")
                ):
                    break
            except Exception:
                self.log.debug("urlDNA get_scan error during polling for %s", scan_id, exc_info=True)
            time.sleep(poll_sleep)

        if data is None:
            return

        # Technologies
        try:
            if hasattr(data, "technologies") and data.technologies:
                for t in data.technologies:
                    name = getattr(t, "name", "Unknown")
                    version = getattr(t, "version", None)
                    cat = getattr(t, "category", "")
                    label = f"{name} v{version}" if version else f"{name} ({cat})" if cat else str(name)
                    yield Technology(
                        value=label,
                        parent_id=entity.id,
                        source_module=self.name,
                        metadata={"name": name, "version": version, "category": cat, "source": "urldna"},
                    )
        except Exception:
            self.log.debug("Error extracting technologies from urlDNA for %s", domain, exc_info=True)

        # Classification verdict
        try:
            if hasattr(data, "classification") and data.classification:
                verdict = getattr(data.classification, "verdict", "Unknown")
                yield Finding(
                    value=str(verdict),
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "urldna", "verdict": str(verdict), "scan_id": str(scan_id)},
                )
        except Exception:
            self.log.debug("Error extracting verdict from urlDNA for %s", domain, exc_info=True)

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            api_key = getattr(self.settings, "urldna", "") or getattr(
                self.settings, "urldna_api_key", ""
            )
            if not api_key:
                self.log.debug("urlDNA API key not configured; skipping %s", domain)
                continue

            try:
                from urldna import UrlDNA
            except ImportError:
                self.log.debug("urldna package not installed; skipping %s", domain)
                continue

            try:
                client = UrlDNA(api_key)
                yield from self._analyze_with_client(entity, client)
            except Exception:
                self.log.debug("urlDNA analysis failed for %s", domain, exc_info=True)
