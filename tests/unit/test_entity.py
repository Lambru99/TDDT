from __future__ import annotations

import re

import pytest

from tddt.core.entity import (
    BaseEntity,
    Domain,
    Email,
    EntityGraph,
    IPAddress,
    Secret,
    Subdomain,
)


# ──────────────────────────────────────────────────────────────────────────────
# BaseEntity semantics
# ──────────────────────────────────────────────────────────────────────────────


def test_base_entity_id_is_stable_hash():
    a = Domain(value="x.com")
    b = Domain(value="x.com")
    assert a.id == b.id
    assert re.fullmatch(r"[0-9a-f]{12}", a.id)


def test_base_entity_id_differs_by_type():
    assert Domain(value="x.com").id != Email(value="x.com").id


def test_subdomain_is_instance_of_domain():
    s = Subdomain(value="a.x.com")
    assert isinstance(s, Domain)


def test_metadata_mutation_does_not_break_hash():
    d = Domain(value="x.com")
    original_hash = hash(d)
    d.metadata["source_count"] = 3
    d.metadata["seen_at"] = "2026-10-18"
    assert hash(d) == original_hash
    assert d.metadata["source_count"] == 3


def test_control_char_value_hashes_cleanly():
    """Review Focus #3: entity with zero-width unicode must still produce a 12-hex id."""
    e = Email(value="x​@y.com")
    assert re.fullmatch(r"[0-9a-f]{12}", e.id)


def test_secret_preview_truncates_and_hashes_full_value():
    long_secret = "A" * 500
    s = Secret(value=long_secret)
    assert len(s.value) <= 40
    assert "preview" in s.metadata
    assert len(s.metadata["preview"]) <= 40
    assert "sha256" in s.metadata
    assert re.fullmatch(r"[0-9a-f]{64}", s.metadata["sha256"])
    # The original full-length value must appear nowhere in the entity.
    assert long_secret not in s.value
    assert long_secret not in s.metadata["preview"]


# ──────────────────────────────────────────────────────────────────────────────
# EntityGraph
# ──────────────────────────────────────────────────────────────────────────────


def test_graph_add_returns_true_for_new_false_for_dedup():
    g = EntityGraph()
    d1 = Domain(value="x.com")
    d2 = Domain(value="x.com")  # same value → same id
    assert g.add(d1) is True
    assert g.add(d2) is False


def test_graph_boost_confidence_updates_entity():
    g = EntityGraph()
    e = Email(value="a@x.com", confidence=0.3)
    g.add(e)
    g.boost_confidence(e.id, 0.2)
    stored = next(iter(g.of_type(Email)))
    assert stored.confidence == pytest.approx(0.5)


def test_graph_boost_confidence_clamps_to_one():
    g = EntityGraph()
    e = Email(value="a@x.com", confidence=0.9)
    g.add(e)
    g.boost_confidence(e.id, 0.5)
    stored = next(iter(g.of_type(Email)))
    assert stored.confidence == pytest.approx(1.0)


def test_graph_dispatched_tracking():
    g = EntityGraph()
    d = Domain(value="x.com")
    g.add(d)
    assert g.is_dispatched("mod.foo", d.id) is False
    g.mark_dispatched("mod.foo", d.id)
    assert g.is_dispatched("mod.foo", d.id) is True
    assert g.is_dispatched("mod.bar", d.id) is False


def test_graph_max_entities_per_type_cap_skips_and_warns(caplog):
    g = EntityGraph(max_entities_per_type=3)
    for i in range(5):
        g.add(Domain(value=f"x{i}.com"))
    assert g.count_of_type(Domain) == 3
    assert any("cap" in rec.message.lower() for rec in caplog.records)


def test_graph_count_of_type():
    g = EntityGraph()
    for i in range(3):
        g.add(Domain(value=f"d{i}.com"))
    for i in range(2):
        g.add(Email(value=f"e{i}@x.com"))
    assert g.count_of_type(Domain) == 3
    assert g.count_of_type(Email) == 2
    assert g.count_of_type(IPAddress) == 0


def test_graph_subdomain_counts_under_domain_type():
    """count_of_type honors polymorphism: Subdomain is a Domain."""
    g = EntityGraph()
    g.add(Domain(value="x.com"))
    g.add(Subdomain(value="a.x.com"))
    assert g.count_of_type(Subdomain) == 1
    assert g.count_of_type(Domain) == 2  # Domain + its Subdomain


def test_graph_update_metadata_patches_entity():
    """Pre-flight ruling: synth modules (pattern_deducer) enrich existing entities."""
    g = EntityGraph()
    d = Domain(value="x.com")
    g.add(d)
    ok = g.update_metadata(d.id, {"naming_pattern": "{name}.{surname}"})
    assert ok is True
    stored = next(iter(g.of_type(Domain)))
    assert stored.metadata["naming_pattern"] == "{name}.{surname}"


def test_graph_update_metadata_unknown_id_returns_false():
    g = EntityGraph()
    assert g.update_metadata("deadbeef0000", {"x": 1}) is False


def test_graph_children_of_follows_parent_id():
    g = EntityGraph()
    d = Domain(value="x.com")
    g.add(d)
    child = Email(value="a@x.com", parent_id=d.id)
    g.add(child)
    children = g.children_of(d.id)
    assert len(children) == 1
    assert children[0].value == "a@x.com"


def test_graph_export_has_stable_shape():
    g = EntityGraph()
    d = Domain(value="x.com")
    g.add(d)
    g.add(Email(value="a@x.com", parent_id=d.id))
    out = g.export()
    assert "by_type" in out
    assert "edges" in out
    assert "Domain" in out["by_type"]
    assert "Email" in out["by_type"]
    assert any(edge["parent_id"] == d.id for edge in out["edges"])
