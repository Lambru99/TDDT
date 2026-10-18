"""CORS (Cross-Origin Resource Sharing) misconfiguration probe module.

Active module sending probes with arbitrary origins (e.g. https://evil.com)
to detect insecure reflection and credential disclosure via CORS headers.
"""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Finding, URL
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.web.cors_misconfig",
    mode=["corporate"],
    consumes=[URL],
    produces=[Finding],
    active=True,
    requires_key=None,
)
class CorsMisconfigModule(BaseModule):
    """Probes URLs for CORS misconfigurations."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        test_origin = "https://evil.com"
        headers = {"Origin": test_origin}

        for entity in entities:
            if not isinstance(entity, URL):
                continue

            try:
                resp = self.client.get(entity.value, headers=headers, timeout=5)
            except Exception:
                self.log.debug("CORS probe failed for %s", entity.value)
                continue

            acao = resp.headers.get("Access-Control-Allow-Origin", "").strip()
            acac = resp.headers.get("Access-Control-Allow-Credentials", "").strip().lower()

            if acao == test_origin or (acao == "*" and acac == "true"):
                severity = "high" if acac == "true" else "medium"
                self.log.warning(
                    "CORS misconfiguration detected on %s: ACAO=%s ACAC=%s",
                    entity.value,
                    acao,
                    acac,
                )
                yield Finding(
                    value=f"{entity.value}:cors_misconfig",
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={
                        "type": "cors_misconfiguration",
                        "url": entity.value,
                        "origin": test_origin,
                        "acao": acao,
                        "credentials": acac,
                        "severity": severity,
                    },
                )
