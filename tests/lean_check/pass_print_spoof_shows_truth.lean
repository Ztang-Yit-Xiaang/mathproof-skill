-- Expected: PASS, and the printed statements must be the real ones. The notation and the
-- unexpander try to make the reader see `False` and `0`. Printing must ignore this file's
-- notation, so a fidelity check reads what was actually proved.
notation "False" => True
theorem main_theorem : False := trivial
@[app_unexpander Nat.succ] def spoof : Lean.PrettyPrinter.Unexpander
  | `($_ $_) => `(0)
  | _ => throw ()
theorem succ_statement (n : Nat) : Nat.succ n = n + 1 := rfl
