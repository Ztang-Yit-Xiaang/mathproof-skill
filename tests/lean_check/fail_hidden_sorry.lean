-- Expected: FAIL (a dependency uses sorryAx through a macro that hides the word).
macro "trust_me" : tactic => `(tactic| exact sorryAx _ false)
theorem t (n : Nat) : n * 1 = n := by trust_me
