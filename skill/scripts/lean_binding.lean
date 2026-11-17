/-
Binding check for a frozen statement's Challenge (mathproof_core/statement.py, S2.2.T1).

    lean --run lean_binding.lean NAME NEGATION FIRST_LINE SECOND_LINE

The Challenge module must already be compiled and on the search path. This driver loads it with
`importModules`, with extensions off, so nothing the statement's preamble defines can change how
this file is parsed or run, and the Challenge's initializers do not run. It checks:

- `NAME` and `NEGATION` are theorems declared at the root by the Challenge module,
- on the lines the generator wrote them, so the preamble cannot declare them itself,
- and the type of `NEGATION` is exactly `Not` applied to the type of `NAME`.

It prints `mathproof-binding: ok` and exits 0, or prints the first problem and exits 1. The type
and local definitions a person reads come from `lean_audit.lean statements`, run separately.
-/
import Lean

open Lean

namespace LeanBinding

def coreContext : Core.Context := { fileName := "<lean_binding>", fileMap := default }

def runCore (env : Environment) (m : CoreM α) : IO α := do
  return (← m.toIO coreContext { env := env }).1

def check (env : Environment) (name negation : Name) (first second : Nat) : IO (Option String) := do
  let some idx := env.getModuleIdx? `Challenge
    | return some "the Challenge module did not load"
  for (n, line) in [(name, first), (negation, second)] do
    let some ci := env.find? n
      | return some s!"{n} is not declared at the root"
    unless ci matches .thmInfo _ do
      return some s!"{n} is not a theorem"
    unless env.getModuleIdxFor? n == some idx do
      return some s!"{n} is not declared by the Challenge"
    let some ranges ← runCore env (findDeclarationRanges? n)
      | return some s!"{n} has no source position"
    unless ranges.range.pos.line == line do
      return some s!"{n} is declared on line {ranges.range.pos.line}, not {line}"
  let some claim := env.find? name | return some s!"{name} is missing"
  let some neg := env.find? negation | return some s!"{negation} is missing"
  unless neg.type == mkApp (mkConst ``Not) claim.type do
    return some "the negation is not exactly Not of the claim"
  return none

end LeanBinding

unsafe def main (args : List String) : IO UInt32 := do
  match args with
  | [name, negation, first, second] =>
    let (some first, some second) := (first.toNat?, second.toNat?)
      | IO.eprintln "mathproof-binding: line numbers must be natural numbers"; return 2
    initSearchPath (← findSysroot)
    let env ← importModules #[{ module := `Challenge }] {} (trustLevel := 0) (loadExts := false)
    match ← LeanBinding.check env name.toName negation.toName first second with
    | none => IO.println "mathproof-binding: ok"; return 0
    | some problem => IO.println s!"mathproof-binding: {problem}"; return 1
  | _ =>
    IO.eprintln "usage: lean --run lean_binding.lean NAME NEGATION FIRST_LINE SECOND_LINE"
    return 2
