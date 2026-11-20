"""Exhaustive unittest for claim status derivation invariants (SPEC.md)."""

from __future__ import annotations

import itertools
import os
import sys
import unittest
from typing import Any

import _paths  # noqa: F401
from mathproof_core.ledger import Ledger
from mathproof_core.status import HEADLINES, derive_status
from mathproof_core.events import validate_event
import status_invariants as si

CLAIM_ID = "inv/c1"
OTHER_CLAIM_ID = "inv/other"

H_STMT = "1" * 64
H_ART_CLAIM = "2" * 64
H_ART_NEG = "3" * 64
H_ART_STEP = "4" * 64
H_REP = "5" * 64
H_PROOF = "6" * 64
H_EXP_OK = "7" * 64
H_EXP_VIOL = "8" * 64
H_CHAL = "9" * 64
H_BOGUS = "f" * 64


def make_event(seq: int, kind: str, data: dict[str, Any], claim: str = CLAIM_ID) -> dict[str, Any]:
    """Build a valid IF-event-v1 event dict at index seq."""
    ev = {
        "seq": seq,
        "prev": "0" * 64,
        "ts": "2026-11-05T00:00:00Z",
        "actor": {"context_id": "ctx", "role": "prover", "kind": "agent"},
        "kind": kind,
        "claim": claim,
        "data": data,
    }
    errs = validate_event(ev)
    assert not errs, f"Invalid template event {kind}: {errs}"
    return ev


# Pool of 15 representative event builders (after claim_created at seq 0).
# Each entry is (name, builder(prior_events, seq) -> event_dict).
EVENT_POOL: tuple[tuple[str, Any], ...] = (
    (
        "check_claim_pass",
        lambda prior, seq: make_event(
            seq,
            "check",
            {
                "artifact": H_ART_CLAIM,
                "target_decl": "main_theorem",
                "polarity": "claim",
                "result": "pass",
                "report_hash": H_REP,
                "pins": {},
                "tier": "local",
            },
        ),
    ),
    (
        "check_claim_fail",
        lambda prior, seq: make_event(
            seq,
            "check",
            {
                "artifact": H_ART_CLAIM,
                "target_decl": "main_theorem",
                "polarity": "claim",
                "result": "fail",
                "report_hash": H_REP,
                "pins": {},
                "tier": "local",
            },
        ),
    ),
    (
        "check_neg_pass",
        lambda prior, seq: make_event(
            seq,
            "check",
            {
                "artifact": H_ART_NEG,
                "target_decl": "main_theorem_negation",
                "polarity": "negation",
                "result": "pass",
                "report_hash": H_REP,
                "pins": {},
                "tier": "local",
            },
        ),
    ),
    (
        "check_neg_fail",
        lambda prior, seq: make_event(
            seq,
            "check",
            {
                "artifact": H_ART_NEG,
                "target_decl": "main_theorem_negation",
                "polarity": "negation",
                "result": "fail",
                "report_hash": H_REP,
                "pins": {},
                "tier": "local",
            },
        ),
    ),
    (
        "check_step_pass",
        lambda prior, seq: make_event(
            seq,
            "check",
            {
                "artifact": H_ART_STEP,
                "target_decl": "lemma_step",
                "polarity": "step",
                "result": "pass",
                "report_hash": H_REP,
                "pins": {},
                "tier": "local",
            },
        ),
    ),
    (
        "fidelity_self_faithful",
        lambda prior, seq: make_event(
            seq,
            "fidelity",
            {
                "statement_hash": H_STMT,
                "class": "faithful",
                "direction": "F=>I",
                "judge": "self-declared",
                "rows": [{"informal": "claim", "formal": "main_theorem", "match": "exact"}],
                "scope_note": "self-declared faithful",
            },
        ),
    ),
    (
        "fidelity_signable_neg",
        lambda prior, seq: make_event(
            seq,
            "fidelity",
            {
                "statement_hash": H_STMT,
                "class": "faithful",
                "direction": "I=>F",
                "judge": "self-declared",
                "rows": [{"informal": "claim", "formal": "main_theorem_negation", "match": "exact"}],
                "scope_note": "signable fidelity for negation",
            },
        ),
    ),
    (
        "informal_proof",
        lambda prior, seq: make_event(
            seq,
            "informal_proof",
            {"artifact": H_PROOF, "author_context": "prover-1"},
        ),
    ),
    (
        "informal_audit_no_flaw",
        lambda prior, seq: make_event(
            seq,
            "informal_audit",
            {"proof_hash": H_PROOF, "result": "no-flaw", "auditor": "reviewer-1"},
        ),
    ),
    (
        "informal_audit_flaw",
        lambda prior, seq: make_event(
            seq,
            "informal_audit",
            {"proof_hash": H_PROOF, "result": "flaw", "auditor": "reviewer-1"},
        ),
    ),
    (
        "experiment_no_violations",
        lambda prior, seq: make_event(
            seq,
            "experiment",
            {"code_hash": H_EXP_OK, "outcome": "completed", "violations": []},
        ),
    ),
    (
        "experiment_with_violations",
        lambda prior, seq: make_event(
            seq,
            "experiment",
            {"code_hash": H_EXP_VIOL, "outcome": "completed", "violations": ["n=7"]},
        ),
    ),
    (
        "budget_stop",
        lambda prior, seq: make_event(
            seq,
            "budget_stop",
            {"reason": "timeout", "open_items": ["case_2"]},
        ),
    ),
    (
        "abandon",
        lambda prior, seq: make_event(
            seq,
            "abandon",
            {"reason": "dead_end"},
        ),
    ),
    (
        "statement_frozen",
        lambda prior, seq: make_event(
            seq,
            "statement_frozen",
            {"artifact": H_STMT},
        ),
    ),
    (
        "retraction_earlier",
        lambda prior, seq: make_event(
            seq,
            "retraction",
            {
                "target_event": Ledger.event_hash(prior[-1]) if prior else H_BOGUS,
                "reason": "retract previous event",
            },
        ),
    ),
)

SIGNABLE_JUDGMENTS_BY_KIND: dict[str, str] = {
    "statement_frozen": "statement",
    "fidelity": "fidelity",
    "informal_audit": "informal_audit",
    "waiver": "waiver",
    "retraction": "retraction",
}


def build_event_sequences(smoke: bool) -> list[list[dict[str, Any]]]:
    """Enumerate event sequences of length 0..3 (or at most 1 event when smoke=True)."""
    e0 = make_event(0, "claim_created", {"text": "The informal claim.", "kind": "theorem"})
    sequences: list[list[dict[str, Any]]] = [
        [],
        [e0],
    ]
    if smoke:
        # At most 1 event from the pool (both standalone 1-event and 1 event after claim_created).
        for _, builder in EVENT_POOL:
            sequences.append([builder([], 0)])
            sequences.append([e0, builder([e0], 1)])
        return sequences

    # Full mode: 0..3 events drawn from the pool, with claim_created first (total length 0..3,
    # plus 3 pool events after claim_created up to length 4).
    for k in (1, 2):
        for combo in itertools.product(EVENT_POOL, repeat=k):
            evs = [e0]
            for _, builder in combo:
                evs.append(builder(evs, len(evs)))
            sequences.append(evs)

    # Also include 3-event sequences drawn across distinct pool items after claim_created
    for combo in itertools.combinations(EVENT_POOL, 3):
        evs = [e0]
        for _, builder in combo:
            evs.append(builder(evs, len(evs)))
        sequences.append(evs)

    return sequences


def build_env_variants(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build env variants for a given event sequence:
    - empty env
    - judged pass/fail for each check event in events
    - signatures on subsets of signable events in events
    """
    check_events = [ev for ev in events if ev.get("kind") == "check"]
    signable_events = [
        ev for ev in events if ev.get("kind") in SIGNABLE_JUDGMENTS_BY_KIND
    ]

    # For each check event: None (not judged), 'pass', or 'fail'
    judged_choices_per_check: list[list[dict[str, Any] | None]] = []
    for ev in check_events:
        data = ev["data"]
        base = {
            "claim": ev["claim"],
            "seq": ev["seq"],
            "artifact": data["artifact"],
            "target_decl": data["target_decl"],
            "polarity": data["polarity"],
            "challenge_hash": H_CHAL,
        }
        judged_choices_per_check.append(
            [
                None,
                {**base, "result": "pass"},
                {**base, "result": "fail"},
            ]
        )

    # For each signable event: unsigned (None) or signed
    sig_choices_per_event: list[list[dict[str, Any] | None]] = []
    for ev in signable_events:
        judgment = SIGNABLE_JUDGMENTS_BY_KIND[ev["kind"]]
        sig_choices_per_event.append(
            [
                None,
                {
                    "claim": ev["claim"],
                    "judgment": judgment,
                    "target_seq": ev["seq"],
                    "target_event": Ledger.event_hash(ev),
                    "identity": "reviewer@example.com",
                },
            ]
        )

    envs: list[dict[str, Any]] = []
    for j_tuple in itertools.product(*judged_choices_per_check):
        j_list = [j for j in j_tuple if j is not None]
        for s_tuple in itertools.product(*sig_choices_per_event):
            s_list = [s for s in s_tuple if s is not None]
            env: dict[str, Any] = {}
            if j_list:
                env["judged"] = j_list
            if s_list:
                env["signed"] = s_list
            envs.append(env)
    return envs


def make_bogus_env_entries(events: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """Construct bogus judged and signed entries (wrong claim, bad seq, mismatched hash)."""
    target_ev = events[-1] if events else make_event(0, "claim_created", {"text": "t", "kind": "k"})
    t_seq = target_ev["seq"]
    return [
        (
            "judged",
            {
                "claim": OTHER_CLAIM_ID,
                "seq": t_seq,
                "artifact": H_ART_CLAIM,
                "target_decl": "main_theorem",
                "polarity": "claim",
                "challenge_hash": H_CHAL,
                "result": "pass",
            },
        ),
        (
            "judged",
            {
                "claim": CLAIM_ID,
                "seq": 999,
                "artifact": H_ART_CLAIM,
                "target_decl": "main_theorem",
                "polarity": "claim",
                "challenge_hash": H_CHAL,
                "result": "pass",
            },
        ),
        (
            "judged",
            {
                "claim": CLAIM_ID,
                "seq": t_seq,
                "artifact": H_BOGUS,
                "target_decl": "main_theorem",
                "polarity": "claim",
                "challenge_hash": H_CHAL,
                "result": "pass",
            },
        ),
        (
            "signed",
            {
                "claim": OTHER_CLAIM_ID,
                "judgment": "statement",
                "target_seq": t_seq,
                "target_event": Ledger.event_hash(target_ev),
                "identity": "reviewer@example.com",
            },
        ),
        (
            "signed",
            {
                "claim": CLAIM_ID,
                "judgment": "statement",
                "target_seq": 999,
                "target_event": Ledger.event_hash(target_ev),
                "identity": "reviewer@example.com",
            },
        ),
        (
            "signed",
            {
                "claim": CLAIM_ID,
                "judgment": "fidelity",
                "target_seq": t_seq,
                "target_event": H_BOGUS,
                "identity": "reviewer@example.com",
            },
        ),
    ]


class TestStatusExhaustive(unittest.TestCase):
    """Exhaustive invariant test suite over sequences of 0-3 events and env variants."""

    cases: list[tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]] = []
    bogus_pairs: list[tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    unsigned_ret_pairs: list[tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    signed_ret_pairs: list[tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    remove_env_pairs: list[tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]] = []

    @classmethod
    def setUpClass(cls) -> None:
        smoke = os.environ.get("STATUS_INV_SMOKE") == "1"
        sequences = build_event_sequences(smoke=smoke)

        cls.cases = []
        cls.bogus_pairs = []
        cls.unsigned_ret_pairs = []
        cls.signed_ret_pairs = []
        cls.remove_env_pairs = []

        # Cache derivations keyed by (seq_idx, j_key, s_key) for fast env removal comparison
        for events in sequences:
            envs = build_env_variants(events)
            env_results: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for env in envs:
                res = derive_status(events, CLAIM_ID, env)
                cls.cases.append((events, env, res))
                env_results.append((env, res))

            # Bogus env relational cases (sample on empty and maximal env for this sequence)
            sample_envs = [envs[0]] + ([envs[-1]] if len(envs) > 1 else [])
            for base_env, base_res in [(e, derive_status(events, CLAIM_ID, e)) for e in sample_envs]:
                for kind_key, bogus_entry in make_bogus_env_entries(events):
                    aug_env = {
                        "judged": list(base_env.get("judged", [])),
                        "signed": list(base_env.get("signed", [])),
                    }
                    aug_env[kind_key].append(bogus_entry)
                    aug_res = derive_status(events, CLAIM_ID, aug_env)
                    cls.bogus_pairs.append((events, aug_env, base_res, aug_res))

            # Retraction relational cases (unsigned and signed retraction of the last event)
            if events:
                target_ev = events[-1]
                ret_ev = make_event(
                    len(events),
                    "retraction",
                    {"target_event": Ledger.event_hash(target_ev), "reason": "test_retract"},
                )
                evs_with_ret = events + [ret_ev]
                ret_sig = {
                    "claim": CLAIM_ID,
                    "judgment": "retraction",
                    "target_seq": ret_ev["seq"],
                    "target_event": Ledger.event_hash(ret_ev),
                    "identity": "reviewer@example.com",
                }
                for base_env, base_res in env_results:
                    uret_res = derive_status(evs_with_ret, CLAIM_ID, base_env)
                    cls.unsigned_ret_pairs.append((evs_with_ret, base_env, base_res, uret_res))

                    sret_env = {
                        "judged": list(base_env.get("judged", [])),
                        "signed": list(base_env.get("signed", [])) + [ret_sig],
                    }
                    sret_res = derive_status(evs_with_ret, CLAIM_ID, sret_env)
                    cls.signed_ret_pairs.append((evs_with_ret, sret_env, base_res, sret_res))

            # Removing supporting env entry relational cases
            for full_env, full_res in env_results:
                for kind_key in ("judged", "signed"):
                    entries = full_env.get(kind_key, [])
                    for idx, entry in enumerate(entries):
                        if not si.is_supporting_env_entry(kind_key, entry, events, CLAIM_ID):
                            continue
                        reduced_env = {
                            k: list(v) for k, v in full_env.items() if k in ("judged", "signed")
                        }
                        reduced_env[kind_key] = entries[:idx] + entries[idx + 1 :]
                        reduced_res = derive_status(events, CLAIM_ID, reduced_env)
                        cls.remove_env_pairs.append((events, full_env, full_res, reduced_res))

        total_checked = (
            len(cls.cases)
            + len(cls.bogus_pairs)
            + len(cls.unsigned_ret_pairs)
            + len(cls.signed_ret_pairs)
            + len(cls.remove_env_pairs)
        )
        print(
            f"\n[test_status_exhaustive] smoke={smoke} sequences={len(sequences)} "
            f"base_cases={len(cls.cases)} total_cases_checked={total_checked}",
            flush=True,
        )

    def _assert_single_invariant(self, inv_fn: Any) -> None:
        for events, env, res in self.cases:
            err = inv_fn(events, env, res)
            if err is not None:
                self.fail(
                    f"{inv_fn.__name__} failed: {err}\n"
                    f"events={events!r}\nenv={env!r}\nresult={res!r}"
                )

    def test_inv_totality_and_shape(self) -> None:
        self._assert_single_invariant(si.inv_totality_and_shape)

    def test_inv_strong_verdict_requires_judged_and_signatures(self) -> None:
        self._assert_single_invariant(si.inv_strong_verdict_requires_judged_and_signatures)

    def test_inv_no_above_local_without_judged(self) -> None:
        self._assert_single_invariant(si.inv_no_above_local_without_judged)

    def test_inv_non_kernel_events_never_raise_above_local(self) -> None:
        self._assert_single_invariant(si.inv_non_kernel_events_never_raise_above_local)

    def test_inv_experiments_cannot_raise_above_evidence(self) -> None:
        self._assert_single_invariant(si.inv_experiments_cannot_raise_above_evidence)

    def test_inv_self_declared_fidelity_stays_unverified(self) -> None:
        self._assert_single_invariant(si.inv_self_declared_fidelity_stays_unverified)

    def test_inv_signed_audit_without_judged_pass_stays_unverified(self) -> None:
        self._assert_single_invariant(si.inv_signed_audit_without_judged_pass_stays_unverified)

    def test_inv_budget_stop_never_refuted(self) -> None:
        self._assert_single_invariant(si.inv_budget_stop_never_refuted)

    def test_inv_conflict_when_claim_and_negation_both_pass(self) -> None:
        self._assert_single_invariant(si.inv_conflict_when_claim_and_negation_both_pass)

    def test_inv_local_pass_with_judge_fail_is_rejected(self) -> None:
        self._assert_single_invariant(si.inv_local_pass_with_judge_fail_is_rejected)

    def test_inv_missing_lists_unmet_gates(self) -> None:
        self._assert_single_invariant(si.inv_missing_lists_unmet_gates)
        reached = [(e, r) for e, _, r in self.cases if r.get("headline") == "judged-unreviewed"]
        self.assertTrue(reached, "the enumeration never reaches judged-unreviewed")
        self.assertTrue(any("statement signature" in r["missing"] for _, r in reached))
        self.assertTrue(any(any(ev["kind"] == "statement_frozen" for ev in e) for e, _ in reached),
                        "the enumeration never reaches judged-unreviewed with a frozen statement")

    def test_inv_determinism(self) -> None:
        # Check determinism on a subset / all base cases
        for events, env, res in self.cases[:250]:
            again = derive_status(events, CLAIM_ID, env)
            err = si.inv_determinism(res, again)
            if err is not None:
                self.fail(f"inv_determinism failed: {err}\nevents={events!r}\nenv={env!r}")

    def test_inv_bogus_env_changes_nothing(self) -> None:
        for events, aug_env, before, after in self.bogus_pairs:
            err = si.inv_bogus_env_changes_nothing(before, after)
            if err is not None:
                self.fail(
                    f"inv_bogus_env_changes_nothing failed: {err}\n"
                    f"events={events!r}\naug_env={aug_env!r}\nbefore={before!r}\nafter={after!r}"
                )

    def test_inv_unsigned_retraction_changes_nothing(self) -> None:
        for events, env, before, after in self.unsigned_ret_pairs:
            err = si.inv_unsigned_retraction_changes_nothing(before, after)
            if err is not None:
                self.fail(
                    f"inv_unsigned_retraction_changes_nothing failed: {err}\n"
                    f"events={events!r}\nenv={env!r}\nbefore={before!r}\nafter={after!r}"
                )

    def test_inv_retraction_never_raises_status(self) -> None:
        for events, env, before, after in self.unsigned_ret_pairs + self.signed_ret_pairs:
            err = si.inv_retraction_never_raises_status(before, after)
            if err is not None:
                self.fail(
                    f"inv_retraction_never_raises_status failed: {err}\n"
                    f"events={events!r}\nenv={env!r}\nbefore={before!r}\nafter={after!r}"
                )

    def test_inv_removing_env_never_raises_status(self) -> None:
        for events, env, before, after in self.remove_env_pairs:
            err = si.inv_removing_env_never_raises_status(before, after)
            if err is not None:
                self.fail(
                    f"inv_removing_env_never_raises_status failed: {err}\n"
                    f"events={events!r}\nenv={env!r}\nbefore={before!r}\nafter={after!r}"
                )


if __name__ == "__main__":
    unittest.main()
