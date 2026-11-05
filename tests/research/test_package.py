"""S0.T1: the package is stdlib-only, optional, and ships with the skill."""

import ast
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SCRIPTS


class PackageTests(unittest.TestCase):
    def test_imports_from_a_copied_scripts_directory(self):
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d, "scripts")
            shutil.copytree(SCRIPTS, copy)
            run = subprocess.run([sys.executable, "-c", "import mathproof_core; print(mathproof_core.__version__)"],
                                 cwd=copy, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(run.stdout.strip())

    def test_only_the_standard_library_is_imported(self):
        for path in (SCRIPTS / "mathproof_core").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module]
                for name in names:
                    root = name.split(".")[0]
                    self.assertTrue(root in sys.stdlib_module_names or root == "mathproof_core", f"{path}: {name}")

    def test_checker_works_without_the_package(self):
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d, "skill")
            shutil.copytree(ROOT / "skill", copy)
            shutil.rmtree(copy / "scripts" / "mathproof_core")
            run = subprocess.run([sys.executable, str(copy / "scripts" / "lean_check.py"), "--help"],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_installer_carries_the_package(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            (home / ".claude").mkdir()
            run = subprocess.run(["bash", str(ROOT / "scripts" / "install.sh")], capture_output=True, text=True,
                                 env={**os.environ, "HOME": str(home)})
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            installed = home / ".claude" / "skills" / "mathproof-skill" / "scripts" / "mathproof_core" / "__init__.py"
            self.assertTrue(installed.exists(), run.stdout)

    def test_ci_runs_these_tests(self):
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        self.assertIn("tests/research", workflow)


if __name__ == "__main__":
    unittest.main()
