import Mathlib

/-!
# probability-003 — `E[X²] = (E[X])²` is false in general

Informal claim: for every square-integrable `X`, `E[X²] = (E[X])²`. Expected verdict:
`INVALID`. Counterexample: `X = ±1` with probability `1/2` each, on the uniform probability
space over `Bool`. Then `E[X] = 0` and `E[X²] = 1`.
-/

namespace MathProofSkill.Evals.Probability003

open MeasureTheory ProbabilityTheory

/-- The uniform probability measure on `Bool`. -/
noncomputable abbrev P : Measure Bool := uniformOn Set.univ

instance : IsProbabilityMeasure P := by unfold P; infer_instance

lemma P_eq : P = (2 : ENNReal)⁻¹ • Measure.count := by
  ext s _
  show uniformOn Set.univ s = _
  rw [uniformOn_univ, Measure.smul_apply, smul_eq_mul, Fintype.card_bool, div_eq_mul_inv, mul_comm]
  rfl

lemma integral_P (f : Bool → ℝ) : ∫ b, f b ∂P = (f true + f false) / 2 := by
  rw [P_eq, integral_smul_measure, integral_count]
  simp [ENNReal.toReal_inv]
  ring

/-- `X = ±1` with equal probability. -/
def X : Bool → ℝ := fun b => if b then 1 else -1

/-- The claim, instantiated on the probability space `(Bool, P)`. -/
def Claim : Prop :=
  ∀ Y : Bool → ℝ, MemLp Y 2 P → ∫ b, Y b ^ 2 ∂P = (∫ b, Y b ∂P) ^ 2

theorem X_memLp : MemLp X 2 P := MemLp.of_discrete

theorem mean_X : ∫ b, X b ∂P = 0 := by rw [integral_P]; norm_num [X]

theorem second_moment_X : ∫ b, X b ^ 2 ∂P = 1 := by rw [integral_P]; norm_num [X]

theorem claim_false : ¬ Claim := by
  intro h
  have := h X X_memLp
  rw [mean_X, second_moment_X] at this
  norm_num at this

end MathProofSkill.Evals.Probability003
