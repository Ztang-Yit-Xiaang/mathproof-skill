-- Expected: FAIL. An axiom with an internal-looking name, unused by the main theorem. Internal
-- names are hidden from the printed list, but they must still be audited.
import Lean
open Lean Elab Command
run_cmd liftCoreM <| addDecl <| Declaration.axiomDecl {
  name := `_hidden_axiom, levelParams := [], type := mkConst ``False, isUnsafe := false }
theorem main_theorem : True := trivial
