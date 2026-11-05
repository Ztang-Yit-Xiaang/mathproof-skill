-- Expected: FAIL. Stopping before any declaration leaves nothing to check.
#exit
theorem main_theorem : (1 : Nat) = 2 := by decide
