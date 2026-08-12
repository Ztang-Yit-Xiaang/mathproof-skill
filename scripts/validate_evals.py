#!/usr/bin/env python3
"""Validate the JSONL evaluation manifest without third-party dependencies."""

from __future__ import annotations

import json
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


def main() -> None:
    errors: list[str] = []
    seen: set[str] = set()
    total = 0

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
        extra = set(case) - REQUIRED
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

    if errors:
        raise SystemExit("Evaluation validation failed:\n- " + "\n- ".join(errors))
    print(f"Validated {total} evaluation cases with {len(seen)} unique IDs.")


if __name__ == "__main__":
    main()
