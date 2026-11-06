"""S1.2.T1: pure status derivation. In M0 no event sequence may reach VALID or INVALID."""

import random
import unittest

import _paths  # noqa: F401
from mathproof_core.events import STATUS_BEARING_KINDS
from mathproof_core.status import HEADLINES, compat, derive_status

A, B, C = "a" * 64, "b" * 64, "c" * 64
CLAIM = "inv/c1"


def ev(kind, data, claim=CLAIM, seq=0, ts="2026-11-05T00:00:00Z"):
    return {"seq": seq, "prev": "0" * 64, "ts": ts, "actor": {"context_id": "x", "role": "r", "kind": "agent"},
            "kind": kind, "claim": claim, "data": data}


def check(polarity="claim", result="pass", artifact=A, tier="local", target="main_theorem"):
    return ev("check", {"artifact": artifact, "target_decl": target, "polarity": polarity, "result": result,
                        "report_hash": C, "pins": {}, "tier": tier})


def fidelity(cls="faithful", direction="F=>I", artifact=A, judge="self-declared", rows=()):
    return ev("fidelity", {"statement_hash": artifact, "rows": list(rows), "class": cls, "direction": direction,
                           "scope_note": "", "judge": judge})


CREATED = ev("claim_created", {"text": "A claim.", "kind": "theorem"})
PROOF = ev("informal_proof", {"artifact": B, "author_context": "x"})
AUDIT_OK = ev("informal_audit", {"proof_hash": B, "result": "no-flaw", "auditor": "y"})
AUDIT_FLAW = ev("informal_audit", {"proof_hash": B, "result": "flaw", "auditor": "y"})
EXPERIMENT = ev("experiment", {"code_hash": A, "outcome": "completed", "violations": []})
VIOLATION = ev("experiment", {"code_hash": A, "outcome": "completed", "violations": [{"point_ref": "p", "magnitude": 1, "precision": "exact"}]})
BUDGET = ev("budget_stop", {"reason": "limit", "open_items": []})
ABANDON = ev("abandon", {"reason": "too weak"})
RETRACT = ev("retraction", {"target_event": 1, "reason": "oops"})
RESOLVE = ev("resolution", {"events": [1, 2], "reason": "typo", "signature": "forged"})


def derive(*events, env=None):
    return derive_status(list(events), CLAIM, env or {})


class HeadlineTests(unittest.TestCase):
    def assert_headline(self, want, *events):
        self.assertEqual(derive(CREATED, *events)["headline"], want)

    def test_precedence_table(self):
        table = [
            ("conjecture", []),
            ("evidence-only", [EXPERIMENT]),
            ("step-passed", [check("step")]),
            ("step-passed", [EXPERIMENT, check("step")]),
            ("argued", [PROOF]),
            ("argued", [PROOF, check("step")]),
            ("abandoned", [ABANDON]),
            ("abandoned", [PROOF, ABANDON]),
            ("unresolved", [BUDGET]),
            ("unresolved", [PROOF, EXPERIMENT, BUDGET]),
            ("unresolved", [ABANDON, BUDGET]),
            ("kernel-passed-local", [check()]),
            ("kernel-passed-local", [check("negation")]),
            ("kernel-passed-local", [check(), BUDGET]),
            ("kernel-passed-local", [check(), ABANDON]),
            ("kernel-passed-local", [PROOF, check()]),
            ("conflict", [check("claim"), check("negation", artifact=B)]),
            ("conflict", [check("claim"), check("negation", artifact=B), BUDGET]),
        ]
        for want, events in table:
            with self.subTest(want=want, kinds=[e["kind"] for e in events]):
                self.assert_headline(want, *events)

    def test_a_failed_check_alone_raises_nothing(self):
        self.assert_headline("conjecture", check(result="fail"))
        self.assertEqual(derive(check(result="fail"))["axes"]["kernel"], "failed")

    def test_a_failed_negation_check_does_not_conflict(self):
        self.assert_headline("kernel-passed-local", check("claim"), check("negation", result="fail", artifact=B))

    def test_a_failure_of_the_same_artifact_beats_its_pass(self):
        for events in ([check(), check(result="fail")], [check(result="fail"), check()]):
            status = derive(*events)
            self.assertEqual(status["axes"]["kernel"], "failed")
            self.assertEqual(status["headline"], "conjecture")

    def test_a_new_artifact_can_pass_after_an_old_one_failed(self):
        self.assert_headline("kernel-passed-local", check(result="fail", artifact=B), check())

    def test_step_check_cannot_reach_kernel_passed(self):
        self.assertEqual(derive(check("step"))["axes"]["kernel"], "none")
        self.assertNotEqual(derive(check("step"))["headline"], "kernel-passed-local")

    def test_step_checks_never_conflict(self):
        self.assert_headline("kernel-passed-local", check("claim"), check("step", artifact=B))

    def test_retraction_and_resolution_are_unsigned_in_m0(self):
        self.assert_headline("kernel-passed-local", check(), RETRACT)
        self.assert_headline("conflict", check("claim"), check("negation", artifact=B), RESOLVE)

    def test_other_claims_events_are_ignored(self):
        other = dict(check(), claim="inv/other")
        self.assert_headline("conjecture", other)

    def test_unknown_kinds_change_nothing(self):
        self.assertEqual(derive(ev("note", {"text": "VALID"}), CREATED), derive(CREATED))
        self.assert_headline("conjecture", ev("verdict_is_valid", {"verdict": "VALID"}))

    def test_open_vocabulary_events_do_not_count_as_ignored(self):
        self.assertEqual(derive(CREATED, ev("note", {"status": "VALID"}))["ignored_events"], 0)

    def test_invalid_events_are_ignored_and_reported(self):
        status = derive(CREATED, ev("check", {"artifact": A}))
        self.assertEqual(status["headline"], "conjecture")
        self.assertEqual(status["ignored_events"], 1)

    def test_malformed_events_cannot_crash_derivation(self):
        bad = [ev("check", {"artifact": [], "target_decl": "t", "polarity": "claim", "result": "pass",
                            "report_hash": C, "pins": {}, "tier": "local"}),
               ev("experiment", {"code_hash": A, "outcome": "completed", "violations": 5}),
               ev("fidelity", {"statement_hash": {}, "rows": [], "class": "faithful", "direction": "F=>I", "judge": "none"}),
               ev("informal_proof", {"artifact": [], "author_context": "x"})]
        status = derive(CREATED, *bad)
        self.assertEqual(status["headline"], "conjecture")
        self.assertEqual(status["ignored_events"], 4)

    def test_a_second_statement_for_a_claim_is_flagged(self):
        second = ev("claim_created", {"text": "A weaker claim.", "kind": "theorem"})
        status = derive(CREATED, second, check())
        self.assertEqual(status["statement"], "A claim.")
        self.assertTrue(any("statement" in w for w in status["warnings"]))
        self.assertEqual(status["headline"], "kernel-passed-local")

    def test_non_event_input_cannot_crash_derivation(self):
        self.assertEqual(derive_status([5, None, "x"], CLAIM, {})["headline"], "conjecture")
        self.assertEqual(derive_status([], CLAIM, None)["headline"], "conjecture")

    def test_contradictory_results_are_flagged(self):
        status = derive(check("claim"), check("negation", artifact=B), check("negation", result="fail", artifact=B))
        self.assertEqual(status["headline"], "kernel-passed-local")
        self.assertTrue(any("contradict" in w for w in status["warnings"]))

    def test_unverified_counterevidence_beside_a_pass_is_flagged(self):
        for event in (VIOLATION, ev("certificate", {"certificate": {}})):
            status = derive(check(), event)
            self.assertEqual(status["headline"], "kernel-passed-local")
            self.assertTrue(any("counter" in w for w in status["warnings"]), event["kind"])

    def test_counterevidence_supporting_a_refutation_is_not_flagged(self):
        self.assertFalse(derive(check("negation"), VIOLATION)["warnings"])

    def test_budget_stop_shows_over_abandon_on_the_search_axis(self):
        self.assertEqual(derive(BUDGET, ABANDON)["axes"]["search"], "budget-stopped")

    def test_versions_are_reported(self):
        status = derive(CREATED, env={"checker_version": "2.3"})
        self.assertEqual(status["checker_version"], "2.3")
        self.assertTrue(status["derivation_version"])

    def test_timestamps_are_never_read(self):
        early = derive(CREATED, dict(check(), ts="1999-01-01T00:00:00Z"))
        late = derive(CREATED, dict(check(), ts="2999-01-01T00:00:00Z"))
        self.assertEqual(early, late)

    def test_derivation_is_pure(self):
        events = [CREATED, check(), fidelity()]
        snapshot = repr(events)
        self.assertEqual(derive_status(events, CLAIM, {}), derive_status(events, CLAIM, {}))
        self.assertEqual(repr(events), snapshot)


class AxisTests(unittest.TestCase):
    def test_informal_axis(self):
        self.assertEqual(derive(CREATED)["axes"]["informal"], "none")
        self.assertEqual(derive(PROOF)["axes"]["informal"], "drafted")
        self.assertEqual(derive(PROOF, AUDIT_OK)["axes"]["informal"], "self-audited")

    def test_unsigned_audit_never_counts_as_signed_or_rejected(self):
        self.assertEqual(derive(PROOF, AUDIT_FLAW)["axes"]["informal"], "self-audited")
        self.assertTrue(any("flaw" in w for w in derive(PROOF, AUDIT_FLAW)["warnings"]))

    def test_audit_of_another_proof_is_ignored(self):
        other = ev("informal_audit", {"proof_hash": A, "result": "no-flaw", "auditor": "y"})
        self.assertEqual(derive(PROOF, other)["axes"]["informal"], "drafted")

    def test_computational_axis_counts_runs_and_candidates(self):
        axis = derive(EXPERIMENT, VIOLATION)["axes"]["computational"]
        self.assertEqual((axis["runs"], axis["candidates"], axis["artifacts"]), (2, 1, [A]))

    def test_search_axis(self):
        self.assertEqual(derive(CREATED)["axes"]["search"], "active")
        self.assertEqual(derive(BUDGET)["axes"]["search"], "budget-stopped")
        self.assertEqual(derive(ABANDON)["axes"]["search"], "abandoned")


class VerdictCapTests(unittest.TestCase):
    """Rule 1: only the authoritative tier plus a human signature can give VALID or INVALID."""

    def test_nothing_an_agent_writes_gets_above_unverified(self):
        attempts = [
            [check(tier="authoritative"), fidelity(judge="signed-human")],
            [check("negation", tier="authoritative"), fidelity(direction="I=>F", judge="signed-human")],
            [check(), fidelity(judge="repo-label"), PROOF, AUDIT_OK],
        ]
        for events in attempts:
            status = derive(CREATED, *events)
            self.assertEqual(status["headline"], "kernel-passed-local")
            self.assertEqual(status["axes"]["kernel"], "passed-local")
            self.assertEqual(status["verdict"], "UNVERIFIED")

    def test_env_cannot_promote_in_m0(self):
        status = derive(CREATED, check(), env={"judged": True, "authoritative": True, "tier": "authoritative"})
        self.assertEqual(status["headline"], "kernel-passed-local")

    def test_mislabeled_target_or_polarity_stays_unverified(self):
        for event in (check(target="trivial_lemma"), check("negation", target="one_equals_one")):
            self.assertEqual(derive(CREATED, event)["verdict"], "UNVERIFIED")

    def test_random_sequences_never_exceed_the_m0_cap(self):
        allowed = {"conflict", "kernel-passed-local", "unresolved", "abandoned", "argued", "step-passed",
                   "evidence-only", "conjecture"}
        pool = [CREATED, PROOF, AUDIT_OK, AUDIT_FLAW, EXPERIMENT, VIOLATION, BUDGET, ABANDON, RETRACT, RESOLVE,
                check(), check("negation", artifact=B), check("step", artifact=C), check(result="fail"),
                check(tier="authoritative"), fidelity(), fidelity(judge="signed-human"), fidelity("unfaithful"),
                fidelity("instance"), fidelity(direction="I=>F", artifact=B), ev("note", {}),
                ev("statement_frozen", {"artifact": A}), ev("witness", {"goal": "g", "artifact": A}),
                ev("waiver", {"what": "v", "reason": "r", "signature": "s"}),
                ev("challenge", {"target": "t", "result": "r", "runner_context": "c"}),
                ev("certificate", {"certificate": {}})]
        rng = random.Random(20261105)
        for _ in range(5000):
            events = [rng.choice(pool) for _ in range(rng.randint(0, 12))]
            status = derive_status(events, CLAIM, {})
            self.assertIn(status["headline"], allowed)
            self.assertNotIn(status["verdict"], ("VALID", "INVALID", "CONDITIONALLY VALID"))
            self.assertIn(status["axes"]["kernel"], ("none", "failed", "passed-local"))

    def test_numeric_events_alone_never_exceed_evidence_only(self):
        rng = random.Random(7)
        for _ in range(500):
            events = [rng.choice([EXPERIMENT, VIOLATION]) for _ in range(rng.randint(1, 20))]
            self.assertEqual(derive(*events)["headline"], "evidence-only")


class CompatTests(unittest.TestCase):
    def test_compat_is_total_over_every_headline(self):
        self.assertEqual(set(HEADLINES), {"conflict", "judge-rejected", "refuted-certified", "established",
                                          "established(partial)", "conditional", "judged-unreviewed",
                                          "kernel-passed-local", "refutation-candidate", "unresolved", "abandoned",
                                          "argued", "step-passed", "evidence-only", "conjecture"})
        for headline in HEADLINES:
            for detail in ({}, {"attempted": True}, {"kernel_passed": True}, {"scope": "n > 0"}):
                verdict, lean = compat(headline, **detail)
                self.assertTrue(verdict and lean, headline)

    def test_unknown_headline_is_an_error_not_a_verdict(self):
        with self.assertRaises(ValueError):
            compat("VALID")

    def test_contract_rows(self):
        rows = [
            (("established",), {}, ("VALID", "LEAN-CHECKED")),
            (("established(partial)",), {"scope": "n > 0"}, ("VALID (n > 0)", "LEAN-CHECKED (partial: n > 0)")),
            (("refuted-certified",), {}, ("INVALID", "LEAN-CHECKED")),
            (("refuted-certified",), {"scope": "n > 0"}, ("INVALID within scope (n > 0)", "LEAN-CHECKED (partial: n > 0)")),
            (("conflict",), {"kernel_passed": True}, ("UNVERIFIED, flagged", "KERNEL-PASSED (conflict)")),
            (("conditional",), {"cost_audit_passed": True, "scope": "n > 0"}, ("CONDITIONALLY VALID", "LEAN-CHECKED (partial: n > 0)")),
            (("conditional",), {"citation": "Thm 1"}, ("CONDITIONALLY VALID (Thm 1)", "LEAN-CHECKED (partial: conditional on Thm 1)")),
            (("conditional",), {}, ("UNVERIFIED", "KERNEL-PASSED (authoritative; blocked: cost audit)")),
            (("judged-unreviewed",), {"missing": ("fidelity",)}, ("UNVERIFIED", "KERNEL-PASSED (authoritative; missing: fidelity)")),
            (("kernel-passed-local",), {"label": "claim"}, ("UNVERIFIED", "KERNEL-PASSED (local; claim)")),
            (("conflict",), {}, ("UNVERIFIED, flagged", "LEAN-FAILED")),
            (("judge-rejected",), {}, ("UNVERIFIED", "LEAN-FAILED")),
            (("step-passed",), {}, ("UNVERIFIED", "KERNEL-PASSED (step only)")),
            (("argued",), {}, ("INCOMPLETE", "NOT FORMALIZED")),
            (("argued",), {"attempted": True}, ("INCOMPLETE", "LEAN-FAILED")),
            (("argued",), {"signed_audit": True}, ("UNVERIFIED, labeled \"informal proof, human-audited, not machine-confirmed\"", "NOT FORMALIZED")),
            (("conjecture",), {}, ("UNVERIFIED", "NOT FORMALIZED")),
            (("evidence-only",), {"attempted": True}, ("UNVERIFIED", "LEAN-FAILED")),
            (("unresolved",), {}, ("UNVERIFIED", "NOT FORMALIZED")),
            (("abandoned",), {}, ("UNVERIFIED", "NOT FORMALIZED")),
            (("refutation-candidate",), {"method": "interval"}, ("UNVERIFIED", "NOT FORMALIZED (interval)")),
        ]
        for args, kwargs, want in rows:
            with self.subTest(args=args, kwargs=kwargs):
                self.assertEqual(compat(*args, **kwargs), want)

    def test_local_kernel_pass_is_labeled_with_polarity_and_fidelity(self):
        status = derive(CREATED, check("negation"), fidelity(direction="I=>F"))
        self.assertEqual(status["verdict"], "UNVERIFIED")
        self.assertEqual(status["lean_status"], "KERNEL-PASSED (local; negation, fidelity: faithful, self-declared)")
        self.assertEqual(derive(check())["lean_status"], "KERNEL-PASSED (local; claim, fidelity: none)")

    def test_attempt_shows_in_lean_status(self):
        self.assertEqual(derive(PROOF)["lean_status"], "NOT FORMALIZED")
        self.assertEqual(derive(PROOF, check(result="fail"))["lean_status"], "LEAN-FAILED")
        self.assertEqual(derive(PROOF, check("step", result="fail"))["lean_status"], "LEAN-FAILED")


class ContractTests(unittest.TestCase):
    def test_kinds_with_m0_effect_exist_in_the_event_table(self):
        for kind in ("claim_created", "check", "fidelity", "informal_proof", "informal_audit", "experiment",
                     "budget_stop", "abandon", "retraction"):
            self.assertIn(kind, STATUS_BEARING_KINDS)


if __name__ == "__main__":
    unittest.main()
