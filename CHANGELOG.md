# Changelog

## Unreleased

- Added `INVESTIGATE` mode ([investigate.md](skill/references/investigate.md)): a durable record of one claim. `skill/scripts/mathproof.py` keeps an append-only ledger, runs Lean checks through the checker, derives each claim's status, re-runs every check with `verify`, and renders a report. No record carries a status. At this stage the strongest result is `kernel-passed-local`, with the verdict `UNVERIFIED`, and nothing an agent writes can raise it. The other modes are unchanged and don't need any of this.
- Checker 2.5: a killed or crashed Lean now exits `2` instead of reporting a failure.
- Corrected `logic-001`, `analysis-001`, and `sets-001` from `instance` to `faithful`. Their Lean statements negate the whole claim, and `instance` means a specific case of it. Verdicts are unchanged.
- `run_benchmark.py` now records the hash of the skill text, and no longer reuses a `skill` answer produced with different text. So a rerun re-asks those cases, which costs model calls.

## 0.2.2 — 2026-11-05

- **Fixed a false `PASS` in the Lean checker.** `lean_check.py` could report `PASS`, exit 0, for files that "proved" `1 = 2` and `False`. The README, site, and protocol said such files were rejected, and that was wrong. The defects:
  - **Forged audit.** The old checker appended its audit to a copy of the file and parsed the file's own output. A file could add an axiom with `run_cmd` and `addDecl`, which the source scan does not see, use it to prove `(1 : Nat) = 2`, print its own `@@MPS_DECL` line claiming only `propext`, and stop with `#exit` so the real audit never ran.
  - **Kernel check switched off.** A file could set `debug.skipKernelTC` with `withOptions` and an option name built by `Name.mkStr`. The source scan removes string literals before searching, so it did not see the option, and nothing replayed the declarations afterward. This gave `false_thm : False` with `axioms: none`.
  - **Hidden axiom.** Internal-looking names were skipped by the audit, so an unused axiom named `_hidden_axiom` passed.
  - **Misleading statements.** The file's own notation applied when statements were printed, so a theorem of `True` could print as `main_theorem : False`.
  - **Weak `axiom` scan.** The source scan matched the keyword only at the start of a line. The audit still caught such axioms when they were used by a declaration.

  None of the 22 eval files uses these constructs. All 22 pass the hardened checker with identical names, types, axioms, and definitions. If you rely on a result checked with an earlier version, re-run the new checker on that file.
- The checker now has five stages, all of which must pass:
  - **Source scan:** Lean's own parser reports the header, so the script cannot disagree with Lean about it.
  - **Packages:** each package in `lake-manifest.json` must come from its official repository and be at its recorded commit with no edited files.
  - **Compile:** the untouched file compiles in its own temporary directory.
  - **Audit:** separate processes (`lean_audit.lean`) do the work. One imports the compiled file with extensions off, so its initializers do not run, and uses Lean's `collectAxioms`. Another prints statements from an environment holding only the file's imports. It audits internal declarations too and requires the real core axioms. Imported modules must load from the toolchain or `.lake/packages` and belong to the real library, which stops a fake `Mathlib.Evil`.
  - **Replay:** `leanchecker` re-checks the compiled file with the kernel.
- Statements now print without the file's own notation. New `statement_uses` and `statement_context` report fields show every definition from the file that a statement depends on, including private ones, and including instances hidden inside a definition such as `def Claim`.
- **Behavior changes:** files importing anything other than the real Lean and Mathlib libraries now fail, as do `prelude` and `module` files. This includes a project's own lemma files, and direct imports of Batteries or Aesop modules that `import Mathlib` does not include. A project whose packages have edited files, or come from anywhere other than their official repositories, now fails, including a Mathlib fork. `autoImplicit` is now off during checks, which the protocol already claimed. A toolchain without `leanchecker` or `lean --deps-json` now exits `2`. Checks take longer, because Mathlib is loaded four times.
- Each declaration now also prints an `explicit:` line, because notation can hide an inline instance (`2 + 2 = 5`) or a numeric type (`1 = 2` in `Fin 1`). Printing can no longer be suppressed by metadata, and control characters in names are escaped so a name cannot forge report lines. `--require` now needs at least one required declaration to be a theorem.
- Known issue: the checker's output can be long, because it prints every definition a statement depends on. The README records this as a problem to solve.
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
