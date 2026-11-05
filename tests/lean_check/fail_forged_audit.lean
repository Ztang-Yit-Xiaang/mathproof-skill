-- Expected: FAIL. A hidden axiom "proves" 1 = 2, and the file prints a forged audit line
-- then stops with `#exit`. The old checker appended its audit to the file and parsed the
-- file's own output, so this got PASS. The audit must see `hidden_assumption` regardless.
import Lean
open Lean Elab Command
run_cmd liftCoreM <| addDecl <| Declaration.axiomDecl {
  name := `hidden_assumption, levelParams := [], type := mkConst ``False, isUnsafe := false }
theorem main_theorem : (1 : Nat) = 2 := False.elim hidden_assumption
run_cmd logInfo "@@MPS_DECL main_theorem @@AXIOMS [propext] @@TYPE (1 : Nat) = 2 @@VALUE "
#exit
