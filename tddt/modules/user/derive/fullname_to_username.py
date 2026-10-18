"""Derives candidate usernames from a person's full name."""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, FullName, Username
from tddt.core.module import BaseModule, register_module


@register_module(
    name="user.derive.fullname_to_username",
    mode=["user"],
    consumes=[FullName],
    produces=[Username],
    active=False,
    requires_key=None,
)
class FullnameToUsernameModule(BaseModule):
    """Generates ~15 candidate username variations from FullName."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, FullName):
                continue

            raw = entity.value.strip().lower()
            parts = raw.split()
            if len(parts) < 2:
                continue

            first, last = parts[0], parts[-1]
            fi = first[0] if first else ""
            li = last[0] if last else ""

            candidates: set[str] = {
                f"{first}{last}",
                f"{first}.{last}",
                f"{first}_{last}",
                f"{first}-{last}",
                f"{fi}{last}",
                f"{first}{li}",
                f"{last}{fi}",
                f"{fi}.{last}",
                f"{fi}_{last}",
                f"{fi}-{last}",
                f"{last}.{first}",
                f"{last}_{first}",
                f"{last}-{first}",
                f"{last}{first}",
                f"{first}_{li}",
                f"{first}.{li}",
                f"{last}_{fi}",
                f"{last}.{fi}",
                f"{first[:3]}{last[:3]}",
                first,
                last,
            }

            for cand in sorted(candidates):
                if cand:
                    yield Username(
                        value=cand,
                        parent_id=entity.id,
                        source_module=self.name,
                        confidence=0.3,
                        metadata={"derived_from": entity.value},
                    )
