"""Tests for external.photon module."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from tddt.core.config import Settings
from tddt.core.entity import Domain, Email, Secret, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.external.photon import PhotonModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_photon_active_attribute(http_client):
    mod = PhotonModule(http_client, Settings())
    assert mod.active is True


def test_photon_uses_sys_executable_and_parses_output(http_client, tmp_path):
    """Bug §2.13 fix: uses sys.executable and parses all photon output files."""
    dummy_photon = tmp_path / "photon.py"
    dummy_photon.touch()
    settings = Settings(photon_path=str(dummy_photon))
    mod = PhotonModule(http_client, settings)
    domain = Domain(value="example.com")

    # Set up dummy output folder structure
    out_dir = tmp_path / "photon_out"
    out_dir.mkdir()
    (out_dir / "internal.txt").write_text("https://example.com/api/v1\nhttps://example.com/login\n")
    (out_dir / "keys.txt").write_text("AKIAIOSFODNN7EXAMPLE\n")
    (out_dir / "intel.txt").write_text("Contact admin@example.com for info\n")

    executed_cmd = []

    def mock_subprocess_run(cmd, **kwargs):
        executed_cmd.extend(cmd)
        assert kwargs.get("timeout") == 300
        return MagicMock(returncode=0, stderr="")

    with patch("subprocess.run", side_effect=mock_subprocess_run), \
         patch.object(mod, "_get_output_dir", return_value=out_dir):
        entities = list(mod.run([domain]))

    # Assert sys.executable was used
    assert sys.executable in executed_cmd

    urls = [e for e in entities if isinstance(e, URL)]
    secrets = [e for e in entities if isinstance(e, Secret)]
    emails = [e for e in entities if isinstance(e, Email)]

    assert len(urls) == 2
    assert len(secrets) == 1
    assert len(emails) == 1
    assert emails[0].value == "admin@example.com"


def test_photon_preserves_partial_results_on_timeout(http_client, tmp_path):
    """Bug §2.13 fix: partial results preserved if subprocess times out."""
    dummy_photon = tmp_path / "photon.py"
    dummy_photon.touch()
    settings = Settings(photon_path=str(dummy_photon))
    mod = PhotonModule(http_client, settings)
    domain = Domain(value="example.com")

    out_dir = tmp_path / "photon_out_partial"
    out_dir.mkdir()
    (out_dir / "internal.txt").write_text("https://example.com/partial_saved\n")

    def mock_timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=300)

    with patch("subprocess.run", side_effect=mock_timeout), \
         patch.object(mod, "_get_output_dir", return_value=out_dir):
        entities = list(mod.run([domain]))

    urls = [e for e in entities if isinstance(e, URL)]
    assert len(urls) == 1
    assert "partial_saved" in urls[0].value
