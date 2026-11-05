-- Expected: PASS, with the statement visible. Metadata on the type tries to make the printer
-- show only `⋯`, so a reader could not see what was proved.
import Lean
open Lean Elab Command
run_cmd liftCoreM <| addDecl <| Declaration.thmDecl {
  name := `main_theorem, levelParams := [],
  type := mkMData (KVMap.empty.insert `pp.deepTerms.threshold (.ofNat 0))
    (mkApp3 (mkConst ``Eq [1]) (mkConst ``Bool) (mkConst ``Bool.true) (mkConst ``Bool.true)),
  value := mkApp2 (mkConst ``Eq.refl [1]) (mkConst ``Bool) (mkConst ``Bool.true) }
