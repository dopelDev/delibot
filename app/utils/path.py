# app/utils/path.py
"""
Normalizes the project structure and returns functions referencing locations
"""
from pathlib import Path


def get_project_root(marker_file='requirements.txt') -> Path:
    """
    return the project root directory
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / marker_file).is_file():
            return parent
    msg = f"Root FIle Not Found: '{marker_file}'"
    raise FileNotFoundError(msg)
