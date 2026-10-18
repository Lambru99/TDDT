"""End-to-end integration test for user email scan."""

import json
from unittest.mock import MagicMock, patch
import pytest

from tddt.cli import main
from tddt.core.http import reset_client


@pytest.fixture(autouse=True)
def _cleanup():
    reset_client()
    yield
    reset_client()


def test_user_scan_email_e2e(tmp_path):
    report_file = tmp_path / "user_report.json"

    # Mock DNS resolution
    mock_dns_answer = MagicMock()
    mock_mx_item = MagicMock()
    mock_mx_item.exchange.to_text.return_value = "mail.example.com."
    mock_dns_answer.__iter__.return_value = [mock_mx_item]

    with patch("dns.resolver.resolve", return_value=mock_dns_answer):
        ret = main([
            "user",
            "--email", "john.doe@example.com",
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
    assert scan["mode"] == "user"
    assert "john.doe@example.com" in str(scan["seed"])

    entities = data["entities"]
    assert "by_type" in entities
    assert "Email" in entities["by_type"]
    email_entity = entities["by_type"]["Email"][0]
    for key in ["id", "type", "value", "confidence", "source_module", "parent_id", "discovered_at", "metadata"]:
        assert key in email_entity
