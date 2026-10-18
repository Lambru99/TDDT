from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from tddt.core.logger import TRACE_LEVEL, get_logger, setup_logging


@pytest.fixture(autouse=True)
def _reset_logging():
    """Each test gets a clean root logger."""
    yield
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:  # noqa: BLE001 - test cleanup, harmless
            pass
    root.setLevel(logging.WARNING)


def test_setup_info_level():
    setup_logging(0)
    assert logging.getLogger().level == logging.INFO


def test_setup_debug_with_v():
    setup_logging(1)
    assert logging.getLogger().level == logging.DEBUG


def test_setup_trace_with_vv():
    setup_logging(2)
    assert TRACE_LEVEL == 5
    assert logging.getLogger().level == TRACE_LEVEL
    log = get_logger("test.trace")
    # method must exist and not raise
    log.trace("hello %s", "world")


def test_file_handler_rotates(tmp_path: Path):
    setup_logging(0, tmp_path)
    get_logger("test.file").info("boom")
    root = logging.getLogger()
    rfh_list = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rfh_list) == 1
    rfh = rfh_list[0]
    assert rfh.maxBytes == 10 * 1024 * 1024
    assert rfh.backupCount == 5
    rfh.flush()
    log_file = tmp_path / "tddt.log"
    assert log_file.exists()
    assert "boom" in log_file.read_text()


def test_control_chars_escaped_in_log(tmp_path: Path):
    """Review Focus #3 (log leg): ANSI escape sequences must be escaped in the
    file handler so a malicious value can't inject terminal control codes
    when the log is viewed with `cat` or `less`."""
    setup_logging(0, tmp_path)
    log = get_logger("test.ansi")
    attacker_msg = "safe \x1b[31mred_part\x1b[0m end"
    log.info(attacker_msg)
    for h in logging.getLogger().handlers:
        h.flush()
    content = (tmp_path / "tddt.log").read_text()
    assert "\x1b[31m" not in content, "raw ANSI escape must not reach the log file"
    assert "\\x1b" in content, "escaped form must be present"
    # The surrounding safe text must still be present.
    assert "safe" in content
    assert "red_part" in content


def test_get_logger_returns_namespaced_logger():
    log = get_logger("tddt.modules.corporate.email.bing")
    assert log.name == "tddt.modules.corporate.email.bing"


def test_control_chars_escaped_in_console_handler():
    """Review Focus #3: the console handler must also escape control chars,
    otherwise an attacker-controlled value in a log line can inject ANSI
    sequences into the user's terminal."""
    setup_logging(0)
    root = logging.getLogger()
    console_h = next(
        h for h in root.handlers if getattr(h, "_tddt_console_handler", False)
    )
    record = logging.LogRecord(
        name="test.console",
        level=logging.WARNING,
        pathname="t.py",
        lineno=1,
        msg="safe \x1b[31mred\x1b[0m end",
        args=(),
        exc_info=None,
    )
    formatted = console_h.format(record)
    assert "\x1b[31m" not in formatted
    assert "\\x1b" in formatted
    assert "safe" in formatted
    assert "red" in formatted


def test_setup_is_idempotent(tmp_path: Path):
    setup_logging(0, tmp_path)
    setup_logging(0, tmp_path)
    root = logging.getLogger()
    rfh_list = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rfh_list) == 1
