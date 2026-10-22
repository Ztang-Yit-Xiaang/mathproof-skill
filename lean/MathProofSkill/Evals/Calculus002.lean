import Mathlib

/-!
# calculus-002 — Extreme value theorem on `[0, 1]`

Informal claim: a continuous real-valued function on `[0, 1]` attains a maximum.
Expected verdict: `VALID`.
-/

namespace MathProofSkill.Evals.Calculus002

open Set

theorem attains_max (f : ℝ → ℝ) (hf : ContinuousOn f (Icc 0 1)) :
    ∃ x ∈ Icc (0 : ℝ) 1, IsMaxOn f (Icc 0 1) x :=
  isCompact_Icc.exists_isMaxOn (nonempty_Icc.mpr zero_le_one) hf

end MathProofSkill.Evals.Calculus002
