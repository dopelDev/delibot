# app/utils/path.py
"""
It looks for file target in the parrent directories and returns that pathlib
as the project root when it's delivered.
By default, it uses requirements.txt
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
    msg = f"Root File Not Found: '{marker_file}'"
    raise FileNotFoundError(msg)
