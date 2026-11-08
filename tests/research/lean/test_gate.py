"""S1.3.T1: `mathproof check` runs the real checker and records the result. Needs Lean."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from _lean_support import ACTOR, core_project, temp_dir
from _paths import SCRIPTS
from mathproof_core.gate import EnvironmentFailure, record_check
from mathproof_core.ledger import Ledger
from mathproof_core.status import derive_status

CLAIM = "inv/c1"
GOOD = "theorem main_theorem : (2 : Nat) + 2 = 4 := rfl\nnamespace Other\ntheorem main_theorem : True := trivial\nend Other\n"
SORRY = "theorem main_theorem : (1 : Nat) = 2 := by sorry\n"


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = temp_dir()
        cls.root = Path(cls._tmp.name)
        cls.project = core_project(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def fresh(self, name):
        directory = self.root / name
        ledger = Ledger.init(directory)
        ledger.append("claim_created", CLAIM, {"text": "A claim.", "kind": "theorem"}, ACTOR)
        return ledger

    def source(self, text):
        path = self.root / "Source.lean"
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_passing_file_is_recorded_with_everything_replay_needs(self):
        ledger = self.fresh("pass")
        event = record_check(ledger, CLAIM, self.source(GOOD), "main_theorem", "claim", self.project)
        data = event["data"]
        self.assertEqual(data["result"], "pass")
        self.assertEqual(data["tier"], "local")
        self.assertEqual(data["project"], str(self.project.resolve()))
        self.assertEqual(data["axioms"], [])
        self.assertIn("2 + 2 = 4", data["type"])
        self.assertIs(data["pins"]["pinned"], False)
        self.assertEqual(ledger.get_artifact(data["artifact"]), GOOD.encode())
        report = json.loads(ledger.get_artifact(data["report_hash"]))
        self.assertEqual(report["status"], "PASS")
        self.assertNotIn(str(self.root), json.dumps({k: report[k] for k in report if k != "file"}))
        status = derive_status(ledger.read(), CLAIM, {})
        self.assertEqual(status["headline"], "kernel-passed-local")
        self.assertEqual(status["verdict"], "UNVERIFIED")
        self.assertTrue(ledger.verify().ok)

    def test_a_sorry_file_fails_with_no_status_gain(self):
        ledger = self.fresh("sorry")
        event = record_check(ledger, CLAIM, self.source(SORRY), "main_theorem", "claim", self.project)
        self.assertEqual(event["data"]["result"], "fail")
        status = derive_status(ledger.read(), CLAIM, {})
        self.assertEqual(status["headline"], "conjecture")
        self.assertEqual(status["axes"]["kernel"], "failed")

    def test_the_target_is_exact_not_a_suffix(self):
        ledger = self.fresh("suffix")
        source = self.source("namespace Other\ntheorem main_theorem : True := trivial\nend Other\n")
        event = record_check(ledger, CLAIM, source, "main_theorem", "claim", self.project)
        self.assertEqual(event["data"]["result"], "fail")
        self.assertEqual(record_check(ledger, CLAIM, source, "Other.main_theorem", "claim", self.project)["data"]["result"], "pass")

    def test_lean_missing_is_an_environment_error_with_no_result_event(self):
        ledger = self.fresh("nolean")
        path = os.environ["PATH"]
        os.environ["PATH"] = "/nonexistent"
        try:
            with self.assertRaises(EnvironmentFailure):
                record_check(ledger, CLAIM, self.source(GOOD), "main_theorem", "claim", self.project)
        finally:
            os.environ["PATH"] = path
        self.assertEqual([e["kind"] for e in ledger.read()], ["claim_created"])

    def test_an_unknown_claim_is_refused(self):
        ledger = self.fresh("noclaim")
        with self.assertRaises(ValueError):
            record_check(ledger, "inv/other", self.source(GOOD), "main_theorem", "claim", self.project)

    def test_cli_runs_the_gate_and_exit_codes_follow_the_checker(self):
        launcher = str(SCRIPTS / "mathproof.py")
        directory = self.root / "cli"
        run = lambda *a: subprocess.run([sys.executable, launcher, *a], capture_output=True, text=True, cwd=self.root)  # noqa: E731
        self.assertEqual(run("init", str(directory)).returncode, 0)
        self.assertEqual(run("claim", "add", "--dir", str(directory), "--id", CLAIM, "--text", "x", "--kind", "theorem").returncode, 0)
        args = ["check", "--dir", str(directory), "--claim", CLAIM, "--decl", "main_theorem", "--polarity", "claim", "--project", str(self.project)]
        good = run(*args, str(self.source(GOOD)))
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(run(*args, str(self.source(SORRY))).returncode, 1)
        status = run("status", "--dir", str(directory), "--claim", CLAIM)
        self.assertEqual(json.loads(status.stdout)["verdict"], "UNVERIFIED")
        report = run("report", "--dir", str(directory), "--claim", CLAIM)
        self.assertIn("**Verdict:** UNVERIFIED", report.stdout)


if __name__ == "__main__":
    unittest.main()
