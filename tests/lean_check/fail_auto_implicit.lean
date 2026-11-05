-- Expected: FAIL. `x` is a typo-style unbound name. Auto-bound implicits would quietly turn it
-- into a universally quantified variable, changing the claim.
theorem main_theorem (h : x = x) : x = x := h
