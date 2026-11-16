import Mathlib

/-!
Woodruff, "Sketching as a Tool for Numerical Linear Algebra" (arXiv 1411.4357), §4.2.1, Lemma 55.
Statement only; the proof is our own.

Survey text (setup, p. 70 and p. 80): compute Z₁ ∈ ℝ^{n×k} with orthonormal columns and
‖A − AZ₁Z₁ᵀ‖_F² ≤ (1 + 1/9)‖A − A_k‖_F²; sample with RandSampling(Z₁, s, p), s = Θ(k log k),
getting Ω₁, D₁ with (32); let M = Z₁ᵀΩ₁D₁ = UΣV_Mᵀ (SVD); compute
S₁ = BssSamplingSparse(V_M, (A − AZ₁Z₁ᵀ)ᵀΩ₁D₁, 4k, .5); set C₁ = AΩ₁D₁S₁ ∈ ℝ^{m×4k}.
"Lemma 55. With probability at least .8, ‖A − C₁C₁†A‖_F² ≤ 90·‖A − A_k‖_F²."

Encoding, with departures recorded.
* Z₁ is an input satisfying its guarantee (`hZgood`), stated against every rank-≤k B.
* Sampling (DEC with the user, 2026-11-11): s ≥ 400k²/9 pairwise-independent leverage-score
  samples, instead of s = Θ(k log k). This is what our second-moment Theorem 17 needs for (32)
  at ε = 1/2 with failure probability 0.09. ΩD is `sampleMat`, as in our Lemma 49 file.
* V_M: any factorization M = R·V_Mᵀ with V_MᵀV_M = I_k (the SVD gives one, R = UΣ). The claim
  holds for every such factorization, and one exists on the event.
* BssSamplingSparse is read through its guarantee, as in our Corollary 54: the weights s₁ on the
  s rows of V_M are nonnegative, at most 4k are non-zero, λ_k(Σ s₁ⱼ vⱼvⱼᵀ) ≥ (1 − √(k/4k))² = 1/4,
  and Σ s₁ⱼ‖W bⱼ‖² ≤ Σ ‖W bⱼ‖² for the columns bⱼ of (A − AZ₁Z₁ᵀ)Ω₁D₁. Weights meeting this exist
  on the event (our Theorem 50).
* W is the sparse embedding (CountSketch) of our Theorem 9 file. It is required to embed the
  column space of A − AZ₁Z₁ᵀ (ξ ≥ 800n²) instead of only the s sampled columns
  (ξ = O(s²/ε²)). The sampled columns are scaled columns of that matrix, so this removes any need
  to condition on the sampling. It changes the sketch size only.
* C₁ = AΩ₁D₁S₁ is A·ΩD·diag(√s₁) (m×s, at most 4k non-zero columns). It has the same column space
  as the survey's m×4k matrix, so the same projection C₁C₁†A.
* C₁C₁†A is C₁·P for any P minimizing ‖A − C₁X‖_F; the first conjunct also gives an explicit X
  with the bound (non-vacuity).
* The constant 90 is replaced by 2410/9 ≈ 268, which is what these hypotheses give:
  (1 + 8·3·10)·(10/9). 8 = 1/(½·¼) from (32) and the λ_k bound, 3 = (1 + ½)/(1 − ½) from the sketch,
  10 from Lemma 49. See COMPARISON.md for the survey's 80.
-/

open MeasureTheory ProbabilityTheory

/-- Frobenius norm. -/
noncomputable def frob {m p : ℕ} (M : Matrix (Fin m) (Fin p) ℝ) : ℝ :=
  Real.sqrt (∑ a, ∑ b, M a b ^ 2)

/-- The sketch of a vector: bucket `j` collects `σ i * v i` over the coordinates `i` hashed to `j`. -/
def sketch {n r : ℕ} (h : Fin n → Fin r) (σ : Fin n → ℝ) (v : Fin n → ℝ) : Fin r → ℝ :=
  fun j => ∑ i, if h i = j then σ i * v i else 0

/-- The product ΩD of RandSampling: column j is e_{I j} scaled by 1/√(q_{I j} s). -/
noncomputable def sampleMat {n s : ℕ} (I : Fin s → Fin n) (q : Fin n → ℝ) :
    Matrix (Fin n) (Fin s) ℝ :=
  fun i j => if I j = i then 1 / Real.sqrt (q i * s) else 0

theorem woodruff_lemma55 {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) [IsProbabilityMeasure μ]
    {m n k s ξ : ℕ} (hk : 0 < k) (A : Matrix (Fin m) (Fin n) ℝ) (Z : Matrix (Fin n) (Fin k) ℝ)
    (hZ : Z.transpose * Z = 1)
    (hZgood : ∀ B : Matrix (Fin m) (Fin n) ℝ, B.rank ≤ k →
      frob (A - A * Z * Z.transpose) ^ 2 ≤ (1 + 1 / 9) * frob (A - B) ^ 2)
    (I : Ω → Fin s → Fin n) (hI : ∀ j, Measurable fun ω => I ω j)
    (hlaw : ∀ j i, μ {ω | I ω j = i} = ENNReal.ofReal ((∑ a, Z i a ^ 2) / k))
    (hind : ∀ j j', j ≠ j' → IndepFun (fun ω => I ω j) (fun ω => I ω j') μ)
    (hs : 400 * (k : ℝ) ^ 2 / 9 ≤ s)
    (h : Ω → Fin m → Fin ξ) (σ : Ω → Fin m → ℝ) (hξ : 800 * (n : ℝ) ^ 2 ≤ ξ)
    (hmeas : Measurable h) (σmeas : Measurable σ)
    (hpair : ∀ i j : Fin m, i ≠ j → ∀ a b : Fin ξ,
      μ {ω | h ω i = a ∧ h ω j = b} = ENNReal.ofReal (1 / (ξ : ℝ) ^ 2))
    (σsign : ∀ ω i, σ ω i = 1 ∨ σ ω i = -1)
    (σfour : ∀ T : Finset (Fin m), T.card ≤ 4 → T.Nonempty → ∫ ω, ∏ i ∈ T, σ ω i ∂μ = 0)
    (hσind : IndepFun h σ μ) :
    ENNReal.ofReal 0.8 ≤ μ {ω |
      (∃ R : Matrix (Fin k) (Fin k) ℝ, ∃ V : Matrix (Fin s) (Fin k) ℝ, V.transpose * V = 1 ∧
        Z.transpose * sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k) = R * V.transpose) ∧
      ∀ (R : Matrix (Fin k) (Fin k) ℝ) (V : Matrix (Fin s) (Fin k) ℝ), V.transpose * V = 1 →
        Z.transpose * sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k) = R * V.transpose →
        (∃ s₁ : Fin s → ℝ, (∀ j, 0 ≤ s₁ j) ∧ (Finset.univ.filter fun j => s₁ j ≠ 0).card ≤ 4 * k ∧
          (∀ x : Fin k → ℝ, 1 / 4 * ∑ b, x b ^ 2 ≤ ∑ j, s₁ j * (∑ b, V j b * x b) ^ 2) ∧
          ∑ j, s₁ j * ∑ l, sketch (h ω) (σ ω) (fun a => ((A - A * Z * Z.transpose) *
            sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k)) a j) l ^ 2 ≤
          ∑ j, ∑ l, sketch (h ω) (σ ω) (fun a => ((A - A * Z * Z.transpose) *
            sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k)) a j) l ^ 2) ∧
        ∀ s₁ : Fin s → ℝ, (∀ j, 0 ≤ s₁ j) → (Finset.univ.filter fun j => s₁ j ≠ 0).card ≤ 4 * k →
          (∀ x : Fin k → ℝ, 1 / 4 * ∑ b, x b ^ 2 ≤ ∑ j, s₁ j * (∑ b, V j b * x b) ^ 2) →
          ∑ j, s₁ j * ∑ l, sketch (h ω) (σ ω) (fun a => ((A - A * Z * Z.transpose) *
            sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k)) a j) l ^ 2 ≤
          ∑ j, ∑ l, sketch (h ω) (σ ω) (fun a => ((A - A * Z * Z.transpose) *
            sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k)) a j) l ^ 2 →
          (∃ X : Matrix (Fin s) (Fin n) ℝ, X.rank ≤ k ∧ ∀ B : Matrix (Fin m) (Fin n) ℝ, B.rank ≤ k →
            frob (A - A * sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k) *
              Matrix.diagonal (fun j => Real.sqrt (s₁ j)) * X) ^ 2 ≤ 2410 / 9 * frob (A - B) ^ 2) ∧
          ∀ P : Matrix (Fin s) (Fin n) ℝ,
            (∀ X : Matrix (Fin s) (Fin n) ℝ,
              frob (A - A * sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k) *
                Matrix.diagonal (fun j => Real.sqrt (s₁ j)) * P) ≤
              frob (A - A * sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k) *
                Matrix.diagonal (fun j => Real.sqrt (s₁ j)) * X)) →
            ∀ B : Matrix (Fin m) (Fin n) ℝ, B.rank ≤ k →
              frob (A - A * sampleMat (I ω) (fun i => (∑ a, Z i a ^ 2) / k) *
                Matrix.diagonal (fun j => Real.sqrt (s₁ j)) * P) ^ 2 ≤ 2410 / 9 * frob (A - B) ^ 2} := by
  sorry
