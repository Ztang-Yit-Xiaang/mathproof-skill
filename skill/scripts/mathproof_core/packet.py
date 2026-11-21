"""Render a claim as a review packet for a person (REQ-126). Like the report, it is a view, never truth.

A claim whose proof Lean has not checked gets its informal proof as numbered steps, each with its
justification and whether Lean checked it, and the first unchecked step is marked. A claim with a
passing kernel check gets only the comparison of the intended statement with what Lean checked,
because that is the one thing the kernel cannot judge.

An informal proof is in step form when its stored file is JSON like

    {"steps": [{"claim": "...", "because": "...", "lean": "optional_decl_name"}, ...]}

A step counts as machine-checked only when a passing `step` check names its `lean` declaration and
no failing check of the same file and declaration cancels it. That shows Lean proved *a*
declaration of that name; whether it says what the step says is for the reader to judge, so the
packet prints the checked statement next to the step.
"""

from __future__ import annotations

import json

from .ledger import ArtifactCorrupt, Ledger
from .report import _indented, _proved_section, _quoted, _stored_report, _target_in, _text
from .status import derive_status, usable_events

APPROVAL_CEILING = ("Approving this packet records a human audit of an informal proof. It does not make the claim "
                    "VALID: the status stays UNVERIFIED until Lean checks the proof.")


def _steps(ledger: Ledger, artifact: str) -> list[dict] | None:
    """The proof's steps, or None if its file is missing or not in step form."""
    try:
        parsed = json.loads(ledger.get_artifact(artifact))
    except (ArtifactCorrupt, FileNotFoundError, ValueError, KeyError):
        return None
    steps = parsed.get("steps") if isinstance(parsed, dict) else None
    if not isinstance(steps, list) or not steps:
        return None
    if not all(isinstance(s, dict) and isinstance(s.get("claim"), str) and isinstance(s.get("because"), str)
               and isinstance(s.get("lean", ""), str) for s in steps):
        return None
    return steps


def _checked_steps(checks: list[dict]) -> dict[str, dict]:
    """Passing step checks by declaration name, after failures of the same file and name cancel them."""
    key = lambda c: (c["artifact"], c["target_decl"])  # noqa: E731
    failed = {key(c) for c in checks if c["polarity"] == "step" and c["result"] == "fail"}
    passing: dict[str, dict] = {}
    for check in checks:
        if check["polarity"] == "step" and check["result"] == "pass" and key(check) not in failed:
            passing.setdefault(check["target_decl"], check)
    return passing


def _proof_section(ledger: Ledger, number: int, proof: dict, audits: list[tuple[int, dict]],
                   checked: dict[str, dict]) -> list[str]:
    lines = [f"## Proof {number}", "", f"Written by: {_text(proof.get('author_context', 'unknown'))}", ""]
    steps = _steps(ledger, proof["artifact"])
    if steps is None:
        lines += ["This proof is not in step form, so it is shown whole. Nothing in it is machine-checked.", "",
                  "**First unverified step:** the whole proof.", ""]
        try:
            lines += _quoted(ledger.get_artifact(proof["artifact"]).decode("utf-8", "replace")) + [""]
        except (ArtifactCorrupt, FileNotFoundError):
            lines += ["The stored proof file is not available.", ""]
    else:
        first = next((i for i, s in enumerate(steps, 1) if not s.get("lean") or s["lean"] not in checked), None)
        lines += [f"**First unverified step:** {first}." if first else
                  "**First unverified step:** none; Lean checked a declaration for every step. "
                  "Check below that each one says what its step says.", ""]
        for i, step in enumerate(steps, 1):
            check = checked.get(step.get("lean", "")) if step.get("lean") else None
            mark = " **(first unverified step)**" if i == first else ""
            lines += [f"{i}. {_text(step['claim'])}{mark}", "",
                      f"    Because: {_text(step['because'])}", ""]
            if check is None:
                lines += ["    Machine-checked: no.", ""]
                continue
            lines += [f"    Machine-checked: Lean proved {_text(check['target_decl'])}, local run. Its statement:", ""]
            target = _target_in(_stored_report(ledger, check), check["target_decl"])
            body = _indented(target.get("type")) if target else ["    The stored report is not available."]
            lines += ["    " + line for line in body] + [""]
    lines += [f"Proof file hash: `{_text(proof['artifact'])}`", ""]
    if audits:
        lines += ["Audits recorded for this proof (a label until signed):", ""]
        lines += [f"- event {seq}: {_text(a['result'])}, by {_text(a['auditor'])}" for seq, a in audits] + [""]
        lines += ["To approve or reject, sign the audit event that states your finding: `sign --event SEQ`.", ""]
    else:
        lines += ["No audit is recorded yet. To approve or reject, record an `informal_audit` event naming the proof "
                  "file hash above, then sign it: `sign --event SEQ`.", ""]
    return lines


def render_packet(ledger: Ledger, claim: str, env: dict | None = None) -> str:
    events = ledger.read()
    status = derive_status(events, claim, env or {})
    usable, _ = usable_events(events, claim)
    checks = [e["data"] for e in usable if e["kind"] == "check"]

    lines = [f"# Review packet: claim {_text(claim)}", "",
             f"**Headline:** `{status['headline']}`", "", f"**Verdict:** {status['verdict']}", ""]
    lines += ["## Intended statement", ""] + _quoted(status["statement"] or "No statement is recorded.") + [""]

    kernel_passed = status["axes"]["kernel"] in ("passed-local", "judged") and status["headline"] != "conflict"
    if kernel_passed:
        lines += ["## What you are asked", "",
                  "Lean's kernel accepted a proof, so the steps need no reading. Lean cannot tell whether the "
                  "statement it checked says what was intended. Compare the intended statement above with the "
                  "statement below, in its explicit form, and with every local definition it uses.", ""]
        if status["axes"]["kernel"] == "passed-local":
            lines += ["The authoritative judge has not confirmed this check; it is a local run.", ""]
        # Only checks of the claim or its negation: a step lemma listed here could pass for the proof.
        lines += _proved_section(ledger, [c for c in checks if c["polarity"] != "step"])
        fidelity = [e["seq"] for e in usable if e["kind"] == "fidelity"]
        lines += ["To record your answer, sign the fidelity judgment that states it: "
                  + (f"events {', '.join(map(str, fidelity))}." if fidelity else "none is recorded yet."), ""]
        return "\n".join(lines)

    proofs = [e["data"] for e in usable if e["kind"] == "informal_proof"]
    lines += ["## What you are asked", "",
              "No proof of this claim has passed Lean's kernel, so you are the check. Read each step and its "
              "justification, and find the first step that does not follow.", "", APPROVAL_CEILING, ""]
    if not proofs:
        return "\n".join(lines + ["No informal proof is recorded for this claim, so there is nothing to review yet.", ""])
    checked = _checked_steps(checks)
    for number, proof in enumerate(proofs, 1):
        audits = [(e["seq"], e["data"]) for e in usable
                  if e["kind"] == "informal_audit" and e["data"]["proof_hash"] == proof["artifact"]]
        lines += _proof_section(ledger, number, proof, audits, checked)
    return "\n".join(lines)
