# Evaluation suite

`cases.jsonl` contains one self-contained proof-audit case per line.

## Fields

| Field | Meaning |
| --- | --- |
| `id` | Unique stable case identifier |
| `title` | Human-readable label |
| `domain` | Primary mathematical area |
| `claim` | Claim the proof attempts to establish |
| `proof_steps` | Ordered material steps; indexing starts at 1 |
| `expected_verdict` | One of the five skill verdicts |
| `expected_first_bad_step` | First false or unsupported step, or `null` |
| `missing_assumption` | Weak natural missing condition, or `null` |
| `counterexample` | Explicit counterexample, or `null` |
| `notes` | Short grading clarification |

The benchmark is intentionally balanced between invalid, conditionally valid, incomplete, and valid arguments. A useful model should not maximize error detection by rejecting everything.

## Suggested scoring

- verdict accuracy;
- first-error localization accuracy, conditional on an invalid or incomplete case;
- missing-assumption identification;
- counterexample validity;
- false-rejection rate on `VALID` cases.

Use exact-match scoring only for IDs, verdicts, and step numbers. Grade free-text diagnoses semantically and verify every generated counterexample independently.
