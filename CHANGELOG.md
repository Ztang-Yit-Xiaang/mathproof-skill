# Changelog

## Unreleased

- **Fixed a false `PASS` in the Lean checker.** `lean_check.py` could report `PASS` for a proof of `1 = 2` or `False`: a file could print a forged audit line and stop with `#exit`, or switch off the kernel check through an option name built from strings. The README, site, and protocol said such files were rejected, and that was wrong. None of the 22 eval files uses these constructs, and all still pass the hardened checker. Results checked with an earlier version rested on the old, weaker check.
- The checker now compiles the untouched file in its own temporary directory, audits the compiled file as data in a separate process (`lean_audit.lean`), and replays it through `leanchecker`. It audits internal declarations too, requires the real core axioms, and prints statements without the file's own notation. A new `statement_uses` report field lists the file's constants in each statement.
- **Behavior changes:** files importing anything other than Lean, Mathlib, and Mathlib's dependencies now fail, as do `prelude` and `module` files. `autoImplicit` is now off during checks, which the protocol already claimed. A toolchain without `leanchecker` now exits `2`. Checks take longer, because Mathlib is loaded three times.
- `lean-verification.md` now states the checker's threat model. It is a local check and is not adversarially sound: compiling a Lean file runs its code as you.

- Added an assumption cost audit to the skill. Every stated or added assumption is now checked for consistency, circularity, collapse of the class, unnecessary strength, downstream fit, and quantitative cost. `CONDITIONALLY VALID` now requires a repair that passes the audit, so a vacuous or circular repair no longer earns it.
- Hard-to-reach conditions (unverifiable a priori bounds, exact constants, assumed minimizers, unquantified "n large") are now treated as defects: the skill tries to drop them, derive them, or replace them with checkable conditions, and labels any that remain.
- Added the assumption harm battery (`adversarial-proof-auditing.md` §6) and a vacuous-hypotheses trap to the Lean protocol: when hypotheses are added, prove a non-vacuity witness.
- Added Example 7 and eval case `linear-004`. The tempting repair for "$A^2=0 \implies A=0$" is invertibility, and it is vacuous; symmetry is the repair that works. All three facts are machine-checked in Lean.

## 0.2.1 — 2026-10-22

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
