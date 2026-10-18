"""Shodan InternetDB port and vulnerability lookup module."""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, CVE, Finding, IPAddress, Port
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.vuln.internetdb",
    mode=["corporate"],
    consumes=[IPAddress],
    produces=[Port, CVE, Finding],
    active=False,
    requires_key=None,
)
class InternetDbModule(BaseModule):
    """Queries Shodan InternetDB for open ports, vulnerabilities, and host tags."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, IPAddress):
                continue

            ip = entity.value.strip()
            url = f"https://internetdb.shodan.io/{ip}"

            try:
                resp = self.client.get(
                    url, host_hint="internetdb.shodan.io", timeout=10
                )
            except Exception:
                self.log.debug("InternetDB lookup failed for %s", ip, exc_info=True)
                continue

            if resp.status_code == 404:
                self.log.debug("InternetDB returned 404 for %s", ip)
                continue
            if resp.status_code != 200:
                self.log.debug("InternetDB returned non-200 status %d for %s", resp.status_code, ip)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.debug("Failed to decode InternetDB JSON for %s", ip, exc_info=True)
                continue

            ports = data.get("ports", [])
            vulns = data.get("vulns", [])
            tags = data.get("tags", [])

            # Bug §2.4 fix: >= 100 ports drops confidence to 0.5 and verified=False
            if len(ports) >= 100:
                conf = 0.5
                verified = False
            else:
                conf = 0.9
                verified = True

            for p in ports:
                yield Port(
                    value=str(p),
                    parent_id=entity.id,
                    source_module=self.name,
                    confidence=conf,
                    metadata={"verified": verified, "ip": ip},
                )

            # Bug §2.3 fix: CVE entities ALWAYS emitted when vulns returned
            for v in vulns:
                yield CVE(
                    value=str(v),
                    parent_id=entity.id,
                    source_module=self.name,
                    confidence=0.9,
                    metadata={"ip": ip},
                )

            for t in tags:
                yield Finding(
                    value=str(t),
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"tag": str(t), "ip": ip},
                )
