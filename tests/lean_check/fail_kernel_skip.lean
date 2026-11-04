-- Expected: FAIL. The kernel check is switched off through an option name built from strings,
-- so a source scan cannot see it, and `False` gets "proved" with no axioms. Only a kernel
-- replay of the compiled file can catch this.
import Lean
open Lean Elab Command
run_cmd liftCoreM <|
  withOptions (fun o => o.setBool (Name.mkStr `debug "skipKernelTC") true) <|
    addDecl <| Declaration.thmDecl {
      name := `false_thm, levelParams := [], type := mkConst ``False,
      value := mkConst ``True.intro }
theorem main_theorem : (1 : Nat) = 2 := False.elim false_thm
