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

Keep the proof short enough that reviewers can independently determine the expected result. Cite a source in `notes` when the case depends on a non-elementary theorem.

## Review standard

A change should answer these questions:

1. Does the expected verdict follow from the stated assumptions?
2. For an invalid proof, is the recorded step truly the first failure?
3. Does a counterexample satisfy every hypothesis?
4. Is a proposed repair sufficient, and is it described as an added assumption rather than silently inserted?
5. Does the change avoid claiming that informal auditing guarantees correctness?

By contributing, you agree that your contribution may be distributed under the MIT License.
