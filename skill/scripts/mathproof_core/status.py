"""Derive a claim's status from its events. This is the trusted core of the research records.

`derive_status` is a pure function: the same events give the same status, nothing is written, and
timestamps are never read. Events carry no status of their own.

Three rules govern it (planning contract IF-claim-status-v2):

1. Only the authoritative tier plus a human signature can give VALID or INVALID. That tier does not
   exist yet in M0, and nothing an agent writes can stand in for it: a `tier` field, a `judge`
   field, a signature field, or `env`. So in M0 the verdict is never VALID or INVALID.
2. A claim's statement never changes.
3. A retraction needs authority at or above its target, so unsigned retractions and resolutions
   change nothing. No signature can be verified in M0.

The headline is the first row that matches, in the order of the contract's table. Rows that need
the authoritative tier arrive in M1. `compat` already covers them, so that it stays total.
"""

from __future__ import annotations

from .events import is_status_bearing, validate_event

DERIVATION_VERSION = "m0-1"

HEADLINES = (
    "conflict", "judge-rejected", "refuted-certified", "established", "established(partial)", "conditional",
    "judged-unreviewed", "kernel-passed-local", "refutation-candidate", "unresolved", "abandoned", "argued",
    "step-passed", "evidence-only", "conjecture",
)

HUMAN_AUDITED = 'UNVERIFIED, labeled "informal proof, human-audited, not machine-confirmed"'

# Worst first, for combining judgments of one artifact.
_FIDELITY_ORDER = ("unfaithful", "partial", "instance", "faithful")

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


def _usable_events(events: list, claim: str) -> tuple[list[dict], int]:
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


def _fidelity(judgments: list[dict], passing: list[dict]) -> tuple[dict, list[str]]:
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


def _informal(events: list[dict]) -> tuple[str, list[str]]:
    proofs = {e["data"]["artifact"] for e in events if e["kind"] == "informal_proof"}
    audits = [e["data"] for e in events if e["kind"] == "informal_audit" and e["data"]["proof_hash"] in proofs]
    warnings = [f"an unsigned audit reports a flaw: {a['auditor']}" for a in audits if a["result"] == "flaw"]
    if not proofs:
        return "none", []
    return ("self-audited" if audits else "drafted"), warnings


def _computational(events: list[dict]) -> dict:
    runs = [e["data"] for e in events if e["kind"] == "experiment"]
    return {"runs": len(runs),
            "candidates": sum(len(r.get("violations") or []) for r in runs),
            "artifacts": sorted({r["code_hash"] for r in runs})}


def derive_status(events: list[dict], claim: str, env: dict) -> dict:
    """Derive a claim's status. `env` can add version notes, and cannot raise anything in M0."""
    env = env or {}
    usable, ignored = _usable_events(events, claim)
    of_kind = lambda kind: [e["data"] for e in usable if e["kind"] == kind]  # noqa: E731

    kernel, passing, step_passed, attempted, warnings = _kernel(of_kind("check"))
    fidelity, fidelity_warnings = _fidelity(of_kind("fidelity"), passing)
    warnings = warnings + fidelity_warnings
    informal, informal_warnings = _informal(usable)
    warnings += informal_warnings
    computational = _computational(usable)
    if "claim" in {c["polarity"] for c in passing} and (computational["candidates"] or of_kind("certificate")):
        warnings.append("unverified counterevidence sits beside a passing check")
    created = of_kind("claim_created")
    if len(created) > 1:
        warnings.append("this claim has more than one statement event; the first one stands")
    budget_stopped, abandoned = bool(of_kind("budget_stop")), bool(of_kind("abandon"))
    search = "budget-stopped" if budget_stopped else "abandoned" if abandoned else "active"
    polarities = {c["polarity"] for c in passing}

    if {"claim", "negation"} <= polarities:
        headline = "conflict"
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
        judged = "none"
        if fidelity["class"]:
            # Quoted, because scope text is written by whoever wrote the event.
            scoped = f'partial: "{fidelity["scope"]}"' if fidelity["class"] == "partial" and fidelity["scope"] else fidelity["class"]
            judged = f"{scoped}, {fidelity['provenance']}"
        label = f"{'+'.join(sorted(polarities))}, fidelity: {judged}"
    verdict, lean_status = compat(headline, kernel_passed=bool(passing), attempted=attempted, label=label)

    return {
        "claim": claim,
        "statement": created[0]["text"] if created else None,
        "headline": headline,
        "verdict": verdict,
        "lean_status": lean_status,
        "axes": {"kernel": kernel, "fidelity": fidelity, "informal": informal,
                 "computational": computational, "search": search},
        "warnings": warnings,
        "ignored_events": ignored,
        "derivation_version": DERIVATION_VERSION,
        "checker_version": env.get("checker_version"),
    }
