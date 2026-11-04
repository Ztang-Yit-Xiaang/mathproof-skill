/-
Audit driver for lean_check.py. Reports what a compiled Lean file's declarations depend on.

    lean --run lean_audit.lean TARGET.olean OUT.json

The compiled file is read as plain data and never imported, so nothing it defines runs here and
its notation, unexpanders, and delaborators cannot change what gets printed. Its imports, which
lean_check.py restricts to an allow-list, are loaded normally so that Mathlib's notation prints.

Because the file's constants are not in that environment, its own definitions print with their
implicit arguments shown (`imp Nat x`, not `imp x`). That is accepted: this output is read to
compare a statement with a claim, and more explicit is safer.

This is a defense for the local checker and not a root of trust. See section 7 of
references/lean-verification.md.
-/
import Lean

open Lean

namespace LeanAudit

/-- The permitted axioms and their exact types in core Lean. A same-named axiom of any other
type, or one defined by the checked file, is not the real one. -/
def coreAxioms : List (Name × String) :=
  [(`propext, "forall {a : Prop} {b : Prop}, (Iff a b) -> (Eq.{1} Prop a b)"),
   (`Classical.choice, "forall {α : Sort.{u}}, (Nonempty.{u} α) -> α"),
   (`Quot.sound, "forall {α : Sort.{u}} {r : α -> α -> Prop} {a : α} {b : α}, (r a b) -> (Eq.{u} (Quot.{u} α r) (Quot.mk.{u} α r a) (Quot.mk.{u} α r b))")]

structure State where
  /-- Axioms of imported constants, computed once each. -/
  imported : NameMap (Array Name) := {}
  /-- Constants referenced but found neither in the file nor in its imports. -/
  unresolved : NameSet := {}

abbrev M := StateT State IO

def coreContext : Core.Context := { fileName := "<lean_audit>", fileMap := default }

def importedAxioms (deps : Environment) (c : Name) : M (Array Name) := do
  if let some axs := (← get).imported.find? c then
    return axs
  let (axs, _) ← (collectAxioms c : CoreM (Array Name)).toIO coreContext { env := deps }
  modify fun s => { s with imported := s.imported.insert c axs }
  return axs

/-- The constants a declaration directly refers to, in the same way as `Lean.collectAxioms`. -/
def references (ci : ConstantInfo) : Array Name :=
  let inTerm (e : Expr) := e.getUsedConstants
  match ci with
  | .axiomInfo v | .ctorInfo v | .recInfo v => inTerm v.type
  | .defnInfo v => inTerm v.type ++ inTerm v.value
  | .thmInfo v => inTerm v.type ++ inTerm v.value
  | .opaqueInfo v => inTerm v.type ++ inTerm v.value
  | .quotInfo _ => #[]
  | .inductInfo v => inTerm v.type ++ v.ctors.toArray

/-- All axioms reachable from `root`, walking the file's constants, then its imports'. -/
partial def axiomsOf (locals : NameMap ConstantInfo) (deps : Environment) (root : Name) :
    M NameSet := do
  let rec visit (c : Name) (st : NameSet × NameSet) : M (NameSet × NameSet) := do
    let (seen, axioms) := st
    if seen.contains c then
      return st
    let seen := seen.insert c
    match locals.find? c with
    | some ci =>
      let axioms := if ci matches .axiomInfo _ then axioms.insert c else axioms
      (references ci).foldlM (fun st d => visit d st) (seen, axioms)
    | none =>
      if deps.contains c then
        let axs ← importedAxioms deps c
        return (seen, axs.foldl NameSet.insert axioms)
      modify fun s => { s with unresolved := s.unresolved.insert c }
      return (seen, axioms)
  return (← visit root ({}, {})).2

/-- Generated eliminators, left out of the printed list (but audited like everything else). -/
def isAuxiliary (n : Name) : Bool :=
  match n with
  | .str _ s => s ∈ ["casesOn", "recOn", "brecOn", "binductionOn", "noConfusion"]
  | _ => false

def pretty (deps : Environment) (e : Expr) : IO String := do
  let m : CoreM String := do
    let f ← Meta.MetaM.run' (Meta.ppExpr e)
    return (toString f).replace "\n" " "
  let (s, _) ← m.toIO coreContext { env := deps }
  return s

def names (xs : Array Name) : Json :=
  toJson (xs.map toString)

def sorted (s : NameSet) : Array Name :=
  s.toArray.qsort Name.lt

/-- Report any permitted axiom that is not the one from core. -/
def coreMismatches (locals : NameMap ConstantInfo) (deps : Environment) : Array Name :=
  coreAxioms.toArray.filterMap fun (n, want) =>
    if locals.contains n then
      some n
    else match deps.find? n with
      | some ci => if ci matches .axiomInfo _ && toString ci.type == want then none else some n
      | none => some n

unsafe def run (target out : String) : IO Unit := do
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let (mod, _) ← readModuleData target
  let deps ← importModules mod.imports {} (trustLevel := 0) (loadExts := true)
  let locals := mod.constants.foldl (fun (m : NameMap ConstantInfo) ci => m.insert ci.name ci) {}
  let ordered := mod.constants.qsort fun a b => Name.lt a.name b.name
  let mut declarations : Array Json := #[]
  let mut hidden : Array Json := #[]
  let mut unsafeDecls : Array Name := #[]
  let mut state : State := {}
  for ci in ordered do
    let n := ci.name
    let (axs, st) ← (axiomsOf locals deps n).run state
    state := st
    let axioms := names (sorted axs)
    if n.isInternal || isAuxiliary n then
      hidden := hidden.push (Json.mkObj [("name", toString n), ("axioms", axioms)])
      continue
    if ci.isUnsafe then
      unsafeDecls := unsafeDecls.push n
    -- This file's own constants in the statement. A local instance can change what `+` means
    -- while the printed statement looks standard, so the reader needs to see these listed.
    let own := ci.type.getUsedConstants.filter (locals.contains ·)
    let mut fields := [("name", toJson (toString n)), ("axioms", axioms),
      ("type", toJson (← pretty deps ci.type)),
      ("statement_uses", names (sorted (own.foldl NameSet.insert {})))]
    if let .defnInfo d := ci then
      if d.type.isProp || d.type.isSort then
        fields := fields ++ [("definition", toJson (← pretty deps d.value))]
    declarations := declarations.push (Json.mkObj fields)
  let report := Json.mkObj
    [("is_module", toJson mod.isModule),
     ("imports", names (mod.imports.map (·.module))),
     ("declarations", toJson declarations),
     ("hidden", toJson hidden),
     ("unsafe", names unsafeDecls),
     ("core_mismatches", names (coreMismatches locals deps)),
     ("unresolved", names (sorted state.unresolved))]
  IO.FS.writeFile out report.compress

end LeanAudit

unsafe def main (args : List String) : IO UInt32 := do
  match args with
  | [target, out] =>
    LeanAudit.run target out
    return 0
  | _ =>
    IO.eprintln "usage: lean --run lean_audit.lean TARGET.olean OUT.json"
    return 2
