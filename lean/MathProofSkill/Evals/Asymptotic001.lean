import Mathlib

/-!
# asymptotic-001 — Approximation is not equality

Informal claim: `sin x = x` for all sufficiently small nonzero `x`. Expected verdict: `INVALID`.
For every `x > 0`, `sin x < x`, so no punctured neighbourhood of `0` works.
-/

namespace MathProofSkill.Evals.Asymptotic001

def Claim : Prop :=
  ∃ δ > (0 : ℝ), ∀ x : ℝ, x ≠ 0 → |x| < δ → Real.sin x = x

theorem claim_false : ¬ Claim := by
  rintro ⟨δ, hδ, h⟩
  have hx : (0 : ℝ) < δ / 2 := by linarith
  have heq := h (δ / 2) hx.ne' (by rw [abs_of_pos hx]; linarith)
  exact (Real.sin_lt hx).ne heq

end MathProofSkill.Evals.Asymptotic001
