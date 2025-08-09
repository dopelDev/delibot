# app/utils/logger.py
"""
Centralized logging for Delibot.

- ROOT_PATH global via get_project_root()
- Loads <ROOT_PATH>/discord.env (only cares about LOG_LEVEL)
- Logs to <ROOT_PATH>/logs/delibot.log with daily rotation (7 backups)
- get_logger() returns child loggers under "delibot.<module>"
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

from dotenv import load_dotenv
from app.utils.path import get_project_root

# ---- Globals ---------------------------------------------------------------

# Project root (single source of truth)
ROOT_PATH: Path = get_project_root()
# Logs directory fixed under root
LOGS_DIR: Path = (ROOT_PATH / "logs").resolve()

# Load env from <ROOT_PATH>/discord.env (LOG_LEVEL opcional)
load_dotenv(dotenv_path=ROOT_PATH / "discord.env", override=False)

_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR":    logging.ERROR,
    "WARNING":  logging.WARNING,
    "INFO":     logging.INFO,
    "DEBUG":    logging.DEBUG,
    "NOTSET":   logging.NOTSET,
}


def _coerce_level(level_str: str | None) -> int:
    """Map a string level to logging constant, defaulting to INFO."""
    if not level_str:
        return logging.INFO
    return _LEVELS.get(level_str.upper(), logging.INFO)


def _configure_root_logger(level: str | None = None) -> logging.Logger:
    """
    Configure the 'delibot' base logger once.
    Handlers:
      - Stream (stdout)
      - TimedRotatingFileHandler (midnight rotation, 7 backups)
    """
    app_logger = logging.getLogger("delibot")

    # Already configured? just normalize levels and return.
    if getattr(_configure_root_logger, "_configured", False):
        resolved = _coerce_level(os.getenv("LOG_LEVEL", level))
        app_logger.setLevel(resolved)
        for h in app_logger.handlers:
            h.setLevel(resolved)
        return app_logger

    resolved = _coerce_level(os.getenv("LOG_LEVEL", level))

    fmt = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # Console (stdout funciona bien en contenedores/supervisores)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(resolved)
    ch.setFormatter(formatter)

    # File <ROOT_PATH>/logs/delibot.log
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fh = TimedRotatingFileHandler(
        filename=os.fspath(LOGS_DIR / "delibot.log"),
        when="midnight",
        backupCount=7,
        encoding="utf-8",
        delay=True,   # no abre el archivo hasta el primer log
        utc=False,
    )
    fh.setLevel(resolved)
    fh.setFormatter(formatter)

    # Bind
    app_logger.setLevel(resolved)
    app_logger.propagate = False  # no burbujear al root
    if not app_logger.handlers:
        app_logger.addHandler(ch)
        app_logger.addHandler(fh)

    _configure_root_logger._configured = True  # evita usar 'global'
    return app_logger


def get_logger(name: str | None = None, *, level: str | None = None) -> logging.Logger:
    """
    Return a logger under "delibot.<name>" (inherits handlers from 'delibot').
    If name is None, infers the caller module name.
    """
    _configure_root_logger(level=level)

    if not name:
        f = sys._getframe(1)  # más ligero que inspect.stack()
        name = f.f_globals.get("__name__", "__main__")

    if not name.startswith("delibot."):
        name = f"delibot.{name}"

    return logging.getLogger(name)
