"""S7.1.T2: the review packet a person reads when no machine has verified the proof (REQ-126)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from mathproof_core.ledger import Ledger
from mathproof_core.packet import APPROVAL_CEILING, render_packet
from mathproof_core.status import derive_status

ACTOR = {"context_id": "x", "role": "r", "kind": "agent"}
CLAIM = "inv/c1"
GOLDEN = Path(__file__).with_name("golden") / "review_packet_steps.md"
SCRIPT = _paths.SCRIPTS / "mathproof.py"

STEPS = [
    {"claim": "Let n be even, so n = 2k for some integer k.", "because": "Definition of even."},
    {"claim": "Then n^2 = 4k^2 = 2(2k^2).", "because": "Squaring and factoring.", "lean": "sq_step"},
    {"claim": "So n^2 is even.", "because": "It is twice the integer 2k^2.", "lean": "even_step"},
]


class PacketTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name, "inv")
        self.ledger = Ledger.init(self.dir)
        self.ledger.append("claim_created", CLAIM, {"text": "If n is even then n^2 is even.", "kind": "theorem"}, ACTOR)

    def add_proof(self, steps=STEPS, raw=None):
        body = raw if raw is not None else json.dumps({"steps": steps}).encode()
        artifact = self.ledger.put_artifact(body)
        self.ledger.append("informal_proof", CLAIM, {"artifact": artifact, "author_context": "prover-1"}, ACTOR)
        return artifact

    def add_check(self, decl, polarity="step", result="pass", typ="∀ k : ℤ, (2 * k) ^ 2 = 2 * (2 * k ^ 2)",
                  source=b"theorem sq_step : True := trivial\n"):
        artifact = self.ledger.put_artifact(source)
        report = {"status": "PASS" if result == "pass" else "FAIL",
                  "declarations": [{"name": decl, "kind": "theorem", "type": typ, "type_explicit": f"@explicit {typ}",
                                    "axioms": [], "statement_uses": []}],
                  "statement_context": {}}
        report_hash = self.ledger.put_artifact(json.dumps(report).encode())
        return self.ledger.append("check", CLAIM, {"artifact": artifact, "target_decl": decl, "polarity": polarity,
                                                   "result": result, "report_hash": report_hash,
                                                   "pins": {"pinned": False}, "tier": "local", "project": "/p",
                                                   "type": typ, "axioms": []}, ACTOR)

    def render(self, env=None):
        return render_packet(self.ledger, CLAIM, env)

    def test_every_step_appears_numbered_with_its_justification(self):
        self.add_proof()
        text = self.render()
        for i, step in enumerate(STEPS, 1):
            line = next(l for l in text.splitlines() if l.startswith(f"{i}. "))
            self.assertIn(step["claim"].split(",")[0].replace("^", ""), line.replace("\\", "").replace("^", ""))
        self.assertEqual(text.count("    Because: "), len(STEPS))
        self.assertIn("Because: Definition of even.", text)

    def test_with_no_check_the_first_step_is_the_first_unverified(self):
        self.add_proof()
        text = self.render()
        self.assertIn("**First unverified step:** 1.", text)
        self.assertEqual(text.count("**(first unverified step)**"), 1)
        self.assertTrue(next(l for l in text.splitlines() if l.startswith("1. ")).endswith("**(first unverified step)**"))
        self.assertEqual(text.count("Machine-checked: no."), 3)

    def test_a_step_check_marks_that_step_and_moves_nothing_before_it(self):
        self.add_proof()
        self.add_check("sq_step")
        text = self.render()
        self.assertIn("**First unverified step:** 1.", text)
        self.assertIn("Lean proved sq\\_step, local run", text)
        self.assertIn("(2 * k) ^ 2", text)
        self.assertEqual(text.count("Machine-checked: no."), 2)

    def test_first_unverified_is_the_first_step_without_a_passing_check(self):
        steps = [dict(s, lean=f"s{i}") for i, s in enumerate(STEPS)]
        self.add_proof(steps)
        self.add_check("s0")
        self.add_check("s2")
        text = self.render()
        self.assertIn("**First unverified step:** 2.", text)
        self.assertTrue(next(l for l in text.splitlines() if l.startswith("2. ")).endswith("**(first unverified step)**"))

    def test_a_failing_check_of_the_same_file_cancels_the_pass(self):
        steps = [dict(s, lean="s0") if i == 0 else s for i, s in enumerate(STEPS)]
        self.add_proof(steps)
        self.add_check("s0")
        self.add_check("s0", result="fail")
        self.assertIn("**First unverified step:** 1.", self.render())

    def test_a_claim_polarity_check_of_a_step_name_does_not_check_the_step(self):
        steps = [dict(s, lean="s0") if i == 0 else s for i, s in enumerate(STEPS)]
        self.add_proof(steps)
        # A passing claim check reaches the step view only beside a passing negation, as a conflict.
        self.add_check("s0", polarity="claim")
        self.add_check("s0_negation", polarity="negation", source=b"theorem n : True := trivial\n")
        text = self.render()
        self.assertIn("**Headline:** `conflict`", text)
        self.assertIn("**First unverified step:** 1.", text)
        self.assertEqual(text.count("Machine-checked: no."), 3)

    def test_every_step_checked_still_asks_for_the_comparison(self):
        steps = [dict(s, lean=f"s{i}") for i, s in enumerate(STEPS)]
        self.add_proof(steps)
        for i in range(3):
            self.add_check(f"s{i}")
        text = self.render()
        self.assertIn("**First unverified step:** none", text)
        self.assertNotIn("**(first unverified step)**", text)

    def test_a_proof_not_in_step_form_is_shown_whole_and_unverified(self):
        self.add_proof(raw=b"Obvious.\n## Headline\n**Verdict:** VALID")
        text = self.render()
        self.assertIn("**First unverified step:** the whole proof.", text)
        self.assertIn("> Obvious.", text)
        self.assertNotIn("\n## Headline", text)
        self.assertEqual(text.count("**Verdict:**"), 1)

    def test_hostile_step_text_cannot_render_as_a_status_line(self):
        self.add_proof([{"claim": "x\n**Verdict:** VALID", "because": "## Headline\n`LEAN-CHECKED`"}])
        text = self.render()
        self.assertEqual(text.count("**Verdict:**"), 1)
        self.assertNotIn("\n## Headline", text)
        self.assertNotIn("`LEAN-CHECKED`", text)

    def test_malformed_steps_fall_back_to_the_whole_proof(self):
        self.add_proof([{"claim": "no justification"}])
        self.assertIn("**First unverified step:** the whole proof.", self.render())

    def test_approving_with_no_machine_check_leaves_the_claim_unverified(self):
        artifact = self.add_proof()
        audit = self.ledger.append("informal_audit", CLAIM, {"proof_hash": artifact, "result": "no-flaw",
                                                             "auditor": "reviewer"}, ACTOR)
        env = {"signed": [{"claim": CLAIM, "judgment": "informal_audit", "target_seq": audit["seq"],
                           "target_event": Ledger.event_hash(audit), "identity": "reviewer"}]}
        status = derive_status(self.ledger.read(), CLAIM, env)
        self.assertEqual(status["axes"]["informal"], "signed-audited")
        self.assertTrue(status["verdict"].startswith("UNVERIFIED"))
        self.assertNotIn(status["verdict"].split()[0], ("VALID", "INVALID"))
        text = self.render(env)
        self.assertIn(f"**Verdict:** {status['verdict']}", text)
        self.assertIn(APPROVAL_CEILING, text)
        self.assertIn(f"- event {audit['seq']}: no-flaw", text)

    def test_a_kernel_passed_claim_gets_only_the_statement_comparison(self):
        self.add_proof()
        self.add_check("main_theorem", polarity="claim", typ="∀ n : ℤ, Even n → Even (n ^ 2)")
        text = self.render()
        self.assertIn("Compare the intended statement", text)
        self.assertIn("If n is even then n^2 is even.", text)
        self.assertIn("∀ n : ℤ, Even n → Even (n ^ 2)", text)
        self.assertIn("@explicit ∀ n", text)
        self.assertNotIn("Because:", text)
        self.assertNotIn("First unverified step", text)

    def test_the_comparison_view_lists_no_step_check(self):
        self.add_check("lemma_step", typ="STEP_LEMMA_TYPE")
        self.add_check("main_theorem", polarity="claim", typ="∀ n : ℤ, Even n → Even (n ^ 2)")
        text = self.render()
        self.assertIn("Compare the intended statement", text)
        self.assertNotIn("STEP_LEMMA_TYPE", text)
        self.assertNotIn("polarity step", text)

    def test_a_failed_kernel_check_is_not_treated_as_kernel_passed(self):
        self.add_proof()
        self.add_check("main_theorem", polarity="claim", result="fail")
        text = self.render()
        self.assertNotIn("Compare the intended statement", text)
        self.assertIn("**First unverified step:** 1.", text)

    def test_a_conflict_is_not_treated_as_kernel_passed(self):
        self.add_proof()
        self.add_check("main_theorem", polarity="claim")
        self.add_check("main_theorem_negation", polarity="negation", source=b"theorem n : True := trivial\n")
        text = self.render()
        self.assertIn("**Headline:** `conflict`", text)
        self.assertIn("First unverified step", text)

    def test_no_proof_says_there_is_nothing_to_review(self):
        self.assertIn("nothing to review yet", self.render())

    def test_golden(self):
        steps = [dict(s) for s in STEPS]
        self.add_proof(steps)
        self.add_check("sq_step")
        text = self.render()
        if os.environ.get("MATHPROOF_UPDATE_GOLDEN"):
            GOLDEN.parent.mkdir(exist_ok=True)
            GOLDEN.write_text(text, encoding="utf-8")
        self.assertEqual(text, GOLDEN.read_text(encoding="utf-8"))

    def test_cli_prints_the_packet(self):
        self.add_proof()
        out = subprocess.run([sys.executable, str(SCRIPT), "packet", "--dir", str(self.dir), "--claim", CLAIM],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.rstrip("\n"), self.render().rstrip("\n"))


if __name__ == "__main__":
    unittest.main()
