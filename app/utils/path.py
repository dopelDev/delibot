# app/utils/path.py
"""
Project root path resolution utilities.

This module provides a function to locate the project root by walking
upward from the current file's directory until it finds a given marker file.

By default, it uses `requirements.txt` as the marker, but you can override it.
It also exports a `ROOT_PATH` constant so you don't have to call the function
manually every time.
"""

from __future__ import annotations
from pathlib import Path


def get_project_root(marker_file: str = 'requirements.txt') -> Path:
    """
    Locate and return the project root directory.

    Args:
        marker_file (str): File name to look for in parent directories.
                           Defaults to 'requirements.txt'.

    Returns:
        Path: Path object pointing to the project root directory.

    Raises:
        FileNotFoundError: If the marker file is not found in any parent directory.
    """
    # Comienza desde la ubicación actual de este archivo y sube directorio por directorio
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / marker_file).is_file():
            return parent

    # Si no encuentra el archivo marcador, lanza excepción
    msg = f"Root file not found: '{marker_file}'"
    raise FileNotFoundError(msg)


# Calcula ROOT_PATH una sola vez al importar este módulo
# Esto evita tener que llamar `get_project_root()` en cada archivo.
ROOT_PATH: Path = get_project_root()
