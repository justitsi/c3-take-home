"""Keep the controller test suite runnable from a mounted Docker workspace."""
import sys
from pathlib import Path

SOLUTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION))
sys.path.insert(0, str(SOLUTION / "fixer"))
