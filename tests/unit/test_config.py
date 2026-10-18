from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from tddt.core.config import ENV_KEY_MAP, Settings, load_settings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    """Each test starts with the TDDT-related env vars unset."""
    for env_name in ENV_KEY_MAP:
        monkeypatch.delenv(env_name, raising=False)


def test_defaults():
    s = load_settings()
    assert s.threads == 20
    assert s.timeout == 15.0
    assert s.verify_tls is True
    assert s.cache_enabled is True
    assert s.proxy is None
    assert s.aggressive_email is False
    assert s.aggressive_phone is False
    assert s.follow_domains is False
    assert s.max_iterations == 5
    assert s.max_runtime == 600.0
    # API keys default to None
    assert s.hunter is None
    assert s.otx is None
    assert s.urlscan is None
    assert s.urldna is None
    assert s.grayhat is None
    assert s.github is None
    assert s.photon_path is None


def test_env_loads_key(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("HUNTER_API_KEY=abc\nOTX_API_KEY=def\n")
    s = load_settings(env_path=env_file)
    assert s.hunter == "abc"
    assert s.otx == "def"


def test_cli_override_wins(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("HUNTER_API_KEY=fromenv\n")
    s = load_settings(env_path=env_file, cli_overrides={"hunter": "fromcli", "threads": 50})
    assert s.hunter == "fromcli"
    assert s.threads == 50


def test_missing_env_file_warns_not_fails(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    nonexistent = tmp_path / "nope.env"
    with caplog.at_level(logging.WARNING):
        s = load_settings(env_path=nonexistent)
    assert isinstance(s, Settings)
    assert s.hunter is None
    # Warning emitted at least once mentioning the path.
    assert any("env" in rec.message.lower() for rec in caplog.records)


def test_env_blank_values_treated_as_none(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("HUNTER_API_KEY=\nOTX_API_KEY=   \n")
    s = load_settings(env_path=env_file)
    assert s.hunter is None
    assert s.otx is None


def test_process_env_fallback_when_env_path_none(monkeypatch: pytest.MonkeyPatch):
    """Without an env_path, process env is still read."""
    monkeypatch.setenv("HUNTER_API_KEY", "fromprocess")
    s = load_settings(env_path=None)
    assert s.hunter == "fromprocess"


def test_github_token_mapped():
    """GITHUB_TOKEN env var maps to settings.github."""
    os.environ["GITHUB_TOKEN"] = "ghp_test"
    try:
        s = load_settings()
        assert s.github == "ghp_test"
    finally:
        del os.environ["GITHUB_TOKEN"]


def test_cli_override_only_known_fields_ignored_cleanly():
    """Unknown CLI override keys should not raise; they just don't bind anywhere.
    (The CLI is expected to validate args; this is a safety net.)"""
    s = load_settings(cli_overrides={"unknown_field_xyz": "ignored", "threads": 7})
    assert s.threads == 7
    assert not hasattr(s, "unknown_field_xyz")
