# tests/test_path.py
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import textwrap

import pytest


_PATH_SOURCE = """
from __future__ import annotations
from pathlib import Path

def get_project_root(marker_file: str = 'requirements.txt') -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / marker_file).is_file():
            return parent
    raise FileNotFoundError(f"Root file not found: '{marker_file}'")
"""


def _load_path_module(tmp_dir: Path, mod_name: str = "tmp_app_utils_path"):
    pkg_dir = tmp_dir / "app" / "utils"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    mod_path = pkg_dir / "path.py"
    mod_path.write_text(textwrap.dedent(_PATH_SOURCE))
    spec = importlib.util.spec_from_file_location(mod_name, mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod, mod_path


def test_get_project_root_finds_default_marker(monkeypatch, tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = a / "b"
    c = b / "c"
    c.mkdir(parents=True)
    (a / "requirements.txt").write_text("# marker\n")

    path_mod, path_file = _load_path_module(tmp_path)
    # Pretend the module file lives under /tmp/a/b/c/path.py
    fake_file = c / "path.py"
    fake_file.write_text("# dummy\n")
    monkeypatch.setattr(path_mod, "__file__", str(fake_file))

    assert path_mod.get_project_root() == a


@pytest.mark.parametrize("marker", ["pyproject.toml", ".git"])
def test_get_project_root_with_custom_marker(monkeypatch, tmp_path: Path, marker: str) -> None:
    root = tmp_path / "root"
    sub = root / "pkg" / "mod"
    sub.mkdir(parents=True)
    (root / marker).write_text("marker\n")

    path_mod, _ = _load_path_module(tmp_path)
    fake_file = sub / "path.py"
    fake_file.write_text("# dummy\n")
    monkeypatch.setattr(path_mod, "__file__", str(fake_file))

    assert path_mod.get_project_root(marker_file=marker) == root


def test_get_project_root_raises_when_marker_missing(monkeypatch, tmp_path: Path) -> None:
    sub = tmp_path / "x" / "y" / "z"
    sub.mkdir(parents=True)

    path_mod, _ = _load_path_module(tmp_path)
    fake_file = sub / "path.py"
    fake_file.write_text("# dummy\n")
    monkeypatch.setattr(path_mod, "__file__", str(fake_file))

    with pytest.raises(FileNotFoundError):
        path_mod.get_project_root()
