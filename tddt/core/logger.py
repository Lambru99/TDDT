"""Logging setup for TDDT: Rich console + rotating file handler with
control-character escaping (prevents terminal injection from attacker-
controlled log messages — Review Focus #3)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from rich.logging import RichHandler

# Custom verbosity level below DEBUG for tracing HTTP body previews etc.
TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")


def _trace(self: logging.Logger, msg: str, *args: Any, **kwargs: Any) -> None:
    if self.isEnabledFor(TRACE_LEVEL):
        self._log(TRACE_LEVEL, msg, args, **kwargs)


# Monkey-patch Logger so `get_logger(...).trace("msg")` works everywhere.
logging.Logger.trace = _trace  # type: ignore[attr-defined]


_FILE_HANDLER_MARK = "_tddt_file_handler"
_CONSOLE_HANDLER_MARK = "_tddt_console_handler"


class _SafeFormatter(logging.Formatter):
    """Formatter that escapes non-printable characters so attacker-controlled
    values cannot inject ANSI sequences, line breaks, or NULs — into the
    on-disk log (file handler) or into the user's terminal (console handler)."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return self._escape(formatted)

    @staticmethod
    def _escape(s: str) -> str:
        out: list[str] = []
        for c in s:
            if c == "\t":
                out.append(c)
            elif c.isprintable():
                out.append(c)
            else:
                out.append(f"\\x{ord(c):02x}")
        return "".join(out)


# Backward-compat alias.
_SafeFileFormatter = _SafeFormatter


def _level_from_verbosity(verbosity: int) -> int:
    if verbosity <= 0:
        return logging.INFO
    if verbosity == 1:
        return logging.DEBUG
    return TRACE_LEVEL


def setup_logging(verbosity: int = 0, log_dir: Path | None = None) -> None:
    """Configure root logging. Idempotent: safe to call multiple times.

    - verbosity 0 → INFO, 1 → DEBUG, 2+ → TRACE
    - log_dir, if provided, installs a RotatingFileHandler at <log_dir>/tddt.log
      with safe formatting (control chars escaped).
    """
    root = logging.getLogger()
    level = _level_from_verbosity(verbosity)
    root.setLevel(level)

    # Remove previously-installed TDDT handlers so repeated calls don't stack.
    for h in list(root.handlers):
        if getattr(h, _FILE_HANDLER_MARK, False) or getattr(h, _CONSOLE_HANDLER_MARK, False):
            root.removeHandler(h)
            try:
                h.close()
            except OSError as exc:
                # Best-effort cleanup — log at WARNING so it's traceable, but
                # a failed close must not prevent configuring the new handler.
                logging.getLogger(__name__).warning(
                    "failed to close previous handler: %s", exc
                )

    console = RichHandler(
        level=level,
        markup=False,  # do not interpret [red]...[/red] in messages (injection surface)
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
    )
    console.setFormatter(_SafeFormatter("[%(name)s] %(message)s"))
    setattr(console, _CONSOLE_HANDLER_MARK, True)
    root.addHandler(console)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_dir / "tddt.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(
            _SafeFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        setattr(fh, _FILE_HANDLER_MARK, True)
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger. Use the module's dotted path, e.g.
    `get_logger(__name__)` or `get_logger("tddt.modules.corporate.email.bing")`.
    """
    return logging.getLogger(name)
