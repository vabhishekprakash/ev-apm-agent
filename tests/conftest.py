"""Make detector/ modules importable from tests without packaging."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "detector"))
