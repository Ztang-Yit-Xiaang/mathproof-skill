import Mathlib

/-!
# calculus-001 — Positive derivative is not positivity

Informal claim: if `f' > 0` on an interval then `f > 0` there. Expected verdict: `INVALID`.
Counterexample: `f x = x` on `(-2, -1)`.
-/

namespace MathProofSkill.Evals.Calculus001

open Set

/-- The claim, instantiated on the interval `I = (-2, -1)`. -/
def Claim : Prop :=
  ∀ f : ℝ → ℝ, Differentiable ℝ f →
    (∀ x ∈ Ioo (-2 : ℝ) (-1), 0 < deriv f x) → ∀ x ∈ Ioo (-2 : ℝ) (-1), 0 < f x

theorem claim_false : ¬ Claim := by
  intro h
  have := h id differentiable_id (fun x _ => by simp) (-3 / 2) ⟨by norm_num, by norm_num⟩
  norm_num at this

end MathProofSkill.Evals.Calculus001
