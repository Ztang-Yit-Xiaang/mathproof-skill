"""Derive a claim's status from its events. This is the trusted core of the research records.

`derive_status` is a pure function: the same events give the same status, nothing is written, and
timestamps are never read. Events carry no status of their own.

Three rules govern it (planning contract IF-claim-status-v2):

1. Only the authoritative tier plus a human signature can give VALID or INVALID. Nothing an agent
   writes can stand in for either: a `tier` field, a `judge` field, or a signature field. The
   authoritative tier reaches derivation only through `env["judged"]`, which `authority.py` builds
   from an attested judge report, and a signature only through `env["signed"]`, which
   `signature.verify` builds from signatures it checked against keys kept outside the ledger.
   Rows 3 to 5 also need the vacuity, assumption, and dependency gates of later tasks, so the
   strongest headline is still `judged-unreviewed`, and the verdict is never VALID or INVALID.
2. A claim's statement never changes.
3. A retraction needs authority at or above its target, so unsigned retractions and resolutions
   change nothing. A verified signed retraction removes the event it names.

The headline is the first row that matches, in the order of the contract's table. Rows 3 to 5
need signatures, which arrive with S2.3.T3. `compat` already covers them, so that it stays total.
"""

from __future__ import annotations

import re

from .events import is_status_bearing, validate_event
from .ledger import Ledger

DERIVATION_VERSION = "m1-1"

HEADLINES = (
    "conflict", "judge-rejected", "refuted-certified", "established", "established(partial)", "conditional",
    "judged-unreviewed", "kernel-passed-local", "refutation-candidate", "unresolved", "abandoned", "argued",
    "step-passed", "evidence-only", "conjecture",
)

HUMAN_AUDITED = 'UNVERIFIED, labeled "informal proof, human-audited, not machine-confirmed"'

# Worst first, for combining judgments of one artifact.
_FIDELITY_ORDER = ("unfaithful", "partial", "instance", "faithful")

_HEX64 = re.compile(r"[0-9a-f]{64}")

# Gates of rows 3 to 5 that no task implements yet (S2.4.T1 and later), so they are always missing.
_NOT_YET = ("assumption audit",)

# The direction a judgment needs depends on what was checked: a proof of F needs F => I, and a
# refutation (a check of not F) needs I => F.
_NEEDED_DIRECTION = {"claim": "F=>I", "negation": "I=>F"}


def compat(headline: str, *, kernel_passed: bool = False, attempted: bool = False, scope: str | None = None,
           signed_audit: bool = False, method: str | None = None, label: str | None = None,
           missing: tuple = (), cost_audit_passed: bool = False, citation: str | None = None) -> tuple[str, str]:
    """Map a headline to the existing (verdict, Lean status) vocabulary. Total over HEADLINES."""
    not_checked = "LEAN-FAILED" if attempted else "NOT FORMALIZED"
    scope_text = scope or "scope not stated"
    if headline == "established":
        return "VALID", "LEAN-CHECKED"
    if headline == "established(partial)":
        return f"VALID ({scope_text})", f"LEAN-CHECKED (partial: {scope_text})"
    if headline == "refuted-certified":
        if scope:
            return f"INVALID within scope ({scope})", f"LEAN-CHECKED (partial: {scope})"
        return "INVALID", "LEAN-CHECKED"
    if headline == "conditional":
        if citation:
            return f"CONDITIONALLY VALID ({citation})", f"LEAN-CHECKED (partial: conditional on {citation})"
        if cost_audit_passed:
            return "CONDITIONALLY VALID", f"LEAN-CHECKED (partial: {scope_text})"
        return "UNVERIFIED", "KERNEL-PASSED (authoritative; blocked: cost audit)"
    if headline == "conflict":
        return "UNVERIFIED, flagged", "KERNEL-PASSED (conflict)" if kernel_passed else "LEAN-FAILED"
    if headline == "judge-rejected":
        return "UNVERIFIED", "LEAN-FAILED"
    if headline == "judged-unreviewed":
        return "UNVERIFIED", f"KERNEL-PASSED (authoritative; missing: {', '.join(missing) or 'not listed'})"
    if headline == "kernel-passed-local":
        return "UNVERIFIED", f"KERNEL-PASSED (local; {label or 'label not stated'})"
    if headline == "refutation-candidate":
        return "UNVERIFIED", f"NOT FORMALIZED ({method or 'method not stated'})"
    if headline == "argued":
        return (HUMAN_AUDITED if signed_audit else "INCOMPLETE"), not_checked
    if headline == "step-passed":
        return "UNVERIFIED", "KERNEL-PASSED (step only)"
    if headline in ("evidence-only", "unresolved", "abandoned", "conjecture"):
        return "UNVERIFIED", not_checked
    raise ValueError(f"unknown headline: {headline}")


def usable_events(events: list, claim: str) -> tuple[list[dict], int]:
    """This claim's status-bearing events, and how many of them were invalid and so ignored."""
    usable, ignored = [], 0
    for event in events:
        if not isinstance(event, dict) or event.get("claim") != claim or not is_status_bearing(str(event.get("kind"))):
            continue
        if validate_event(event):
            ignored += 1
        else:
            usable.append(event)
    return usable, ignored


def _kernel(checks: list[dict]) -> tuple[str, list[dict], bool, bool, list[str]]:
    """Returns (axis, passing non-step checks, step passed?, Lean attempted?, warnings).

    A failure of an artifact beats a pass of the same artifact, target, and polarity, in either
    order: identical input cannot honestly have both results.
    """
    key = lambda c: (c["artifact"], c["target_decl"], c["polarity"])  # noqa: E731
    failed = {key(c) for c in checks if c["result"] == "fail"}
    claimed_pass = {key(c) for c in checks if c["result"] == "pass"}
    passing = [c for c in checks if c["result"] == "pass" and key(c) not in failed]
    proper = [c for c in passing if c["polarity"] != "step"]
    if proper:
        axis = "passed-local"
    elif any(c["polarity"] != "step" for c in checks if c["result"] == "fail"):
        axis = "failed"
    else:
        axis = "none"
    warnings = []
    if failed & claimed_pass:
        warnings.append("checks of the same artifact contradict each other, so the failure stands")
    return axis, proper, any(c["polarity"] == "step" for c in passing), bool(checks), warnings


def _fidelity(judgments: list[dict], passing: list[dict], signed: set | frozenset = frozenset()) -> tuple[dict, list[str]]:
    """Combine the judgments of the passing artifacts, worst first. Labels only, in M0.

    An artifact with no accepted judgment counts as unjudged, so one judged artifact cannot speak
    for another. An `unfaithful` on any artifact of the claim stays visible as a warning.
    """
    warnings: list[str] = []
    if any(j["class"] == "unfaithful" for j in judgments):
        warnings.append("a judgment says a statement is unfaithful to the claim")
    polarities: dict[str, set[str]] = {}
    for check in passing:
        polarities.setdefault(check["artifact"], set()).add(check["polarity"])
    accepted: dict[str, list[dict]] = {}
    for judgment in judgments:
        target = judgment["statement_hash"]
        if target not in polarities:
            continue
        cls = judgment["class"]
        if cls != "unfaithful":
            if cls == "instance" and "negation" not in polarities[target]:
                warnings.append("ignored `instance` judgment: it can only support a refutation")
                continue
            if not any(judgment["direction"] == _NEEDED_DIRECTION[p] for p in polarities[target]):
                warnings.append(f"ignored judgment with the wrong direction: {judgment['direction']}")
                continue
        accepted.setdefault(target, []).append(judgment)
    unjudged = {"class": None, "direction": None, "provenance": "none", "scope": None, "signed": False}
    # Signed judgments decide, worst-of among them; unsigned ones are shown only when none is signed.
    signed_accepted = {target: [j for j in js if id(j) in signed] for target, js in accepted.items()}
    signed_accepted = {target: js for target, js in signed_accepted.items() if js}
    if signed_accepted and (set(signed_accepted) == set(polarities)
                            or any(j["class"] == "unfaithful" for js in signed_accepted.values() for j in js)):
        worst = min((j for js in signed_accepted.values() for j in js), key=lambda j: _FIDELITY_ORDER.index(j["class"]))
        return {"class": worst["class"], "direction": worst["direction"], "provenance": "signed-human",
                "scope": worst.get("scope_note") or None, "signed": True}, warnings
    combined = [j for js in accepted.values() for j in js]
    unfaithful = any(j["class"] == "unfaithful" for j in combined)
    if not combined or (not unfaithful and set(accepted) != set(polarities)):
        return unjudged, warnings
    worst = min(combined, key=lambda j: _FIDELITY_ORDER.index(j["class"]))
    # Signatures cannot be verified in M0, so a claim to be signed, or no stated judge at all, is
    # a self-declaration. Other labels are shown as claimed, and `signed` stays false.
    provenance = "self-declared" if worst["judge"] in ("signed-human", "none") else worst["judge"]
    return {"class": worst["class"], "direction": worst["direction"], "provenance": provenance,
            "scope": worst.get("scope_note") or None, "signed": False}, warnings


def _informal(events: list[dict], signed: set | frozenset = frozenset()) -> tuple[str, list[str]]:
    proofs = {e["data"]["artifact"] for e in events if e["kind"] == "informal_proof"}
    audits = [e for e in events if e["kind"] == "informal_audit" and e["data"]["proof_hash"] in proofs]
    signed_audits = [e["data"] for e in audits if e["seq"] in signed]
    warnings = [f"an unsigned audit reports a flaw: {e['data']['auditor']}" for e in audits
                if e["data"]["result"] == "flaw" and e["seq"] not in signed]
    if not proofs:
        return "none", []
    if signed_audits:
        return ("rejected" if any(a["result"] == "flaw" for a in signed_audits) else "signed-audited"), warnings
    return ("self-audited" if audits else "drafted"), warnings


def _computational(events: list[dict]) -> dict:
    runs = [e["data"] for e in events if e["kind"] == "experiment"]
    return {"runs": len(runs),
            "candidates": sum(len(r.get("violations") or []) for r in runs),
            "artifacts": sorted({r["code_hash"] for r in runs})}


def _judged(env: dict, claim: str, usable: list[dict], passing: list[dict]) -> tuple[set, set]:
    """The passing local checks of this claim the authoritative judge accepted, and those it rejected.

    A result counts only if it is well formed, names this claim, and names by seq a passing check
    event of this claim with the same artifact, target, and polarity. `authority.py` has already
    matched that event, its Challenge, and the ledger head. Results are returned as check keys; a
    rejection of an artifact beats an acceptance of the same one.
    """
    results = env.get("judged") if isinstance(env, dict) else None
    if not isinstance(results, list):
        return set(), set()
    key = lambda c: (c["artifact"], c["target_decl"], c["polarity"])  # noqa: E731
    passing_keys = {key(c) for c in passing}
    events = {(e["seq"], key(e["data"])) for e in usable
              if e["kind"] == "check" and e["data"]["result"] == "pass" and key(e["data"]) in passing_keys}
    accepted, rejected = set(), set()
    for result in results:
        if not isinstance(result, dict) or result.get("claim") != claim:
            continue
        seq = result.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int):
            continue
        entry = (result.get("artifact"), result.get("target_decl"), result.get("polarity"))
        if not all(isinstance(part, str) for part in entry):
            continue
        challenge = result.get("challenge_hash")
        if not isinstance(challenge, str) or not _HEX64.fullmatch(challenge):
            continue
        if (seq, entry) not in events:
            continue
        if result.get("result") == "pass":
            accepted.add(entry)
        elif result.get("result") == "fail":
            rejected.add(entry)
    return accepted - rejected, rejected


def _retractable(event: dict, rejected_seqs: set, usable: list[dict]) -> bool:
    """Whether a signed retraction may remove this event. Removing it must never make the claim look
    stronger: a retraction can withdraw evidence for the claim, never evidence against it."""
    kind, data = event["kind"], event["data"]
    if kind == "check":
        opposite = {"claim": "negation", "negation": "claim"}.get(data["polarity"])
        return (data["result"] == "pass" and event["seq"] not in rejected_seqs
                and not any(e["kind"] == "check" and e["data"]["result"] == "pass" and e["data"]["polarity"] == opposite
                            for e in usable))
    if kind == "fidelity":
        return data["class"] == "faithful"
    if kind == "informal_audit":
        return data["result"] == "no-flaw"
    if kind == "informal_proof":
        return not any(e["kind"] == "informal_audit" and e["data"]["proof_hash"] == data["artifact"]
                       and e["data"]["result"] == "flaw" for e in usable)
    if kind == "experiment":
        return not data.get("violations")
    return False


def _signed(env: dict, claim: str, usable: list[dict]) -> set[int]:
    """Seqs of this claim's events with a verified signature (`env["signed"]`, from signature.verify).

    An entry counts only if it names this claim and an event of this claim, by seq and hash, whose
    kind is the judgment it says it signs. A seq that two different usable events claim counts for
    neither.
    """
    entries = env.get("signed") if isinstance(env, dict) else None
    if not isinstance(entries, list):
        return set()
    kinds: dict[int, set] = {}
    for e in usable:
        kinds.setdefault(e["seq"], set()).add((e["kind"], Ledger.event_hash(e)))
    judgment_kind = {"statement": "statement_frozen", "fidelity": "fidelity", "informal_audit": "informal_audit",
                     "waiver": "waiver", "retraction": "retraction"}
    seqs = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("claim") != claim:
            continue
        seq = entry.get("target_seq")
        # The entry names the event by hash too, so another event that claims the same seq gets nothing.
        if (isinstance(seq, int) and not isinstance(seq, bool)
                and kinds.get(seq) == {(judgment_kind.get(entry.get("judgment")), entry.get("target_event"))}):
            seqs.add(seq)
    return seqs


def derive_status(events: list[dict], claim: str, env: dict) -> dict:
    """Derive a claim's status. Only `env["judged"]` can raise it, and only up to judged-unreviewed."""
    env = env or {}
    usable, ignored = usable_events(events, claim)
    signed = _signed(env, claim, usable)
    retracted = {e["data"]["target_event"] for e in usable if e["kind"] == "retraction" and e["seq"] in signed}
    if retracted:
        # A signed retraction removes the event it names, but only evidence for the claim: never the
        # claim, its statement, a failure, a judge's rejection, an unfaithful judgment, or a flaw.
        rejected_seqs = {r.get("seq") for r in (env.get("judged") or []) if isinstance(r, dict)
                         and r.get("claim") == claim and r.get("result") == "fail"}
        usable = [e for e in usable if not _retractable(e, rejected_seqs, usable) or Ledger.event_hash(e) not in retracted]
    of_kind = lambda kind: [e["data"] for e in usable if e["kind"] == kind]  # noqa: E731

    kernel, passing, step_passed, attempted, warnings = _kernel(of_kind("check"))
    fidelity_events = [e for e in usable if e["kind"] == "fidelity"]
    fidelity, fidelity_warnings = _fidelity([e["data"] for e in fidelity_events], passing,
                                            {id(e["data"]) for e in fidelity_events if e["seq"] in signed})
    warnings = warnings + fidelity_warnings
    informal, informal_warnings = _informal(usable, signed)
    warnings += informal_warnings
    computational = _computational(usable)
    if "claim" in {c["polarity"] for c in passing} and (computational["candidates"] or of_kind("certificate")):
        warnings.append("unverified counterevidence sits beside a passing check")
    created = of_kind("claim_created")
    if len(created) > 1:
        warnings.append("this claim has more than one statement event; the first one stands")
    frozen = of_kind("statement_frozen")
    if len(frozen) > 1:
        warnings.append("this claim has more than one frozen statement; the first one stands")
    revised_by = sorted({e["claim"] for e in events if isinstance(e, dict) and e.get("kind") == "statement_frozen"
                         and isinstance(e.get("data"), dict) and e["data"].get("revises") == claim
                         and e.get("claim") != claim and not validate_event(e)})
    statement = None
    statement_signed = False
    if frozen:
        first = frozen[0]
        first_seq = next(e["seq"] for e in usable if e["kind"] == "statement_frozen")
        statement_signed = first_seq in signed
        statement = {"artifact": first["artifact"], "name": first.get("name"), "revises": first.get("revises"),
                     "signed": statement_signed}
    if revised_by:
        statement = (statement or {}) | {"revised_by": revised_by}
    budget_stopped, abandoned = bool(of_kind("budget_stop")), bool(of_kind("abandon"))
    search = "budget-stopped" if budget_stopped else "abandoned" if abandoned else "active"
    polarities = {c["polarity"] for c in passing}
    judged, rejected = _judged(env, claim, usable, passing)
    if rejected:
        kernel = "judge-rejected"
    elif judged:
        kernel = "judged"
    missing: list[str] = []
    blocked: list[str] = []
    if judged:
        if not statement_signed:
            missing.append("statement signature")
        if not fidelity["signed"]:
            missing.append("fidelity signature")
        missing += _NOT_YET
        if "claim" in {polarity for _, _, polarity in judged}:
            missing.append("vacuity witness")
        if fidelity["class"] == "unfaithful":
            blocked.append("unfaithful")

    if {"claim", "negation"} <= polarities:
        headline = "conflict"
    elif rejected:
        headline = "judge-rejected"
    elif judged:
        headline = "judged-unreviewed"
    elif kernel == "passed-local":
        headline = "kernel-passed-local"
    elif budget_stopped:
        headline = "unresolved"
    elif abandoned:
        headline = "abandoned"
    elif informal != "none":
        headline = "argued"
    elif step_passed:
        headline = "step-passed"
    elif computational["runs"]:
        headline = "evidence-only"
    else:
        headline = "conjecture"

    label = None
    if polarities:
        # Only closed values go in this line. Scope text is free text, so it stays in the axis.
        judged = f"{fidelity['class']}, {fidelity['provenance']}" if fidelity["class"] else "none"
        label = f"{'+'.join(sorted(polarities))}, fidelity: {judged}"
    verdict, lean_status = compat(headline, kernel_passed=bool(passing), attempted=attempted, label=label,
                                  missing=tuple(missing), signed_audit=informal == "signed-audited")

    return {
        "claim": claim,
        "statement": created[0]["text"] if created else None,
        "formal_statement": statement,
        "headline": headline,
        "verdict": verdict,
        "lean_status": lean_status,
        "axes": {"kernel": kernel, "fidelity": fidelity, "informal": informal,
                 "computational": computational, "search": search},
        "missing": missing,
        "blocked": blocked,
        "warnings": warnings,
        "ignored_events": ignored,
        "derivation_version": DERIVATION_VERSION,
        "checker_version": env.get("checker_version"),
    }
