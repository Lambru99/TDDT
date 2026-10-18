"""Tests for cross-mode --follow-domains flag."""

import json
from unittest.mock import MagicMock, patch
import pytest

from tddt.cli import main
from tddt.core.entity import Domain, EntityGraph, Subdomain, Website
from tddt.report.json_exporter import export_json


def test_export_json_nests_cross_mode_results(tmp_path):
    user_graph = EntityGraph()
    user_graph.add(Website(value="https://personal.org"))

    corp_graph = EntityGraph()
    corp_graph.add(Domain(value="personal.org"))
    corp_graph.add(Subdomain(value="api.personal.org"))

    cross_mode = {
        "corporate": {
            "personal.org": corp_graph.export(),
        }
    }

    out_file = tmp_path / "out.json"
    export_json(user_graph, {"mode": "user"}, out_file, cross_mode_results=cross_mode)

    data = json.loads(out_file.read_text(encoding="utf-8"))
    # cross_mode_results now lives UNDER scan (not top-level), preserving the
    # stable {scan, entities, profile} top-level contract. See I2.
    assert set(data.keys()) == {"scan", "entities", "profile"}
    cm = data["scan"]["cross_mode_results"]
    assert "corporate" in cm
    assert "personal.org" in cm["corporate"]
    corp_data = cm["corporate"]["personal.org"]
    assert "by_type" in corp_data
    assert "Subdomain" in corp_data["by_type"]


def test_cli_follow_domains_runs_corporate_scan(tmp_path):
    out_file = tmp_path / "report.json"

    user_graph = EntityGraph()
    user_graph.add(Website(value="https://johndoe.me"))

    corp_graph = EntityGraph()
    corp_graph.add(Domain(value="johndoe.me"))
    corp_graph.add(Subdomain(value="blog.johndoe.me"))

    def mock_scan(seeds, mode, **kwargs):
        if mode == "user":
            return user_graph
        if mode == "corporate":
            return corp_graph
        return EntityGraph()

    with patch("tddt.cli.CorrelationEngine.scan", side_effect=mock_scan):
        code = main([
            "user",
            "--name", "John Doe",
            "--follow-domains",
            "-o", str(out_file),
            "--light",
        ])

    assert code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    cm = data["scan"]["cross_mode_results"]
    assert "corporate" in cm
    assert "johndoe.me" in cm["corporate"]


def test_follow_domains_caps_corporate_scans(tmp_path):
    """A user-scan returning many Websites must not fan out into unbounded
    corp scans — each with its own max_runtime. Cap at FOLLOW_DOMAINS_MAX."""
    from tddt.cli import FOLLOW_DOMAINS_MAX

    out_file = tmp_path / "report.json"
    # Build a user graph with FOLLOW_DOMAINS_MAX + 5 Websites on distinct hosts.
    user_graph = EntityGraph()
    for i in range(FOLLOW_DOMAINS_MAX + 5):
        user_graph.add(Website(value=f"https://site{i}.example{i}.com/path"))

    corp_scan_calls = []

    def mock_scan(seeds, mode, **kwargs):
        if mode == "user":
            return user_graph
        if mode == "corporate":
            corp_scan_calls.append(seeds[0].value)
        return EntityGraph()

    with patch("tddt.cli.CorrelationEngine.scan", side_effect=mock_scan):
        code = main([
            "user",
            "--name", "Someone",
            "--follow-domains",
            "-o", str(out_file),
            "--light",
        ])

    assert code == 0
    assert len(corp_scan_calls) == FOLLOW_DOMAINS_MAX, (
        f"expected at most {FOLLOW_DOMAINS_MAX} corp scans, got {len(corp_scan_calls)}"
    )
