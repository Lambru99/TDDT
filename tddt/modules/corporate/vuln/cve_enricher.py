"""CVE enrichment module using public vulnerability APIs."""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, CVE, Finding
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.vuln.cve_enricher",
    mode=["corporate"],
    consumes=[CVE],
    produces=[Finding],
    active=False,
    requires_key=None,
)
class CveEnricherModule(BaseModule):
    """Enriches CVE entities with CVSS score, severity, and summary details."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, CVE):
                continue

            cve_id = entity.value.strip().upper()
            url = f"https://cve.circl.lu/api/cve/{cve_id}"

            try:
                resp = self.client.get(
                    url, host_hint="cve.circl.lu", timeout=10
                )
            except Exception:
                self.log.debug("CVE lookup failed for %s", cve_id, exc_info=True)
                continue

            if resp.status_code == 404:
                self.log.debug("CVE %s not found on circl.lu", cve_id)
                continue
            if resp.status_code != 200:
                self.log.debug("CVE API returned status %d for %s", resp.status_code, cve_id)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.debug("Failed to decode CVE JSON for %s", cve_id, exc_info=True)
                continue

            if isinstance(data, dict):
                cvss = data.get("cvss")
                summary = data.get("summary") or ""
                yield Finding(
                    value=cve_id,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={
                        "cve": cve_id,
                        "cvss": float(cvss) if cvss is not None else 0.0,
                        "summary": summary,
                        "published": data.get("Published"),
                        "source": "cve_enricher",
                    },
                )
