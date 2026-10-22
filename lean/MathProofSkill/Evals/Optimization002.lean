import Mathlib

/-!
# optimization-002 — Stationary points of strongly convex functions

Informal claim: a stationary point of a differentiable strongly convex function is its unique
global minimizer. Expected verdict: `VALID`.

Formalization scope: **one real variable**, with strong convexity weakened to *strict*
convexity (strong convexity implies strict convexity, so this proves a stronger statement on
`ℝ`). The informal claim on `ℝⁿ` is not covered by this file.
-/

namespace MathProofSkill.Evals.Optimization002

open Set

/-- Convexity alone makes a stationary point a global minimizer. -/
theorem isMinOn_of_deriv_eq_zero {f : ℝ → ℝ} (hconv : ConvexOn ℝ univ f)
    (hd : Differentiable ℝ f) {x : ℝ} (hx : deriv f x = 0) : IsMinOn f univ x := by
  intro y _
  show f x ≤ f y
  rcases lt_trichotomy x y with hxy | rfl | hxy
  · have h := hconv.deriv_le_slope (mem_univ x) (mem_univ y) hxy (hd x)
    rw [hx, slope_def_field] at h
    have := (le_div_iff₀ (sub_pos.2 hxy)).mp h
    linarith
  · exact le_rfl
  · have h := hconv.slope_le_deriv (mem_univ y) (mem_univ x) hxy (hd x)
    rw [hx, slope_def_field] at h
    have := (div_le_iff₀ (sub_pos.2 hxy)).mp h
    linarith

/-- Strict convexity adds uniqueness. -/
theorem unique_min_of_deriv_eq_zero {f : ℝ → ℝ} (hconv : StrictConvexOn ℝ univ f)
    (hd : Differentiable ℝ f) {x : ℝ} (hx : deriv f x = 0) :
    IsMinOn f univ x ∧ ∀ y, IsMinOn f univ y → y = x := by
  have hmin := isMinOn_of_deriv_eq_zero hconv.convexOn hd hx
  refine ⟨hmin, fun y hy => ?_⟩
  by_contra hne
  have hmid := hconv.2 (mem_univ x) (mem_univ y) (Ne.symm hne)
    (by norm_num : (0 : ℝ) < 1 / 2) (by norm_num : (0 : ℝ) < 1 / 2) (by norm_num)
  have h1 := hmin (mem_univ ((1 / 2 : ℝ) • x + (1 / 2 : ℝ) • y))
  have h2 := hy (mem_univ x)
  simp only [smul_eq_mul, mem_setOf_eq] at hmid h1 h2
  linarith

end MathProofSkill.Evals.Optimization002
