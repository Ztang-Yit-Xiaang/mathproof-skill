# MathProof Red Team v0.1.0

First experimental release of a correctness-first AI skill for constructing, explaining, researching, and adversarially auditing mathematical proofs.

## Highlights

- Four modes: `PROVE`, `AUDIT`, `EXPLAIN`, and `RESEARCH`
- First-unsupported-step localization
- Challenged-step protocol that forbids downstream facts from rescuing an earlier gap
- Explicit assumption ledger
- Five calibrated verdicts
- Domain checks for analysis, linear algebra, optimization, probability, and asymptotics
- Human-readable examples and an initial adversarial evaluation suite

## Important boundary

This project is not a formal theorem prover and does not guarantee correctness. It provides a structured informal audit intended to reduce hidden logical errors and make uncertainty explicit.

## Try it

Ask your agent:

```text
Use @mathproof-red-team in AUDIT mode. Identify the first unsupported
step and do not repair the proof until after giving a verdict.
```
