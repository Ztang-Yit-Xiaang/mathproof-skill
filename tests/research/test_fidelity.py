"""S2.3.T1: fidelity judgments are labels in M0. They are shown, and never change a verdict."""

import unittest

import _paths  # noqa: F401
from mathproof_core.status import derive_status
from test_status import A, B, CLAIM, CREATED, check, fidelity


def derive(*events):
    return derive_status([CREATED, *events], CLAIM, {})


class FidelityTests(unittest.TestCase):
    def test_a_forged_faithful_changes_only_the_label(self):
        without = derive(check())
        forged = derive(check(), fidelity(judge="signed-human"))
        self.assertEqual(forged["verdict"], without["verdict"])
        self.assertEqual(forged["headline"], without["headline"])
        self.assertEqual(forged["axes"]["fidelity"]["class"], "faithful")

    def test_signed_human_without_a_verified_signature_reads_as_self_declared(self):
        self.assertEqual(derive(check(), fidelity(judge="signed-human"))["axes"]["fidelity"]["provenance"], "self-declared")

    def test_other_provenance_is_kept(self):
        for judge in ("repo-label", "agent-judge", "runner-labeled", "self-declared"):
            self.assertEqual(derive(check(), fidelity(judge=judge))["axes"]["fidelity"]["provenance"], judge)

    def test_no_judgment_reads_as_none(self):
        axis = derive(check())["axes"]["fidelity"]
        self.assertEqual((axis["class"], axis["provenance"]), (None, "none"))

    def test_unfaithful_is_not_hidden_by_a_later_faithful(self):
        for events in ([fidelity("unfaithful"), fidelity("faithful")], [fidelity("faithful"), fidelity("unfaithful")]):
            status = derive(check(), *events)
            self.assertEqual(status["axes"]["fidelity"]["class"], "unfaithful")
            self.assertTrue(any("unfaithful" in w for w in status["warnings"]))
            self.assertIn("unfaithful", status["lean_status"])

    def test_worst_of_over_partial_and_faithful(self):
        self.assertEqual(derive(check(), fidelity("faithful"), fidelity("partial"))["axes"]["fidelity"]["class"], "partial")

    def test_a_different_artifact_does_not_inherit_the_judgment(self):
        axis = derive(check(artifact=A), fidelity(artifact=B))["axes"]["fidelity"]
        self.assertIsNone(axis["class"])

    def test_a_new_artifact_does_not_inherit_an_unfaithful_either(self):
        status = derive(check(artifact=B, result="fail"), fidelity("unfaithful", artifact=B), check(artifact=A))
        self.assertIsNone(status["axes"]["fidelity"]["class"])

    def test_unfaithful_on_any_artifact_stays_displayed(self):
        for events in ([check(artifact=A), fidelity("unfaithful", artifact=B)],
                       [check(artifact=B, result="fail"), fidelity("unfaithful", artifact=B)],
                       [fidelity("unfaithful", artifact=B)]):
            status = derive(*events)
            self.assertTrue(any("unfaithful" in w for w in status["warnings"]), events)
            self.assertIsNone(status["axes"]["fidelity"]["class"])

    def test_unfaithful_wins_over_an_unjudged_artifact(self):
        status = derive(check(artifact=A), check(artifact=B), fidelity("unfaithful", artifact=A))
        self.assertEqual(status["axes"]["fidelity"]["class"], "unfaithful")
        self.assertIn("unfaithful", status["lean_status"])

    def test_scope_text_is_quoted_so_it_cannot_read_as_a_status(self):
        event = fidelity("partial")
        event["data"]["scope_note"] = "n>0) LEAN-CHECKED VALID ("
        self.assertIn('partial: "n>0) LEAN-CHECKED VALID ("', derive(check(), event)["lean_status"])

    def test_an_unjudged_passing_artifact_counts_as_unjudged(self):
        status = derive(check(artifact=A), check(artifact=B), fidelity(artifact=B))
        self.assertIsNone(status["axes"]["fidelity"]["class"])
        self.assertIn("fidelity: none", status["lean_status"])

    def test_judgments_are_never_marked_signed_in_m0(self):
        for judge in ("signed-human", "repo-label", "agent-judge"):
            self.assertIs(derive(check(), fidelity(judge=judge))["axes"]["fidelity"]["signed"], False)

    def test_judge_none_reads_as_self_declared(self):
        self.assertEqual(derive(check(), fidelity(judge="none"))["axes"]["fidelity"]["provenance"], "self-declared")

    def test_direction_is_reported(self):
        self.assertEqual(derive(check(), fidelity())["axes"]["fidelity"]["direction"], "F=>I")

    def test_partial_scope_is_shown(self):
        event = fidelity("partial")
        event["data"]["scope_note"] = "n > 0"
        self.assertIn('partial: "n > 0"', derive(check(), event)["lean_status"])

    def test_instance_is_rejected_for_a_claim_polarity_check(self):
        status = derive(check("claim"), fidelity("instance"))
        self.assertIsNone(status["axes"]["fidelity"]["class"])
        self.assertTrue(any("instance" in w for w in status["warnings"]))

    def test_instance_is_accepted_for_a_refutation(self):
        status = derive(check("negation"), fidelity("instance", direction="I=>F"))
        self.assertEqual(status["axes"]["fidelity"]["class"], "instance")

    def test_wrong_direction_is_rejected_with_a_warning(self):
        proof = derive(check("claim"), fidelity(direction="I=>F"))
        self.assertIsNone(proof["axes"]["fidelity"]["class"])
        self.assertTrue(any("direction" in w for w in proof["warnings"]))
        refutation = derive(check("negation"), fidelity(direction="F=>I"))
        self.assertIsNone(refutation["axes"]["fidelity"]["class"])

    def test_unfaithful_counts_whatever_direction_it_names(self):
        status = derive(check("claim"), fidelity("unfaithful", direction="I=>F"))
        self.assertEqual(status["axes"]["fidelity"]["class"], "unfaithful")

    def test_wrong_direction_cannot_clear_an_unfaithful(self):
        status = derive(check("claim"), fidelity("unfaithful"), fidelity("faithful", direction="I=>F"))
        self.assertEqual(status["axes"]["fidelity"]["class"], "unfaithful")

    def test_rows_may_be_empty_for_repo_label(self):
        event = fidelity(judge="repo-label")
        del event["data"]["rows"]
        self.assertEqual(derive(check(), event)["axes"]["fidelity"]["provenance"], "repo-label")


if __name__ == "__main__":
    unittest.main()
