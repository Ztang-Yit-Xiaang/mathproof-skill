import Mathlib

/-!
# analysis-001 — Bounded is not compact

Informal claim: every continuous function on `(0, 1)` attains a maximum. Expected verdict:
`INVALID`. Counterexample: `f x = x`.
-/

namespace MathProofSkill.Evals.Analysis001

open Set

def Claim : Prop :=
  ∀ f : ℝ → ℝ, ContinuousOn f (Ioo 0 1) → ∃ x ∈ Ioo (0 : ℝ) 1, IsMaxOn f (Ioo 0 1) x

theorem claim_false : ¬ Claim := by
  intro h
  obtain ⟨x, ⟨hx0, hx1⟩, hmax⟩ := h id continuousOn_id
  have hy : (x + 1) / 2 ∈ Ioo (0 : ℝ) 1 := ⟨by linarith, by linarith⟩
  have : (x + 1) / 2 ≤ x := hmax hy
  linarith

end MathProofSkill.Evals.Analysis001
