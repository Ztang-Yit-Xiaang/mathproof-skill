-- Expected: FAIL. The `axiom` keyword is not at the start of a line.
section axiom bad : (1 : Nat) = 2
theorem main_theorem : (1 : Nat) = 2 := bad
end
