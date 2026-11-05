-- Expected: FAIL. The axiom's last name component is `propext`, added programmatically so the
-- source scan sees no `axiom` keyword. Only an exact name match against core may be allowed.
import Lean
open Lean Elab Command
run_cmd liftCoreM <| addDecl <| Declaration.axiomDecl {
  name := `Evil.propext, levelParams := [], type := mkConst ``False, isUnsafe := false }
theorem main_theorem : (1 : Nat) = 2 := False.elim Evil.propext
