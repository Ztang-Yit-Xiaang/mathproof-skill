"""S1.1.T1: IF-event-v1 envelope and the closed table of status-bearing kinds."""

import json
import unittest

from _paths import SCRIPTS
from mathproof_core import events

HASH = "a" * 64
EXAMPLES = {
    "claim_created": {"text": "Every even integer squared is even.", "kind": "theorem"},
    "assumption": {"text": "n is an integer", "standing": "given", "origin": "statement", "change": "add"},
    "check": {"artifact": HASH, "target_decl": "main_theorem", "polarity": "claim", "result": "pass",
              "report_hash": HASH, "pins": {"toolchain": "v4.32.0"}, "tier": "local"},
    "fidelity": {"statement_hash": HASH, "rows": [], "class": "faithful", "direction": "F=>I",
                 "scope_note": "", "judge": "repo-label"},
    "informal_proof": {"artifact": HASH, "author_context": "ctx1"},
    "informal_audit": {"proof_hash": HASH, "result": "no-flaw", "auditor": "ctx2"},
    "experiment": {"code_hash": HASH, "env_lock_hash": HASH, "seed": 1, "params": {}, "limits": {},
                   "outcome": "completed", "results_hash": HASH, "violations": [], "diagnostics": {}, "tags": []},
    "budget_stop": {"reason": "attempt limit", "open_items": ["goal 2"]},
    "abandon": {"reason": "statement is too weak"},
    "resolution": {"events": [1, 2], "reason": "typo", "signature": "sig"},
    "retraction": {"target_event": 3, "reason": "wrong artifact"},
    "statement_frozen": {"artifact": HASH},
    "witness": {"goal": "exists x, h x", "artifact": HASH},
    "waiver": {"what": "vacuity", "reason": "see note", "signature": "sig"},
    "audit": {"assumption": "h", "cost_axes": {}},
    "challenge": {"target": "main_theorem", "result": "no flaw", "runner_context": "ctx3"},
    "certificate": {"certificate": {}},
    "dependency": {"from": "a/b", "to": "a/c", "source_hash": HASH},
    "bridge": {"card": "c", "hypothesis": "h", "match": "matched"},
}


def event(kind="claim_created", data=None, **overrides):
    base = {"seq": 1, "prev": HASH, "ts": "2026-11-05T00:00:00Z",
            "actor": {"context_id": "ctx1", "role": "prover", "kind": "agent"},
            "kind": kind, "claim": "inv/claim-1", "data": EXAMPLES.get(kind, {}) if data is None else data}
    base.update(overrides)
    return base


class EventTests(unittest.TestCase):
    def test_every_kind_in_the_contract_table_has_a_valid_example(self):
        self.assertEqual(set(EXAMPLES), set(events.STATUS_BEARING_KINDS))
        for kind in EXAMPLES:
            self.assertEqual(events.validate_event(event(kind)), [], kind)
            self.assertTrue(events.is_status_bearing(kind))

    def test_missing_envelope_fields_are_rejected(self):
        for field in ("seq", "prev", "ts", "actor", "kind", "claim", "data"):
            bad = event()
            del bad[field]
            self.assertTrue(events.validate_event(bad), field)

    def test_malformed_values_are_rejected(self):
        for claim in ("no-slash", "a/b/c", "/b", "a/", "A B/c", ""):
            self.assertTrue(events.validate_event(event(claim=claim)), claim)
        for prev in ("short", "g" * 64, "A" * 64, None):
            self.assertTrue(events.validate_event(event(prev=prev)), prev)
        for seq in (-1, "1", 1.5, True):
            self.assertTrue(events.validate_event(event(seq=seq)), seq)
        self.assertTrue(events.validate_event(event(actor={"role": "prover"})))
        self.assertTrue(events.validate_event(event(data=[])))

    def test_claim_may_be_null(self):
        self.assertEqual(events.validate_event(event(kind="note", claim=None, data={})), [])

    def test_unknown_kind_validates_and_bears_no_status(self):
        self.assertEqual(events.validate_event(event(kind="my_new_kind", data={"x": 1})), [])
        self.assertFalse(events.is_status_bearing("my_new_kind"))

    def test_a_status_field_is_rejected_anywhere_at_the_top(self):
        self.assertTrue(events.validate_event(event(data={**EXAMPLES["abandon"], "status": "VALID"}, kind="abandon")))
        self.assertTrue(events.validate_event(event(kind="note", data={"status": "VALID"})))
        self.assertTrue(events.validate_event(event(status="VALID")))

    def test_status_is_rejected_for_every_kind_with_no_exception(self):
        for kind in EXAMPLES:
            self.assertTrue(events.validate_event(event(kind, {**EXAMPLES[kind], "status": "VALID"})), kind)

    def test_hash_fields_must_be_hashes(self):
        fields = {"check": ["artifact", "report_hash"], "fidelity": ["statement_hash"], "informal_proof": ["artifact"],
                  "informal_audit": ["proof_hash"], "experiment": ["code_hash"], "statement_frozen": ["artifact"]}
        for kind, names in fields.items():
            for name in names:
                for bad in ([], {}, 1, "short", None):
                    self.assertTrue(events.validate_event(event(kind, {**EXAMPLES[kind], name: bad})), (kind, name, bad))

    def test_list_fields_must_be_lists(self):
        self.assertTrue(events.validate_event(event("experiment", {**EXAMPLES["experiment"], "violations": 5})))
        self.assertTrue(events.validate_event(event("fidelity", {**EXAMPLES["fidelity"], "rows": "x"})))
        self.assertTrue(events.validate_event(event("budget_stop", {"reason": "r", "open_items": "x"})))

    def test_a_trailing_newline_does_not_pass_as_valid(self):
        self.assertTrue(events.validate_event(event("check", {**EXAMPLES["check"], "artifact": HASH + "\n"})))
        self.assertTrue(events.validate_event(event(claim="inv/c1\n")))
        self.assertTrue(events.validate_event(event(prev=HASH + "\n")))

    def test_path_like_claim_ids_are_rejected(self):
        for claim in ("../..", "./x", "a/..", ".a/b"):
            self.assertTrue(events.validate_event(event(claim=claim)), claim)

    def test_unhashable_values_are_errors_not_crashes(self):
        for kind, field in (("check", "polarity"), ("check", "result"), ("fidelity", "class"), ("fidelity", "direction"),
                            ("fidelity", "judge"), ("experiment", "outcome"), ("informal_audit", "result")):
            for bad in ([], {}):
                self.assertTrue(events.validate_event(event(kind, {**EXAMPLES[kind], field: bad})), (kind, field))

    def test_unstorable_values_are_errors_not_crashes(self):
        self.assertTrue(events.validate_event(event("note", {"text": "\ud800"})))
        deep = {}
        for _ in range(200000):
            deep = {"x": deep}
        self.assertTrue(events.validate_event(event("note", {"deep": deep})))

    def test_a_statement_must_be_non_empty_text(self):
        for text in ("", 5, None, []):
            self.assertTrue(events.validate_event(event("claim_created", {"text": text, "kind": "theorem"})), text)

    def test_scope_note_must_be_one_line_of_text(self):
        for bad in ("a\nb", "a\rb", 5, [], "x" * 501):
            self.assertTrue(events.validate_event(event("fidelity", {**EXAMPLES["fidelity"], "scope_note": bad})), bad)

    def test_a_claim_needs_a_claim_id(self):
        self.assertTrue(events.validate_event(event(claim=None)))

    def test_schema_matches_the_validator_on_claim_ids(self):
        schema = json.loads((SCRIPTS / "mathproof_core" / "schema" / "event-v1.json").read_text(encoding="utf-8"))
        text = json.dumps(schema["properties"]["claim"])
        self.assertNotIn("[a-z0-9._-]+/", text)
        self.assertIn("hash", schema["properties"])

    def test_informal_audit_result_is_closed(self):
        self.assertTrue(events.validate_event(event("informal_audit", {**EXAMPLES["informal_audit"], "result": "fine"})))
        self.assertEqual(events.validate_event(event("informal_audit", {**EXAMPLES["informal_audit"], "result": "flaw"})), [])

    def test_check_requires_exact_target_and_known_polarity(self):
        for field in ("target_decl", "polarity", "artifact", "result"):
            data = dict(EXAMPLES["check"])
            del data[field]
            self.assertTrue(events.validate_event(event("check", data)), field)
        self.assertTrue(events.validate_event(event("check", {**EXAMPLES["check"], "polarity": "both"})))
        self.assertTrue(events.validate_event(event("check", {**EXAMPLES["check"], "result": "maybe"})))
        self.assertTrue(events.validate_event(event("check", {**EXAMPLES["check"], "target_decl": ""})))

    def test_fidelity_values_are_closed(self):
        self.assertTrue(events.validate_event(event("fidelity", {**EXAMPLES["fidelity"], "class": "great"})))
        self.assertTrue(events.validate_event(event("fidelity", {**EXAMPLES["fidelity"], "direction": "sideways"})))
        self.assertTrue(events.validate_event(event("fidelity", {**EXAMPLES["fidelity"], "judge": "me"})))
        rows_missing = {k: v for k, v in EXAMPLES["fidelity"].items() if k != "rows"}
        self.assertEqual(events.validate_event(event("fidelity", rows_missing)), [])
        self.assertTrue(events.validate_event(event("fidelity", {**rows_missing, "judge": "self-declared"})))

    def test_schema_file_is_valid_json_describing_the_envelope(self):
        schema = json.loads((SCRIPTS / "mathproof_core" / "schema" / "event-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(set(schema["required"]), {"seq", "prev", "ts", "actor", "kind", "claim", "data"})


if __name__ == "__main__":
    unittest.main()
