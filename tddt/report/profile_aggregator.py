"""ProfileAggregator — clusters Service entities by avatar hash and builds a
user-mode profile with primary + alternates, per spec §10.3."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tddt.core.entity import BaseEntity, EntityGraph

CONFIDENCE_FLOOR = 0.6  # spec §9.10


def build_profile(graph: "EntityGraph") -> dict:
    """Return a profile dict for a user-mode scan.

    Returns ``{"primary": {}, "alternates": []}`` for an empty graph.
    Otherwise clusters Service entities by avatar_hash, picks the largest
    cluster as primary, resolves FullName conflicts, and aggregates linked
    entities (children by parent_id).
    """
    from tddt.core.entity import (
        Document,
        Email,
        FullName,
        Organization,
        Phone,
        Service,
        Website,
    )

    # Empty-graph fast path
    if not list(graph.all()):
        return {"primary": {}, "alternates": []}

    # Only Services that meet the confidence floor enter the profile
    eligible: list[Service] = [
        s for s in graph.of_type(Service) if s.confidence >= CONFIDENCE_FLOOR
    ]

    # Cluster eligible services by avatar_hash (fall back to entity id for ungrouped)
    clusters: dict[str, list] = {}
    for svc in eligible:
        key = svc.metadata.get("avatar_hash", svc.id)
        clusters.setdefault(key, []).append(svc)

    sorted_clusters = sorted(clusters.values(), key=len, reverse=True)
    primary_svcs = sorted_clusters[0] if sorted_clusters else []
    alt_clusters = sorted_clusters[1:]

    names = _resolve_names(graph.of_type(FullName))
    primary_linked = _collect_linked(graph, {s.id for s in primary_svcs})

    primary: dict = {
        "services": [_svc_dict(s) for s in primary_svcs],
        "names": names,
        "emails": primary_linked["emails"],
        "websites": primary_linked["websites"],
        "organizations": primary_linked["organizations"],
        "documents": primary_linked["documents"],
        "phones": primary_linked["phones"],
    }

    alternates = []
    for alt_svcs in alt_clusters:
        alt_linked = _collect_linked(graph, {s.id for s in alt_svcs})
        alternates.append(
            {
                "services": [_svc_dict(s) for s in alt_svcs],
                "emails": alt_linked["emails"],
                "websites": alt_linked["websites"],
                "organizations": alt_linked["organizations"],
                "documents": alt_linked["documents"],
                "phones": alt_linked["phones"],
            }
        )

    return {"primary": primary, "alternates": alternates}


def _svc_dict(svc) -> dict:
    return {"value": svc.value, "confidence": svc.confidence, "id": svc.id}


def _collect_linked(graph: "EntityGraph", service_ids: set[str]) -> dict:
    """Collect child entities linked to any service in *service_ids*."""
    from tddt.core.entity import Document, Email, Organization, Phone, Website

    result: dict[str, list] = {
        "emails": [],
        "websites": [],
        "organizations": [],
        "documents": [],
        "phones": [],
    }
    for svc_id in service_ids:
        for child in graph.children_of(svc_id):
            type_name = type(child).__name__
            entry = {"value": child.value, "confidence": child.confidence, "id": child.id}
            if type_name == "Email":
                result["emails"].append(entry)
            elif type_name == "Website":
                result["websites"].append(entry)
            elif type_name == "Organization":
                result["organizations"].append(entry)
            elif type_name == "Document":
                result["documents"].append(entry)
            elif type_name == "Phone":
                result["phones"].append(entry)
    return result


def _resolve_names(fullnames: list) -> list[dict]:
    """Resolve FullName entities: pick highest confidence; on tie mark all conflicting."""
    if not fullnames:
        return []

    max_conf = max(fn.confidence for fn in fullnames)
    at_max = [fn for fn in fullnames if fn.confidence == max_conf]

    if len(at_max) == 1:
        # Return all names, highest first, no conflict flag
        return sorted(
            [{"value": fn.value, "confidence": fn.confidence} for fn in fullnames],
            key=lambda n: n["confidence"],
            reverse=True,
        )
    else:
        # Tie among top candidates — all marked conflicting
        return [
            {"value": fn.value, "confidence": fn.confidence, "conflicting": True}
            for fn in at_max
        ]
