-- Expected: FAIL. `#guard_msgs` swallows the elaboration error, so Lean exits 0 and prints no
-- error. The failed proof is still recorded with `sorryAx`, and the audit must see that.
#guard_msgs(drop all) in
theorem main_theorem : (1 : Nat) = 2 := by rfl
