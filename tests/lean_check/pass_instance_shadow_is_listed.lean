-- Expected: PASS, with the local instance reported. The kernel is right to accept this: `+` here
-- means the file's own constant-zero addition. The printed `1 + 1 = 0` looks like a false claim
-- about Nat, so the report must list `evilAdd` under what the statement uses.
instance evilAdd : Add Nat := ⟨fun _ _ => 0⟩
theorem main_theorem : (1 : Nat) + 1 = 0 := rfl
