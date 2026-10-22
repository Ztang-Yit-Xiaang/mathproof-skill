import Mathlib

/-!
# analysis-002 — Pointwise convergence does not justify exchanging limit and integral

Informal claim: pointwise convergence permits exchanging limit and integral. Expected verdict:
`INCOMPLETE` (an interchange theorem is missing). We machine-check the counterexample:
`f n = (n + 1) · 1_{(0, 1/(n+1))}` on `(0, 1)`. Each `f n` has integral `1` over `(0, 1)`,
yet `f n x → 0` for every `x ∈ (0, 1)`, so `lim ∫ f n = 1 ≠ 0 = ∫ lim f n`.
(Indexing by `n + 1` avoids the junk value `1/0 = 0` in Lean.)
-/

namespace MathProofSkill.Evals.Analysis002

open MeasureTheory Set Filter Topology

noncomputable def f (n : ℕ) : ℝ → ℝ :=
  (Ioo (0 : ℝ) (1 / (n + 1))).indicator fun _ => (n + 1 : ℝ)

theorem integral_f (n : ℕ) : ∫ x in Ioo (0 : ℝ) 1, f n x = 1 := by
  have hsub : Ioo (0 : ℝ) (1 / (n + 1)) ⊆ Ioo 0 1 := by
    apply Ioo_subset_Ioo_right
    rw [div_le_one (by positivity)]
    linarith [(n.cast_nonneg : (0 : ℝ) ≤ n)]
  rw [f, integral_indicator measurableSet_Ioo, Measure.restrict_restrict measurableSet_Ioo,
    inter_eq_left.mpr hsub, setIntegral_const, Measure.real, Real.volume_Ioo,
    ENNReal.toReal_ofReal (by rw [sub_zero]; positivity), smul_eq_mul]
  field_simp
  ring

theorem tendsto_f (x : ℝ) (hx : x ∈ Ioo (0 : ℝ) 1) : Tendsto (fun n => f n x) atTop (𝓝 0) := by
  obtain ⟨N, hN⟩ := exists_nat_one_div_lt hx.1
  apply tendsto_atTop_of_eventually_const (i₀ := N)
  intro n hn
  rw [f, indicator_of_notMem]
  rintro ⟨_, hlt⟩
  have : (1 : ℝ) / (n + 1) ≤ 1 / (N + 1) :=
    one_div_le_one_div_of_le (by positivity) (by exact_mod_cast Nat.add_le_add_right hn 1)
  linarith

/-- The exchange fails: the integrals are constantly `1`, the pointwise limit is `0`. -/
theorem exchange_fails :
    Tendsto (fun n => ∫ x in Ioo (0 : ℝ) 1, f n x) atTop (𝓝 1) ∧
    (∀ x ∈ Ioo (0 : ℝ) 1, Tendsto (fun n => f n x) atTop (𝓝 0)) ∧
    ∫ _ in Ioo (0 : ℝ) 1, (0 : ℝ) ≠ 1 := by
  refine ⟨?_, tendsto_f, by simp⟩
  simp only [integral_f]
  exact tendsto_const_nhds

end MathProofSkill.Evals.Analysis002
