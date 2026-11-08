"""Shared setup for the tests that run Lean. These run only in lean.yml."""

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _paths import ROOT  # noqa: E402

REPO_PROJECT = ROOT / "lean"
FIXTURES = ROOT / "tests" / "lean_check"
ACTOR = {"context_id": "test", "role": "tester", "kind": "agent"}


def core_project(root: Path) -> Path:
    """A project with no packages: fast, and not on the tested Mathlib, so reported as unpinned."""
    project = root / "project"
    project.mkdir()
    shutil.copy(REPO_PROJECT / "lean-toolchain", project / "lean-toolchain")
    (project / "lakefile.toml").write_text('name = "project"\n', encoding="utf-8")
    return project


def temp_dir() -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory()
