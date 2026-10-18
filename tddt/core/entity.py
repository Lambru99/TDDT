"""Entity model and EntityGraph for TDDT v2.

Entities are frozen dataclasses with identity based on `(type_name, value)`.
`metadata` is a mutable dict for accessory data (preview, hashes, source counts);
it is excluded from hash/eq. The graph deduplicates by `entity.id`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────────────────────
# BaseEntity
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, eq=False)
class BaseEntity:
    """Base class for all entities tracked by the correlation engine.

    Identity is `(type(self).__name__, self.value)`. Two entities are equal
    when their `.id` matches. `metadata` is a mutable piggyback for accessory
    data (preview, hashes, source counts) and does NOT participate in hash/eq.
    """

    value: str
    confidence: float = 1.0
    source_module: str = ""
    parent_id: str | None = None
    discovered_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)

    @property
    def id(self) -> str:
        key = f"{type(self).__name__}:{self.value}".encode("utf-8", errors="surrogatepass")
        return hashlib.sha1(key, usedforsecurity=False).hexdigest()[:12]

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.value))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, BaseEntity) and self.id == other.id


# ──────────────────────────────────────────────────────────────────────────────
# Concrete entities — Infrastructure
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, eq=False)
class Domain(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Subdomain(Domain):
    pass


@dataclass(frozen=True, eq=False)
class IPAddress(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class URL(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Certificate(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Port(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class CVE(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Technology(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Bucket(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class WHOISRecord(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class DNSRecord(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class TrackerID(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class TakeoverFinding(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Finding(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Secret(BaseEntity):
    """Secret with mandatory redaction of the full value.

    After construction, `value` holds only the preview (<=40 chars) and
    `metadata["preview"]` + `metadata["sha256"]` cover the full secret's
    identity. The full value appears nowhere in the entity.
    """

    _PREVIEW_LEN = 40

    def __post_init__(self) -> None:
        full = self.value
        preview = full[: self._PREVIEW_LEN]
        sha = hashlib.sha256(full.encode("utf-8", errors="surrogatepass")).hexdigest()
        object.__setattr__(self, "value", preview)
        self.metadata["preview"] = preview
        self.metadata["sha256"] = sha


# ──────────────────────────────────────────────────────────────────────────────
# Concrete entities — People / User mode
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, eq=False)
class Email(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Username(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class FullName(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Phone(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Service(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Document(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Website(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Breach(BaseEntity):
    pass


@dataclass(frozen=True, eq=False)
class Organization(BaseEntity):
    pass


# ──────────────────────────────────────────────────────────────────────────────
# EntityGraph
# ──────────────────────────────────────────────────────────────────────────────


DEFAULT_MAX_ENTITIES_PER_TYPE = 2000


class EntityGraph:
    """In-memory graph of entities with dedup, confidence boost, and
    (module, entity) dispatch tracking.

    `max_entities_per_type` caps the number of entities of each exact type
    (Review Focus #1: wildcard DNS producing thousands of subdomains).
    When the cap is reached, further adds of that type are skipped with a warning.
    """

    def __init__(self, max_entities_per_type: int = DEFAULT_MAX_ENTITIES_PER_TYPE) -> None:
        self._nodes: dict[str, BaseEntity] = {}
        self._by_type: dict[str, list[str]] = defaultdict(list)
        self._dispatched: set[tuple[str, str]] = set()
        self._max = max_entities_per_type
        self._capped_warned: set[str] = set()
        self.metadata: dict[str, Any] = {}

    # ── Mutation ─────────────────────────────────────────────────────────────

    def add(self, entity: BaseEntity) -> bool:
        """Add an entity; return True if new, False if dedup or capped."""
        if entity.id in self._nodes:
            return False
        type_name = type(entity).__name__
        if len(self._by_type[type_name]) >= self._max:
            if type_name not in self._capped_warned:
                _log.warning(
                    "entity cap reached for type %s (max=%d); further adds silenced",
                    type_name,
                    self._max,
                )
                self._capped_warned.add(type_name)
            return False
        self._nodes[entity.id] = entity
        self._by_type[type_name].append(entity.id)
        return True

    def boost_confidence(self, entity_id: str, delta: float) -> None:
        """Replace the stored entity with its confidence boosted (clamped to 1.0)."""
        current = self._nodes.get(entity_id)
        if current is None:
            return
        new_conf = min(1.0, current.confidence + delta)
        self._nodes[entity_id] = dataclasses.replace(current, confidence=new_conf)

    def update_metadata(self, entity_id: str, patch: dict[str, Any]) -> bool:
        """Merge `patch` into the entity's metadata. Returns False if unknown id."""
        current = self._nodes.get(entity_id)
        if current is None:
            return False
        current.metadata.update(patch)
        return True

    # ── Dispatch tracking ────────────────────────────────────────────────────

    def is_dispatched(self, module_name: str, entity_id: str) -> bool:
        return (module_name, entity_id) in self._dispatched

    def mark_dispatched(self, module_name: str, entity_id: str) -> None:
        self._dispatched.add((module_name, entity_id))

    # ── Queries ──────────────────────────────────────────────────────────────

    def children_of(self, entity_id: str) -> list[BaseEntity]:
        return [e for e in self._nodes.values() if e.parent_id == entity_id]

    def of_type(self, cls: type[BaseEntity]) -> list[BaseEntity]:
        return [e for e in self._nodes.values() if isinstance(e, cls)]

    def all(self) -> Iterator[BaseEntity]:
        return iter(self._nodes.values())

    def count_of_type(self, cls: type[BaseEntity]) -> int:
        return sum(1 for e in self._nodes.values() if isinstance(e, cls))

    # ── Export ───────────────────────────────────────────────────────────────

    def export(self) -> dict[str, Any]:
        by_type: dict[str, list[dict[str, Any]]] = {}
        for e in self._nodes.values():
            type_name = type(e).__name__
            by_type.setdefault(type_name, []).append(
                {
                    "id": e.id,
                    "type": type_name,
                    "value": e.value,
                    "confidence": e.confidence,
                    "source_module": e.source_module,
                    "parent_id": e.parent_id,
                    "discovered_at": e.discovered_at.isoformat(),
                    "metadata": dict(e.metadata),
                }
            )
        edges = [
            {"parent_id": e.parent_id, "child_id": e.id, "type": type(e).__name__}
            for e in self._nodes.values()
            if e.parent_id
        ]
        return {"by_type": by_type, "edges": edges, "metadata": dict(self.metadata)}
