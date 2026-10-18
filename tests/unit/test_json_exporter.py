"""Unit tests for tddt.report.json_exporter — Task 2.2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tddt.core.entity import Domain, Email, EntityGraph, Secret


def _graph_with(*entities):
    g = EntityGraph()
    for e in entities:
        g.add(e)
    return g


# ── schema shape ──────────────────────────────────────────────────────────────


def test_schema_shape(tmp_path):
    from tddt.report.json_exporter import export_json

    path = tmp_path / "out.json"
    export_json(_graph_with(Domain(value="x.com")), {"mode": "corporate"}, path)

    data = json.loads(path.read_text())
    assert set(data.keys()) == {"scan", "entities", "profile"}


# ── entities grouping ─────────────────────────────────────────────────────────


def test_entities_by_type_grouped(tmp_path):
    from tddt.report.json_exporter import export_json

    graph = _graph_with(
        Domain(value="a.com"),
        Domain(value="b.com"),
        Domain(value="c.com"),
        Email(value="x@a.com"),
        Email(value="y@a.com"),
    )
    path = tmp_path / "out.json"
    export_json(graph, {"mode": "corporate"}, path)

    by_type = json.loads(path.read_text())["entities"]["by_type"]
    assert len(by_type["Domain"]) == 3
    assert len(by_type["Email"]) == 2


# ── edges ─────────────────────────────────────────────────────────────────────


def test_edges_recorded(tmp_path):
    from tddt.report.json_exporter import export_json

    parent = Domain(value="x.com")
    child = Email(value="a@x.com", parent_id=parent.id)
    graph = _graph_with(parent, child)

    path = tmp_path / "out.json"
    export_json(graph, {"mode": "corporate"}, path)

    edges = json.loads(path.read_text())["entities"]["graph_edges"]
    assert any(e["parent_id"] == parent.id and e["child_id"] == child.id for e in edges)


# ── secret redaction ──────────────────────────────────────────────────────────


def test_secret_full_value_never_in_output(tmp_path):
    """Secret entity stores only preview ≤40 chars; full value must not appear."""
    from tddt.report.json_exporter import export_json

    full_value = "KEY-" + "A" * 496
    secret = Secret(value=full_value)
    graph = _graph_with(secret)

    path = tmp_path / "out.json"
    export_json(graph, {"mode": "corporate"}, path)

    text = path.read_text()
    assert full_value not in text, "full secret value leaked into JSON output"
    data = json.loads(text)
    secret_entries = data["entities"]["by_type"].get("Secret", [])
    assert len(secret_entries) == 1
    entry = secret_entries[0]
    # value stored is the preview (≤40 chars), sha256 in metadata
    assert len(entry["value"]) <= 40
    assert len(entry["metadata"].get("sha256", "")) == 64


# ── valid json ────────────────────────────────────────────────────────────────


def test_output_is_valid_json(tmp_path):
    from tddt.report.json_exporter import export_json

    path = tmp_path / "out.json"
    export_json(
        _graph_with(Domain(value="y.com"), Email(value="b@y.com")),
        {"mode": "corporate", "started_at": "2026-01-01T00:00:00"},
        path,
    )
    assert json.loads(path.read_text()) is not None


# ── terminated_reason / iterations / elapsed_s (I1) ─────────────────────────


def test_terminated_reason_from_graph_metadata_in_scan_dict(tmp_path):
    """CorrelationEngine writes terminated_reason/iterations/elapsed_s to
    graph.metadata. The exporter must surface them in the top-level scan dict."""
    from tddt.report.json_exporter import export_json

    graph = _graph_with(Domain(value="x.com"))
    graph.metadata["terminated_reason"] = "max_iterations"
    graph.metadata["iterations"] = 5
    graph.metadata["elapsed_s"] = 123.45

    path = tmp_path / "out.json"
    export_json(graph, {"mode": "corporate"}, path)
    data = json.loads(path.read_text())
    assert data["scan"]["terminated_reason"] == "max_iterations"
    assert data["scan"]["iterations"] == 5
    assert data["scan"]["elapsed_s"] == 123.45


# ── cross_mode_results nested under scan (I2) ───────────────────────────────


def test_cross_mode_results_nested_under_scan(tmp_path):
    """Top-level keys must stay {scan, entities, profile}. cross_mode_results,
    when passed, belongs under scan — not as a 4th top-level key."""
    from tddt.report.json_exporter import export_json

    cross = {"corporate": {"example.com": {"by_type": {"Domain": []}}}}
    path = tmp_path / "out.json"
    export_json(
        _graph_with(Domain(value="x.com")),
        {"mode": "user"},
        path,
        cross_mode_results=cross,
    )
    data = json.loads(path.read_text())
    assert set(data.keys()) == {"scan", "entities", "profile"}
    assert data["scan"]["cross_mode_results"] == cross


def test_cross_mode_results_absent_when_none(tmp_path):
    from tddt.report.json_exporter import export_json

    path = tmp_path / "out.json"
    export_json(_graph_with(Domain(value="x.com")), {"mode": "user"}, path)
    data = json.loads(path.read_text())
    assert "cross_mode_results" not in data
    assert "cross_mode_results" not in data["scan"]
