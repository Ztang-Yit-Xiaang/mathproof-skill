import Mathlib

theorem weak_thm : (∀ n : ℕ, 0 < n → 2 ≤ n * 2) := by
  intro n h
  omega
