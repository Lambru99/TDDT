"""Settings dataclass + loader.

Precedence (lowest → highest):
  1. field defaults
  2. .env file (if path given)
  3. process environment
  4. CLI overrides dict
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from tddt.core.logger import get_logger

_log = get_logger(__name__)


# Map .env / process-env variable → Settings attribute.
ENV_KEY_MAP: dict[str, str] = {
    "HUNTER_API_KEY": "hunter",
    "OTX_API_KEY": "otx",
    "URLSCAN_API_KEY": "urlscan",
    "URLDNA_API_KEY": "urldna",
    "GRAYHAT_API_KEY": "grayhat",
    "GITHUB_TOKEN": "github",
    "PHOTON_PATH": "photon_path",
    "HIBP_API_KEY": "hibp",
    "DEHASHED_API_KEY": "dehashed",
    "TRUECALLER_API_KEY": "truecaller",
    "TRUECALLER_AUTH": "truecaller",
}


@dataclass
class Settings:
    # Runtime
    threads: int = 20
    timeout: float = 15.0
    verify_tls: bool = True
    cache_enabled: bool = True
    proxy: str | None = None
    aggressive_email: bool = False
    aggressive_phone: bool = False
    follow_domains: bool = False
    max_iterations: int = 5
    max_runtime: float = 600.0
    # API keys (all optional)
    hunter: str | None = None
    otx: str | None = None
    urlscan: str | None = None
    urldna: str | None = None
    grayhat: str | None = None
    github: str | None = None
    photon_path: str | None = None
    hibp: str | None = None
    dehashed: str | None = None
    truecaller: str | None = None


def _clean(value: str | None) -> str | None:
    """Strip whitespace; blank → None."""
    if value is None:
        return None
    v = value.strip()
    return v or None


def load_settings(
    env_path: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> Settings:
    """Build a Settings instance applying .env file + process env + CLI overrides.

    - `env_path`: optional path to a `.env` file. If given but the file does not
      exist, a warning is logged and defaults/process-env are used.
    - `cli_overrides`: dict of attribute names → values that override everything.
      Unknown keys are silently ignored (CLI argparse is the validator).
    """
    s = Settings()

    # Layer 1: .env file
    if env_path is not None:
        if env_path.exists():
            env_values = dotenv_values(env_path)
        else:
            _log.warning(".env file not found at %s; using defaults + process env", env_path)
            env_values = {}
    else:
        env_values = {}

    # Layer 2: process environment overrides what the .env file provided
    for env_name, attr in ENV_KEY_MAP.items():
        proc_val = os.environ.get(env_name)
        env_val = env_values.get(env_name)
        chosen = _clean(proc_val) if proc_val is not None else _clean(env_val)
        if chosen is not None:
            setattr(s, attr, chosen)

    # Layer 3: CLI overrides
    if cli_overrides:
        known_attrs = {f.name for f in fields(s)}
        for k, v in cli_overrides.items():
            if k in known_attrs and v is not None:
                setattr(s, k, v)

    return s
