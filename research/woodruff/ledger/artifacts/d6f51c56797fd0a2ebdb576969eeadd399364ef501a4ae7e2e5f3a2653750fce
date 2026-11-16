import Mathlib

/-!
Woodruff, "Sketching as a Tool for Numerical Linear Algebra" (arXiv 1411.4357), §4.2.1,
Corollary 54. Statement only; the proof is our own.

Survey text: "Let V = {v₁, …, vₙ} be a decomposition of the identity, where vᵢ ∈ ℝᵏ (k < n) and
Σᵢ vᵢvᵢᵀ = I_k; let A = {a₁, …, aₙ} be an arbitrary set of vectors, where aᵢ ∈ ℝ^ℓ. Let
W ∈ ℝ^{ξ×ℓ} be a randomly chosen sparse subspace embedding with ξ = O(n²/ε²) < ℓ, for some
0 < ε < 1. Consider a new set of vectors B = {Wa₁, …, Waₙ}. Run Algorithm 2 with V, B, and some
integer r such that k < r ≤ n. Let the output of this be a set of weights sᵢ ≥ 0, at most r of
which are non-zero. Then, with probability at least 0.99, λ_k(Σᵢ sᵢvᵢvᵢᵀ) ≥ (1 − √(k/r))² and
Tr(Σᵢ sᵢaᵢaᵢᵀ) ≤ (1+ε)/(1−ε)·Tr(Σᵢ aᵢaᵢᵀ) = (1+ε)/(1−ε)·Σᵢ ‖aᵢ‖²."

Encoding.
* W is the sparse embedding (CountSketch) of our Theorem 9 file, with the same hypotheses on
  `h` and `σ`; Waᵢ is `sketch (h ω) (σ ω) (a i)`. O(n²/ε²) is made explicit as ξ ≥ 200n²/ε².
  The efficiency condition ξ < ℓ plays no role in correctness and is dropped.
* "The output of Algorithm 2" is read through Algorithm 2's guarantee (our Theorem 50) on the input
  (V, B): nonnegative weights, at most r non-zero, the λ_k bound, and Σ sᵢ‖Waᵢ‖² ≤ Σ ‖Waᵢ‖². The
  claim has two parts on one event of probability ≥ 0.99:
  (1) such weights exist (so the claim is not vacuous), and
  (2) every nonnegative s with Σ sᵢ‖Waᵢ‖² ≤ Σ ‖Waᵢ‖² satisfies the (1+ε)/(1−ε) trace bound.
  The λ_k bound does not depend on W and is part of (1).
* λ_k ≥ c is the quadratic-form inequality, as in our Theorem 50 file.
-/

open MeasureTheory ProbabilityTheory

/-- The sketch of a vector: bucket `j` collects `σ i * v i` over the coordinates `i` hashed to `j`. -/
def sketch {n r : ℕ} (h : Fin n → Fin r) (σ : Fin n → ℝ) (v : Fin n → ℝ) : Fin r → ℝ :=
  fun j => ∑ i, if h i = j then σ i * v i else 0

theorem woodruff_corollary54 {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) [IsProbabilityMeasure μ]
    {n k ℓ ξ : ℕ} (v : Fin n → Fin k → ℝ)
    (hv : ∀ a b : Fin k, ∑ i, v i a * v i b = if a = b then 1 else 0)
    (a : Fin n → Fin ℓ → ℝ) (r : ℕ) (hkn : k < n) (hkr : k < r) (hrn : r ≤ n)
    (ε : ℝ) (hε : 0 < ε) (hε1 : ε < 1) (hξ : 200 * (n : ℝ) ^ 2 / ε ^ 2 ≤ ξ)
    (h : Ω → Fin ℓ → Fin ξ) (σ : Ω → Fin ℓ → ℝ)
    (hmeas : Measurable h) (σmeas : Measurable σ)
    (hpair : ∀ i j : Fin ℓ, i ≠ j → ∀ a b : Fin ξ,
      μ {ω | h ω i = a ∧ h ω j = b} = ENNReal.ofReal (1 / (ξ : ℝ) ^ 2))
    (σsign : ∀ ω i, σ ω i = 1 ∨ σ ω i = -1)
    (σfour : ∀ T : Finset (Fin ℓ), T.card ≤ 4 → T.Nonempty → ∫ ω, ∏ i ∈ T, σ ω i ∂μ = 0)
    (hσind : IndepFun h σ μ) :
    ENNReal.ofReal 0.99 ≤ μ {ω |
      (∃ s : Fin n → ℝ, (∀ i, 0 ≤ s i) ∧ (Finset.univ.filter fun i => s i ≠ 0).card ≤ r ∧
        (∀ x : Fin k → ℝ, (1 - Real.sqrt (k / r)) ^ 2 * ∑ b, x b ^ 2 ≤
          ∑ i, s i * (∑ b, v i b * x b) ^ 2) ∧
        ∑ i, s i * ∑ j, sketch (h ω) (σ ω) (a i) j ^ 2 ≤ ∑ i, ∑ j, sketch (h ω) (σ ω) (a i) j ^ 2) ∧
      ∀ s : Fin n → ℝ, (∀ i, 0 ≤ s i) →
        ∑ i, s i * ∑ j, sketch (h ω) (σ ω) (a i) j ^ 2 ≤ ∑ i, ∑ j, sketch (h ω) (σ ω) (a i) j ^ 2 →
        ∑ i, s i * ∑ j, a i j ^ 2 ≤ (1 + ε) / (1 - ε) * ∑ i, ∑ j, a i j ^ 2} := by
  sorry
