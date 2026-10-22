import Mathlib

/-!
# linear-001 — Symmetric is not PSD

Informal claim: every real symmetric matrix is positive semidefinite. Expected verdict:
`INVALID`. Counterexample: the `1 × 1` matrix `[-1]`.
-/

namespace MathProofSkill.Evals.Linear001

open Matrix

def Claim : Prop :=
  ∀ A : Matrix (Fin 1) (Fin 1) ℝ, A.IsSymm → A.PosSemidef

theorem claim_false : ¬ Claim := by
  intro h
  have hA : (!![-1] : Matrix (Fin 1) (Fin 1) ℝ).IsSymm := by
    ext i j; fin_cases i; fin_cases j; rfl
  have hdiag : (0 : ℝ) ≤ (!![-1] : Matrix (Fin 1) (Fin 1) ℝ) 0 0 := (h _ hA).diag_nonneg
  norm_num at hdiag

end MathProofSkill.Evals.Linear001
