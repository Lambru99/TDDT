"""Favicon reconnaissance module via MurmurHash3 hashing.

Fetches favicon.ico for discovered domains and calculates its MurmurHash3 value
on base64-encoded content (standard Shodan / FavFreak format). Matches hashes
against a signature database to identify technologies, frameworks, and appliances.
"""

from __future__ import annotations

import codecs
from collections.abc import Iterable
from urllib.parse import urljoin

import mmh3
from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Domain, Technology
from tddt.core.module import BaseModule, register_module

# MurmurHash3 (base64) signature database
FAVICON_SIGNATURES: dict[int, str] = {
    116323821: "Spring Boot",
    -1566948357: "Jenkins",
    81586312: "Jenkins (Old)",
    -674393285: "Docker",
    -205568434: "Kubernetes",
    1768625805: "Atlassian Jira",
    -1255745778: "Cobalt Strike Beacon",
    366968058: "Outlook Web Access",
    -446862803: "Plesk",
    -1473489816: "cPanel",
    -150253027: "Grafana",
    708578229: "GitLab",
    1461153895: "Fortinet",
    -373567943: "F5 BIG-IP",
    1062420841: "Cisco ASA",
    -305179312: "phpMyAdmin",
    1356064789: "Kibana",
    -120560460: "RabbitMQ",
    -1014138096: "Prometheus",
    127455077: "Traefik",
    -13086938: "Vault by HashiCorp",
    -1090158302: "Consul by HashiCorp",
    2018873738: "Keycloak",
    -127886975: "pfSense",
    -346747164: "Apache Tomcat",
    -1755151594: "Zabbix",
}


@register_module(
    name="corporate.web.favicon_recon",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Technology],
    active=False,
    requires_key=None,
)
class FaviconReconModule(BaseModule):
    """Identifies technologies from favicon MurmurHash3 hashes."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.signatures = dict(FAVICON_SIGNATURES)

    def _get_favicon_bytes(self, domain: str) -> bytes | None:
        for proto in ("https", "http"):
            # 1. Try direct /favicon.ico
            fav_url = f"{proto}://{domain}/favicon.ico"
            try:
                resp = self.client.get(fav_url, timeout=5)
                if resp.status_code == 200 and resp.content:
                    return resp.content
            except Exception:
                self.log.debug("Favicon fetch failed for %s", fav_url)

            # 2. Try parsing <link rel="icon"> from homepage
            home_url = f"{proto}://{domain}"
            try:
                home_resp = self.client.get(home_url, timeout=5)
                if home_resp.status_code == 200:
                    soup = BeautifulSoup(home_resp.text, "html.parser")
                    for link in soup.find_all("link", rel=True):
                        rel = [r.lower() for r in link["rel"]]
                        if any(r in ("icon", "shortcut icon") for r in rel):
                            href = link.get("href")
                            if href:
                                icon_url = urljoin(home_url, href)
                                icon_resp = self.client.get(icon_url, timeout=5)
                                if icon_resp.status_code == 200 and icon_resp.content:
                                    return icon_resp.content
            except Exception:
                self.log.debug("Homepage icon link parsing failed for %s", home_url)
        return None

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            content = self._get_favicon_bytes(domain)
            if not content:
                continue

            try:
                b64 = codecs.encode(content, "base64")
                fav_hash = mmh3.hash(b64)
            except Exception:
                self.log.warning("Failed to compute mmh3 favicon hash for %s", domain, exc_info=True)
                continue

            tech_name = self.signatures.get(fav_hash)
            if tech_name:
                yield Technology(
                    value=tech_name,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"category": "favicon", "hash": fav_hash, "domain": domain},
                )
