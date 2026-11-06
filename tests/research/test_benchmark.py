"""The benchmark must record which skill text produced its answers, and never reuse stale ones."""

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from _paths import ROOT

spec = importlib.util.spec_from_file_location("run_benchmark", ROOT / "scripts" / "run_benchmark.py")
run_benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_benchmark)

CASE = {"id": "case-1", "claim": "c", "proof_steps": ["s"]}
ANSWER = '{"verdict": "VALID", "first_bad_step": null}\n'


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.skill = root / "SKILL.md"
        self.skill.write_text("version one", encoding="utf-8")
        self.out = root / "results"
        for name, value in (("OUT", self.out), ("SKILL", self.skill)):
            patcher = mock.patch.object(run_benchmark, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(run_benchmark.subprocess, "run",
                                    return_value=SimpleNamespace(returncode=0, stdout=ANSWER, stderr=""))
        self.model = patcher.start()
        self.addCleanup(patcher.stop)

    def ask(self, condition="skill"):
        return run_benchmark.ask("haiku", condition, CASE, 10)

    def test_a_skill_answer_is_reused_for_the_same_text(self):
        self.ask()
        self.ask()
        self.assertEqual(self.model.call_count, 1)

    def test_a_skill_answer_is_not_reused_after_the_text_changes(self):
        self.ask()
        self.skill.write_text("version two", encoding="utf-8")
        self.ask()
        self.assertEqual(self.model.call_count, 2)

    def test_a_skill_answer_with_no_recorded_text_is_not_reused(self):
        path = self.out / "raw" / "haiku" / "skill" / "case-1.txt"
        path.parent.mkdir(parents=True)
        path.write_text(ANSWER, encoding="utf-8")
        self.ask()
        self.assertEqual(self.model.call_count, 1)

    def test_a_baseline_answer_does_not_depend_on_the_skill(self):
        self.ask("baseline")
        self.skill.write_text("version two", encoding="utf-8")
        self.ask("baseline")
        self.assertEqual(self.model.call_count, 1)

    def test_a_failed_call_records_no_hash(self):
        self.model.return_value = SimpleNamespace(returncode=1, stdout="", stderr="boom")
        with self.assertRaises(RuntimeError):
            self.ask()
        self.assertEqual(list(self.out.rglob("*.sha256")), [])

    def test_the_summary_records_the_skill_hash(self):
        with mock.patch.object(sys, "argv", ["run_benchmark.py", "--model", "haiku", "-j", "1"]), \
                mock.patch.object(run_benchmark, "CASES", self._cases_file()), mock.patch("builtins.print"):
            run_benchmark.main()
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["skill_sha256"], hashlib.sha256(b"version one").hexdigest())

    def _cases_file(self):
        path = Path(self._tmp.name, "cases.jsonl")
        case = {**CASE, "expected_verdict": "VALID", "expected_first_bad_step": None}
        path.write_text(json.dumps(case) + "\n", encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
