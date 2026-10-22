import Mathlib

/-!
# logic-002 — One-sided biconditional

Informal claim: for integers `n`, `6 ∣ n ↔ 2 ∣ n`. Expected verdict: `INCOMPLETE`
(only the forward direction was argued, and the omitted converse is false).
We machine-check both facts: the forward direction holds, and the converse fails at `n = 2`.
-/

namespace MathProofSkill.Evals.Logic002

/-- The direction the proof does establish. -/
theorem forward (n : ℤ) (h : 6 ∣ n) : 2 ∣ n :=
  dvd_trans ⟨3, by norm_num⟩ h

/-- The omitted converse is false: `2 ∣ 2` but `¬ 6 ∣ 2`. -/
theorem converse_false : ¬ ∀ n : ℤ, 2 ∣ n → 6 ∣ n := by
  intro h
  have : (6 : ℤ) ∣ 2 := h 2 (dvd_refl 2)
  omega

/-- Hence the stated biconditional itself is false. -/
theorem claim_false : ¬ ∀ n : ℤ, 6 ∣ n ↔ 2 ∣ n :=
  fun h => converse_false fun n => (h n).mpr

end MathProofSkill.Evals.Logic002
