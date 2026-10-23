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
| `lean` | Optional. Machine-checked formalization; see below |

The benchmark mixes invalid (14) and valid (8) arguments, so a model cannot score well by rejecting everything. It has no `CONDITIONALLY VALID` or `INCOMPLETE` cases yet; contributions of those, and of harder cases in general, are especially welcome.

## Running models

`scripts/run_benchmark.py` sends every case to a model with and without the skill's instructions and scores the verdict and first bad step. Results and every raw answer are in [`results/`](results/README.md). On the first 21 cases, current models already scored 19–21/21 either way, so this set is too easy to show the skill's effect on informal verdicts.

## Lean formalizations

The optional `lean` object links a case to a file under `lean/`:

| Key | Meaning |
| --- | --- |
| `file` | Path from the repository root, e.g. `lean/MathProofSkill/Evals/Logic001.lean` |
| `declarations` | Names the checker must find (the main theorem, refutation, or witness facts) |
| `formalization` | `faithful`, `instance` (a specific case; refutations only), or `partial` (a strict special case) |
| `scope_note` | What the formalization covers or leaves out; required for `partial` |

`validate_evals.py` checks that the file exists and declares every listed name. `check_lean_evals.py` compiles each file and runs the axiom audit:

```bash
python3 scripts/check_lean_evals.py        # all cases
python3 scripts/check_lean_evals.py logic-001 linear-002
```

Every case currently has a passing formalization. A `VALID` case may not use an `instance` formalization.

## Suggested scoring

- verdict accuracy;
- first-error localization accuracy, conditional on an invalid or incomplete case;
- missing-assumption identification;
- counterexample validity;
- false-rejection rate on `VALID` cases.

Use exact-match scoring only for IDs, verdicts, and step numbers. Grade free-text diagnoses semantically and verify every generated counterexample independently.
