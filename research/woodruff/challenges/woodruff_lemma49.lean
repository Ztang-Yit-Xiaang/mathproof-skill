import Mathlib

/-!
Woodruff, "Sketching as a Tool for Numerical Linear Algebra" (arXiv 1411.4357), §4.2, Lemma 49,
with Definition 16 (RandSampling). Statement only; the proof is our own.

Survey text: "With probability at least .9 over the randomness in the algorithm
RandSampling(Z, s, p), ‖ZᵀΩD‖_F² ≤ 10‖Zᵀ‖_F²."
Definition 16: Z ∈ ℝ^{n×k} has orthonormal columns, p_i = ‖e_iᵀZ‖²/k. For each column j of Ω, D,
pick a row index i with probability q_i, and set Ω_{ij} = 1, D_{jj} = 1/√(q_i s). Here q = p.

Encoding.
* Generalization: the bound is stated for every fixed matrix M with n columns, not only M = Zᵀ.
  The survey applies the lemma to the residual E₁ (proof of Lemma 55, step (h), p. 81), so Zᵀ in the
  statement is a typo for a general matrix. Literally, for M = Zᵀ and q = p, the bound holds for
  every outcome: each column of ZᵀΩD has squared norm k/s.
* The sampled indices are `I ω j`; each index j has the marginal law P(I j = i) = p_i, as in
  Definition 16. Independence across j is not needed and not assumed. Each `I · j` is measurable.
* ΩD is the n×s matrix `sampleMat`: entry (i, j) is 1/√(p_i s) if I j = i, else 0. (When p_i = 0,
  index i is sampled with probability 0; Lean's 1/√0 = 0 makes that column zero.)
-/

open MeasureTheory

/-- The product ΩD of RandSampling: column j is e_{I j} scaled by 1/√(q_{I j} s). -/
noncomputable def sampleMat {n s : ℕ} (I : Fin s → Fin n) (q : Fin n → ℝ) :
    Matrix (Fin n) (Fin s) ℝ :=
  fun i j => if I j = i then 1 / Real.sqrt (q i * s) else 0

theorem woodruff_lemma49 {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) [IsProbabilityMeasure μ]
    {n k s r : ℕ} (Z : Matrix (Fin n) (Fin k) ℝ) (hZ : Z.transpose * Z = 1)
    (I : Ω → Fin s → Fin n) (hI : ∀ j, Measurable fun ω => I ω j)
    (hlaw : ∀ j i, μ {ω | I ω j = i} = ENNReal.ofReal ((∑ a, Z i a ^ 2) / k))
    (M : Matrix (Fin r) (Fin n) ℝ) :
    ENNReal.ofReal 0.9 ≤ μ {ω | ∑ a, ∑ b, (M * sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k)) a b ^ 2
      ≤ 10 * ∑ a, ∑ b, M a b ^ 2} := by
  sorry
