-- Expected: FAIL (custom axiom).
axiom magic : ∀ p : Prop, p
theorem t : 1 = 2 := magic _
