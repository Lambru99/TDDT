"""Tests for external.urldna module."""

from unittest.mock import MagicMock
import pytest

from tddt.core.config import Settings
from tddt.core.entity import Domain, Finding, Technology
from tddt.core.http import HttpClient
from tddt.modules.corporate.external.urldna import UrlDnaModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_urldna_missing_key_skips(http_client):
    settings = Settings(urldna="")
    mod = UrlDnaModule(http_client, settings)
    domain = Domain(value="example.com")
    entities = list(mod.run([domain]))
    assert len(entities) == 0


def test_urldna_polling_and_technology_discovery(http_client):
    """Bug §2.11 fix: polling loop until completion."""
    settings = Settings(urldna="urldna_key_123")
    mod = UrlDnaModule(http_client, settings)
    domain = Domain(value="example.com")

    # Mock UrlDNA client
    mock_client = MagicMock()
    mock_client.search.return_value = []
    
    mock_scan_create = MagicMock()
    mock_scan_create.scan.id = "scan_abc_123"
    mock_client.create_scan.return_value = mock_scan_create

    # First poll: not ready (no technologies yet); Second poll: ready
    scan_pending = MagicMock()
    scan_pending.technologies = []
    scan_pending.classification = None

    scan_finished = MagicMock()
    tech1 = MagicMock(name="React")
    tech1.name = "React"
    tech1.version = "18.2"
    tech1.category = "JavaScript Framework"
    scan_finished.technologies = [tech1]

    classif = MagicMock()
    classif.verdict = "Clean"
    scan_finished.classification = classif

    # Sequence of responses on get_scan
    mock_client.get_scan.side_effect = [scan_pending, scan_finished]

    entities = list(mod._analyze_with_client(domain, mock_client, poll_sleep=0.01, max_poll=5))

    techs = [e for e in entities if isinstance(e, Technology)]
    findings = [e for e in entities if isinstance(e, Finding)]

    assert len(techs) == 1
    assert "React" in techs[0].value
    assert len(findings) == 1
    assert findings[0].value == "Clean"
    assert mock_client.get_scan.call_count == 2
