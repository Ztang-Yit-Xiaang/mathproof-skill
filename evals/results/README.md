# Benchmark results

Run on 2026-10-22 with `python3 scripts/run_benchmark.py --model haiku --model sonnet` (Claude Haiku 5.5 and Sonnet 5.5 via `claude -p`).

Each case's claim and numbered proof steps go to the model in an isolated session: no user settings, CLAUDE.md, skills, MCP servers, or tools. The `skill` condition appends `skill/SKILL.md` to the system prompt; `baseline` does not. Tools are disabled in both, so **Lean is not run**: this measures the informal audit protocol alone. A case counts as correct when both the verdict and the first unjustified step (or `null`) match.

| Model | Condition | Verdict | First bad step | Both | False accepts |
| --- | --- | --- | --- | --- | --- |
| Haiku | baseline | 21/21 | 21/21 | **21/21** | 0 |
| Haiku | skill | 19/21 | 20/21 | **19/21** | 0 |
| Sonnet | baseline | 20/21 | 20/21 | **20/21** | 0 |
| Sonnet | skill | 21/21 | 21/21 | **21/21** | 0 |

A false accept is a `VALID` verdict on a case that should be rejected.

## What this shows

- **The benchmark is saturated.** Current models already get nearly every case right without the skill, so these 21 cases cannot measure the skill's effect on informal verdicts. Harder cases are needed: subtle hypothesis misuse, research-level claims, and proofs whose flaw sits several steps before the false conclusion.
- **The skill can make a small model over-strict.** With the skill, Haiku rejected two correct proofs: `topology-001` (it asked for detail in a standard open-cover step) and `probability-002` (it read "linear" as also requiring homogeneity). The cost of extra skepticism is visible even on easy cases.
- **The one baseline miss** is Sonnet on `optimization-002`. It objected that step 3 attaches "strict inequality" to the wrong expression, which is a fair reading of an ambiguous step.
- What the benchmark does not exercise is the Lean layer, which is the part that turns a verdict into a checked result. All 21 cases are separately formalized and checked in CI (`scripts/check_lean_evals.py`).

## Label corrections made during this run

All four runs answered `INVALID` on `logic-002` and `analysis-002`, where the expected label was `INCOMPLETE`. By the skill's own definitions, `INVALID` means "a counterexample defeats the claim" and `INCOMPLETE` means "the claim may be true". Both claims are false: `logic-002`'s Lean file proves `claim_false`, and `analysis-002` records a counterexample. The labels were corrected to `INVALID` before scoring. Under the old labels, the totals were 19, 17, 18 and 19.

## Files

- `summary.json`: per-case scores for every run.
- `raw/<model>/<condition>/<id>.txt`: every model answer, unedited.
