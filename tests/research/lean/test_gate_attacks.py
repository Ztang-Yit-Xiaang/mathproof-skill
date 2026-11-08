"""S8.1.T2 (BM-001): attacks run through check, status, report, and replay. Needs Lean.

Passing shows these known attacks fail. It does not show resistance to unknown ones.
"""

import unittest
from pathlib import Path

from _lean_support import ACTOR, FIXTURES, REPO_PROJECT, temp_dir
from mathproof_core.gate import record_check
from mathproof_core.ledger import Ledger
from mathproof_core.replay import verify_investigation
from mathproof_core.report import render_report
from mathproof_core.status import derive_status

CLAIM = "inv/c1"
STRONG = ("VALID", "INVALID", "CONDITIONALLY VALID")

# Every failing fixture, with the declaration it claims to prove.
BYPASS_TARGETS = {
    "fail_auto_implicit.lean": "main_theorem", "fail_axiom.lean": "t", "fail_core_shadow.lean": "main_theorem",
    "fail_error.lean": "t", "fail_exit_only.lean": "main_theorem", "fail_forged_audit.lean": "main_theorem",
    "fail_guarded_error.lean": "main_theorem", "fail_hidden_sorry.lean": "t",
    "fail_import_hides_bypass.lean": "main_theorem", "fail_internal_axiom.lean": "main_theorem",
    "fail_kernel_skip.lean": "main_theorem", "fail_midline_axiom.lean": "main_theorem",
    "fail_missing_required.lean": "main_theorem", "fail_module_header.lean": "main_theorem",
    "fail_native_decide.lean": "t", "fail_prelude_spoof.lean": "main_theorem",
    "fail_require_definition.lean": "main_theorem", "fail_sorry.lean": "t",
}


class AttackTests(unittest.TestCase):
    def setUp(self):
        self._tmp = temp_dir()
        self.addCleanup(self._tmp.cleanup)
        self.ledger = Ledger.init(Path(self._tmp.name, "inv"))
        self.ledger.append("claim_created", CLAIM, {"text": "A claim.", "kind": "theorem"}, ACTOR)

    def status(self):
        return derive_status(self.ledger.read(), CLAIM, {})

    def assert_not_strong(self):
        status = self.status()
        self.assertNotIn(status["verdict"], STRONG)
        report = render_report(self.ledger, CLAIM)
        self.assertRegex(report, r"\*\*Verdict:\*\* (UNVERIFIED|INCOMPLETE)")
        return status

    def test_the_table_covers_every_failing_fixture(self):
        self.assertEqual(set(BYPASS_TARGETS), {p.name for p in FIXTURES.glob("fail_*.lean")})

    def test_each_bypass_fixture_ends_with_kernel_failed(self):
        for fixture, target in BYPASS_TARGETS.items():
            with self.subTest(fixture):
                event = record_check(self.ledger, CLAIM, FIXTURES / fixture, target, "claim", REPO_PROJECT)
                self.assertEqual(event["data"]["result"], "fail")
                # The axis stays failed or none after every attack, not merely below a cap.
                self.assertIn(self.assert_not_strong()["axes"]["kernel"], ("failed", "none"))

    def test_replay_confirms_a_recorded_bypass_failed(self):
        record_check(self.ledger, CLAIM, FIXTURES / "fail_kernel_skip.lean", "main_theorem", "claim", REPO_PROJECT)
        self.assertTrue(verify_investigation(self.ledger.directory)["ok"])

    def test_forging_a_pass_for_a_bypass_fixture_is_caught_by_replay(self):
        source = (FIXTURES / "fail_kernel_skip.lean").read_bytes()
        artifact = self.ledger.put_artifact(source)
        report = self.ledger.put_artifact(b'{"status": "PASS", "declarations": []}')
        self.ledger.append("check", CLAIM, {"artifact": artifact, "target_decl": "main_theorem", "polarity": "claim",
                                            "result": "pass", "report_hash": report, "pins": {}, "tier": "authoritative",
                                            "project": str(REPO_PROJECT)}, ACTOR)
        status = self.status()
        self.assertEqual(status["headline"], "kernel-passed-local")
        self.assertEqual(status["verdict"], "UNVERIFIED")
        self.assertFalse(verify_investigation(self.ledger.directory)["ok"])

    def test_statements_an_agent_can_write_do_not_promote(self):
        proof = self.ledger.put_artifact(b"informal proof")
        artifact = self.ledger.put_artifact(b"theorem t : True := trivial")
        for kind, data in [
            ("informal_proof", {"artifact": proof, "author_context": "x"}),
            ("informal_audit", {"proof_hash": proof, "result": "no-flaw", "auditor": "A Professor", "signature": "signed"}),
            ("experiment", {"code_hash": proof, "outcome": "completed", "violations": []}),
            ("fidelity", {"statement_hash": artifact, "rows": [], "class": "faithful", "direction": "F=>I",
                          "judge": "signed-human", "signature": "signed"}),
            ("statement_frozen", {"artifact": artifact, "signature": "signed"}),
            ("witness", {"goal": "g", "artifact": artifact}),
            ("waiver", {"what": "v", "reason": "r", "signature": "signed"}),
            ("challenge", {"target": "t", "result": "no flaw", "runner_context": "c"}),
            ("resolution", {"events": [1], "reason": "r", "signature": "signed"}),
        ]:
            self.ledger.append(kind, CLAIM, data, ACTOR)
            self.assert_not_strong()
        self.assertEqual(self.status()["headline"], "argued")

    def test_a_judgment_copied_from_another_claim_does_nothing(self):
        artifact = self.ledger.put_artifact(b"x")
        self.ledger.append("fidelity", "inv/other", {"statement_hash": artifact, "rows": [], "class": "faithful",
                                                     "direction": "F=>I", "judge": "signed-human"}, ACTOR)
        self.assertIsNone(self.status()["axes"]["fidelity"]["class"])

    def test_numeric_evidence_alone_stays_evidence(self):
        code = self.ledger.put_artifact(b"x")
        for _ in range(3):
            self.ledger.append("experiment", CLAIM, {"code_hash": code, "outcome": "completed", "violations": []}, ACTOR)
        self.assertEqual(self.assert_not_strong()["headline"], "evidence-only")


if __name__ == "__main__":
    unittest.main()
