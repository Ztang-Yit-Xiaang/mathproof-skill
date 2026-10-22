-- Expected: FAIL (native_decide trusts the compiler: Lean.ofReduceBool).
theorem t : 2 ^ 10 = 1024 := by native_decide
