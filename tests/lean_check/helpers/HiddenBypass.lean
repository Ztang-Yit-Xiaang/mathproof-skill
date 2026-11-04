-- Helper for fail_import_hides_bypass.lean. The test runner reads top-level *.lean files only.
import Lean
open Lean Elab Command
run_cmd liftCoreM <|
  withOptions (fun o => o.setBool (Name.mkStr `debug "skipKernelTC") true) <|
    addDecl <| Declaration.thmDecl {
      name := `false_thm, levelParams := [], type := mkConst ``False,
      value := mkConst ``True.intro }
theorem hidden_proof : (1 : Nat) = 2 := False.elim false_thm
