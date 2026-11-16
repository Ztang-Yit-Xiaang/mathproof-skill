import Mathlib

/-!
Woodruff, "Sketching as a Tool for Numerical Linear Algebra" (arXiv 1411.4357), §4.1, Lemma 44 and
Lemma 45. Statements only; the proofs are our own.

Encoding (common).
* ‖·‖_F is `frob`, the square root of the sum of squared entries; `vnorm` is the Euclidean norm.
* "B is a best rank-k approximation to M" is written without the SVD: `B.rank ≤ k` and
  ‖M − B‖_F ≤ ‖M − B'‖_F for every B' with `B'.rank ≤ k`.
* "A matrix with rows in the row space of Uᵀ" is `C = Y * Uᵀ` for some Y.

Lemma 44. Survey: "The best rank-k approximation to A in Frobenius norm in the row space of a matrix
Uᵀ with orthonormal rows is given by [AU]_k Uᵀ, where [AU]_k denotes the best rank-k approximation
to AU." Encoded for any best rank-k approximation B of AU: B·Uᵀ has rank ≤ k, lies in the row space
of Uᵀ, and is at least as good as every rank-≤k matrix in that row space.

Lemma 45. Survey: S is a subspace embedding with distortion (1 ± 1/3) for any fixed k-dimensional
subspace with probability ≥ 9/10, and satisfies the conclusion of Theorem 13 at accuracy 3√(ε/k)
with failure probability ≤ 1/10; "then the rowspace of SA contains a (1 + ε) rank-k approximation
to A". Encoding choices, each a departure we record:
* The survey's "A and B each with k rows" is read as "n rows" (S has n columns); with k rows the
  product SᵀS·B is not defined.
* The success probability, unstated in the survey, is 4/5 (two failure events of 1/10).
* k ≤ n is added: for k > n there is no k-dimensional subspace of ℝⁿ, the embedding hypothesis is
  vacuous, and the claim fails (S = 0).
* The factor (1 + ε) is replaced by (1 + 23ε). The stated hypotheses (distortion 1/3, accuracy
  3√(ε/k)) give 1 + O(ε) only; the survey rescales ε by a constant, as it says it does in the
  proof of Theorem 23. 23 is what these hypotheses give: (1 + (27/4)²ε)^{1/2} ≤ 1 + 23ε.
* "Contains a (1 + 23ε) rank-k approximation" is: there is C of rank ≤ k with rows in the row space
  of SA (C = X·(SA)) and ‖A − C‖_F ≤ (1 + 23ε)‖A − B‖_F for every B of rank ≤ k.
* S is any random r×n matrix; no measurability is assumed (μ of a set is its outer measure).
-/

open MeasureTheory

/-- Frobenius norm. -/
noncomputable def frob {m p : ℕ} (M : Matrix (Fin m) (Fin p) ℝ) : ℝ :=
  Real.sqrt (∑ a, ∑ b, M a b ^ 2)

/-- Euclidean norm of a vector. -/
noncomputable def vnorm {m : ℕ} (v : Fin m → ℝ) : ℝ := Real.sqrt (∑ i, v i ^ 2)

/-- Lemma 44. -/
theorem woodruff_lemma44 {n d m k : ℕ} (A : Matrix (Fin n) (Fin d) ℝ) (U : Matrix (Fin d) (Fin m) ℝ)
    (hU : U.transpose * U = 1) (B : Matrix (Fin n) (Fin m) ℝ)
    (hB : B.rank ≤ k ∧ ∀ B' : Matrix (Fin n) (Fin m) ℝ, B'.rank ≤ k →
      frob (A * U - B) ≤ frob (A * U - B')) :
    (B * U.transpose).rank ≤ k ∧ (∃ Y : Matrix (Fin n) (Fin m) ℝ, B * U.transpose = Y * U.transpose) ∧
      ∀ C : Matrix (Fin n) (Fin d) ℝ, C.rank ≤ k →
        (∃ Y : Matrix (Fin n) (Fin m) ℝ, C = Y * U.transpose) →
        frob (A - B * U.transpose) ≤ frob (A - C) := by
  sorry

