# Changelog

## Unreleased

- Added Example 6 and eval case `optimization-003`: the $O(1/k)$ rate of gradient descent for convex $L$-smooth functions on a real Hilbert space (Nesterov, Thm 2.1.14), machine-checked in Lean from Mathlib's definitions alone. The formal proof shows the minimizer hypothesis is unnecessary.
- `validate_evals.py` now accepts Lean names ending in a prime (e.g. `gd_rate'`).
- Added `scripts/run_benchmark.py` and the first results (`evals/results/`): Haiku and Sonnet, with and without the skill, score 19–21/21. The set is too easy to show an effect, and the skill made Haiku over-strict on two valid proofs.
- Corrected `logic-002` and `analysis-002` from `INCOMPLETE` to `INVALID`: both claims are refuted by a counterexample, which the skill's own verdict definitions classify as `INVALID`.
- Packaged as a Claude Code plugin (`.claude-plugin/`): `/plugin install mathproof-skill --marketplace Ztang-Yit-Xiaang/mathproof-skill`.
- Added a project website (`docs/`, GitHub Pages) with a social preview image.
- README and examples use GitHub math delimiters (`$`, `$$`) so formulas render.

## 0.2.0 — 2026-10-21

- Added Lean 4 / Mathlib machine checking as a workflow step, with a protocol in `skill/references/lean-verification.md`: statement-first formalization, a fidelity table, encoding traps (junk values, coercions, bundled Mathlib definitions), and four Lean statuses (`LEAN-CHECKED`, `LEAN-CHECKED (partial)`, `LEAN-FAILED`, `NOT FORMALIZED`).
- Added `skill/scripts/lean_check.py`: compiles a file, rejects `sorry`, custom axioms, `native_decide`, and kernel-bypassing options, audits every declaration's axioms, and prints elaborated statements for fidelity review. `--init` scaffolds a pinned Mathlib project.
- Added a Lean project (`lean/`, Lean v4.32.0, Mathlib v4.32.0) that machine-checks all 20 evaluation cases: proofs of the valid claims and formal refutations of the invalid ones.
- Added an optional `lean` field to evaluation cases, validated by `scripts/validate_evals.py`; `scripts/check_lean_evals.py` runs the checker on every linked case.
- Added regression fixtures for the checker (`tests/lean_check/`) and a Lean CI workflow.
- Fixed the Lean snippet in `formal-logic-bridge.md`, which did not compile: Mathlib's `Even n` unfolds to `n = r + r`, not `n = 2 * r`.
- Added Example 5, a Lean-checked refutation.

## 0.1.0 — 2026-08-12

- Introduced `PROVE`, `AUDIT`, `EXPLAIN`, and `RESEARCH` modes.
- Added an explicit assumption ledger and five-level verdict system.
- Added first-failure localization and the challenged-step protocol.
- Added domain checks for analysis, linear algebra, optimization, probability, and approximation.
- Made literature search conditional and source-aware.
- Added examples and an initial adversarial evaluation suite.
