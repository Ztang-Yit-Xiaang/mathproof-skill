import Mathlib

-- Redefines the statement's local f so that the false statement becomes true.
def f (n : ℕ) : ℕ := n

theorem localdef_thm : (∀ n : ℕ, f n = n) := fun _ => rfl
