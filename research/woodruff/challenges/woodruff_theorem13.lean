import Mathlib

/-!
Woodruff, "Sketching as a Tool for Numerical Linear Algebra" (arXiv 1411.4357), Definition 12,
Theorem 13 and Theorem 14. Statements only; the proofs are our own.

Encoding.
* Definition 12, the (ε, δ, ℓ)-JL moment property of a random k×d matrix `S`: for every x with
  ‖x‖₂ = 1, E|‖Sx‖₂² − 1|^ℓ ≤ ε^ℓ·δ. The expectation is a lower Lebesgue integral in [0, ∞], so a
  non-integrable quantity cannot satisfy the bound vacuously.
* ‖·‖_F is written out as the square root of the sum of squared entries.
* `S` is measurable entrywise (Mathlib has no measurable-space instance on `Matrix`).
* Theorem 13 keeps the survey's ranges ε, δ ∈ (0, 1/2) and ℓ ≥ 2 (real).
* Theorem 14 uses the sparse embedding of the survey's §2.1 with the same encoding as our
  Theorem 9: `h` pairwise independent and uniform, `σ` ±1 and 4-wise independent, `h` independent
  of `σ`. "At least 2/(ε²δ) rows" is `2/(ε²δ) ≤ r`.
-/

open MeasureTheory ProbabilityTheory

/-- Definition 12: the (ε, δ, ℓ)-JL moment property. -/
def JLMoment {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) {k d : ℕ}
    (S : Ω → Matrix (Fin k) (Fin d) ℝ) (ε δ ℓ : ℝ) : Prop :=
  ∀ x : Fin d → ℝ, ∑ i, x i ^ 2 = 1 →
    ∫⁻ ω, ENNReal.ofReal (|∑ j, ((S ω).mulVec x j) ^ 2 - 1| ^ ℓ) ∂μ ≤ ENNReal.ofReal (ε ^ ℓ * δ)

/-- Frobenius norm. -/
noncomputable def frob {m p : ℕ} (M : Matrix (Fin m) (Fin p) ℝ) : ℝ :=
  Real.sqrt (∑ a, ∑ b, M a b ^ 2)

/-- Theorem 13. -/
theorem woodruff_theorem13 {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) [IsProbabilityMeasure μ]
    {k d m p : ℕ} (S : Ω → Matrix (Fin k) (Fin d) ℝ) (hS : ∀ a b, Measurable fun ω => S ω a b)
    (ε δ ℓ : ℝ) (hε : 0 < ε) (hε2 : ε < 1 / 2) (hδ : 0 < δ) (hδ2 : δ < 1 / 2) (hℓ : 2 ≤ ℓ)
    (hJL : JLMoment μ S ε δ ℓ)
    (A : Matrix (Fin d) (Fin m) ℝ) (B : Matrix (Fin d) (Fin p) ℝ) :
    μ {ω | 3 * ε * frob A * frob B <
      frob (A.transpose * (S ω).transpose * S ω * B - A.transpose * B)} ≤ ENNReal.ofReal δ := by
  sorry

