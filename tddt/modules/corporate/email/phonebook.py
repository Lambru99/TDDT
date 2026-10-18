"""Phonebook.cz scraping module for email discovery."""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, Email
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import extract_domain_emails


@register_module(
    name="corporate.email.phonebook",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email],
    active=False,
    requires_key=None,
)
class PhonebookEmailModule(BaseModule):
    """Harvests emails from Phonebook.cz database."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            url = f"https://phonebook.cz/?search={domain}&type=2"
            headers = {"Referer": "https://phonebook.cz/"}

            try:
                resp = self.client.get(
                    url, headers=headers, host_hint="phonebook.cz", timeout=15
                )
            except Exception:
                self.log.debug("Phonebook.cz query failed for %s", domain, exc_info=True)
                continue

            if resp.status_code in (403, 429):
                self.log.warning(
                    "Phonebook.cz returned status %d for %s (forbidden / rate limit)",
                    resp.status_code,
                    domain,
                )
                continue
            if resp.status_code != 200:
                self.log.debug("Phonebook.cz returned status %d for %s", resp.status_code, domain)
                continue

            # Bug §2.14 fix: check for login page or auth wall
            text_low = resp.text.lower()
            if "type=\"password\"" in text_low or "action=\"/login\"" in text_low or "<title>login" in text_low:
                self.log.warning(
                    "Phonebook.cz returned login page or authentication required for %s",
                    domain,
                )
                continue

            emails = extract_domain_emails(resp.text, domain)
            for email in sorted(emails):
                yield Email(
                    value=email,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "phonebook", "domain": domain},
                )
