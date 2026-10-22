import Mathlib

/-!
# optimization-003 — The `O(1/k)` rate of gradient descent

Informal claim (Nesterov, *Lectures on Convex Optimization*, Thm 2.1.14). Let `E` be a real
Hilbert space and `f : E → ℝ` convex and differentiable with `L`-Lipschitz gradient, `L > 0`,
with a minimizer `x⋆`. Gradient descent with step `1/L`,

  `x (k+1) = x k - (1/L) ∇f (x k)`,

satisfies `f (x k) - f x⋆ ≤ L ‖x 0 - x⋆‖² / (2k)` for every `k ≥ 1`. Expected verdict: `VALID`.

The formal proof shows more: **the minimizer hypothesis is never used.** The bound holds for
*every* reference point `x⋆ : E`; minimality is only needed to read `f (x k) - f x⋆` as the
optimality gap. The theorems below therefore omit it, which makes them strictly stronger.

Nothing is assumed beyond Mathlib's definitions: the descent lemma and the first-order
convexity inequality are proved here from `LipschitzWith L (∇ f)` and `ConvexOn ℝ univ f`.

Fidelity note: Lean has `a / 0 = 0`, so the bound is first proved in the division-free form
`k (f (x k) - f x⋆) ≤ L/2 ‖x 0 - x⋆‖²`, which is meaningful for every `k`, and the familiar
form is derived only for `0 < k`.
-/

namespace MathProofSkill.Evals.Optimization003

open Set
open scoped RealInnerProductSpace NNReal Gradient

variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [CompleteSpace E]

/-- The derivative of `f` along the line `t ↦ x + t • d` is `⟪∇f (x + t • d), d⟫`. -/
lemma hasDerivAt_line {f : E → ℝ} (hf : Differentiable ℝ f) (x d : E) (t : ℝ) :
    HasDerivAt (fun s : ℝ => f (x + s • d)) ⟪∇ f (x + t • d), d⟫ t := by
  have hl : HasDerivAt (fun s : ℝ => x + s • d) d t := by
    simpa using ((hasDerivAt_id t).smul_const d).const_add x
  have := (hf (x + t • d)).hasGradientAt.hasFDerivAt.comp_hasDerivAt t hl
  simpa [Function.comp_def, InnerProductSpace.toDual_apply_apply] using this

/-- **Descent lemma.** An `L`-Lipschitz gradient gives the quadratic upper bound. -/
theorem descent_lemma {f : E → ℝ} {L : ℝ≥0} (hf : Differentiable ℝ f)
    (hL : LipschitzWith L (∇ f)) (x y : E) :
    f y ≤ f x + ⟪∇ f x, y - x⟫ + L / 2 * ‖y - x‖ ^ 2 := by
  set d := y - x with hd
  -- φ(t) = f(x + t d) - t ⟪∇f x, d⟫ - (L/2) t² ‖d‖² is antitone on [0, 1].
  set φ : ℝ → ℝ := fun t => f (x + t • d) - t * ⟪∇ f x, d⟫ - L / 2 * t ^ 2 * ‖d‖ ^ 2 with hφdef
  have hφ : ∀ t, HasDerivAt φ (⟪∇ f (x + t • d), d⟫ - ⟪∇ f x, d⟫ - L * t * ‖d‖ ^ 2) t := by
    intro t
    have h1 := hasDerivAt_line hf x d t
    have h2 := (hasDerivAt_id t).mul_const ⟪∇ f x, d⟫
    have h3 := ((hasDerivAt_pow 2 t).const_mul ((L : ℝ) / 2)).mul_const (‖d‖ ^ 2)
    exact ((h1.sub h2).sub h3).congr_deriv
      (by rw [show (2 : ℕ) - 1 = 1 from rfl, pow_one]; push_cast; ring)
  have hanti : AntitoneOn φ (Icc 0 1) := by
    apply antitoneOn_of_hasDerivWithinAt_nonpos (convex_Icc 0 1)
    · exact fun t _ => (hφ t).continuousAt.continuousWithinAt
    · exact fun t _ => (hφ t).hasDerivWithinAt
    · intro t ht
      rw [interior_Icc] at ht
      have hle : ⟪∇ f (x + t • d) - ∇ f x, d⟫ ≤ L * t * ‖d‖ ^ 2 :=
        calc ⟪∇ f (x + t • d) - ∇ f x, d⟫
            ≤ ‖∇ f (x + t • d) - ∇ f x‖ * ‖d‖ := real_inner_le_norm _ _
          _ ≤ (L * ‖(x + t • d) - x‖) * ‖d‖ := by
              gcongr
              exact hL.norm_sub_le _ _
          _ = L * t * ‖d‖ ^ 2 := by
              rw [add_sub_cancel_left, norm_smul, Real.norm_of_nonneg ht.1.le]
              ring
      rw [inner_sub_left] at hle
      linarith
  have h01 := hanti (left_mem_Icc.2 zero_le_one) (right_mem_Icc.2 zero_le_one) zero_le_one
  simp only [hφdef, one_smul, zero_smul, add_zero, one_mul, one_pow, zero_mul, sub_zero,
    ne_eq, OfNat.ofNat_ne_zero, not_false_eq_true, zero_pow, mul_zero] at h01
  rw [hd, add_sub_cancel] at h01
  linarith

/-- **First-order convexity.** A differentiable convex function lies above its tangent planes. -/
theorem convex_first_order {f : E → ℝ} (hf : Differentiable ℝ f) (hconv : ConvexOn ℝ univ f)
    (x y : E) : f x + ⟪∇ f x, y - x⟫ ≤ f y := by
  have hψ : ConvexOn ℝ univ (fun t : ℝ => f (x + t • (y - x))) := by
    have := hconv.comp_affineMap (AffineMap.lineMap x y)
    rw [preimage_univ] at this
    refine this.congr fun t _ => ?_
    simp [AffineMap.lineMap_apply_module', add_comm]
  have := hψ.le_slope_of_hasDerivAt (mem_univ 0) (mem_univ 1) zero_lt_one
    (hasDerivAt_line hf x (y - x) 0)
  simp only [slope_def_field, zero_smul, add_zero, one_smul, add_sub_cancel, sub_zero,
    div_one] at this
  linarith

section GradientDescent

variable {f : E → ℝ} {L : ℝ≥0} (hL0 : 0 < L) (hf : Differentiable ℝ f)
  (hL : LipschitzWith L (∇ f)) (x : ℕ → E)
  (hx : ∀ k, x (k + 1) = x k - (1 / (L : ℝ)) • ∇ f (x k))
include hL0 hf hL hx

/-- **Sufficient decrease.** One step lowers `f` by at least `‖∇f‖² / (2L)`. -/
theorem sufficient_decrease (k : ℕ) :
    f (x (k + 1)) ≤ f (x k) - 1 / (2 * L) * ‖∇ f (x k)‖ ^ 2 := by
  have hLr : (0 : ℝ) < L := hL0
  have h := descent_lemma hf hL (x k) (x (k + 1))
  rw [hx k] at h ⊢
  rw [sub_sub_cancel_left, inner_neg_right, real_inner_smul_right, norm_neg, norm_smul,
    real_inner_self_eq_norm_sq, Real.norm_of_nonneg (by positivity)] at h
  have : (L : ℝ) / 2 * (1 / L * ‖∇ f (x k)‖) ^ 2 = 1 / (2 * L) * ‖∇ f (x k)‖ ^ 2 := by
    field_simp
  have h2 : 1 / (L : ℝ) * ‖∇ f (x k)‖ ^ 2 = 2 * (1 / (2 * L) * ‖∇ f (x k)‖ ^ 2) := by
    field_simp
  linarith

variable (hconv : ConvexOn ℝ univ f) {xstar : E}
include hconv

/-- **One-step progress** toward `x⋆`, measured by the squared distance. -/
theorem one_step (k : ℕ) :
    f (x (k + 1)) - f xstar ≤ L / 2 * (‖x k - xstar‖ ^ 2 - ‖x (k + 1) - xstar‖ ^ 2) := by
  have hLr : (0 : ℝ) < L := hL0
  have hdec := sufficient_decrease hL0 hf hL x hx k
  have hcvx := convex_first_order hf hconv (x k) xstar
  set g := ∇ f (x k)
  have hdist : ‖x (k + 1) - xstar‖ ^ 2
      = ‖x k - xstar‖ ^ 2 - 2 * (1 / L) * ⟪x k - xstar, g⟫ + (1 / L) ^ 2 * ‖g‖ ^ 2 := by
    rw [hx k, show x k - (1 / (L : ℝ)) • g - xstar = (x k - xstar) - (1 / (L : ℝ)) • g by abel,
      norm_sub_sq_real, real_inner_smul_right, norm_smul, Real.norm_of_nonneg (by positivity)]
    ring
  have hinner : ⟪g, xstar - x k⟫ = -⟪x k - xstar, g⟫ := by
    rw [← neg_sub, inner_neg_right, real_inner_comm]
  rw [hdist]
  rw [hinner] at hcvx
  have : (L : ℝ) / 2 * (‖x k - xstar‖ ^ 2 - (‖x k - xstar‖ ^ 2 - 2 * (1 / L) * ⟪x k - xstar, g⟫
      + (1 / L) ^ 2 * ‖g‖ ^ 2)) = ⟪x k - xstar, g⟫ - 1 / (2 * L) * ‖g‖ ^ 2 := by
    field_simp
    ring
  linarith

/-- **Lyapunov bound.** `k (f (x k) - f x⋆) + (L/2) ‖x k - x⋆‖²` never exceeds its value at `k = 0`. -/
theorem lyapunov (k : ℕ) :
    k * (f (x k) - f xstar) + L / 2 * ‖x k - xstar‖ ^ 2 ≤ L / 2 * ‖x 0 - xstar‖ ^ 2 := by
  have hLr : (0 : ℝ) < L := hL0
  induction k with
  | zero => simp
  | succ k ih =>
    have hstep := one_step hL0 hf hL x hx hconv (xstar := xstar) k
    have hdec := sufficient_decrease hL0 hf hL x hx k
    have hmono : f (x (k + 1)) ≤ f (x k) := by
      have : 0 ≤ 1 / (2 * (L : ℝ)) * ‖∇ f (x k)‖ ^ 2 := by positivity
      linarith
    have hk : (0 : ℝ) ≤ k := k.cast_nonneg
    push_cast
    nlinarith [mul_le_mul_of_nonneg_left hmono hk]

/-- **Main theorem**, division-free: `k (f (x k) - f x⋆) ≤ (L/2) ‖x 0 - x⋆‖²` for every `k`. -/
theorem gd_rate (k : ℕ) : k * (f (x k) - f xstar) ≤ L / 2 * ‖x 0 - xstar‖ ^ 2 := by
  have := lyapunov hL0 hf hL x hx hconv (xstar := xstar) k
  have : 0 ≤ (L : ℝ) / 2 * ‖x k - xstar‖ ^ 2 := by positivity
  linarith

/-- **Main theorem**, textbook form: `f (x k) - f x⋆ ≤ L ‖x 0 - x⋆‖² / (2k)` for `k ≥ 1`. -/
theorem gd_rate' (k : ℕ) (hk : 0 < k) :
    f (x k) - f xstar ≤ L * ‖x 0 - xstar‖ ^ 2 / (2 * k) := by
  have h := gd_rate hL0 hf hL x hx hconv (xstar := xstar) k
  have hk' : (0 : ℝ) < k := by exact_mod_cast hk
  rw [le_div_iff₀ (by positivity)]
  linarith

end GradientDescent

end MathProofSkill.Evals.Optimization003
