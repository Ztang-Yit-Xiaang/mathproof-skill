"""Puts the skill's scripts on sys.path for the tests in this directory.

MATHPROOF_TEST_SCRIPTS points the tests at another copy, which is how test_mutants.py checks that
the tests catch deliberately broken code. Only tests read it; the tools themselves never do.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(os.environ.get("MATHPROOF_TEST_SCRIPTS", ROOT / "skill" / "scripts"))
sys.path.insert(0, str(SCRIPTS))
