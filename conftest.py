# conftest.py
import sys
from pathlib import Path

# Añade el root del proyecto al sys.path si no está
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
