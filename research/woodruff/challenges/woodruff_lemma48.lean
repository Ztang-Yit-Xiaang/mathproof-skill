import Mathlib

/-!
Woodruff, "Sketching as a Tool for Numerical Linear Algebra" (arXiv 1411.4357), §4.2, Lemma 48
(due to Boutsidis, Drineas and Magdon-Ismail). Statement only; the proof is our own.

Survey text: "Let A = AZZᵀ + E ∈ ℝ^{m×n} be a low-rank matrix factorization of A, with
Z ∈ ℝ^{n×k}, and ZᵀZ = I_k. Let S ∈ ℝ^{n×c} (c ≥ k) be any matrix such that
rank(ZᵀS) = rank(Z) = k. Let C = AS ∈ ℝ^{m×c}. Then
‖A − CC†A‖_F² ≤ ‖A − Π_{C,k}(A)‖_F² ≤ ‖E‖_F² + ‖ES(ZᵀS)†‖_F².
Here, Π_{C,k}(A) = CX_opt, where X_opt has rank at most k and CX_opt is the best rank k
approximation to A in the column space of C."

Encoding.
* ‖·‖_F is `frob`. C is written A·S.
* CC†A is the projection of A onto the column space of C, i.e. C·P for any P minimizing
  ‖A − CX‖_F over all X; Π_{C,k}(A) is C·X_k for any X_k minimizing ‖A − CX‖_F over rank(X) ≤ k.
  The second conjunct states both inequalities for every such P and X_k.
* (ZᵀS)† is generalized to any right inverse W of ZᵀS (ZᵀS·W = I_k). Since ZᵀS has full row rank
  k, its pseudoinverse is such a W, so this is a stronger claim than the survey's.
* The first conjunct makes the bound non-vacuous without assuming minimizers exist: some X of rank
  ≤ k already achieves ‖A − CX‖_F² ≤ ‖E‖_F² + ‖ESW‖_F².
-/

/-- Frobenius norm. -/
noncomputable def frob {m p : ℕ} (M : Matrix (Fin m) (Fin p) ℝ) : ℝ :=
  Real.sqrt (∑ a, ∑ b, M a b ^ 2)

theorem woodruff_lemma48 {m n k c : ℕ} (A : Matrix (Fin m) (Fin n) ℝ)
    (Z : Matrix (Fin n) (Fin k) ℝ) (hZ : Z.transpose * Z = 1)
    (E : Matrix (Fin m) (Fin n) ℝ) (hE : A = A * Z * Z.transpose + E)
    (S : Matrix (Fin n) (Fin c) ℝ) (hck : k ≤ c) (hrank : (Z.transpose * S).rank = k)
    (W : Matrix (Fin c) (Fin k) ℝ) (hW : Z.transpose * S * W = 1) :
    (∃ X : Matrix (Fin c) (Fin n) ℝ, X.rank ≤ k ∧
      frob (A - A * S * X) ^ 2 ≤ frob E ^ 2 + frob (E * S * W) ^ 2) ∧
    ∀ P Xk : Matrix (Fin c) (Fin n) ℝ,
      (∀ X : Matrix (Fin c) (Fin n) ℝ, frob (A - A * S * P) ≤ frob (A - A * S * X)) →
      Xk.rank ≤ k →
      (∀ X : Matrix (Fin c) (Fin n) ℝ, X.rank ≤ k → frob (A - A * S * Xk) ≤ frob (A - A * S * X)) →
      frob (A - A * S * P) ^ 2 ≤ frob (A - A * S * Xk) ^ 2 ∧
        frob (A - A * S * Xk) ^ 2 ≤ frob E ^ 2 + frob (E * S * W) ^ 2 := by
  sorry
