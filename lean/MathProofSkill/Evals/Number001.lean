import Mathlib

/-!
# number-001 — Even square

Informal claim: the square of an even integer is even. Expected verdict: `VALID`.
The Lean proof follows the informal witness argument `n = 2k ⇒ n² = 2(2k²)`.
-/

namespace MathProofSkill.Evals.Number001

theorem even_sq (n : ℤ) (h : Even n) : Even (n ^ 2) := by
  obtain ⟨k, rfl⟩ := h
  exact ⟨2 * k ^ 2, by ring⟩

end MathProofSkill.Evals.Number001
