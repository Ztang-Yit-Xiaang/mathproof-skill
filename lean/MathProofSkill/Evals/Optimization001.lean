import Mathlib

/-!
# optimization-001 — Stationary is not globally optimal

Informal claim: every stationary point of a differentiable function is a global minimum.
Expected verdict: `INVALID`. Counterexample: `f x = -x²` at `0`.
-/

namespace MathProofSkill.Evals.Optimization001

open Set

def Claim : Prop :=
  ∀ f : ℝ → ℝ, Differentiable ℝ f → ∀ x, deriv f x = 0 → IsMinOn f univ x

theorem claim_false : ¬ Claim := by
  intro h
  have hd : Differentiable ℝ (fun x : ℝ => -x ^ 2) := by fun_prop
  have hstat : deriv (fun x : ℝ => -x ^ 2) 0 = 0 := by simp
  have := h _ hd 0 hstat (mem_univ 1)
  norm_num at this

end MathProofSkill.Evals.Optimization001
