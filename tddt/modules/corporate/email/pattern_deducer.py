"""Email naming pattern deduction synthesis module."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Email, Finding
from tddt.core.module import BaseModule, register_module

GENERIC_KEYWORDS = (
    "info",
    "admin",
    "contact",
    "support",
    "sales",
    "hr",
    "job",
    "recruit",
    "office",
    "privacy",
    "press",
    "legal",
    "noreply",
    "no-reply",
    "newsletter",
    "marketing",
    "billing",
    "abuse",
    "security",
    "webmaster",
    "postmaster",
    "help",
    "team",
)


@register_module(
    name="corporate.email.pattern_deducer",
    mode=["corporate"],
    consumes=[Email],
    produces=[Finding],
    batch_size=0,
    active=False,
    requires_key=None,
)
class PatternDeducerModule(BaseModule):
    """Synthesizes corporate email naming patterns from discovered addresses."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        pattern_votes: list[str] = []
        parent_id: str | None = None

        for entity in entities:
            if not isinstance(entity, Email):
                continue
            if not parent_id and entity.parent_id:
                parent_id = entity.parent_id

            val = entity.value.strip().lower()
            if "@" not in val:
                continue

            local = val.split("@")[0]
            if any(k in local for k in GENERIC_KEYWORDS):
                continue

            if "." in local:
                parts = local.split(".")
                if len(parts) == 2:
                    if len(parts[0]) == 1:
                        pattern_votes.append("{initial}.{surname}")
                    elif len(parts[1]) == 1:
                        pattern_votes.append("{name}.{initial}")
                    else:
                        pattern_votes.append("{name}.{surname}")
            elif "_" in local:
                pattern_votes.append("{name}_{surname}")
            elif len(local) > 3:
                pattern_votes.append("{surname}{initial} or {name}")

        if not pattern_votes:
            return

        top_pattern = Counter(pattern_votes).most_common(1)[0][0]
        yield Finding(
            value=top_pattern,
            parent_id=parent_id,
            source_module=self.name,
            metadata={"type": "naming_pattern", "pattern": top_pattern, "sample_size": len(pattern_votes)},
        )
