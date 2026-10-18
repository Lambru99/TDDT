"""crt.sh Subject Alternative Name (SAN) cert email harvester module."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote

from tddt.core.entity import BaseEntity, Domain, Email
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import extract_domain_emails


@register_module(
    name="corporate.email.crtsh_san",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email],
    active=False,
    requires_key=None,
)
class CrtShSanModule(BaseModule):
    """Harvests emails from crt.sh certificate logs and SAN fields."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            url = f"https://crt.sh/?q=%25.{quote(domain)}&output=json"

            try:
                resp = self.client.get(url, host_hint="crt.sh", timeout=15)
            except Exception:
                self.log.debug("crt.sh SAN query failed for %s", domain, exc_info=True)
                continue

            if resp.status_code in (403, 429, 502, 503):
                self.log.warning(
                    "crt.sh returned status %d for %s (busy / rate limited)",
                    resp.status_code,
                    domain,
                )
                continue
            if resp.status_code != 200:
                self.log.debug("crt.sh returned status %d for %s", resp.status_code, domain)
                continue

            emails: set[str] = set()
            try:
                data = resp.json()
                if isinstance(data, list):
                    for entry in data:
                        if isinstance(entry, dict):
                            cn = str(entry.get("common_name", ""))
                            nv = str(entry.get("name_value", ""))
                            emails.update(extract_domain_emails(f"{cn}\n{nv}", domain))
            except Exception:
                # Fallback to scanning raw response text
                emails.update(extract_domain_emails(resp.text, domain))

            for email in sorted(emails):
                yield Email(
                    value=email,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "crtsh_san", "domain": domain},
                )
