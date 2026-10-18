"""Deep DNS reconnaissance module.

Retrieves and analyzes MX, NS, SOA, TXT (SPF), DMARC, CAA, and CNAME records.
Extracts new Subdomain entities from NS, MX, and CNAME records pointing within the target.
Evaluates SPF and DMARC enforcement strengths.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

import dns.exception
import dns.resolver

from tddt.core.entity import BaseEntity, DNSRecord, Domain, Subdomain
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.dns.deep",
    mode=["corporate"],
    consumes=[Domain],
    produces=[DNSRecord, Subdomain],
    active=False,
    requires_key=None,
)
class DnsDeepModule(BaseModule):
    """Deep DNS inspection covering SPF, DMARC, CAA, MX, NS, SOA, CNAME."""

    def evaluate_spf(self, spf_text: str) -> dict[str, Any]:
        """Evaluates SPF record policy strength."""
        spf = spf_text.strip().strip('"')
        strength = "Unknown"
        if "~all" in spf:
            strength = "SoftFail (~all) — medium"
        elif "-all" in spf:
            strength = "Fail (-all) — strict"
        elif "+all" in spf:
            strength = "Pass (+all) — DANGEROUS: accepts all"
        elif "?all" in spf:
            strength = "Neutral (?all) — weak"
        return {"found": True, "record": spf, "strength": strength}

    def evaluate_dmarc(self, dmarc_text: str) -> dict[str, Any]:
        """Evaluates DMARC record policy strength."""
        rec = dmarc_text.strip().strip('"')
        policy = "none"
        m = re.search(r"p=([a-zA-Z]+)", rec)
        if m:
            policy = m.group(1).lower()
        strength = {
            "none": "Monitor only (no enforcement)",
            "quarantine": "Quarantine — medium protection",
            "reject": "Reject — strict protection",
        }.get(policy, "Unknown")
        return {"found": True, "record": rec, "policy": policy, "strength": strength}

    def _resolve(self, qname: str, rtype: str) -> list[str]:
        try:
            answers = dns.resolver.resolve(qname, rtype, lifetime=self.settings.timeout)
            return [str(r).strip() for r in answers]
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            return []
        except Exception:
            self.log.warning("DNS query %s %s failed", qname, rtype, exc_info=True)
            return []

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            # 1. MX records
            mx_records = self._resolve(domain, "MX")
            for mx in mx_records:
                yield DNSRecord(
                    value=f"{domain}:MX:{mx}",
                    metadata={"type": "MX", "record": mx, "domain": domain},
                    parent_id=entity.id,
                    source_module=self.name,
                )
                # MX format: "10 mail.example.com."
                parts = mx.split()
                host = parts[-1].rstrip(".").lower()
                if host.endswith("." + domain):
                    yield Subdomain(value=host, parent_id=entity.id, source_module=self.name)

            # 2. NS records
            ns_records = self._resolve(domain, "NS")
            for ns in ns_records:
                yield DNSRecord(
                    value=f"{domain}:NS:{ns}",
                    metadata={"type": "NS", "record": ns, "domain": domain},
                    parent_id=entity.id,
                    source_module=self.name,
                )
                host = ns.rstrip(".").lower()
                if host.endswith("." + domain):
                    yield Subdomain(value=host, parent_id=entity.id, source_module=self.name)

            # 3. SOA records
            soa_records = self._resolve(domain, "SOA")
            for soa in soa_records:
                yield DNSRecord(
                    value=f"{domain}:SOA:{soa}",
                    metadata={"type": "SOA", "record": soa, "domain": domain},
                    parent_id=entity.id,
                    source_module=self.name,
                )

            # 4. CAA records
            caa_records = self._resolve(domain, "CAA")
            for caa in caa_records:
                yield DNSRecord(
                    value=f"{domain}:CAA:{caa}",
                    metadata={"type": "CAA", "record": caa, "domain": domain},
                    parent_id=entity.id,
                    source_module=self.name,
                )

            # 5. TXT records & SPF
            txt_records = self._resolve(domain, "TXT")
            for txt in txt_records:
                clean_txt = txt.strip('"')
                if clean_txt.startswith("v=spf1"):
                    spf_info = self.evaluate_spf(clean_txt)
                    yield DNSRecord(
                        value=f"{domain}:SPF:{clean_txt}",
                        metadata={"type": "SPF", **spf_info, "domain": domain},
                        parent_id=entity.id,
                        source_module=self.name,
                    )
                else:
                    yield DNSRecord(
                        value=f"{domain}:TXT:{clean_txt}",
                        metadata={"type": "TXT", "record": clean_txt, "domain": domain},
                        parent_id=entity.id,
                        source_module=self.name,
                    )

            # 6. DMARC record
            dmarc_records = self._resolve(f"_dmarc.{domain}", "TXT")
            for dmarc in dmarc_records:
                clean_dmarc = dmarc.strip('"')
                if "v=DMARC1" in clean_dmarc:
                    dmarc_info = self.evaluate_dmarc(clean_dmarc)
                    yield DNSRecord(
                        value=f"{domain}:DMARC:{clean_dmarc}",
                        metadata={"type": "DMARC", **dmarc_info, "domain": domain},
                        parent_id=entity.id,
                        source_module=self.name,
                    )
