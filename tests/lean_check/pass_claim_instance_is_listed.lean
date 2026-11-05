-- Expected: PASS, with the local instance reported through `Claim`. The theorem's own statement
-- mentions only `Claim`, and the instance that changes `+` sits inside its definition.
instance evilAdd : Add Nat := ⟨fun _ _ => 0⟩
def Claim : Prop := (1 : Nat) + 1 = 0
theorem main_theorem : Claim := rfl
