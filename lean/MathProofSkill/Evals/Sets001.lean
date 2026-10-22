import Mathlib

/-!
# sets-001 — Bounded sets need not have a minimum

Informal claim: every nonempty bounded subset of `ℝ` has a minimum. Expected verdict:
`INVALID`. Counterexample: `S = (0, 1)`.
-/

namespace MathProofSkill.Evals.Sets001

open Set

def Claim : Prop :=
  ∀ S : Set ℝ, S.Nonempty → BddBelow S → BddAbove S → ∃ m ∈ S, ∀ y ∈ S, m ≤ y

theorem claim_false : ¬ Claim := by
  intro h
  obtain ⟨m, ⟨hm0, hm1⟩, hmin⟩ :=
    h (Ioo 0 1) (nonempty_Ioo.mpr zero_lt_one) bddBelow_Ioo bddAbove_Ioo
  have := hmin (m / 2) ⟨by linarith, by linarith⟩
  linarith

end MathProofSkill.Evals.Sets001
