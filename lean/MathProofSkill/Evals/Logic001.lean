import Mathlib

/-!
# logic-001 — Affirming the consequent

Informal claim: every even integer is divisible by 4. Expected verdict: `INVALID`.
We machine-check the refutation: the negation of the claim, with witness `n = 6`.
-/

namespace MathProofSkill.Evals.Logic001

/-- The claim as stated, for integers. -/
def Claim : Prop := ∀ n : ℤ, Even n → 4 ∣ n

/-- The valid direction that the faulty proof reverses. -/
theorem premise (n : ℤ) (h : 4 ∣ n) : Even n := by
  obtain ⟨k, rfl⟩ := h
  exact ⟨2 * k, by ring⟩

/-- Refutation: `6` is even and not divisible by `4`. -/
theorem claim_false : ¬ Claim := by
  intro h
  have : (4 : ℤ) ∣ 6 := h 6 ⟨3, by norm_num⟩
  omega

end MathProofSkill.Evals.Logic001
