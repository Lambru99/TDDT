"""Tests for legacy main.py shim."""

from pathlib import Path
import sys
from unittest.mock import patch
import pytest

root_dir = str(Path(__file__).resolve().parents[2])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import main as legacy_main


def test_legacy_shim_redirects_to_v2_corp(capsys):
    import main as legacy_main

    with patch("tddt.cli.main", return_value=0) as mock_cli_main:
        with patch.object(sys, "argv", ["main.py", "example.com", "--light"]):
            code = legacy_main.main()

    assert code == 0
    captured = capsys.readouterr()
    assert "DEPRECATION" in captured.err or "deprecated" in captured.err.lower()
    mock_cli_main.assert_called_once()
    args_passed = mock_cli_main.call_args[0][0]
    assert args_passed[0] == "corp"
    assert "example.com" in args_passed
    assert "--light" in args_passed


def test_legacy_shim_translates_output_flag():
    import main as legacy_main

    with patch("tddt.cli.main", return_value=0) as mock_cli_main:
        with patch.object(sys, "argv", ["main.py", "target.org", "-o", "custom.json"]):
            legacy_main.main()

    args_passed = mock_cli_main.call_args[0][0]
    assert args_passed[0] == "corp"
    assert "target.org" in args_passed
    assert "-o" in args_passed
    assert "custom.json" in args_passed
