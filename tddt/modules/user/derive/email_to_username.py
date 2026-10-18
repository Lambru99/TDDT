"""Derives candidate usernames from an email address."""

from __future__ import annotations

import re
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Email, Username
from tddt.core.module import BaseModule, register_module


@register_module(
    name="user.derive.email_to_username",
    mode=["user"],
    consumes=[Email],
    produces=[Username],
    active=False,
    requires_key=None,
)
class EmailToUsernameModule(BaseModule):
    """Generates ~15 candidate usernames from email local part."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Email):
                continue

            val = entity.value.strip().lower()
            if "@" not in val:
                continue

            local = val.split("@")[0]
            candidates: set[str] = {local}
            candidates.add(local.replace(".", "").replace("-", "").replace("_", ""))
            candidates.add(local.replace(".", "_"))
            candidates.add(local.replace(".", "-"))

            parts = [p for p in re.split(r"[._\-]", local) if p]
            if len(parts) >= 2:
                first, last = parts[0], parts[1]
                fi = first[0] if first else ""
                li = last[0] if last else ""

                candidates.add(f"{fi}{last}")
                candidates.add(f"{first}{li}")
                candidates.add(f"{last}{fi}")
                candidates.add(f"{fi}.{last}")
                candidates.add(f"{fi}_{last}")
                candidates.add(f"{fi}-{last}")
                candidates.add(f"{last}.{first}")
                candidates.add(f"{last}_{first}")
                candidates.add(f"{last}-{first}")
                candidates.add(f"{last}{first}")
                candidates.add(f"{first}_{li}")
                candidates.add(f"{first}.{li}")
                candidates.add(f"{last}_{fi}")
                candidates.add(f"{last}.{fi}")
                candidates.add(f"{first[:3]}{last[:3]}")
                candidates.add(first)
                candidates.add(last)

            for cand in sorted(candidates):
                if cand:
                    yield Username(
                        value=cand,
                        parent_id=entity.id,
                        source_module=self.name,
                        confidence=0.3,
                        metadata={"derived_from": val},
                    )
