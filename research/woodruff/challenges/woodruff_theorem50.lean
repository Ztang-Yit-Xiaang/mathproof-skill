import Mathlib

/-!
Woodruff, "Sketching as a Tool for Numerical Linear Algebra" (arXiv 1411.4357), §4.2.1,
Theorem 50 (Dual Set Spectral-Frobenius Sparsification). Statement only; the proof is our own.

Survey text: "Let vᵢ ∈ ℝᵏ for i = 1, …, n with k < n, and Σᵢ vᵢvᵢᵀ = I_k. Let A = {a₁, …, aₙ} be
an arbitrary set of vectors, where aᵢ ∈ ℝ^ℓ for all i. Then, given an integer r such that
k < r ≤ n, there exists a set of weights sᵢ ≥ 0 (i = 1, …, n), at most r of which are non-zero,
such that λ_k(Σᵢ sᵢvᵢvᵢᵀ) ≥ (1 − √(k/r))², Tr(Σᵢ sᵢaᵢaᵢᵀ) ≤ Tr(Σᵢ aᵢaᵢᵀ) = Σᵢ ‖aᵢ‖²."

Encoding.
* vᵢ is `v i : Fin k → ℝ`, aᵢ is `a i : Fin ℓ → ℝ`. Σᵢ vᵢvᵢᵀ = I_k is entrywise.
* λ_k is the smallest eigenvalue of the symmetric k×k matrix Σᵢ sᵢvᵢvᵢᵀ. "λ_k ≥ c" is stated by
  the equivalent quadratic-form inequality: xᵀ(Σᵢ sᵢvᵢvᵢᵀ)x = Σᵢ sᵢ⟨vᵢ, x⟩² ≥ c‖x‖² for all x.
* "At most r non-zero" is the cardinality of the support of s.
* Tr(Σᵢ sᵢaᵢaᵢᵀ) = Σᵢ sᵢ‖aᵢ‖².
-/

theorem woodruff_theorem50 {n k ℓ : ℕ} (v : Fin n → Fin k → ℝ)
    (hv : ∀ a b : Fin k, ∑ i, v i a * v i b = if a = b then 1 else 0)
    (a : Fin n → Fin ℓ → ℝ) (r : ℕ) (hkn : k < n) (hkr : k < r) (hrn : r ≤ n) :
    ∃ s : Fin n → ℝ, (∀ i, 0 ≤ s i) ∧ (Finset.univ.filter fun i => s i ≠ 0).card ≤ r ∧
      (∀ x : Fin k → ℝ, (1 - Real.sqrt (k / r)) ^ 2 * ∑ b, x b ^ 2 ≤
        ∑ i, s i * (∑ b, v i b * x b) ^ 2) ∧
      ∑ i, s i * ∑ j, a i j ^ 2 ≤ ∑ i, ∑ j, a i j ^ 2 := by
  sorry
