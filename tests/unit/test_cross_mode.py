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
    assert "cross_mode_results" in data
    assert "corporate" in data["cross_mode_results"]
    assert "personal.org" in data["cross_mode_results"]["corporate"]
    corp_data = data["cross_mode_results"]["corporate"]["personal.org"]
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
    assert "cross_mode_results" in data
    assert "corporate" in data["cross_mode_results"]
    assert "johndoe.me" in data["cross_mode_results"]["corporate"]
