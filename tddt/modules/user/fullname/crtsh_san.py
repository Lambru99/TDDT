"""Certificate SAN / CommonName search module for full name."""

from __future__ import annotations

from typing import ClassVar, Iterable
from urllib.parse import quote_plus

from tddt.core.entity import BaseEntity, Domain, FullName
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)


@register_module(
    name="user.fullname.crtsh_san",
    mode=["user"],
    consumes=[FullName],
    produces=[Domain],
    active=False,
    requires_key=None,
)
class FullNameCrtshSanModule(BaseModule):
    """Searches crt.sh certificate records matching a person's full name."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, FullName):
                continue

            query = entity.value.strip()
            url = f"https://crt.sh/?q={quote_plus(query)}&output=json"

            try:
                resp = self.client.get(url, host_hint="crt.sh")
            except Exception as e:
                _log.warning("HTTP error querying crt.sh for name %s: %s", entity.value, e)
                continue

            if resp.status_code in (403, 429):
                _log.warning("crt.sh rate limited for %s (status %d)", entity.value, resp.status_code)
                continue

            if resp.status_code != 200:
                _log.debug("crt.sh returned status %d for %s", resp.status_code, entity.value)
                continue

            try:
                records = resp.json()
            except Exception as e:
                _log.debug("crt.sh returned invalid JSON for %s: %s", entity.value, e)
                continue

            if not isinstance(records, list):
                continue

            seen_domains = set()
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                names = []
                cn = rec.get("common_name")
                if cn and isinstance(cn, str):
                    names.append(cn)
                nv = rec.get("name_value")
                if nv and isinstance(nv, str):
                    names.extend(nv.split("\n"))

                for raw_name in names:
                    clean = raw_name.strip().lower()
                    if clean.startswith("*."):
                        clean = clean[2:]
                    if not clean or "@" in clean or "." not in clean:
                        continue
                    if clean in seen_domains:
                        continue
                    seen_domains.add(clean)

                    yield Domain(
                        value=clean,
                        source_module=self.name,
                        confidence=0.75,
                        metadata={"fullname": entity.value, "source": "crtsh"},
                    )
