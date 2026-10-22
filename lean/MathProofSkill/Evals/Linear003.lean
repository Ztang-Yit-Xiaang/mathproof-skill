import Mathlib

/-!
# linear-003 — PSD is not invertible

Informal claim: every PSD matrix is invertible. Expected verdict: `INVALID`.
Counterexample: the zero matrix.
-/

namespace MathProofSkill.Evals.Linear003

open Matrix

def Claim : Prop :=
  ∀ A : Matrix (Fin 1) (Fin 1) ℝ, A.PosSemidef → IsUnit A

theorem claim_false : ¬ Claim := by
  intro h
  have := (Matrix.isUnit_iff_isUnit_det _).mp (h 0 PosSemidef.zero)
  simp at this

/-- The natural repair: positive definite matrices are invertible. -/
theorem posDef_isUnit {n : Type*} [Fintype n] [DecidableEq n]
    (A : Matrix n n ℝ) (hA : A.PosDef) : IsUnit A :=
  hA.isUnit

end MathProofSkill.Evals.Linear003
