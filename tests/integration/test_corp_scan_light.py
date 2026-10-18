"""End-to-end integration test for corporate light scan."""

import json
from unittest.mock import MagicMock, patch
import pytest

from tddt.cli import main
from tddt.core.http import HttpClient, reset_client


@pytest.fixture(autouse=True)
def _cleanup():
    reset_client()
    yield
    reset_client()


def test_corp_scan_light_e2e(tmp_path):
    report_file = tmp_path / "corp_report.json"

    mock_dns_answer = MagicMock()
    mock_a_item = MagicMock()
    mock_a_item.address = "93.184.216.34"
    mock_dns_answer.__iter__.return_value = [mock_a_item]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><a href='https://sub.example.com'></a></html>"
    mock_resp.content = b"<html></html>"
    mock_resp.json.return_value = []
    mock_resp.headers = {"Content-Type": "text/html"}

    with patch("dns.resolver.resolve", return_value=mock_dns_answer), \
         patch.object(HttpClient, "get", return_value=mock_resp), \
         patch.object(HttpClient, "post", return_value=mock_resp):
        ret = main([
            "corp",
            "example.com",
            "--light",
            "--no-cache",
            "--max-iterations", "2",
            "--max-runtime", "10",
            "-o", str(report_file),
        ])

    assert ret == 0
    assert report_file.exists()

    data = json.loads(report_file.read_text(encoding="utf-8"))
    assert "scan" in data
    assert "entities" in data
    assert "profile" in data

    scan = data["scan"]
    assert scan["mode"] == "corporate"
    assert "example.com" in str(scan["seed"])
    assert "started_at" in scan
    assert "finished_at" in scan
    assert "duration_s" in scan

    entities = data["entities"]
    assert "by_type" in entities
    assert "graph_edges" in entities
    assert "Domain" in entities["by_type"]
    domain_entity = entities["by_type"]["Domain"][0]
    for key in ["id", "type", "value", "confidence", "source_module", "parent_id", "discovered_at", "metadata"]:
        assert key in domain_entity
