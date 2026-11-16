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

/-- The sketch of a vector, as in our Theorem 9 file. -/
def sketch {n r : ℕ} (h : Fin n → Fin r) (σ : Fin n → ℝ) (v : Fin n → ℝ) : Fin r → ℝ :=
  fun j => ∑ i, if h i = j then σ i * v i else 0

/-- Definition 12: the (ε, δ, ℓ)-JL moment property. -/
def JLMoment {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) {k d : ℕ}
    (S : Ω → Matrix (Fin k) (Fin d) ℝ) (ε δ ℓ : ℝ) : Prop :=
  ∀ x : Fin d → ℝ, ∑ i, x i ^ 2 = 1 →
    ∫⁻ ω, ENNReal.ofReal (|∑ j, ((S ω).mulVec x j) ^ 2 - 1| ^ ℓ) ∂μ ≤ ENNReal.ofReal (ε ^ ℓ * δ)

/-- Frobenius norm. -/
noncomputable def frob {m p : ℕ} (M : Matrix (Fin m) (Fin p) ℝ) : ℝ :=
  Real.sqrt (∑ a, ∑ b, M a b ^ 2)

/-- The CountSketch matrix of `h` and `σ`: entry `(j, i)` is `σ i` if `h i = j`, else 0. -/
def countSketch {n r : ℕ} (h : Fin n → Fin r) (σ : Fin n → ℝ) : Matrix (Fin r) (Fin n) ℝ :=
  fun j i => if h i = j then σ i else 0

/-- Theorem 14. -/
theorem woodruff_theorem14 {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) [IsProbabilityMeasure μ]
    {n r : ℕ} (ε δ : ℝ) (hε : 0 < ε) (hδ : 0 < δ)
    (hr : 2 / (ε ^ 2 * δ) ≤ r)
    (h : Ω → Fin n → Fin r) (σ : Ω → Fin n → ℝ)
    (hmeas : Measurable h) (σmeas : Measurable σ)
    (hpair : ∀ i j : Fin n, i ≠ j → ∀ a b : Fin r,
      μ {ω | h ω i = a ∧ h ω j = b} = ENNReal.ofReal (1 / (r : ℝ) ^ 2))
    (σsign : ∀ ω i, σ ω i = 1 ∨ σ ω i = -1)
    (σfour : ∀ T : Finset (Fin n), T.card ≤ 4 → T.Nonempty → ∫ ω, ∏ i ∈ T, σ ω i ∂μ = 0)
    (hσind : IndepFun h σ μ) :
    JLMoment μ (fun ω => countSketch (h ω) (σ ω)) ε δ 2 := by
  sorry
