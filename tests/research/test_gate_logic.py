"""S1.3.T1 and S1.3.T2: the decisions the gate and replay make from a report. No Lean is run."""

import unittest

import _paths  # noqa: F401
from mathproof_core.gate import EnvironmentFailure, normalized, outcome
from mathproof_core.replay import compare_rerun

DECL = {"name": "ns.main_theorem", "kind": "theorem", "type": "1 = 1", "axioms": ["propext"]}
CHECKER = {"version": "2.3", "sha256_checker": "a", "sha256_driver": "b"}


def report(status="PASS", declarations=(DECL,), **extra):
    return {"status": status, "problems": [], "declarations": list(declarations), "checker": CHECKER,
            "file": "/tmp/x", "stages": {"compile": {"seconds": 1.0}}, **extra}


class OutcomeTests(unittest.TestCase):
    def test_pass_needs_the_exact_name(self):
        self.assertEqual(outcome(report(), "ns.main_theorem")[0], "pass")
        for wrong in ("main_theorem", "s.main_theorem", "ns.main_theorem2", "NS.main_theorem"):
            result, reasons = outcome(report(), wrong)
            self.assertEqual(result, "fail", wrong)
            self.assertTrue(any("exact" in r for r in reasons))

    def test_a_failed_report_is_a_failure(self):
        self.assertEqual(outcome(report("FAIL"), "ns.main_theorem")[0], "fail")

    def test_only_the_word_pass_counts(self):
        for status in ("pass", "PASSED", "", None):
            self.assertEqual(outcome(report(status), "ns.main_theorem")[0], "fail", status)

    def test_a_definition_cannot_be_the_target(self):
        definition = {**DECL, "kind": "other"}
        self.assertEqual(outcome(report(declarations=[definition]), "ns.main_theorem")[0], "fail")

    def test_a_nonstandard_axiom_on_the_target_fails_even_in_a_passing_report(self):
        bad = {**DECL, "axioms": ["sorryAx"]}
        self.assertEqual(outcome(report(declarations=[bad]), "ns.main_theorem")[0], "fail")

    def test_an_environment_report_is_not_a_result(self):
        with self.assertRaises(EnvironmentFailure):
            outcome(report("FAIL", environment_error=True), "ns.main_theorem")


class CompareTests(unittest.TestCase):
    def event(self, result="pass", **data):
        return {"result": result, "target_decl": "ns.main_theorem", "type": "1 = 1", "axioms": ["propext"], **data}

    def test_timing_and_paths_never_differ(self):
        fresh = report(file="/other/path", stages={"compile": {"seconds": 99.0}})
        self.assertEqual(compare_rerun(self.event(), report(), fresh), [])

    def test_order_of_declarations_and_axioms_never_differs(self):
        one = {**DECL, "axioms": ["propext", "Quot.sound"]}
        two = {**DECL, "axioms": ["Quot.sound", "propext"]}
        other = {**DECL, "name": "ns.other"}
        self.assertEqual(normalized(report(declarations=[one, other])), normalized(report(declarations=[other, two])))

    def test_a_different_result_type_or_axiom_is_a_difference(self):
        changes = [report("FAIL"), report(declarations=[{**DECL, "type": "2 = 2"}]),
                   report(declarations=[{**DECL, "axioms": ["sorryAx"]}])]
        for fresh in changes:
            self.assertTrue(compare_rerun(self.event(), report(), fresh))

    def test_a_stored_report_alone_differing_is_a_difference(self):
        stored = report(declarations=[{**DECL, "type": "2 = 2"}])
        self.assertEqual(compare_rerun(self.event(), stored, report()), ["stored report differs from the re-run"])

    def test_event_axioms_alone_differing_is_a_difference(self):
        self.assertEqual(compare_rerun(self.event(axioms=["sorryAx"]), report(), report()),
                         ["event's axioms differ from the re-run"])

    def test_a_forged_pass_is_a_difference_even_with_a_matching_stored_report(self):
        failed = report("FAIL")
        self.assertTrue(compare_rerun(self.event("pass"), failed, failed))

    def test_a_stored_report_that_disagrees_with_the_event_is_a_difference(self):
        self.assertTrue(compare_rerun(self.event(type="9 = 9"), report(), report()))

    def test_a_changed_checker_is_reported_as_such(self):
        fresh = report(checker={**CHECKER, "sha256_checker": "changed"})
        differences = compare_rerun(self.event(), report(), fresh)
        self.assertTrue(any("checker" in d for d in differences))


if __name__ == "__main__":
    unittest.main()
