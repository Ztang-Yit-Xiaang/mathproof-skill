-- Expected: PASS. Core Lean only; mentions sorry in a comment and in "a sorry string".
def Claim : Prop := ∀ n : Nat, n + 0 = n
theorem claim_true : Claim := fun n => rfl
theorem uses_choice (p : Prop) : p ∨ ¬p := Classical.em p
/- block comment with sorry and axiom inside -/
def msg : String := "sorry"
