# Contributing

Contributions should make the skill more reliable, not merely longer.

## Best contributions

- a minimal invalid proof with a precisely localized first failure;
- a valid proof that a skeptical auditor might falsely reject;
- a missing-assumption case with the weakest natural repair;
- a matrix, probability, optimization, or asymptotic reasoning trap;
- an improvement that removes duplicated instructions from `skill/SKILL.md`.

## Add an evaluation case

Add one JSON object to `evals/cases.jsonl`. Required fields are documented in `evals/README.md`. Then run:

```bash
python3 scripts/validate_evals.py
```

If the case is expressible in Mathlib, add a Lean file under `lean/MathProofSkill/Evals/`, import it from `lean/MathProofSkill/Evals.lean`, link it with the case's `lean` field, and run:

```bash
python3 scripts/check_lean_evals.py <case-id>
```

For an invalid claim, state it as `def Claim : Prop := …` and prove `¬ Claim`. Never use `sorry`, `axiom`, or `native_decide`; the checker rejects them. Explain any gap between the informal claim and the Lean statement in `scope_note`.

Keep the proof short enough that reviewers can independently determine the expected result. Cite a source in `notes` when the case depends on a non-elementary theorem.

## Review standard

A change should answer these questions:

1. Does the expected verdict follow from the stated assumptions?
2. For an invalid proof, is the recorded step truly the first failure?
3. Does a counterexample satisfy every hypothesis?
4. Is a proposed repair sufficient, and is it described as an added assumption rather than silently inserted?
5. Does the change avoid claiming that informal auditing guarantees correctness?
6. Does every Lean statement say what the informal case says, and is any difference recorded as `instance` or `partial`?

By contributing, you agree that your contribution may be distributed under the MIT License.
