"""Unit tests for tddt.report.profile_aggregator — Task 2.4."""

from __future__ import annotations

import dataclasses

from tddt.core.entity import (
    Email,
    EntityGraph,
    FullName,
    Organization,
    Service,
    Website,
)


def _graph_with(*entities):
    g = EntityGraph()
    for e in entities:
        g.add(e)
    return g


def _service(value: str, avatar_hash: str, confidence: float = 1.0) -> Service:
    s = Service(value=value, confidence=confidence)
    s.metadata["avatar_hash"] = avatar_hash
    return s


# ── cluster selection ─────────────────────────────────────────────────────────


def test_profile_primary_has_largest_cluster():
    from tddt.report.profile_aggregator import build_profile

    graph = _graph_with(
        _service("github/alice", "hashA"),
        _service("twitter/alice", "hashA"),
        _service("reddit/alice", "hashA"),
        _service("github/bob", "hashB"),
        _service("twitter/bob", "hashB"),
    )
    profile = build_profile(graph)

    primary_services = profile["primary"].get("services", [])
    assert len(primary_services) == 3, "Primary cluster should be the largest (3)"
    alternates = profile["alternates"]
    assert len(alternates) >= 1
    alt_services = alternates[0].get("services", [])
    assert len(alt_services) == 2


# ── linked entity aggregation ─────────────────────────────────────────────────


def test_profile_aggregates_linked_emails():
    from tddt.report.profile_aggregator import build_profile

    svc = _service("github/alice", "hashA")
    email = Email(value="alice@example.com", parent_id=svc.id)
    graph = _graph_with(svc, email)

    profile = build_profile(graph)
    emails = profile["primary"].get("emails", [])
    assert any(e.get("value") == "alice@example.com" for e in emails), (
        "Email linked to primary service not in primary.emails"
    )


# ── fullname conflict resolution ──────────────────────────────────────────────


def test_profile_resolves_fullname_conflict_picks_highest():
    from tddt.report.profile_aggregator import build_profile

    graph = _graph_with(
        FullName(value="Alice Smith", confidence=0.9),
        FullName(value="Alice A. Smith", confidence=0.5),
    )
    profile = build_profile(graph)
    names = profile["primary"].get("names", [])
    assert names, "Profile should include at least one name"
    # highest-confidence name should not be marked conflicting
    highest = max(names, key=lambda n: n.get("confidence", 0))
    assert highest["value"] == "Alice Smith"


def test_profile_resolves_fullname_conflict_tie_marks_both():
    from tddt.report.profile_aggregator import build_profile

    graph = _graph_with(
        FullName(value="Alice Smith", confidence=0.7),
        FullName(value="Alice A. Smith", confidence=0.7),
    )
    profile = build_profile(graph)
    names = profile["primary"].get("names", [])
    assert all(n.get("conflicting") is True for n in names), (
        "Tied confidence → all names should have conflicting=True"
    )


# ── empty graph ───────────────────────────────────────────────────────────────


def test_profile_empty_graph():
    from tddt.report.profile_aggregator import build_profile

    profile = build_profile(EntityGraph())
    assert profile == {"primary": {}, "alternates": []}


# ── confidence floor ──────────────────────────────────────────────────────────


def test_profile_confidence_floor():
    from tddt.report.profile_aggregator import build_profile

    graph = _graph_with(
        _service("github/alice", "hashA", confidence=0.4),
        _service("twitter/alice", "hashA", confidence=0.5),
    )
    profile = build_profile(graph)
    # Both services below the 0.6 floor — primary should have no services
    services = profile["primary"].get("services", [])
    assert len(services) == 0, "Services below confidence floor 0.6 should be excluded"
    assert profile["alternates"] == []
