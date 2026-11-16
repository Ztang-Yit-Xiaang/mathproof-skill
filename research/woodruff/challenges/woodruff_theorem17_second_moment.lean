import Mathlib

/-!
Woodruff, "Sketching as a Tool for Numerical Linear Algebra" (arXiv 1411.4357), §2.4, Theorem 17,
in a second-moment variant (our own statement and proof; DEC with the user, 2026-11-11).

Survey text: "Suppose Z ∈ ℝ^{n×k} has orthonormal columns. Suppose s > 144k ln(2k/δ)/(βε²) and
Ω and D are constructed from the RandSampling(Z, s, q) procedure. Then with probability at least
1 − δ, simultaneously for all i, 1 − ε ≤ σᵢ²(ZᵀΩD) ≤ 1 + ε."

Variant, recorded as a departure: the sample size is s ≥ k²/(ε²δ) instead of
s > 144k ln(2k/δ)/(βε²). The survey's bound needs a matrix Chernoff inequality; ours needs only
second moments and Markov, at the price of k² instead of k log k. As in Lemma 55, q = p (β = 1).

Encoding.
* RandSampling (Definition 16): `I ω j` is the j-th sampled row index, with law
  P(I j = i) = pᵢ = ‖eᵢᵀZ‖²/k, and the samples are pairwise independent (Definition 16 picks them
  independently, which implies this). ΩD is `sampleMat`, as in our Lemma 49 file.
* "1 − ε ≤ σᵢ²(ZᵀΩD) ≤ 1 + ε for all i" is the equivalent quadratic-form statement
  (1 − ε)‖x‖² ≤ ‖(ZᵀΩD)ᵀx‖² ≤ (1 + ε)‖x‖² for all x ∈ ℝᵏ.
-/

open MeasureTheory ProbabilityTheory

/-- The product ΩD of RandSampling: column j is e_{I j} scaled by 1/√(q_{I j} s). -/
noncomputable def sampleMat {n s : ℕ} (I : Fin s → Fin n) (q : Fin n → ℝ) :
    Matrix (Fin n) (Fin s) ℝ :=
  fun i j => if I j = i then 1 / Real.sqrt (q i * s) else 0

theorem woodruff_theorem17_second_moment {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    [IsProbabilityMeasure μ] {n k s : ℕ} (Z : Matrix (Fin n) (Fin k) ℝ) (hZ : Z.transpose * Z = 1)
    (I : Ω → Fin s → Fin n) (hI : ∀ j, Measurable fun ω => I ω j)
    (hlaw : ∀ j i, μ {ω | I ω j = i} = ENNReal.ofReal ((∑ a, Z i a ^ 2) / k))
    (hind : ∀ j j', j ≠ j' → IndepFun (fun ω => I ω j) (fun ω => I ω j') μ)
    (ε δ : ℝ) (hε : 0 < ε) (hδ : 0 < δ) (hs : (k : ℝ) ^ 2 / (ε ^ 2 * δ) ≤ s) :
    ENNReal.ofReal (1 - δ) ≤ μ {ω | ∀ x : Fin k → ℝ,
      (1 - ε) * ∑ a, x a ^ 2 ≤
        ∑ j, (∑ a, x a * (Z.transpose * sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k)) a j) ^ 2 ∧
      ∑ j, (∑ a, x a * (Z.transpose * sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k)) a j) ^ 2 ≤
        (1 + ε) * ∑ a, x a ^ 2} := by
  sorry
