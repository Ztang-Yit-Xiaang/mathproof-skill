-- Expected: PASS, and the explicit form must expose what the short form hides. These print as
-- `5 ≤ 3`, `2 + 2 = 5`, and `1 = 2`. No constant from this file appears in any of them.
theorem inline_le : letI : LE Nat := ⟨fun _ _ => True⟩; (5 : Nat) ≤ 3 := trivial
theorem inline_add : @HAdd.hAdd Nat Nat Nat ⟨fun _ _ => 5⟩ 2 2 = 5 := rfl
theorem small_type : (1 : Fin 1) = 2 := rfl
