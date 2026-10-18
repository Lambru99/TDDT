"""Derives candidate FullName from an email local part."""

from __future__ import annotations

import re
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Email, FullName
from tddt.core.module import BaseModule, register_module

GENERIC_EMAILS = {
    "info", "admin", "contact", "support", "sales", "hr", "job", "office",
    "privacy", "press", "legal", "noreply", "no-reply", "marketing", "billing",
    "security", "help", "team", "postmaster", "webmaster",
}


@register_module(
    name="user.derive.email_to_name",
    mode=["user"],
    consumes=[Email],
    produces=[FullName],
    active=False,
    requires_key=None,
)
class EmailToNameModule(BaseModule):
    """Extracts candidate FullName from email address local part."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Email):
                continue

            val = entity.value.strip().lower()
            if "@" not in val:
                continue

            local = val.split("@")[0]
            if any(local.startswith(g) or local == g for g in GENERIC_EMAILS):
                continue

            parts = [p for p in re.split(r"[._\-]", local) if p]
            if len(parts) >= 2 and all(p.isalpha() for p in parts[:2]):
                candidate_name = f"{parts[0].capitalize()} {parts[1].capitalize()}"
                yield FullName(
                    value=candidate_name,
                    parent_id=entity.id,
                    source_module=self.name,
                    confidence=0.3,
                    metadata={"derived_from": val},
                )
