from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

import pytest


# ---------------------------- helpers ---------------------------------

def _install_fake_get_project_root(fake_root: Path) -> None:
    """
    Install a stub module 'app.utils.path' in sys.modules providing
    get_project_root() that returns fake_root.
    """
    app_pkg = sys.modules.setdefault("app", ModuleType("app"))
    utils_pkg = sys.modules.setdefault("app.utils", ModuleType("app.utils"))

    path_mod = ModuleType("app.utils.path")

    def get_project_root(marker_file: str = "requirements.txt") -> Path:  # noqa: ARG001
        return fake_root
    path_mod.get_project_root = get_project_root  # type: ignore[attr-defined]

    sys.modules["app.utils.path"] = path_mod
    app_pkg.utils = utils_pkg  # type: ignore[attr-defined]


def _load_module_from_path(mod_name: str, file_path: Path):
    """Load a module object from a given file path using importlib."""
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


# ------------------------------ tests ---------------------------------

def test_configures_handlers_once_and_respects_env_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    When LOG_LEVEL is defined in <ROOT>/discord.env, the base 'delibot' logger
    and its handlers should use that level. Handlers: Stream + TimedRotatingFileHandler.
    """
    project_root = tmp_path
    _install_fake_get_project_root(project_root)

    # Provide an env file the module will load on import.
    (project_root / "discord.env").write_text("LOG_LEVEL=WARNING\n")

    # Write the logger module under a temp package path and load it.
    pkg_dir = project_root / "app" / "utils"
    pkg_dir.mkdir(parents=True)
    logger_py = pkg_dir / "logger.py"
    logger_py.write_text(
        (
            'from __future__ import annotations\n'
            'import os, sys, logging\n'
            'from pathlib import Path\n'
            'from logging.handlers import TimedRotatingFileHandler\n'
            'from dotenv import load_dotenv\n'
            'from app.utils.path import get_project_root\n'
            '\n'
            'try:\n'
            '    ROOT_PATH: Path = get_project_root()\n'
            'except FileNotFoundError:\n'
            '    ROOT_PATH: Path = Path.cwd()\n'
            'LOGS_DIR: Path = (ROOT_PATH / "logs").resolve()\n'
            'load_dotenv(dotenv_path=ROOT_PATH / "discord.env", override=False)\n'
            '_LEVELS = {"CRITICAL":50,"ERROR":40,"WARNING":30,"INFO":20,"DEBUG":10,"NOTSET":0}\n'
            'def _coerce_level(level_str: str | None) -> int:\n'
            '    if not level_str: return logging.INFO\n'
            '    return _LEVELS.get(level_str.upper(), logging.INFO)\n'
            'def _configure_root_logger(level: str | None = None) -> logging.Logger:\n'
            '    app_logger = logging.getLogger("delibot")\n'
            '    if getattr(_configure_root_logger, "_configured", False):\n'
            '        resolved = _coerce_level(os.getenv("LOG_LEVEL", level))\n'
            '        app_logger.setLevel(resolved)\n'
            '        for h in app_logger.handlers: h.setLevel(resolved)\n'
            '        return app_logger\n'
            '    resolved = _coerce_level(os.getenv("LOG_LEVEL", level))\n'
            '    fmt = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"\n'
            '    datefmt = "%Y-%m-%d %H:%M:%S"\n'
            '    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)\n'
            '    ch = logging.StreamHandler(sys.stdout)\n'
            '    ch.setLevel(resolved); ch.setFormatter(formatter)\n'
            '    LOGS_DIR.mkdir(parents=True, exist_ok=True)\n'
            '    fh = TimedRotatingFileHandler(\n'
            '        filename=os.fspath(LOGS_DIR / "delibot.log"), when="midnight", backupCount=7,'
            '        encoding="utf-8", delay=True, utc=False)\n'
            '    fh.setLevel(resolved); fh.setFormatter(formatter)\n'
            '    app_logger.setLevel(resolved); app_logger.propagate = False\n'
            '    if not app_logger.handlers:\n'
            '        app_logger.addHandler(ch); app_logger.addHandler(fh)\n'
            '    _configure_root_logger._configured = True\n'
            '    return app_logger\n'
            'def get_logger(name: str | None = None, *, level: str | None = None) -> logging.Logger:\n'
            '    _configure_root_logger(level=level)\n'
            '    if not name:\n'
            '        f = sys._getframe(1)\n'
            '        name = f.f_globals.get("__name__", "__main__")\n'
            '    if not name.startswith("delibot."):\n'
            '        name = f"delibot.{name}"\n'
            '    return logging.getLogger(name)\n'
        )
    )

    mod = _load_module_from_path("tmp_delibot_logger", logger_py)

    # First call configures the base logger
    log = mod.get_logger("test")
    assert log.name == "delibot.test"

    base = logging.getLogger("delibot")
    assert base.propagate is False
    assert len(base.handlers) == 2
    assert {type(h).__name__ for h in base.handlers} == {
        "StreamHandler", "TimedRotatingFileHandler"}

    # Level from env is WARNING
    assert base.level == logging.WARNING
    for h in base.handlers:
        assert h.level == logging.WARNING

    # After emitting, the file should exist
    log.warning("hello")
    assert (project_root / "logs" / "delibot.log").exists()


def test_reconfigure_updates_levels_on_second_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path
    _install_fake_get_project_root(project_root)
    (project_root / "discord.env").write_text("LOG_LEVEL=ERROR\n")

    # 👇 clave: que no exista LOG_LEVEL en el entorno del proceso
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    pkg_dir = project_root / "app" / "utils"
    pkg_dir.mkdir(parents=True)
    logger_py = pkg_dir / "logger.py"

    from textwrap import dedent
    logger_py.write_text(dedent(_LOGGER_SOURCE))

    mod = _load_module_from_path("tmp_delibot_logger2", logger_py)

    base = mod.get_logger("init")  # configura con ERROR
    parent = logging.getLogger("delibot")
    n_handlers = len(parent.handlers)
    assert parent.level == logging.ERROR
    assert base.getEffectiveLevel() == logging.ERROR

    # ahora cambia a DEBUG y reconfigura sin duplicar handlers
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    again = mod.get_logger("again")
    parent2 = logging.getLogger("delibot")
    assert len(parent2.handlers) == n_handlers
    assert parent2.level == logging.DEBUG
    for h in parent2.handlers:
        assert h.level == logging.DEBUG
    assert again.getEffectiveLevel() == logging.DEBUG


def test_get_logger_prefixing(tmp_path: Path) -> None:
    """
    Names not starting with 'delibot.' should be prefixed; already-prefixed names stay intact.
    """
    project_root = tmp_path
    _install_fake_get_project_root(project_root)
    (project_root / "discord.env").write_text("LOG_LEVEL=INFO\n")

    pkg_dir = project_root / "app" / "utils"
    pkg_dir.mkdir(parents=True)
    logger_py = pkg_dir / "logger.py"

    from textwrap import dedent
    logger_py.write_text(dedent(_LOGGER_SOURCE))

    mod = _load_module_from_path("tmp_delibot_logger3", logger_py)

    l1 = mod.get_logger("my.module")
    l2 = mod.get_logger("delibot.already")

    assert l1.name == "delibot.my.module"
    assert l2.name == "delibot.already"


def test__coerce_level_defaults_and_unknown(tmp_path: Path) -> None:
    """
    _coerce_level(None) and unknown strings should fall back to INFO.
    """
    project_root = tmp_path
    _install_fake_get_project_root(project_root)
    (project_root / "discord.env").write_text("")  # empty

    pkg_dir = project_root / "app" / "utils"
    pkg_dir.mkdir(parents=True)
    logger_py = pkg_dir / "logger.py"

    from textwrap import dedent
    logger_py.write_text(dedent(_LOGGER_SOURCE))

    mod = _load_module_from_path("tmp_delibot_logger4", logger_py)

    import builtins
    assert mod._coerce_level(None) == logging.INFO
    assert mod._coerce_level("weird") == logging.INFO
    assert mod._coerce_level("DEBUG") == logging.DEBUG
    assert mod._coerce_level("warning") == logging.WARNING


# -------------------------- shared module source ---------------------------

# Single-source the logger code body so we don't copy/paste in each test.
_LOGGER_SOURCE = """
from __future__ import annotations
import os, sys, logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
from app.utils.path import get_project_root

try:
    ROOT_PATH: Path = get_project_root()
except FileNotFoundError:
    ROOT_PATH: Path = Path.cwd()

LOGS_DIR: Path = (ROOT_PATH / "logs").resolve()
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
    if not level_str:
        return logging.INFO
    return _LEVELS.get(level_str.upper(), logging.INFO)

def _configure_root_logger(level: str | None = None) -> logging.Logger:
    app_logger = logging.getLogger("delibot")

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

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(resolved)
    ch.setFormatter(formatter)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fh = TimedRotatingFileHandler(
        filename=os.fspath(LOGS_DIR / "delibot.log"),
        when="midnight",
        backupCount=7,
        encoding="utf-8",
        delay=True,
        utc=False,
    )
    fh.setLevel(resolved)
    fh.setFormatter(formatter)

    app_logger.setLevel(resolved)
    app_logger.propagate = False
    if not app_logger.handlers:
        app_logger.addHandler(ch)
        app_logger.addHandler(fh)

    _configure_root_logger._configured = True
    return app_logger

def get_logger(name: str | None = None, *, level: str | None = None) -> logging.Logger:
    _configure_root_logger(level=level)

    if not name:
        f = sys._getframe(1)
        name = f.f_globals.get("__name__", "__main__")

    if not name.startswith("delibot."):
        name = f"delibot.{name}"

    return logging.getLogger(name)
"""
