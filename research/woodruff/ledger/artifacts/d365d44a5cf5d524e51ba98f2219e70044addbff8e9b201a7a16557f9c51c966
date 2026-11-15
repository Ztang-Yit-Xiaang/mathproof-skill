import Mathlib

/-!
Woodruff, "Sketching as a Tool for Numerical Linear Algebra" (arXiv 1411.4357), §4.1, Theorem 47.
Statement only; the proof is our own.

Survey text: "Now let R be a (1 + O(ε))-approximate ℓ2-subspace embedding for the row space of SA,
where S is as in Lemma 45. Then ‖AR(SAR)†SA − A‖_F² ≤ (1 + ε)‖A − A_k‖_F². Furthermore,
‖[ARU]_k Uᵀ(SAR)†SA − A‖_F² ≤ (1 + ε)‖A − A_k‖_F², where UUᵀ = (SAR)†SAR is the projection
matrix onto the rowspace of SAR."

Encoding, with each departure recorded.
* "S is as in Lemma 45": S is a fixed matrix for which the conclusion of our Lemma 45 holds
  (`hS`): some X₀·(SA) of rank ≤ k is within (1 + 23ε) of every rank-≤k B. The randomness of S is
  Lemma 45's; this statement is about R given such an S.
* R is random (R : Ω → d×t). The survey's hypothesis, a (1 ± ε) subspace embedding for the row
  space of SA, is `hSE` (failure probability ≤ 1/10).
* Repair: an embedding of the row space of SA alone does NOT suffice: R can be an exact isometry
  on that row space while mixing in the residual directions, so the error is unbounded. We add the approximate
  matrix product property that oblivious sketches (such as CountSketch, used for R in the survey's
  algorithm) also have, `hAMM`, at accuracy ε/√m (m = rows of S).
  (Concretely, with k = 1: A = I₂, S = [1 0] satisfies `hS` since ‖A − A₁‖_F = 1, R = [1; c] is an
  exact isometry on span(e₁), and the unique minimizer X′ = [1; c] gives error √(1 + c²).)
* "AR(SAR)†" is read as "any minimizer X′ of ‖X·SAR − AR‖_F over all X" (AR(SAR)† is one), and
  "[ARU]_k Uᵀ(SAR)†" as "any minimizer over X with rank(X·SA) ≤ k". The latter is his matrix:
  X·SAR has rank ≤ k with rows in the row space of SAR, so Lemma 44 makes [ARU]_k Uᵀ the best
  such X·SAR, and his X attains it. This avoids pseudoinverses and the SVD in the statement.
  Existence of minimizers is not part of the claim.
* Norms are not squared; the factor (1 + ε) becomes the explicit 1 + 40ε (the survey rescales ε),
  with ε ≤ 1/10. Success probability 4/5 (two failure events of 1/10), unstated in the survey.
-/

open MeasureTheory

/-- Frobenius norm. -/
noncomputable def frob {m p : ℕ} (M : Matrix (Fin m) (Fin p) ℝ) : ℝ :=
  Real.sqrt (∑ a, ∑ b, M a b ^ 2)

/-- Euclidean norm of a vector. -/
noncomputable def vnorm {m : ℕ} (v : Fin m → ℝ) : ℝ := Real.sqrt (∑ i, v i ^ 2)

theorem woodruff_theorem47 {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) [IsProbabilityMeasure μ]
    {n d m t k : ℕ} (A : Matrix (Fin n) (Fin d) ℝ) (S : Matrix (Fin m) (Fin n) ℝ)
    (R : Ω → Matrix (Fin d) (Fin t) ℝ) (ε : ℝ) (hε : 0 < ε) (hε1 : ε ≤ 1 / 10)
    (hS : ∃ X : Matrix (Fin n) (Fin m) ℝ, (X * (S * A)).rank ≤ k ∧
      ∀ B : Matrix (Fin n) (Fin d) ℝ, B.rank ≤ k →
        frob (A - X * (S * A)) ≤ (1 + 23 * ε) * frob (A - B))
    (hSE : μ {ω | ∃ y : Fin m → ℝ,
      ¬ ((1 - ε) * vnorm (Matrix.vecMul y (S * A)) ≤ vnorm (Matrix.vecMul y (S * A * R ω)) ∧
        vnorm (Matrix.vecMul y (S * A * R ω)) ≤ (1 + ε) * vnorm (Matrix.vecMul y (S * A)))}
      ≤ ENNReal.ofReal (1 / 10))
    (hAMM : ∀ {p q : ℕ} (P : Matrix (Fin p) (Fin d) ℝ) (Q : Matrix (Fin q) (Fin d) ℝ),
      μ {ω | ε / Real.sqrt m * frob P * frob Q <
        frob (P * R ω * (R ω).transpose * Q.transpose - P * Q.transpose)} ≤ ENNReal.ofReal (1 / 10)) :
    ENNReal.ofReal (4 / 5) ≤ μ {ω |
      (∀ X' : Matrix (Fin n) (Fin m) ℝ,
        (∀ X : Matrix (Fin n) (Fin m) ℝ,
          frob (X' * (S * A) * R ω - A * R ω) ≤ frob (X * (S * A) * R ω - A * R ω)) →
        ∀ B : Matrix (Fin n) (Fin d) ℝ, B.rank ≤ k →
          frob (X' * (S * A) - A) ≤ (1 + 40 * ε) * frob (A - B)) ∧
      (∀ X' : Matrix (Fin n) (Fin m) ℝ, (X' * (S * A)).rank ≤ k →
        (∀ X : Matrix (Fin n) (Fin m) ℝ, (X * (S * A)).rank ≤ k →
          frob (X' * (S * A) * R ω - A * R ω) ≤ frob (X * (S * A) * R ω - A * R ω)) →
        ∀ B : Matrix (Fin n) (Fin d) ℝ, B.rank ≤ k →
          frob (X' * (S * A) - A) ≤ (1 + 40 * ε) * frob (A - B))} := by
  sorry
