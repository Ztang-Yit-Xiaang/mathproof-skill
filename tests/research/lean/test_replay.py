"""S1.3.T2: `mathproof verify` re-runs checks and reports differences. Needs Lean."""

import json
import os
import shutil
import unittest
from pathlib import Path

from _lean_support import ACTOR, core_project, temp_dir
from mathproof_core.gate import record_check
from mathproof_core.ledger import Ledger
from mathproof_core.replay import DELETION_NOTE, verify_investigation

CLAIM = "inv/c1"
GOOD = "theorem main_theorem : (2 : Nat) + 2 = 4 := rfl\n"
BAD = "theorem main_theorem : (1 : Nat) = 2 := by sorry\n"


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = temp_dir()
        cls.root = Path(cls._tmp.name)
        cls.project = core_project(cls.root)
        cls.clean = cls.root / "clean"
        ledger = Ledger.init(cls.clean)
        ledger.append("claim_created", CLAIM, {"text": "A claim.", "kind": "theorem"}, ACTOR)
        source = cls.root / "Good.lean"
        source.write_text(GOOD, encoding="utf-8")
        record_check(ledger, CLAIM, source, "main_theorem", "claim", cls.project)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def copy(self, name):
        target = self.root / name
        shutil.copytree(self.clean, target)
        return target

    def lines(self, directory):
        return (directory / "events.jsonl").read_text(encoding="utf-8").splitlines(keepends=True)

    def rewrite(self, directory, events):
        """A careful forger: recomputes every hash, so the chain itself is consistent."""
        prev = "0" * 64
        out = []
        for index, event in enumerate(events):
            event["seq"], event["prev"] = index, prev
            event.pop("hash", None)
            event["hash"] = prev = Ledger.event_hash(event)
            out.append(json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
        (directory / "events.jsonl").write_text("".join(out), encoding="utf-8")

    def assert_difference(self, result, text):
        self.assertFalse(result["ok"])
        self.assertTrue(any(text in json.dumps(d) for d in result["differences"]), result["differences"])

    def test_a_clean_ledger_passes_and_writes_nothing(self):
        before = {p: p.read_bytes() for p in self.clean.rglob("*") if p.is_file()}
        names = set(before)
        result = verify_investigation(self.clean)
        self.assertTrue(result["ok"], result["differences"])
        self.assertEqual(result["statuses"][CLAIM]["headline"], "kernel-passed-local")
        self.assertEqual(result["reruns"], 1)
        self.assertEqual({p for p in self.clean.rglob("*") if p.is_file()}, names)
        self.assertEqual(before, {p: p.read_bytes() for p in names})

    def test_output_states_that_deletion_is_not_detected(self):
        result = verify_investigation(self.clean)
        self.assertIn(DELETION_NOTE, result["notes"])
        self.assertIn("deletion", DELETION_NOTE.lower())

    def test_an_edited_event_is_reported_with_its_claim(self):
        directory = self.copy("edited_event")
        lines = self.lines(directory)
        lines[1] = lines[1].replace('"result":"pass"', '"result":"fail"')
        (directory / "events.jsonl").write_text("".join(lines), encoding="utf-8")
        self.assert_difference(verify_investigation(directory), CLAIM)

    def test_an_edited_artifact_is_reported_with_its_claim(self):
        directory = self.copy("edited_artifact")
        artifact = json.loads(self.lines(directory)[1])["data"]["artifact"]
        (directory / "artifacts" / artifact).write_text(BAD, encoding="utf-8")
        result = verify_investigation(directory)
        self.assert_difference(result, CLAIM)
        self.assert_difference(result, artifact)

    def test_a_consistent_rewrite_with_a_forged_pass_fails_because_the_rerun_disagrees(self):
        directory = self.copy("forged")
        ledger = Ledger(directory)
        bad = ledger.put_artifact(BAD.encode())
        events = ledger.read()
        events[1]["data"]["artifact"] = bad
        self.rewrite(directory, events)
        self.assertTrue(ledger.verify().ok)
        self.assert_difference(verify_investigation(directory), CLAIM)

    def test_a_hand_written_check_event_is_caught(self):
        directory = self.copy("hand_written")
        ledger = Ledger(directory)
        bad = ledger.put_artifact(BAD.encode())
        report = ledger.put_artifact(b"{}")
        ledger.append("check", CLAIM, {"artifact": bad, "target_decl": "main_theorem", "polarity": "claim", "result": "pass",
                                       "report_hash": report, "pins": {}, "tier": "authoritative", "project": str(self.project)}, ACTOR)
        self.assert_difference(verify_investigation(directory), CLAIM)

    def test_a_check_with_no_stored_artifact_is_caught(self):
        directory = self.copy("missing")
        artifact = json.loads(self.lines(directory)[1])["data"]["artifact"]
        (directory / "artifacts" / artifact).unlink()
        self.assert_difference(verify_investigation(directory), artifact)

    def test_project_override_is_used(self):
        directory = self.copy("moved")
        events = Ledger(directory).read()
        events[1]["data"]["project"] = "/nonexistent/project"
        self.rewrite(directory, events)
        self.assertTrue(verify_investigation(directory, project=self.project)["ok"])

    def test_a_missing_project_is_an_environment_error_not_a_pass(self):
        directory = self.copy("no_project")
        events = Ledger(directory).read()
        events[1]["data"]["project"] = "/nonexistent/project"
        self.rewrite(directory, events)
        result = verify_investigation(directory)
        self.assertFalse(result["ok"])
        self.assertTrue(result["environment_errors"])

    def test_lean_missing_is_an_environment_error_not_a_pass(self):
        path = os.environ["PATH"]
        os.environ["PATH"] = "/nonexistent"
        try:
            result = verify_investigation(self.clean)
        finally:
            os.environ["PATH"] = path
        self.assertFalse(result["ok"])
        self.assertTrue(result["environment_errors"])


if __name__ == "__main__":
    unittest.main()
