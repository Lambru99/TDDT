"""EmailRep reputation and deliverability validator module."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Email
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.email.emailrep_validator",
    mode=["corporate", "user"],
    consumes=[Email],
    produces=[Email],
    active=False,
    requires_key=None,
)
class EmailRepValidatorModule(BaseModule):
    """Validates email addresses using EmailRep API reputation and deliverability."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Email):
                continue

            email_val = entity.value.strip().lower()
            url = f"https://emailrep.io/{email_val}"

            try:
                resp = self.client.get(
                    url, host_hint="emailrep.io", timeout=10
                )
            except Exception:
                self.log.debug("EmailRep lookup failed for %s", email_val, exc_info=True)
                continue

            if resp.status_code in (429, 403):
                self.log.warning(
                    "EmailRep API rate limit or forbidden status %d for %s",
                    resp.status_code,
                    email_val,
                )
                continue
            if resp.status_code != 200:
                self.log.debug("EmailRep API status %d for %s", resp.status_code, email_val)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.debug("Failed to decode EmailRep JSON for %s", email_val, exc_info=True)
                continue

            suspicious = data.get("suspicious", False)
            deliverable = data.get("deliverable", True)

            meta = dict(entity.metadata)
            meta["emailrep"] = data
            meta["deliverable"] = deliverable
            meta["suspicious"] = suspicious

            if deliverable and not suspicious:
                new_conf = min(1.0, entity.confidence + 0.3)
            else:
                new_conf = max(0.1, min(entity.confidence, 0.2))

            yield dataclasses.replace(entity, confidence=new_conf, metadata=meta)
