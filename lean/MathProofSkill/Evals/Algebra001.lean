import Mathlib

/-!
# algebra-001 — Division by zero

Informal claim: if `a = b` then `2 = 1`. Expected verdict: `INVALID`; the faulty step cancels
`a - b`, which the hypothesis forces to be `0`.
We machine-check that at `a = b = 1` every pre-cancellation equation holds, yet the cancelled
equation `a + b = b` is false — so the cancellation step is the first failure.
-/

namespace MathProofSkill.Evals.Algebra001

/-- At `a = b = 1`: `(a + b)(a - b) = b(a - b)` holds but `a + b = b` does not. -/
theorem cancellation_step_fails :
    ∃ a b : ℝ, a = b ∧ (a + b) * (a - b) = b * (a - b) ∧ a + b ≠ b :=
  ⟨1, 1, rfl, by norm_num, by norm_num⟩

/-- The correct cancellation law needs exactly the missing assumption `a - b ≠ 0`. -/
theorem cancel_of_ne {a b c : ℝ} (h : a - b ≠ 0) (hc : c * (a - b) = b * (a - b)) : c = b :=
  mul_right_cancel₀ h hc

end MathProofSkill.Evals.Algebra001
