"""Active SMTP RCPT bruteforce email discovery module."""

from __future__ import annotations

import smtplib
from collections.abc import Iterable
from pathlib import Path

import dns.resolver

from tddt.core.entity import BaseEntity, Domain, Email
from tddt.core.module import BaseModule, register_module

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@register_module(
    name="corporate.email.smtp_bruteforce",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email],
    active=True,
    requires_key=None,
)
class SmtpBruteforceModule(BaseModule):
    """Actively probes candidate email addresses against domain MX via SMTP RCPT."""

    def _get_mx_host(self, domain: str) -> str | None:
        try:
            answers = dns.resolver.resolve(domain, "MX")
            records = sorted(answers, key=lambda r: getattr(r, "preference", 0))
            if records:
                return records[0].exchange.to_text().rstrip(".")
        except Exception:
            self.log.debug("MX lookup failed for %s", domain, exc_info=True)
        return None

    def _load_names(self) -> list[str]:
        names: list[str] = []
        for filename in ("common_names_it.txt", "common_names_en.txt"):
            filepath = DATA_DIR / filename
            if filepath.is_file():
                try:
                    with open(filepath, encoding="utf-8") as f:
                        for line in f:
                            clean = line.strip()
                            if clean:
                                names.append(clean)
                except Exception:
                    self.log.debug("Failed to read wordlist %s", filepath, exc_info=True)
        return names

    def _probe_candidates(
        self, entity: Domain, mx_host: str, names: list[str]
    ) -> Iterable[Email]:
        domain = entity.value.strip().lower()
        pattern = entity.metadata.get("naming_pattern") or "{initial}.{surname}"

        try:
            smtp = smtplib.SMTP(mx_host, 25, timeout=10)
            smtp.ehlo()
            smtp.mail(f"probe@{domain}")
        except Exception:
            self.log.debug("Failed to connect/handshake SMTP on %s", mx_host, exc_info=True)
            return

        try:
            # Catch-all check: probe a random nonexistent address
            test_addr = f"xyz99824nonexistent@{domain}"
            code, _ = smtp.rcpt(test_addr)
            if code == 250:
                self.log.info("Catch-all SMTP detected on %s for %s; skipping bruteforce", mx_host, domain)
                try:
                    smtp.quit()
                except Exception:
                    self.log.debug("SMTP quit error", exc_info=True)
                return

            for name_entry in names:
                parts = name_entry.split()
                if len(parts) < 2:
                    continue
                first, last = parts[0], parts[1]
                initial = first[0] if first else ""
                try:
                    local = pattern.format(
                        name=first,
                        surname=last,
                        first=first,
                        last=last,
                        initial=initial,
                    )
                except Exception:
                    local = f"{initial}.{last}"

                candidate = f"{local}@{domain}"
                try:
                    code, _ = smtp.rcpt(candidate)
                    if code in (250, 251):
                        yield Email(
                            value=candidate,
                            parent_id=entity.id,
                            source_module=self.name,
                            confidence=0.9,
                            metadata={
                                "verified": True,
                                "method": "smtp_rcpt",
                                "mx": mx_host,
                                "domain": domain,
                            },
                        )
                except Exception:
                    self.log.debug("RCPT probe error for %s", candidate, exc_info=True)
                    break
        finally:
            try:
                smtp.quit()
            except Exception:
                self.log.debug("SMTP quit error", exc_info=True)

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            mx_host = self._get_mx_host(domain)
            if not mx_host:
                self.log.debug("No MX host resolved for %s; skipping SMTP bruteforce", domain)
                continue

            names = self._load_names()
            yield from self._probe_candidates(entity, mx_host, names)
