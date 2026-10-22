import Mathlib

/-!
# linear-002 — PSD square root

Informal claim: every real symmetric PSD matrix has a real symmetric PSD square root.
Expected verdict: `VALID`. In Mathlib, `PosSemidef` over `ℝ` already includes symmetry
(`IsHermitian`, which over `ℝ` is `Aᵀ = A`), so the conclusion `B.PosSemidef` covers both
"symmetric" and "PSD".
-/

namespace MathProofSkill.Evals.Linear002

open Matrix MatrixOrder

theorem exists_psd_sqrt {n : Type*} [Fintype n] [DecidableEq n]
    (A : Matrix n n ℝ) (hA : A.PosSemidef) :
    ∃ B : Matrix n n ℝ, B.PosSemidef ∧ B * B = A :=
  ⟨CFC.sqrt A, (CFC.sqrt_nonneg A).posSemidef, CFC.sqrt_mul_sqrt_self A hA.nonneg⟩

end MathProofSkill.Evals.Linear002
