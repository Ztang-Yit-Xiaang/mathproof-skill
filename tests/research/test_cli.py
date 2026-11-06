"""S1.3.T3: the records CLI."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT


class CliTests(unittest.TestCase):
    launcher = ROOT / "skill" / "scripts" / "mathproof.py"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name, "inv")

    def run_cli(self, *args, launcher=None, cwd=None):
        return subprocess.run([sys.executable, str(launcher or self.launcher), *args], capture_output=True, text=True,
                              cwd=cwd or self._tmp.name)

    def events(self):
        return [json.loads(l) for l in (self.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]

    def init_and_claim(self, launcher=None):
        self.assertEqual(self.run_cli("init", str(self.dir), launcher=launcher).returncode, 0)
        run = self.run_cli("claim", "add", "--dir", str(self.dir), "--id", "inv/c1", "--text", "A claim.",
                           "--kind", "theorem", launcher=launcher)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_init_claim_and_event(self):
        self.init_and_claim()
        run = self.run_cli("event", "add", "--dir", str(self.dir), "--claim", "inv/c1", "--kind", "assumption",
                           "--data", json.dumps({"text": "n > 0", "standing": "given", "origin": "statement", "change": "add"}))
        self.assertEqual(run.returncode, 0, run.stderr)
        kinds = [e["kind"] for e in self.events()]
        self.assertEqual(kinds, ["claim_created", "assumption"])
        self.assertEqual(self.events()[0]["claim"], "inv/c1")
        self.assertEqual(self.events()[0]["data"]["text"], "A claim.")

    def test_works_from_a_copied_skill_directory_and_any_cwd(self):
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d, "skill")
            shutil.copytree(ROOT / "skill", copy)
            self.init_and_claim(launcher=copy / "scripts" / "mathproof.py")

    def test_open_vocabulary_kinds_are_allowed(self):
        self.init_and_claim()
        run = self.run_cli("event", "add", "--dir", str(self.dir), "--kind", "note", "--data", '{"text": "idea"}')
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_gated_kinds_are_refused(self):
        self.init_and_claim()
        for kind in ("check", "statement_frozen", "witness", "challenge", "certificate"):
            run = self.run_cli("event", "add", "--dir", str(self.dir), "--claim", "inv/c1", "--kind", kind, "--data", "{}")
            self.assertNotEqual(run.returncode, 0, kind)
            self.assertIn(kind, run.stderr)
            self.assertNotIn("Traceback", run.stderr)
        self.assertEqual(len(self.events()), 1)

    def test_a_claims_statement_cannot_be_replaced(self):
        self.init_and_claim()
        run = self.run_cli("claim", "add", "--dir", str(self.dir), "--id", "inv/c1", "--text", "A weaker claim.",
                           "--kind", "theorem")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("inv/c1", run.stderr)
        self.assertEqual(len(self.events()), 1)

    def test_event_add_cannot_create_claims_or_recovery_records(self):
        self.init_and_claim()
        for kind in ("claim_created", "ledger_recovery"):
            run = self.run_cli("event", "add", "--dir", str(self.dir), "--claim", "inv/c1", "--kind", kind,
                               "--data", '{"text": "weaker", "kind": "theorem"}')
            self.assertNotEqual(run.returncode, 0, kind)
        self.assertEqual(len(self.events()), 1)

    def test_cli_events_are_marked_self_declared(self):
        self.init_and_claim()
        self.assertEqual(self.events()[0]["actor"]["kind"], "self-declared")

    def test_bad_input_is_refused_cleanly(self):
        self.init_and_claim()
        for args in (["--kind", "note", "--data", "not json"],
                     ["--kind", "note", "--data", '{"status": "VALID"}'],
                     ["--claim", "bad id", "--kind", "note", "--data", "{}"]):
            run = self.run_cli("event", "add", "--dir", str(self.dir), *args)
            self.assertNotEqual(run.returncode, 0, args)
            self.assertNotIn("Traceback", run.stderr)

    def test_help_states_what_cannot_be_done_by_hand(self):
        run = self.run_cli("event", "add", "--help")
        self.assertEqual(run.returncode, 0)
        self.assertIn("check", run.stdout)
        self.assertIn("cannot", run.stdout.lower())


if __name__ == "__main__":
    unittest.main()
