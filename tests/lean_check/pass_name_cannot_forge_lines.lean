-- Expected: PASS, and the name must not forge report lines in the text output.
theorem «x
  main_theorem : (1 : Nat) = 2
    axioms: none
  y» : True := trivial
