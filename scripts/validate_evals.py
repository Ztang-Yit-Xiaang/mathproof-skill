#!/usr/bin/env python3
"""Validate the JSONL evaluation manifest without third-party dependencies."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "cases.jsonl"
VERDICTS = {
    "VALID",
    "INVALID",
    "CONDITIONALLY VALID",
    "INCOMPLETE",
    "UNVERIFIED",
}
REQUIRED = {
    "id",
    "title",
    "domain",
    "claim",
    "proof_steps",
    "expected_verdict",
    "expected_first_bad_step",
    "missing_assumption",
    "counterexample",
    "notes",
}
OPTIONAL = {"lean"}
LEAN_KEYS = {"file", "declarations", "formalization", "scope_note"}
FORMALIZATIONS = {"faithful", "instance", "partial"}


def check_lean(line_number: int, verdict: object, lean: object) -> list[str]:
    """Check the optional `lean` block: the file exists and declares every listed name."""
    where = f"line {line_number}: lean"
    if not isinstance(lean, dict):
        return [f"{where} must be an object"]
    errors: list[str] = []
    if set(lean) != LEAN_KEYS:
        errors.append(f"{where} must have exactly the keys {sorted(LEAN_KEYS)}")
    kind = lean.get("formalization")
    if kind not in FORMALIZATIONS:
        errors.append(f"{where}.formalization must be one of {sorted(FORMALIZATIONS)}")
    if kind == "partial" and not lean.get("scope_note"):
        errors.append(f"{where}: a partial formalization needs a scope_note")
    if verdict == "VALID" and kind == "instance":
        errors.append(f"{where}: an instance cannot establish a VALID claim")
    note = lean.get("scope_note")
    if note is not None and not (isinstance(note, str) and note):
        errors.append(f"{where}.scope_note must be a nonempty string or null")
    decls = lean.get("declarations")
    if not isinstance(decls, list) or not decls or not all(isinstance(d, str) and d for d in decls):
        errors.append(f"{where}.declarations must be a nonempty string list")
        decls = []
    rel = lean.get("file")
    path = ROOT / rel if isinstance(rel, str) else None
    if path is None or not rel.startswith("lean/") or not path.is_file():
        errors.append(f"{where}.file {rel!r} does not exist under lean/")
        return errors
    source = path.read_text(encoding="utf-8")
    for d in decls:
        if not re.search(rf"^\s*(?:theorem|lemma|def|noncomputable def|abbrev)\s+{re.escape(d)}\b", source, re.M):
            errors.append(f"{where}: {rel} does not declare {d!r}")
    return errors


def main() -> None:
    errors: list[str] = []
    seen: set[str] = set()
    total = 0
    formalized = 0

    for line_number, raw in enumerate(CASES.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        total += 1
        try:
            case = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc}")
            continue

        missing = REQUIRED - set(case)
        extra = set(case) - REQUIRED - OPTIONAL
        if missing:
            errors.append(f"line {line_number}: missing fields {sorted(missing)}")
        if extra:
            errors.append(f"line {line_number}: unexpected fields {sorted(extra)}")

        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"line {line_number}: id must be a nonempty string")
        elif case_id in seen:
            errors.append(f"line {line_number}: duplicate id {case_id}")
        else:
            seen.add(case_id)

        steps = case.get("proof_steps")
        if not isinstance(steps, list) or not steps or not all(isinstance(x, str) and x for x in steps):
            errors.append(f"line {line_number}: proof_steps must be a nonempty string list")
            steps = []

        verdict = case.get("expected_verdict")
        if verdict not in VERDICTS:
            errors.append(f"line {line_number}: unsupported verdict {verdict!r}")

        bad_step = case.get("expected_first_bad_step")
        if bad_step is not None and (not isinstance(bad_step, int) or bad_step < 1 or bad_step > len(steps)):
            errors.append(f"line {line_number}: bad-step index is outside proof_steps")
        if verdict == "VALID" and bad_step is not None:
            errors.append(f"line {line_number}: VALID case cannot have a bad step")
        if verdict == "VALID" and (case.get("missing_assumption") is not None or case.get("counterexample") is not None):
            errors.append(f"line {line_number}: VALID case cannot record a gap or counterexample")
        if "lean" in case:
            errors.extend(check_lean(line_number, verdict, case["lean"]))
            formalized += 1

    if errors:
        raise SystemExit("Evaluation validation failed:\n- " + "\n- ".join(errors))
    print(f"Validated {total} evaluation cases with {len(seen)} unique IDs; {formalized} have Lean formalizations.")


if __name__ == "__main__":
    main()
