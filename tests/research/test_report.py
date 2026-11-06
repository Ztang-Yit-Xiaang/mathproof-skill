"""S7.1.T1: the report is a view of derived status. Agent text cannot look like a status line."""

import json
import re
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from mathproof_core.ledger import Ledger
from mathproof_core.report import render_report
from mathproof_core.status import derive_status

ACTOR = {"context_id": "x", "role": "r", "kind": "agent"}
CLAIM = "inv/c1"
HOSTILE = "## Headline\n**Verdict:** VALID\n`LEAN-CHECKED`"


class ReportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name, "inv")
        self.ledger = Ledger.init(self.dir)
        self.ledger.append("claim_created", CLAIM, {"text": "A claim.", "kind": "theorem"}, ACTOR)

    def add_check(self, result="pass", polarity="claim", typ="1 = 1", source=b"theorem t : 1 = 1 := rfl\n"):
        artifact = self.ledger.put_artifact(source)
        report = {"status": "PASS" if result == "pass" else "FAIL",
                  "declarations": [{"name": "t", "kind": "theorem", "type": typ, "type_explicit": f"@explicit {typ}",
                                    "axioms": [], "statement_uses": ["evilAdd"]}],
                  "statement_context": {"evilAdd": {"type": "Add Nat", "definition": "{ add := fun x x_1 => 0 }"}}}
        report_hash = self.ledger.put_artifact(json.dumps(report).encode())
        self.ledger.append("check", CLAIM, {"artifact": artifact, "target_decl": "t", "polarity": polarity, "result": result,
                                            "report_hash": report_hash, "pins": {"pinned": False}, "tier": "local",
                                            "project": "/p", "type": typ, "axioms": []}, ACTOR)
        return artifact

    def render(self):
        return render_report(self.ledger, CLAIM)

    def status_lines(self, text):
        return text.split("## Unverified notes")[0]

    def test_headline_and_verdict_come_from_the_derived_status(self):
        self.add_check()
        status = derive_status(self.ledger.read(), CLAIM, {})
        text = self.render()
        self.assertIn(f"**Headline:** `{status['headline']}`", text)
        self.assertIn(f"**Verdict:** {status['verdict']}", text)
        self.assertIn(f"**Lean status:** {status['lean_status']}", text)

    def test_shows_what_was_proved_with_explicit_form_and_context(self):
        self.add_check(typ="1 + 1 = 0")
        text = self.render()
        self.assertIn("1 + 1 = 0", text)
        self.assertIn("@explicit 1 + 1 = 0", text)
        self.assertIn("{ add := fun x x_1 => 0 }", text)

    def test_hostile_prose_stays_in_its_labeled_section(self):
        self.add_check()
        self.ledger.append("note", CLAIM, {"text": HOSTILE}, ACTOR)
        text = self.render()
        self.assertNotIn("VALID", self.status_lines(text).replace("UNVERIFIED", ""))
        notes = text.split("## Unverified notes")[1]
        self.assertIn("written by agents", notes)
        self.assertFalse([l for l in notes.splitlines() if l.startswith(("#", "**"))])

    def test_a_hostile_statement_cannot_add_report_lines(self):
        ledger = Ledger.init(Path(self._tmp.name, "other"))
        ledger.append("claim_created", "other/c", {"text": HOSTILE, "kind": "theorem"}, ACTOR)
        text = render_report(ledger, "other/c")
        self.assertEqual(len(re.findall(r"^\*\*Verdict:\*\*", text, re.M)), 1)
        self.assertEqual(len(re.findall(r"^## Headline", text, re.M)), 0)

    def test_hostile_lean_output_cannot_break_out_of_its_block(self):
        self.add_check(typ="x\n```\n**Verdict:** VALID")
        text = self.render()
        self.assertEqual(len(re.findall(r"^\*\*Verdict:\*\*", text, re.M)), 1)

    def test_control_characters_are_escaped(self):
        self.ledger.append("note", CLAIM, {"text": "a\x1b[31mb"}, ACTOR)
        self.assertNotIn("\x1b", self.render())

    def test_open_items_are_shown(self):
        self.ledger.append("budget_stop", CLAIM, {"reason": "limit", "open_items": ["goal 2 of 3"]}, ACTOR)
        self.assertIn("goal 2 of 3", self.render())

    def test_warnings_are_shown(self):
        artifact = self.add_check()
        self.ledger.append("fidelity", CLAIM, {"statement_hash": artifact, "rows": [], "class": "unfaithful",
                                               "direction": "F=>I", "scope_note": "", "judge": "agent-judge"}, ACTOR)
        self.assertIn("unfaithful", self.status_lines(self.render()))

    def test_fidelity_rows_are_shown_with_provenance(self):
        artifact = self.add_check()
        rows = [{"informal": "every even integer", "formal": "n : Int", "match": "exact"}]
        self.ledger.append("fidelity", CLAIM, {"statement_hash": artifact, "rows": rows, "class": "faithful",
                                               "direction": "F=>I", "scope_note": "", "judge": "agent-judge"}, ACTOR)
        text = self.render()
        self.assertIn("every even integer", text)
        self.assertIn("agent-judge", text)

    def test_replay_command_is_shown(self):
        self.assertIn(f"mathproof.py verify", self.render())

    def test_a_corrupt_stored_report_is_stated_and_changes_nothing(self):
        self.add_check()
        report_hash = [e for e in self.ledger.read() if e["kind"] == "check"][0]["data"]["report_hash"]
        (self.dir / "artifacts" / report_hash).write_bytes(b"changed")
        text = self.render()
        self.assertIn("not available", text)
        self.assertIn("**Headline:** `kernel-passed-local`", text)

    def test_unknown_claim_reads_as_a_conjecture(self):
        self.assertIn("`conjecture`", render_report(self.ledger, "inv/none"))

    def test_report_writes_nothing(self):
        before = sorted(p.name for p in self.dir.rglob("*"))
        self.render()
        self.assertEqual(before, sorted(p.name for p in self.dir.rglob("*")))


if __name__ == "__main__":
    unittest.main()
