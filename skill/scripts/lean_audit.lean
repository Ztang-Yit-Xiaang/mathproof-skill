/-
Audit driver for lean_check.py. Reports what a compiled Lean file's declarations depend on.

    lean --run lean_audit.lean axioms TARGET_MODULE EXPECTED_OLEAN OUT.json
    lean --run lean_audit.lean statements TARGET_OLEAN OUT.json
    lean --run lean_audit.lean reachable OUT.json ROOTS MODULE...

Each mode is its own process, because each imports Mathlib once. Two imports in one process used
about 9 GB per process on Linux and ran a CI machine out of memory.

- `axioms` imports the file with extensions off and uses Lean's own `collectAxioms`. With
  extensions off, the file's initializers do not run and data it stored is not trusted.
- `statements` reads the compiled file without importing it, and prints in an environment holding
  only its imports, with extensions on. Mathlib's notation prints, and the file's own notation,
  unexpanders, and delaborators do not. The file's own definitions therefore print with their
  implicit arguments shown.
- `reachable` checks that direct imports belong to a real library, such as `import Mathlib`.

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

def coreContext : Core.Context := { fileName := "<lean_audit>", fileMap := default }

def runCore (env : Environment) (m : CoreM α) (options : Options := {}) : IO α := do
  return (← m.toIO { coreContext with options } { env := env }).1

/-- Metadata can carry printing options, so a statement could ask to be hidden. -/
partial def stripMData (e : Expr) : Expr :=
  e.replace fun e => if e.isMData then some (stripMData e.consumeMData) else none

/-- Print in the short form, or with `explicit` in a form that shows every instance and numeric
type, which notation can hide: `2 + 2 = 5` may use a local `+`, and `1 = 2` may be in `Fin 1`. -/
def pretty (deps : Environment) (e : Expr) (explicit := false) : IO String := do
  let mut options : Options := ({} : Options).setBool `pp.deepTerms true
  if explicit then
    options := (options.setBool `pp.explicit true).setBool `pp.numericTypes true
  try
    runCore deps (options := options) do
      let f ← Meta.MetaM.run' (Meta.ppExpr (stripMData e))
      return (toString f).replace "\n" " "
  catch err =>
    return s!"<could not print: {err}>"

def names (xs : Array Name) : Json :=
  toJson (xs.map toString)

def sorted (s : NameSet) : Array Name :=
  s.toArray.qsort Name.lt

/-- A generated eliminator of an inductive type from this file. The name alone is not enough:
a user could call their own definition `Foo.casesOn`. -/
def isAuxiliary (locals : NameMap ConstantInfo) (n : Name) : Bool :=
  match n with
  | .str parent s =>
    s ∈ ["casesOn", "recOn", "brecOn", "binductionOn", "noConfusion"] &&
      match locals.find? parent with
      | some (.inductInfo _) | some (.ctorInfo _) => true
      | _ => false
  | _ => false

/-- What a reader must know to understand a constant. A theorem's proof is not part of what a
statement means, so only its type counts. -/
def meaningRefs (ci : ConstantInfo) : Array Name :=
  let used (e : Expr) := e.getUsedConstants
  match ci with
  | .defnInfo v => used v.type ++ used v.value
  | .opaqueInfo v => used v.type ++ used v.value
  | .ctorInfo v => used v.type ++ #[v.induct]
  | .inductInfo v => used v.type ++ v.ctors.toArray
  | ci => used ci.type

/-- Every constant of this file that a statement depends on for its meaning. -/
partial def statementClosure (locals : NameMap ConstantInfo) (statement : Expr) : NameSet :=
  let rec visit (seen : NameSet) (c : Name) : NameSet :=
    if seen.contains c then seen else
    match locals.find? c with
    | some ci => (meaningRefs ci).foldl visit (seen.insert c)
    | none => seen
  statement.getUsedConstants.foldl visit {}

/-- Report any permitted axiom that is not the one from core. -/
def coreMismatches (locals : NameMap ConstantInfo) (env : Environment) : Array Name :=
  coreAxioms.toArray.filterMap fun (n, want) =>
    if locals.contains n then
      some n
    else match env.find? n with
      | some ci => if ci matches .axiomInfo _ && toString ci.type == want then none else some n
      | none => some n

def isUnder (path : System.FilePath) (dir : System.FilePath) : Bool :=
  path.toString.startsWith (dir.toString ++ "/")

/-- Every imported module must come from the toolchain or from the project's packages. -/
def locationProblems (env : Environment) (target : Name) : IO (Array String) := do
  let toolchain := (← findSysroot) / "lib" / "lean"
  let packages := (← IO.currentDir) / ".lake" / "packages"
  let mut problems := #[]
  for m in env.header.moduleNames do
    if m == target then continue
    let path ← findOLean m
    unless isUnder path toolchain || isUnder path packages do
      problems := problems.push s!"import-location: {m} is loaded from {path}"
  return problems

/-- Modules must be reachable from a root that exists here, so a file planted under a real
package's directory is refused. -/
def reachabilityProblems (roots others : Array Name) : IO (Array String) := do
  let mut present : Array Import := #[]
  for root in roots do
    -- A project without Mathlib has no such package, and Lean reports that by throwing.
    let found ← try (← findOLean root).pathExists catch _ => pure false
    if found then
      present := present.push { module := root }
  let trusted ← importModules present {} (trustLevel := 0) (loadExts := false)
  let known := trusted.header.moduleNames.foldl NameSet.insert {}
  return (others.filter (!known.contains ·)).map fun m =>
    s!"import-not-reachable: {m} is not part of Lean or `import Mathlib`"

/-- The module under audit must be the file just compiled, not a planted one of the same name. -/
def targetProblems (target : Name) (expected : String) : IO (Array String) := do
  let path ← findOLean target
  return if path.toString == expected then #[]
    else #[s!"target-location: {target} loads from {path}, not the file just compiled"]

unsafe def runAxioms (target : Name) (expected out : String) : IO Unit := do
  initSearchPath (← findSysroot)
  let planted ← targetProblems target expected
  let env ← importModules #[{ module := target }] {} (trustLevel := 0) (loadExts := false)
  let some idx := env.getModuleIdx? target
    | throw (IO.userError s!"module {target} did not load")
  let mod := env.header.moduleData[idx.toNat]!
  let locals := mod.constants.foldl (fun (m : NameMap ConstantInfo) ci => m.insert ci.name ci) {}
  let direct := (mod.imports.map (·.module)).foldl NameSet.insert {} |> sorted
  let mut constants : Array (String × Json) := #[]
  for n in mod.constNames do
    constants := constants.push (toString n, names (← runCore env (collectAxioms n)))
  let report := Json.mkObj
    [("is_module", toJson mod.isModule),
     ("imports", names direct),
     ("import_problems", toJson (planted ++ (← locationProblems env target))),
     ("constants", Json.mkObj constants.toList),
     ("core_mismatches", names (coreMismatches locals env))]
  IO.FS.writeFile out report.compress

unsafe def runStatements (olean out : String) : IO Unit := do
  initSearchPath (← findSysroot)
  let (mod, _) ← readModuleData olean
  enableInitializersExecution
  let deps ← importModules mod.imports {} (trustLevel := 0) (loadExts := true)
  let locals := mod.constants.foldl (fun (m : NameMap ConstantInfo) ci => m.insert ci.name ci) {}
  let ordered := mod.constants.qsort fun a b => Name.lt a.name b.name
  let mut declarations : Array Json := #[]
  let mut unsafeDecls : Array Name := #[]
  let mut context : NameSet := {}
  for ci in ordered do
    let n := ci.name
    if n.isInternal || isAuxiliary locals n then
      continue
    if ci.isUnsafe then
      unsafeDecls := unsafeDecls.push n
    let uses := statementClosure locals ci.type
    context := uses.foldl NameSet.insert context
    let mut fields := [("name", toJson (toString n)),
      ("kind", toJson (if ci matches .thmInfo _ then "theorem" else "other")),
      ("type", toJson (← pretty deps ci.type)),
      ("type_explicit", toJson (← pretty deps ci.type (explicit := true))),
      ("statement_uses", names (sorted uses))]
    if let .defnInfo d := ci then
      if d.type.isProp || d.type.isSort then
        fields := fields ++ [("definition", toJson (← pretty deps d.value))]
    declarations := declarations.push (Json.mkObj fields)
  let mut statementContext : Array (String × Json) := #[]
  for n in sorted context do
    let some ci := locals.find? n | continue
    let mut fields := [("type", toJson (← pretty deps ci.type))]
    match ci with
    | .defnInfo d => fields := fields ++ [("definition", toJson (← pretty deps d.value))]
    | .opaqueInfo d => fields := fields ++ [("definition", toJson (← pretty deps d.value))]
    | _ => pure ()
    statementContext := statementContext.push (toString n, Json.mkObj fields)
  let report := Json.mkObj
    [("declarations", toJson declarations),
     ("statement_context", Json.mkObj statementContext.toList),
     ("unsafe", names unsafeDecls)]
  IO.FS.writeFile out report.compress

unsafe def runReachable (out roots : String) (modules : List String) : IO Unit := do
  initSearchPath (← findSysroot)
  let rootNames := ((roots.splitOn ",").map String.toName).toArray
  let problems ← reachabilityProblems rootNames (modules.map String.toName).toArray
  IO.FS.writeFile out (toJson problems).compress

end LeanAudit

unsafe def main (args : List String) : IO UInt32 := do
  match args with
  | ["axioms", target, expected, out] =>
    LeanAudit.runAxioms target.toName expected out
    return 0
  | ["statements", olean, out] =>
    LeanAudit.runStatements olean out
    return 0
  | "reachable" :: out :: roots :: modules =>
    LeanAudit.runReachable out roots modules
    return 0
  | _ =>
    IO.eprintln "usage: see the comment at the top of lean_audit.lean"
    return 2
