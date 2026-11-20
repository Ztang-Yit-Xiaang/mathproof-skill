"""Requirement-derived invariants for claim status derivation.

Derived strictly from SPEC.md, investigate.md, and events.py without reading status.py.

Authority Ranking of HEADLINES (justified from investigate.md and SPEC.md):
---------------------------------------------------------------------------
From investigate.md ("What the status can say", "Authoritative judgment",
"Signing judgments", "Choosing the polarity", "Experiments") and SPEC.md
(REQ-002, REQ-009, REQ-125, plan objective):

- Tier 0 (Adverse / contradictory / rejected states: rank 0):
  * 'conflict': both a proof ('claim') and a refutation ('negation') pass.
    Per SPEC.md plan objective, conflict is never a verdict; per investigate.md
    ("Signing judgments"), a retraction cannot remove one side of a conflict to
    make the claim look stronger.
  * 'judge-rejected': a local passing check failed the authoritative judge
    (REQ-125, investigate.md "What the status can say"). Per investigate.md
    ("Signing judgments"), a judge-rejected check cannot be retracted to make
    the claim look stronger.

- Tier 1 (Unproved baseline / stopped search / bare claim: rank 1):
  * 'abandoned': search explicitly abandoned ('abandon' event).
  * 'unresolved': search stopped ('budget_stop') without proof or certified
    counterexample (REQ-009: unresolved, never refuted or false).
  * 'conjecture': initial claim state with no positive evidence or proof.

- Tier 2 (Computational evidence only: rank 2):
  * 'evidence-only': numerical experiment completed without elevating claim
    status (REQ-002; investigate.md "Experiments": "A numerical experiment is
    evidence, never a proof or a refutation: it can't raise a claim's status").
  * 'refutation-candidate': numerical experiment reported counterexample
    candidates ("violations"), which show up only as candidates to examine
    (REQ-002; investigate.md "Experiments").

- Tier 3 (Partial formal step only: rank 3):
  * 'step-passed': a local check with polarity 'step' passed (investigate.md
    "Choosing the polarity": "A step never counts as proving or refuting the
    claim").

- Tier 4 (Informal argument only: rank 4):
  * 'argued': an informal proof (with or without a human-signed 'no-flaw'
    informal_audit) without a passing formal claim/negation check (REQ-125:
    "A signed audit of an informal proof without an authoritative pass stays
    UNVERIFIED"; investigate.md "Signing judgments").

- Tier 5 (Local formal kernel check ceiling: rank 5):
  * 'kernel-passed-local': ceiling for any local check ('claim' or 'negation'
    polarity) without an authoritative judge report (investigate.md "What the
    status can say": "A local check gives at most kernel-passed-local";
    REQ-125: "A local pass with self-declared fidelity is UNVERIFIED").

- Tier 6 (Authoritative judge pass without full certification gates: rank 6):
  * 'judged-unreviewed': ceiling for an authoritative judge pass before all
    signatures and later gates (assumption audit, vacuity witness) are met
    (investigate.md "What the status can say" & "Signing judgments": "An
    authoritative judge report, described below, gives at most
    judged-unreviewed").

- Tier 7 (Certified / gated authoritative outcomes: rank 7..8):
  * 'conditional' (rank 7): authoritative pass conditioned on unverified
    assumptions or partial gates.
  * 'established(partial)' (rank 7): authoritative pass with partial/instance
    fidelity.
  * 'established' (rank 8): fully certified authoritative proof with signed
    statement, signed faithful fidelity, and all required gates (REQ-125).
  * 'refuted-certified' (rank 8): fully certified authoritative refutation
    with signed statement, signed fidelity, and all required gates (REQ-125).
"""

from __future__ import annotations

import sys
from typing import Any, Callable

import _paths  # noqa: F401
from mathproof_core.ledger import Ledger
from mathproof_core.status import HEADLINES
from mathproof_core.events import validate_event


HEADLINE_AUTHORITY_RANK: dict[str, int] = {
    "conflict": 0,
    "judge-rejected": 0,
    "abandoned": 1,
    "unresolved": 1,
    "conjecture": 1,
    "evidence-only": 2,
    "refutation-candidate": 2,
    "step-passed": 3,
    "argued": 4,
    "kernel-passed-local": 5,
    "judged-unreviewed": 6,
    "conditional": 7,
    "established(partial)": 7,
    "established": 8,
    "refuted-certified": 8,
}

HEADLINES_ABOVE_LOCAL: frozenset[str] = frozenset(
    h for h, r in HEADLINE_AUTHORITY_RANK.items() if r > HEADLINE_AUTHORITY_RANK["kernel-passed-local"]
)

CERTIFIED_HEADLINES: frozenset[str] = frozenset(
    {"established", "established(partial)", "refuted-certified"}
)


def headline_rank(headline: str) -> int:
    """Return the integer authority rank of a headline in HEADLINES."""
    return HEADLINE_AUTHORITY_RANK[headline]


def is_strong_verdict(verdict: Any) -> bool:
    """Return True if verdict is VALID or INVALID (possibly followed by more text).

    Per SPEC.md: 'the strong verdicts are exactly "VALID" and "INVALID",
    possibly followed by more text'.
    """
    if not isinstance(verdict, str):
        return False
    token = verdict.split()[0] if verdict.strip() else ""
    return (
        token in ("VALID", "INVALID")
        or verdict.startswith("VALID")
        or verdict.startswith("INVALID")
    )


def _target_claim(events: list[dict], result: dict) -> str | None:
    """Identify the claim ID under evaluation from result or events."""
    if isinstance(result, dict) and isinstance(result.get("claim"), str):
        return result["claim"]
    for ev in events:
        if isinstance(ev, dict) and isinstance(ev.get("claim"), str):
            return ev["claim"]
    return None


def _valid_claim_events(events: list[dict], claim: str | None) -> list[dict]:
    """Return valid events belonging to the target claim at matching seq indices."""
    out: list[dict] = []
    for idx, ev in enumerate(events):
        if not isinstance(ev, dict):
            continue
        if validate_event(ev):
            continue
        if ev.get("seq") != idx:
            continue
        if claim is not None and ev.get("claim") != claim:
            continue
        out.append(ev)
    return out


def _valid_judged_for_claim(events: list[dict], env: dict, claim: str | None) -> list[dict]:
    """Return env['judged'] entries that validly match an event of the target claim."""
    judged = (env or {}).get("judged") or []
    valid_evs = {ev["seq"]: ev for ev in _valid_claim_events(events, claim)}
    matched: list[dict] = []
    for j in judged:
        if not isinstance(j, dict):
            continue
        if claim is not None and j.get("claim") != claim:
            continue
        seq = j.get("seq")
        ev = valid_evs.get(seq)
        if ev is None or ev.get("kind") != "check":
            continue
        data = ev.get("data", {})
        if (
            j.get("artifact") == data.get("artifact")
            and j.get("target_decl") == data.get("target_decl")
            and j.get("polarity") == data.get("polarity")
            and j.get("result") in ("pass", "fail")
        ):
            matched.append(j)
    return matched


def _valid_signed_for_claim(events: list[dict], env: dict, claim: str | None) -> list[dict]:
    """Return env['signed'] entries that validly match an event of the target claim."""
    signed = (env or {}).get("signed") or []
    valid_evs = {ev["seq"]: ev for ev in _valid_claim_events(events, claim)}
    matched: list[dict] = []
    for s in signed:
        if not isinstance(s, dict):
            continue
        if claim is not None and s.get("claim") != claim:
            continue
        tseq = s.get("target_seq")
        ev = valid_evs.get(tseq)
        if ev is None:
            continue
        if s.get("target_event") != Ledger.event_hash(ev):
            continue
        matched.append(s)
    return matched


def _retracted_hashes(events: list[dict], env: dict, claim: str | None) -> set[str]:
    """Return event hashes targeted by a human-signed retraction for this claim."""
    signed_rets = {
        s["target_seq"]
        for s in _valid_signed_for_claim(events, env, claim)
        if s.get("judgment") == "retraction"
    }
    hashes: set[str] = set()
    for ev in _valid_claim_events(events, claim):
        if ev.get("kind") == "retraction" and ev.get("seq") in signed_rets:
            th = ev.get("data", {}).get("target_event")
            if isinstance(th, str):
                hashes.add(th)
    return hashes


# ---------------------------------------------------------------------------
# Single-derivation invariants: inv_*(events, env, result) -> str | None
# ---------------------------------------------------------------------------


def inv_totality_and_shape(events: list[dict], env: dict, result: dict) -> str | None:
    """SPEC.md ('The function under test' & 'What to deliver'):
    Derivation is total and returns a dict with keys headline (in HEADLINES),
    verdict (str), axes, missing (list of str), blocked, warnings, ignored_events.
    """
    if not isinstance(result, dict):
        return f"derive_status returned non-dict: {type(result)!r}"
    required = ("headline", "verdict", "axes", "missing", "blocked", "warnings", "ignored_events")
    for key in required:
        if key not in result:
            return f"derive_status output missing required key {key!r}"
    if result["headline"] not in HEADLINES:
        return f"headline {result['headline']!r} not in HEADLINES"
    if not isinstance(result["verdict"], str):
        return f"verdict {result['verdict']!r} is not a str"
    if not isinstance(result["missing"], list) or not all(
        isinstance(x, str) for x in result["missing"]
    ):
        return f"missing {result['missing']!r} must be a list of str"
    return None


def inv_strong_verdict_requires_judged_and_signatures(
    events: list[dict], env: dict, result: dict
) -> str | None:
    """REQ-125 & SPEC.md plan objective:
    VALID or INVALID (or certified headlines established / established(partial) /
    refuted-certified) only for a claim that passed the authoritative tier
    against a human-signed statement with human-signed fidelity.
    """
    headline = result.get("headline")
    verdict = result.get("verdict")
    if not is_strong_verdict(verdict) and headline not in CERTIFIED_HEADLINES:
        return None

    claim = _target_claim(events, result)
    judged = _valid_judged_for_claim(events, env, claim)
    has_judged_pass = any(
        j.get("result") == "pass" and j.get("polarity") in ("claim", "negation")
        for j in judged
    )
    signed = _valid_signed_for_claim(events, env, claim)
    has_stmt_sig = any(s.get("judgment") == "statement" for s in signed)
    has_fid_sig = any(s.get("judgment") == "fidelity" for s in signed)

    if not (has_judged_pass and has_stmt_sig and has_fid_sig):
        return (
            f"strong verdict/headline ({verdict!r}, {headline!r}) without "
            f"judged_pass={has_judged_pass}, stmt_sig={has_stmt_sig}, fid_sig={has_fid_sig}"
        )
    return None


def inv_no_above_local_without_judged(
    events: list[dict], env: dict, result: dict
) -> str | None:
    """REQ-125 & investigate.md ('What the status can say'):
    Without a matching authoritative judge result in env['judged'], there is no
    strong verdict, no headline above 'kernel-passed-local', and no 'judge-rejected'.
    """
    claim = _target_claim(events, result)
    judged = _valid_judged_for_claim(events, env, claim)
    if judged:
        return None

    headline = result.get("headline")
    verdict = result.get("verdict")
    if is_strong_verdict(verdict):
        return f"strong verdict {verdict!r} without any valid env['judged'] entry"
    if headline in HEADLINES_ABOVE_LOCAL or headline == "judge-rejected":
        return f"headline {headline!r} reached without any valid env['judged'] entry"
    return None


def inv_non_kernel_events_never_raise_above_local(
    events: list[dict], env: dict, result: dict
) -> str | None:
    """REQ-002, REQ-125 & investigate.md ('What the status can say', 'Experiments',
    'Choosing the polarity', 'Signing judgments'):
    Numerical evidence (experiments), agent assertions/notes, informal proofs
    (even with a human-signed informal_audit), self-declared fidelity, and 'step'
    polarity checks never raise a claim to a strong verdict or above
    'kernel-passed-local'; and without a passing 'claim' or 'negation' check,
    the headline cannot reach 'kernel-passed-local' or higher.
    """
    claim = _target_claim(events, result)
    valid_evs = _valid_claim_events(events, claim)
    has_claim_or_neg_pass = any(
        ev.get("kind") == "check"
        and ev.get("data", {}).get("polarity") in ("claim", "negation")
        and ev.get("data", {}).get("result") == "pass"
        for ev in valid_evs
    )
    if has_claim_or_neg_pass:
        return None

    headline = result.get("headline")
    verdict = result.get("verdict")
    if is_strong_verdict(verdict):
        return f"strong verdict {verdict!r} without any passing claim/negation check"
    if headline_rank(headline) >= headline_rank("kernel-passed-local"):
        return (
            f"headline {headline!r} (rank {headline_rank(headline)}) reached "
            f"without any passing claim/negation check"
        )
    return None


def inv_experiments_cannot_raise_above_evidence(
    events: list[dict], env: dict, result: dict
) -> str | None:
    """REQ-002 & investigate.md ('Experiments'):
    No claim reaches a proved or refuted status from numerical evidence. When a
    claim has only claim_created, experiments, fidelity, statement_frozen, or
    notes (no checks, no informal_proof, no budget_stop, no abandon), its
    headline rank is at most 'evidence-only' / 'refutation-candidate' (rank 2)
    and its verdict is UNVERIFIED.
    """
    claim = _target_claim(events, result)
    valid_evs = _valid_claim_events(events, claim)
    other_kinds = {
        ev.get("kind")
        for ev in valid_evs
        if ev.get("kind")
        not in ("claim_created", "experiment", "fidelity", "statement_frozen", "retraction")
        and ev.get("kind") in (
            "check",
            "informal_proof",
            "informal_audit",
            "budget_stop",
            "abandon",
        )
    }
    if other_kinds:
        return None

    headline = result.get("headline")
    verdict = result.get("verdict")
    if is_strong_verdict(verdict) or verdict != "UNVERIFIED":
        return f"experiment/metadata-only events produced verdict {verdict!r}"
    if headline_rank(headline) > headline_rank("evidence-only"):
        return f"experiment/metadata-only events raised headline to {headline!r}"
    return None


def inv_self_declared_fidelity_stays_unverified(
    events: list[dict], env: dict, result: dict
) -> str | None:
    """REQ-125 & investigate.md ('Other records', 'Signing judgments'):
    A local pass with self-declared fidelity (without a verified human fidelity
    signature) stays UNVERIFIED and never reaches a strong verdict or certified
    headline.
    """
    claim = _target_claim(events, result)
    signed = _valid_signed_for_claim(events, env, claim)
    has_fid_sig = any(s.get("judgment") == "fidelity" for s in signed)
    if has_fid_sig:
        return None

    headline = result.get("headline")
    verdict = result.get("verdict")
    if is_strong_verdict(verdict):
        return f"strong verdict {verdict!r} reached without a verified fidelity signature"
    if headline in CERTIFIED_HEADLINES:
        return f"certified headline {headline!r} reached without a verified fidelity signature"
    return None


def inv_signed_audit_without_judged_pass_stays_unverified(
    events: list[dict], env: dict, result: dict
) -> str | None:
    """REQ-125:
    A signed audit of an informal proof without an authoritative pass stays
    UNVERIFIED (never VALID/INVALID and never above kernel-passed-local).
    """
    claim = _target_claim(events, result)
    judged = _valid_judged_for_claim(events, env, claim)
    has_judged_pass = any(
        j.get("result") == "pass" and j.get("polarity") in ("claim", "negation")
        for j in judged
    )
    if has_judged_pass:
        return None

    headline = result.get("headline")
    verdict = result.get("verdict")
    if is_strong_verdict(verdict):
        return f"strong verdict {verdict!r} without an authoritative judged pass"
    if headline in HEADLINES_ABOVE_LOCAL:
        return f"headline {headline!r} above kernel-passed-local without a judged pass"
    return None


def inv_budget_stop_never_refuted(
    events: list[dict], env: dict, result: dict
) -> str | None:
    """REQ-009:
    A claim whose search stops ('budget_stop') without proof or certified
    counterexample is unresolved, never refuted or false.
    """
    claim = _target_claim(events, result)
    valid_evs = _valid_claim_events(events, claim)
    has_budget_stop = any(ev.get("kind") == "budget_stop" for ev in valid_evs)
    if not has_budget_stop:
        return None

    retracted = _retracted_hashes(events, env, claim)
    has_neg_pass = any(
        ev.get("kind") == "check"
        and ev.get("data", {}).get("polarity") == "negation"
        and ev.get("data", {}).get("result") == "pass"
        and Ledger.event_hash(ev) not in retracted
        for ev in valid_evs
    )
    has_exp_viol = any(
        ev.get("kind") == "experiment"
        and bool(ev.get("data", {}).get("violations"))
        and Ledger.event_hash(ev) not in retracted
        for ev in valid_evs
    )

    headline = result.get("headline")
    verdict = result.get("verdict")
    if not has_neg_pass:
        if headline == "refuted-certified":
            return "budget_stop without passing negation check produced 'refuted-certified'"
        if not has_exp_viol and headline == "refutation-candidate":
            return "budget_stop without violation experiment produced 'refutation-candidate'"
        if isinstance(verdict, str) and verdict.startswith("INVALID"):
            return f"budget_stop without passing negation check produced verdict {verdict!r}"
    return None


def _failed_artifact_polarities(valid_evs: list[dict]) -> set[tuple[Any, Any]]:
    """Return {(artifact, polarity)} for all failing check events of the claim.

    When an artifact has both a passing and a failing check of the same polarity,
    the failure stands and the pass does not count.
    """
    return {
        (ev.get("data", {}).get("artifact"), ev.get("data", {}).get("polarity"))
        for ev in valid_evs
        if ev.get("kind") == "check" and ev.get("data", {}).get("result") == "fail"
    }


def inv_conflict_when_claim_and_negation_both_pass(
    events: list[dict], env: dict, result: dict
) -> str | None:
    """SPEC.md plan objective & what to deliver (with same-artifact failure rule):
    A proof ('claim') and a refutation ('negation') that both pass is 'conflict'
    and never a strong verdict. (Per investigate.md 'Signing judgments', a
    retraction cannot remove a passing check when a passing check of the other
    polarity contradicts it. When an artifact has both a passing and a failing
    check of the same polarity, the failure stands and the pass does not count;
    that rule is safe since it only lowers the status, though investigate.md
    does not state it.)
    """
    claim = _target_claim(events, result)
    valid_evs = _valid_claim_events(events, claim)
    judged = _valid_judged_for_claim(events, env, claim)
    rejected_seqs = {
        j["seq"] for j in judged if j.get("result") == "fail"
    }
    failed_ap = _failed_artifact_polarities(valid_evs)

    has_claim_pass = any(
        ev.get("kind") == "check"
        and ev.get("data", {}).get("polarity") == "claim"
        and ev.get("data", {}).get("result") == "pass"
        and ev.get("seq") not in rejected_seqs
        and (ev.get("data", {}).get("artifact"), "claim") not in failed_ap
        for ev in valid_evs
    )
    has_neg_pass = any(
        ev.get("kind") == "check"
        and ev.get("data", {}).get("polarity") == "negation"
        and ev.get("data", {}).get("result") == "pass"
        and ev.get("seq") not in rejected_seqs
        and (ev.get("data", {}).get("artifact"), "negation") not in failed_ap
        for ev in valid_evs
    )

    if not (has_claim_pass and has_neg_pass):
        return None

    headline = result.get("headline")
    verdict = result.get("verdict")
    if is_strong_verdict(verdict):
        return f"claim+negation both passing produced strong verdict {verdict!r}"
    if headline != "conflict":
        return f"claim+negation both passing produced headline {headline!r} != 'conflict'"
    return None


def inv_local_pass_with_judge_fail_is_rejected(
    events: list[dict], env: dict, result: dict
) -> str | None:
    """REQ-125 & investigate.md ('What the status can say', 'Signing judgments',
    with same-artifact failure rule):
    A local pass plus a judge failure is 'judge-rejected' (unless both polarities
    pass, giving 'conflict', or another non-rejected check overrides in conflict),
    and never reaches 'kernel-passed-local' or above or a strong verdict when
    every passing claim/negation check is rejected by the judge. A check counts
    as a local pass only if no failing check of the same artifact and polarity
    exists (when an artifact has both a passing and a failing check of the same
    polarity, the failure stands and the pass does not count).
    """
    claim = _target_claim(events, result)
    valid_evs = _valid_claim_events(events, claim)
    judged = _valid_judged_for_claim(events, env, claim)
    rejected_seqs = {j["seq"] for j in judged if j.get("result") == "fail"}
    if not rejected_seqs:
        return None
    failed_ap = _failed_artifact_polarities(valid_evs)

    passing_claim_neg = [
        ev
        for ev in valid_evs
        if ev.get("kind") == "check"
        and ev.get("data", {}).get("polarity") in ("claim", "negation")
        and ev.get("data", {}).get("result") == "pass"
        and (ev.get("data", {}).get("artifact"), ev.get("data", {}).get("polarity"))
        not in failed_ap
    ]
    if not passing_claim_neg:
        return None

    all_rejected = all(ev.get("seq") in rejected_seqs for ev in passing_claim_neg)
    if not all_rejected:
        return None

    passing_polarities = {ev.get("data", {}).get("polarity") for ev in passing_claim_neg}
    expected_headline = "conflict" if len(passing_polarities) > 1 else "judge-rejected"

    headline = result.get("headline")
    verdict = result.get("verdict")
    if is_strong_verdict(verdict):
        return f"judge-rejected check produced strong verdict {verdict!r}"
    if headline != expected_headline:
        return (
            f"local pass with judge failure produced headline {headline!r} != "
            f"{expected_headline!r}"
        )
    return None


# ---------------------------------------------------------------------------
# Relational invariants: inv_*(before, after) -> str | None
# ---------------------------------------------------------------------------


def inv_determinism(before: dict, after: dict) -> str | None:
    """SPEC.md ('What to deliver'):
    Derivation is deterministic: running derive_status twice on identical inputs
    returns equal results.
    """
    if before != after:
        return f"non-deterministic derivation: {before!r} != {after!r}"
    return None


def inv_bogus_env_changes_nothing(before: dict, after: dict) -> str | None:
    """SPEC.md ('What to deliver') & investigate.md ('Authoritative judgment',
    'Signing judgments'):
    An env['judged'] or env['signed'] entry naming another claim, a non-existent
    seq, or a mismatched hash changes nothing.
    """
    if before != after:
        return (
            f"bogus env entry changed derivation from "
            f"(headline={before.get('headline')!r}, verdict={before.get('verdict')!r}) to "
            f"(headline={after.get('headline')!r}, verdict={after.get('verdict')!r})"
        )
    return None


def inv_unsigned_retraction_changes_nothing(before: dict, after: dict) -> str | None:
    """SPEC.md ('What to deliver') & investigate.md ('Signing judgments'):
    'An unsigned retraction changes nothing.' Adding an unsigned retraction event
    leaves headline, verdict, axes, missing, and blocked unchanged.
    """
    for field in ("headline", "verdict", "axes", "missing", "blocked"):
        if before.get(field) != after.get(field):
            return (
                f"unsigned retraction changed {field!r}: "
                f"{before.get(field)!r} -> {after.get(field)!r}"
            )
    return None


def inv_retraction_never_raises_status(before: dict, after: dict) -> str | None:
    """SPEC.md ('Requirements to turn into invariants' & 'What to deliver') &
    investigate.md ('Signing judgments'):
    Adding a retraction (signed or unsigned) never raises the status in the
    authority ranking of HEADLINES and never upgrades a non-strong verdict to a
    strong verdict.
    """
    h_before = before["headline"]
    h_after = after["headline"]
    r_before = headline_rank(h_before)
    r_after = headline_rank(h_after)
    if r_after > r_before:
        return (
            f"adding retraction raised headline from {h_before!r} (rank {r_before}) "
            f"to {h_after!r} (rank {r_after})"
        )
    if not is_strong_verdict(before.get("verdict")) and is_strong_verdict(after.get("verdict")):
        return (
            f"adding retraction upgraded verdict from {before.get('verdict')!r} "
            f"to {after.get('verdict')!r}"
        )
    return None


def is_supporting_env_entry(
    kind_key: str, entry: dict, events: list[dict], claim: str | None = None
) -> bool:
    """Return True if an env entry supports the claim.

    Supporting entries are:
    - in env['judged']: a judged pass (result == 'pass')
    - in env['signed']: a signature on an event that supports the claim:
      * statement signature (judgment == 'statement' on a statement_frozen event)
      * faithful fidelity signature (judgment == 'fidelity' on a fidelity event
        with class == 'faithful')
      * no-flaw informal audit signature (judgment == 'informal_audit' on an
        informal_audit event with result == 'no-flaw')
    Removing a judge's rejection (result == 'fail') or a retraction/negative
    signature may raise the status by design.
    """
    if not isinstance(entry, dict):
        return False
    if kind_key == "judged":
        return entry.get("result") == "pass"
    if kind_key == "signed":
        valid_evs = {ev["seq"]: ev for ev in _valid_claim_events(events, claim)}
        ev = valid_evs.get(entry.get("target_seq"))
        if ev is None or entry.get("target_event") != Ledger.event_hash(ev):
            return False
        judgment = entry.get("judgment")
        data = ev.get("data", {})
        if judgment == "statement" and ev.get("kind") == "statement_frozen":
            return True
        if (
            judgment == "fidelity"
            and ev.get("kind") == "fidelity"
            and data.get("class") == "faithful"
        ):
            return True
        if (
            judgment == "informal_audit"
            and ev.get("kind") == "informal_audit"
            and data.get("result") == "no-flaw"
        ):
            return True
        return False
    return False


def inv_removing_env_never_raises_status(
    before: dict,
    after: dict,
    *,
    kind_key: str | None = None,
    removed_entry: dict | None = None,
    events: list[dict] | None = None,
) -> str | None:
    """SPEC.md ('What to deliver', refined):
    Removing a supporting env entry — a judged pass or a signature on an event
    that supports the claim (statement, faithful fidelity, no-flaw audit) —
    never raises the status in the authority ranking of HEADLINES and never
    upgrades a non-strong verdict to a strong verdict. Removing a judge's
    rejection or a retraction signature may raise the status and is excluded.
    """
    if (
        kind_key is not None
        and removed_entry is not None
        and events is not None
        and not is_supporting_env_entry(
            kind_key, removed_entry, events, _target_claim(events, before)
        )
    ):
        return None
    h_before = before["headline"]
    h_after = after["headline"]
    r_before = headline_rank(h_before)
    r_after = headline_rank(h_after)
    if r_after > r_before:
        return (
            f"removing supporting env entry raised headline from {h_before!r} "
            f"(rank {r_before}) to {h_after!r} (rank {r_after})"
        )
    if not is_strong_verdict(before.get("verdict")) and is_strong_verdict(after.get("verdict")):
        return (
            f"removing supporting env entry upgraded verdict from "
            f"{before.get('verdict')!r} to {after.get('verdict')!r}"
        )
    return None


def inv_missing_lists_unmet_gates(events: list[dict], env: dict, result: dict) -> str | None:
    """investigate.md ('Signing judgments'): a claim the judge accepted reads `judged-unreviewed`, and its
    `missing` list names what is still needed. Signed statements and fidelity judgments clear their
    entries, and "a fully signed claim still reads judged-unreviewed with missing: assumption audit".
    So for `judged-unreviewed`: 'assumption audit' is always listed; 'statement signature' is listed
    exactly when the claim's first frozen statement has no valid signature; 'fidelity signature' is
    listed when no fidelity event has one.

    Written by the integrating reviewer, not the independent author, from the sentence quoted above.
    """
    if result.get("headline") != "judged-unreviewed":
        return None
    claim = _target_claim(events, result)
    missing = result.get("missing") or []
    signed_seqs = {s.get("target_seq") for s in _valid_signed_for_claim(events, env, claim)}
    claim_events = _valid_claim_events(events, claim)
    frozen = [ev for ev in claim_events if ev.get("kind") == "statement_frozen"]
    statement_signed = bool(frozen) and frozen[0]["seq"] in signed_seqs
    fidelity_signed = any(ev.get("kind") == "fidelity" and ev["seq"] in signed_seqs for ev in claim_events)
    if "assumption audit" not in missing:
        return f"judged-unreviewed without 'assumption audit' in missing: {missing}"
    if statement_signed == ("statement signature" in missing):
        return f"statement signed={statement_signed} but missing={missing}"
    if not fidelity_signed and "fidelity signature" not in missing:
        return f"no signed fidelity judgment but missing={missing}"
    return None


SINGLE_INVARIANTS: tuple[Callable[[list[dict], dict, dict], str | None], ...] = (
    inv_totality_and_shape,
    inv_strong_verdict_requires_judged_and_signatures,
    inv_no_above_local_without_judged,
    inv_non_kernel_events_never_raise_above_local,
    inv_experiments_cannot_raise_above_evidence,
    inv_self_declared_fidelity_stays_unverified,
    inv_signed_audit_without_judged_pass_stays_unverified,
    inv_budget_stop_never_refuted,
    inv_conflict_when_claim_and_negation_both_pass,
    inv_local_pass_with_judge_fail_is_rejected,
    inv_missing_lists_unmet_gates,
)

RELATIONAL_INVARIANTS: tuple[Callable[[dict, dict], str | None], ...] = (
    inv_determinism,
    inv_bogus_env_changes_nothing,
    inv_unsigned_retraction_changes_nothing,
    inv_retraction_never_raises_status,
    inv_removing_env_never_raises_status,
)

ALL_INVARIANTS: tuple[Callable[..., str | None], ...] = SINGLE_INVARIANTS + RELATIONAL_INVARIANTS
