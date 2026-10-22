import Mathlib

/-!
# probability-001 — Uncorrelated does not imply independent

Informal claim: uncorrelated random variables are independent. Expected verdict: `INVALID`.
Counterexample: `X` uniform on `{-1, 0, 1}` and `Y = X²`, on the uniform probability space
over `Fin 3`. Then `Cov(X, Y) = 0`, but `P(X = 0, Y = 0) = 1/3 ≠ 1/9 = P(X = 0) P(Y = 0)`.
-/

namespace MathProofSkill.Evals.Probability001

open MeasureTheory ProbabilityTheory

/-- The uniform probability measure on `Fin 3`. -/
noncomputable abbrev P : Measure (Fin 3) := uniformOn Set.univ

instance : IsProbabilityMeasure P := by unfold P; infer_instance

lemma P_eq : P = (3 : ENNReal)⁻¹ • Measure.count := by
  ext s _
  show uniformOn Set.univ s = _
  rw [uniformOn_univ, Measure.smul_apply, smul_eq_mul, Fintype.card_fin, div_eq_mul_inv, mul_comm]
  rfl

lemma integral_P (f : Fin 3 → ℝ) : ∫ ω, f ω ∂P = (f 0 + f 1 + f 2) / 3 := by
  rw [P_eq, integral_smul_measure, integral_count, Fin.sum_univ_three]
  simp [ENNReal.toReal_inv]
  ring

lemma P_singleton (ω : Fin 3) : P {ω} = 3⁻¹ := by
  rw [P_eq, Measure.smul_apply, Measure.count_singleton, smul_eq_mul, mul_one]

/-- `X` takes the values `-1, 0, 1`. -/
def X : Fin 3 → ℝ := ![-1, 0, 1]

/-- `Y = X²`. -/
def Y : Fin 3 → ℝ := fun ω => X ω ^ 2

/-- Covariance written out as `E[XY] - E[X] E[Y]`. -/
noncomputable def cov (U V : Fin 3 → ℝ) : ℝ :=
  ∫ ω, U ω * V ω ∂P - (∫ ω, U ω ∂P) * ∫ ω, V ω ∂P

/-- The claim, instantiated on the probability space `(Fin 3, P)`. -/
def Claim : Prop := ∀ U V : Fin 3 → ℝ, cov U V = 0 → IndepFun U V P

theorem cov_X_Y : cov X Y = 0 := by
  simp only [cov, integral_P, Y, X]
  simp [Matrix.cons_val]

theorem not_indep : ¬ IndepFun X Y P := by
  intro h
  have key := (indepFun_iff_measure_inter_preimage_eq_mul.mp h) {0} {0}
    (measurableSet_singleton 0) (measurableSet_singleton 0)
  have hX : X ⁻¹' {0} = {1} := by
    ext ω; fin_cases ω <;> simp [X]
  have hY : Y ⁻¹' {0} = {1} := by
    ext ω; fin_cases ω <;> simp [Y, X]
  rw [hX, hY, Set.inter_self, P_singleton] at key
  have := congrArg ENNReal.toReal key
  rw [ENNReal.toReal_mul, ENNReal.toReal_inv] at this
  norm_num at this

theorem claim_false : ¬ Claim := fun h => not_indep (h X Y cov_X_Y)

end MathProofSkill.Evals.Probability001
