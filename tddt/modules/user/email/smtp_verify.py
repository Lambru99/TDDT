"""SMTP direct mailbox verification module for user emails."""

from __future__ import annotations

import smtplib
from typing import ClassVar, Iterable

import dns.resolver

from tddt.core.entity import BaseEntity, Email
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)


@register_module(
    name="user.email.smtp_verify",
    mode=["user"],
    consumes=[Email],
    produces=[Email],
    active=True,
    requires_key=None,
)
class UserSmtpVerifyModule(BaseModule):
    """Directly verifies recipient mailbox existence via SMTP RCPT TO."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Email):
                continue

            if "@" not in entity.value:
                continue

            user_part, domain = entity.value.split("@", 1)

            try:
                answers = dns.resolver.resolve(domain, "MX")
            except Exception as e:
                _log.debug("MX lookup failed for %s: %s", domain, e)
                continue

            mx_hosts = []
            for rdata in answers:
                exchange_str = getattr(rdata, "exchange", None)
                if exchange_str is not None:
                    if hasattr(exchange_str, "to_text"):
                        mx_hosts.append(exchange_str.to_text().rstrip("."))
                    else:
                        mx_hosts.append(str(exchange_str).rstrip("."))

            if not mx_hosts:
                continue

            mx_host = mx_hosts[0]
            smtp_client = None
            try:
                smtp_client = smtplib.SMTP(mx_host, port=25, timeout=10)
                try:
                    smtp_client.ehlo()
                except smtplib.SMTPException:
                    smtp_client.helo()

                smtp_client.mail("check@tddt-recon.org")

                # Test catch-all behavior
                catch_all_addr = f"xyz99824nonexistent@{domain}"
                code, _ = smtp_client.rcpt(catch_all_addr)
                if code == 250:
                    _log.debug("Domain %s is catch-all, cannot verify recipient", domain)
                    continue

                # Verify actual recipient
                code, _ = smtp_client.rcpt(entity.value)
                if code == 250:
                    yield Email(
                        value=entity.value,
                        source_module=self.name,
                        confidence=0.9,
                        metadata={"smtp_verified": True},
                    )
            except Exception as e:
                _log.debug("SMTP verification error on %s via %s: %s", entity.value, mx_host, e)
            finally:
                if smtp_client is not None:
                    try:
                        smtp_client.quit()
                    except Exception as e:
                        _log.debug("SMTP quit error for %s: %s", mx_host, e)
