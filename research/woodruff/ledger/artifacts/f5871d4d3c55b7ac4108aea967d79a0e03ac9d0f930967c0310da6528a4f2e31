import Mathlib

/-!
Woodruff, "Sketching as a Tool for Numerical Linear Algebra" (arXiv 1411.4357), Theorem 23, with
Definition 20 (the ℓ2-regression problem). Statement only; the proof is our own.

Survey text: "If S is a sparse subspace embedding with O(d²/ε) rows, then with probability .99, the
solution min_{x'} ‖SAx' − Sb‖₂ = (1 ± ε) min_x ‖Ax − b‖₂."

Encoding.
* Reading: as in Definition 20, the sketched solution x' (any minimizer of ‖S(Ax' − b)‖) is a
  (1 + ε)-approximate solution of the original problem: ‖Ax' − b‖ ≤ (1 + ε)‖Ax − b‖ for all x.
  The lower side of "(1 ± ε)" holds trivially for a cost. The other literal reading, that the
  sketched optimal value is within (1 ± ε) of the true one, is false with O(d²/ε) rows, since
  ‖Sw‖² for the residual w fluctuates by about √ε; we do not encode it.
* "For every minimizer x'" is stated, which covers non-unique minimizers.
* S is the sparse embedding (CountSketch) matrix of §2.1, encoded exactly as in our Theorem 9
  file: `h` pairwise independent and uniform, `σ` ±1 and 4-wise independent, `h` independent of
  `σ` (our assumption, as for Theorem 9).
* ε ∈ (0, 1), as in Definition 20 with ε > 0. O(d²/ε) is made explicit as r ≥ 3200·d²/ε, which is
  a stronger claim than the O(·) form.
-/

open MeasureTheory ProbabilityTheory

/-- The sketch of a vector: bucket `j` collects `σ i * v i` over the coordinates `i` hashed to `j`. -/
def sketch {n r : ℕ} (h : Fin n → Fin r) (σ : Fin n → ℝ) (v : Fin n → ℝ) : Fin r → ℝ :=
  fun j => ∑ i, if h i = j then σ i * v i else 0

theorem woodruff_theorem23 {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) [IsProbabilityMeasure μ]
    {n d r : ℕ} (A : Matrix (Fin n) (Fin d) ℝ) (b : Fin n → ℝ) (ε : ℝ) (hε : 0 < ε) (hε1 : ε < 1)
    (hr : 3200 * (d : ℝ) ^ 2 / ε ≤ r)
    (h : Ω → Fin n → Fin r) (σ : Ω → Fin n → ℝ)
    (hmeas : Measurable h) (σmeas : Measurable σ)
    (hpair : ∀ i j : Fin n, i ≠ j → ∀ a b : Fin r,
      μ {ω | h ω i = a ∧ h ω j = b} = ENNReal.ofReal (1 / (r : ℝ) ^ 2))
    (σsign : ∀ ω i, σ ω i = 1 ∨ σ ω i = -1)
    (σfour : ∀ T : Finset (Fin n), T.card ≤ 4 → T.Nonempty → ∫ ω, ∏ i ∈ T, σ ω i ∂μ = 0)
    (hσind : IndepFun h σ μ) :
    ENNReal.ofReal 0.99 ≤ μ {ω | ∀ x' : Fin d → ℝ,
      (∀ z : Fin d → ℝ, ∑ j, (sketch (h ω) (σ ω) (fun i => A.mulVec x' i - b i) j) ^ 2 ≤
        ∑ j, (sketch (h ω) (σ ω) (fun i => A.mulVec z i - b i) j) ^ 2) →
      ∀ x : Fin d → ℝ, Real.sqrt (∑ i, (A.mulVec x' i - b i) ^ 2) ≤
        (1 + ε) * Real.sqrt (∑ i, (A.mulVec x i - b i) ^ 2)} := by
  sorry
