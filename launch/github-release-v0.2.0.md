# MathProof Skill v0.2.0 — Lean machine checking

MathProof Skill now checks its results with **Lean 4 and Mathlib**. The reasoning stays informal, but a verdict can now carry a machine check, and the skill says exactly what was checked.

## Highlights

- **Lean step in the workflow.** The skill formalizes the claim, or its negation for a refutation. It compares the formal statement with the informal one in a fidelity table, proves it, and runs a checker before giving the verdict.
- **Lean status on every verdict:** `LEAN-CHECKED`, `LEAN-CHECKED (partial: …)`, `LEAN-FAILED`, or `NOT FORMALIZED`, each with a reason.
- **`skill/scripts/lean_check.py`.** A file passes only if it compiles, nothing uses `sorry`, and every declaration depends only on `propext`, `Classical.choice`, and `Quot.sound`. That rules out custom axioms and `native_decide`, and kernel bypasses are rejected. The checker prints each elaborated statement so it can be compared with the informal claim. `--init` sets up a pinned Mathlib project.
- **Traps the fidelity check covers:** junk values (`x / 0 = 0`, truncated `ℕ` subtraction, `deriv` of a non-differentiable function), number-type coercions, and Mathlib definitions that bundle extra content.
- **All 20 evaluation cases are machine-checked** in `lean/` (Lean v4.32.0, Mathlib v4.32.0). Valid claims are proved and invalid ones are formally refuted. Two are honestly marked `partial`.
- **Installer** (`scripts/install.sh`) for Claude Code, Codex, Antigravity (IDE and the `agy` CLI), and `~/.agents/skills`.
- **CI** builds the Lean project, checks every eval case, and runs the checker's own tests (including a `sorry` hidden behind a macro).
- **Fix:** the Lean snippet in `formal-logic-bridge.md` did not compile, because Mathlib's `Even n` unfolds to `n = r + r`.

## Important boundary

A passing Lean check confirms that Lean's kernel accepted the proof using only the standard axioms. It does not confirm that the formal statement means what you meant; the fidelity table covers that. In `AUDIT` mode, a Lean proof of the claim does not validate your argument unless your own steps were formalized.

## Install

```bash
git clone https://github.com/Ztang-Yit-Xiaang/mathproof-skill
cd mathproof-skill
(cd lean && lake exe cache get)   # one-time Mathlib download; requires elan
./scripts/install.sh
```

## Try it

```text
Use @mathproof-skill in AUDIT mode. Identify the first unsupported step,
give a verdict, and machine-check the verdict in Lean.
```
