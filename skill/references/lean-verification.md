# Lean Verification Protocol

Lean 4 with Mathlib is the skill's machine checker. A proof or refutation counts as machine-checked only when the bundled checker (`scripts/lean_check.py`) passes and the formal statement has been shown to match the informal claim. Either half alone is worthless: a compiled proof of the wrong statement verifies nothing.

## 1. When to run Lean

Run Lean by default whenever a Lean toolchain is reachable and the claim is expressible in Mathlib:

- `PROVE`: formalize the final claim and prove it.
- `AUDIT`: formalize the claim, and formalize the challenged or first-failing step as a lemma from the facts available before it (the challenged-step protocol, made formal).
- Refutations in any mode: formalize the counterexample as a proof of `¬ Claim`.
- `EXPLAIN` and `RESEARCH`: only on request, or to confirm a surprising step or a cited theorem's exact hypotheses.

Skip Lean, and say so with a reason, when the statement depends on objects Mathlib lacks, when faithful formalization would take disproportionate effort for the user's purpose, or when no toolchain is available. Never imply machine checking that did not happen.

## 2. Locate or create the Lean project

1. If the working directory, or a parent, contains `lakefile.toml` or `lakefile.lean` with Mathlib, use it.
2. Otherwise use `$MATHPROOF_LEAN_PROJECT` or `~/.mathproof/lean` (the repository's installer links the latter to its `lean/` project). The checker falls back to these automatically, so a file anywhere can be checked against them; keep scratch files in your scratch directory, not in the shared project.
3. Otherwise create a scratch project once and reuse it:
   ```bash
   python3 <skill-dir>/scripts/lean_check.py --init <scratch-dir>/proofcheck
   ```
   This pins Lean and Mathlib to the versions the skill is tested against and downloads the Mathlib cache (several GB, one time). Ask the user before the first download.

Put each formalization in its own file inside the project. Start every file with `import Mathlib` unless a narrower import is known to suffice.

## 3. Write the statement first, then check fidelity

Write the Lean statement before attempting any proof, and compare it with the informal claim **before** proving anything. Give the claim a name with `def Claim : Prop := ...` when the target is a refutation, so the checker prints its full body.

Produce a fidelity table for every formalization the user sees:

| Informal | Lean | Match |
| --- | --- | --- |
| "every even integer" | `∀ n : ℤ, Even n → …` | exact |
| "on an interval" | `Set.Ioo (-2) (-1)` | instance (one interval suffices to refute) |
| "strongly convex" | `StrictConvexOn ℝ univ f` | weaker hypothesis on `ℝ` only — partial |

Classify the formalization:

- `faithful`: same objects, quantifiers, hypotheses, and conclusion, up to standard Mathlib encodings.
- `instance`: a specific case of the claim. This is enough to refute a universal claim and never enough to prove it.
- `partial`: a strict special case (fewer dimensions, extra hypotheses, simple graphs only, …). It supports the informal verdict only for that scope.
- `unfaithful`: anything else. Fix it; do not report a check of an unfaithful statement.

### Encoding traps that silently change meaning

- **Junk values.** In Lean `x / 0 = 0`, `Real.sqrt` of a negative number is `0`, `Real.log 0 = 0`, `deriv f x = 0` where `f` is not differentiable, and `ℕ` subtraction truncates (`2 - 5 = 0`). A statement that hits a junk value may be "true" for the wrong reason. Add the side conditions (`x ≠ 0`, `0 ≤ x`, `DifferentiableAt ℝ f x`) or index around them (`1 / (n + 1)` instead of `1 / n`).
- **Wrong number type.** `ℕ`, `ℤ`, `ℚ`, `ℝ` differ in division, subtraction, and order. Make coercions explicit (`(n : ℝ)`).
- **Missing or extra hypotheses.** Every informal hypothesis must appear; no hypothesis may be added silently. An added hypothesis turns `faithful` into `partial`.
- **Vacuous hypotheses.** Contradictory hypotheses prove any conclusion, and Lean will accept the proof. When a statement has added or nonstandard hypotheses, prove a witness `∃ x, hyp₁ x ∧ … ∧ hypₖ x` in the same file. Watch empty index types too: over `Fin 0`, every matrix is both zero and invertible.
- **Quantifier order and scope.** `∀ ε, ∃ δ` versus `∃ δ, ∀ ε`; check that every variable is bound where the informal claim binds it.
- **Mathlib definitions that bundle extra content.** `Matrix.PosSemidef` includes Hermitian (symmetric over `ℝ`); `SimpleGraph` excludes loops and multi-edges; `IsMinOn f s x` does not require `x ∈ s`; `Continuous` is global while `ContinuousOn f s` is not. Read the definition when unsure (`#print`, or grep the Mathlib source).
- **Open versus closed sets.** `Set.Ioo`, `Set.Icc`, `Set.Ico` are different claims.
- **Auto-bound implicits.** Keep `autoImplicit false` (the provided project sets it) so a typo cannot become a new universally quantified variable.
- **Notation shadowing.** Do not define local notation or instances that change the meaning of standard symbols.

## 4. Prove

Iterate with fast, single-file compilation:

```bash
cd <project> && lake env lean path/to/File.lean
```

Useful automation, roughly in order: `simp`, `norm_num`, `ring`, `field_simp`, `linarith`, `nlinarith`, `positivity`, `omega`, `decide` (small decidable goals only), `fun_prop`, `aesop`, `gcongr`. To find a lemma, use `exact?` / `apply?` / `simp?` / `rw?` in the file, or grep the Mathlib source under `<project>/.lake/packages/mathlib/Mathlib`, and read the lemma's exact hypotheses before relying on it.

Rules:

- Never use `sorry`, `admit`, `axiom`, `native_decide`, `implemented_by`, `extern`, `unsafe`, or `set_option debug.skipKernelTC`. The checker rejects all of them.
- Never weaken, specialize, or alter the statement to make a proof go through. If the statement must change, stop, record the change in the fidelity table, and reclassify (`partial`, or `unfaithful`).
- Prefer short named lemmas mirroring the informal dependency map, so the Lean file doubles as the dependency audit.
- For a refutation, prove `¬ Claim` by exhibiting the witness and discharging every hypothesis on it. A counterexample whose hypotheses were not checked in Lean is not machine-checked.
- Budget: if roughly five focused attempts make no progress on a goal, stop and report that goal as the remaining obligation rather than looping.

## 5. Check

```bash
python3 <skill-dir>/scripts/lean_check.py path/to/File.lean --require <main declaration>
```

The checker passes only if the file compiles with no errors, no declaration uses `sorry`, every declaration in the file depends only on `propext`, `Classical.choice`, and `Quot.sound`, no forbidden construct appears outside comments, and each `--require`d declaration exists. It prints every declaration's elaborated type (and the body of each `Prop`-valued definition) for the fidelity comparison. Read that output; do not rely on the source text alone.

Exit status `0` is the only acceptable result. Treat anything else as not machine-checked.

## 6. Report

Attach a `Lean verification` block to the verdict:

1. `Lean status`, exactly one of:
   - `LEAN-CHECKED` — the checker passed and the formalization is `faithful` (or `instance`, for a refutation).
   - `LEAN-CHECKED (partial: <scope>)` — the checker passed for a `partial` formalization.
   - `LEAN-FAILED` — attempted but not completed; name the remaining goal or error.
   - `NOT FORMALIZED` — not attempted; give the reason.
2. `File` and the main declaration name(s).
3. `Checker output`: the PASS line and the main declaration's type and axioms.
4. The fidelity table.

How the Lean status interacts with the verdict:

- A `LEAN-CHECKED` proof of a `faithful` statement supports `VALID` for the **claim**. In `AUDIT` mode it does not validate the user's argument; only formalizing the user's own steps does that.
- A `LEAN-CHECKED` proof of `¬ Claim` supports `INVALID`.
- `LEAN-FAILED` does not by itself mean the claim is false. Keep the informal verdict, and downgrade to `UNVERIFIED` if the informal argument depended on the step Lean could not close.
- Any disagreement between Lean and the informal analysis is decided by finding the error, never by trusting either side by default; a passing check of a faithful statement outranks an informal argument.

## 7. Trust boundary

A checker pass establishes that Lean's kernel accepted the proof using only the standard axioms, relative to the pinned Mathlib. It does not establish that the formal statement means what the user meant (that is the fidelity table's job), that Mathlib's definitions match the user's conventions, or that the Lean toolchain itself is bug-free.
