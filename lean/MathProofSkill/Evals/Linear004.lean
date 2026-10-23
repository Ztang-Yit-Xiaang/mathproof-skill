import Mathlib

/-!
# linear-004 — Square-zero matrix, and a repair that hurts

Informal claim: every real square matrix `A` with `A^2 = 0` is the zero matrix.
Expected verdict: `INVALID`, refuted by `!![0, 1; 0, 0]`.

The proof's step 2 multiplies by `A⁻¹`, which suggests the repair "assume `A` invertible".
`invertible_repair_vacuous` shows that repair is vacuous: for a nonempty index type, no
invertible `A` has `A * A = 0`. (Over an empty index type `Matrix n n ℝ` is the zero ring, where
every matrix is both zero and invertible, hence the `Nonempty n` hypothesis.)
`symmetric_repair` is the repair that works: `Aᵀ A = A A = 0` forces `A = 0`.
-/

namespace MathProofSkill.Evals.Linear004

open Matrix

theorem claim_false : ¬ ∀ A : Matrix (Fin 2) (Fin 2) ℝ, A * A = 0 → A = 0 := by
  intro h
  let A : Matrix (Fin 2) (Fin 2) ℝ := !![0, 1; 0, 0]
  have hmul : A * A = 0 := by
    ext i j
    fin_cases i <;> fin_cases j <;> norm_num [A, mul_apply, Fin.sum_univ_two]
  have hzero : A = 0 := h A hmul
  have h1 : A 0 1 = 0 := by rw [hzero]; rfl
  revert h1
  norm_num [A]

theorem invertible_repair_vacuous {n : Type*} [Fintype n] [DecidableEq n] [Nonempty n]
    (A : Matrix n n ℝ) (hA : IsUnit A) : A * A ≠ 0 :=
  (hA.mul hA).ne_zero

theorem symmetric_repair {n : Type*} [Fintype n] [DecidableEq n]
    (A : Matrix n n ℝ) (hsym : Aᵀ = A) (h : A * A = 0) : A = 0 := by
  rw [← Matrix.conjTranspose_mul_self_eq_zero]
  have hconj : Aᴴ = A := by
    ext i j
    simp [Matrix.conjTranspose, hsym]
  rw [hconj, h]

end MathProofSkill.Evals.Linear004
