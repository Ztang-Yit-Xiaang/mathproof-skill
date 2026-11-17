import Mathlib

def f (n : ℕ) : ℕ := n + 1

theorem localdef_thm_negation : ¬ (∀ n : ℕ, f n = n) := by
  intro h
  have := h 0
  simp [f] at this
