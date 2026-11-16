import Mathlib

/-!
Woodruff, "Sketching as a Tool for Numerical Linear Algebra" (arXiv 1411.4357), Theorem 9, with
Definition 1 (squared norms). Statement only; the proof is our own, not the survey's.

Encoding.
* `A` is any real n×d matrix. `S ω` is the r×n sparse embedding (CountSketch) matrix with
  `(S ω)_{j,i} = σ ω i` if `h ω i = j` and 0 otherwise, unscaled, as in the survey.
* `h` is pairwise independent and uniform: any two distinct coordinates take any pair of values
  with probability 1/r².
* `σ` takes values ±1 and is 4-wise independent and uniform: the product over any set of at most
  four distinct coordinates has expectation 0 unless the set is empty.
* `h` and `σ` are independent of each other. The survey does not say this explicitly; we assume it.
* The survey's r = O(d²/(δε²)) is made explicit as r ≥ 2d²/(δε²), which is a stronger claim.
-/

open MeasureTheory ProbabilityTheory

/-- The sketch of a vector: bucket `j` collects `σ i * v i` over the coordinates `i` hashed to `j`. -/
def sketch {n r : ℕ} (h : Fin n → Fin r) (σ : Fin n → ℝ) (v : Fin n → ℝ) : Fin r → ℝ :=
  fun j => ∑ i, if h i = j then σ i * v i else 0

theorem woodruff_theorem9 {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) [IsProbabilityMeasure μ]
    {n d r : ℕ} (A : Matrix (Fin n) (Fin d) ℝ) (ε δ : ℝ) (hε : 0 < ε) (hδ : 0 < δ) (hδ1 : δ < 1)
    (hr : 2 * (d : ℝ) ^ 2 / (δ * ε ^ 2) ≤ r)
    (h : Ω → Fin n → Fin r) (σ : Ω → Fin n → ℝ)
    (hmeas : Measurable h) (σmeas : Measurable σ)
    (hpair : ∀ i j : Fin n, i ≠ j → ∀ a b : Fin r,
      μ {ω | h ω i = a ∧ h ω j = b} = ENNReal.ofReal (1 / (r : ℝ) ^ 2))
    (σsign : ∀ ω i, σ ω i = 1 ∨ σ ω i = -1)
    (σfour : ∀ T : Finset (Fin n), T.card ≤ 4 → T.Nonempty → ∫ ω, ∏ i ∈ T, σ ω i ∂μ = 0)
    (hσind : IndepFun h σ μ) :
    ENNReal.ofReal (1 - δ) ≤ μ {ω | ∀ x : Fin d → ℝ,
      (1 - ε) * ∑ i, (A.mulVec x i) ^ 2 ≤ ∑ j, (sketch (h ω) (σ ω) (A.mulVec x) j) ^ 2 ∧
      ∑ j, (sketch (h ω) (σ ω) (A.mulVec x) j) ^ 2 ≤ (1 + ε) * ∑ i, (A.mulVec x i) ^ 2} := by
  sorry
