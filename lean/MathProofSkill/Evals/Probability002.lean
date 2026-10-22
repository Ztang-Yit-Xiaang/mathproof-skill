import Mathlib

/-!
# probability-002 — Linearity of expectation

Informal claim: expectation is linear without an independence assumption. Expected verdict:
`VALID`. Integrability of each summand is the (necessary) side condition; no independence
hypothesis appears.
-/

namespace MathProofSkill.Evals.Probability002

open MeasureTheory

theorem expectation_add {Ω : Type*} [MeasurableSpace Ω] (P : Measure Ω)
    {X Y : Ω → ℝ} (hX : Integrable X P) (hY : Integrable Y P) :
    ∫ ω, (X ω + Y ω) ∂P = ∫ ω, X ω ∂P + ∫ ω, Y ω ∂P :=
  integral_add hX hY

theorem expectation_smul {Ω : Type*} [MeasurableSpace Ω] (P : Measure Ω)
    (c : ℝ) (X : Ω → ℝ) : ∫ ω, c * X ω ∂P = c * ∫ ω, X ω ∂P :=
  integral_const_mul c X

end MathProofSkill.Evals.Probability002
