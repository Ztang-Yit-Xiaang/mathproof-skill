#!/usr/bin/env python3
"""Spike S2.1.T6: run attacks through `lake comparator` in its sandbox and record what happens.

Run this only in a throwaway Linux CI job. Each case is its own Lake project. Nothing hostile is
ever built outside the sandbox: the manifest is written by hand, not by building.

Prints each result verbatim and writes spike_report.json. Exits 1 only if a control misbehaves or
a hostile case passes, so that a surprise cannot be missed in the CI status.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent
TOOLCHAIN = "leanprover/lean4:v4.35.0"
AXIOMS = ["propext", "Quot.sound", "Classical.choice"]
ESCAPE_MARKERS = [Path("/tmp/mps_spike_escape"), Path.home() / "mps_spike_escape",
                  Path(os.environ.get("GITHUB_WORKSPACE", "/tmp")) / "mps_spike_escape"]

ONE_IS_TWO = "theorem main_theorem : (1 : Nat) = 2 := sorry\n"
FALSE = "theorem main_theorem : False := sorry\n"
TRUE = "theorem main_theorem : True := sorry\n"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def escape_attempt() -> str:
    writes = "\n".join(f'run_cmd do try IO.FS.writeFile "{m}" "escaped" catch _ => pure ()' for m in ESCAPE_MARKERS)
    return f"import Lean\nopen Lean Elab Command\n{writes}\ntheorem main_theorem : True := trivial\n"


# A complete fake core, so the exporter's lookup of Quot and Nat.* cannot stop it by crashing.
FULL_PRELUDE = """prelude
universe u
set_option genCtorIdx false
unsafe axiom lcErased : Type
unsafe axiom lcAny : Type
unsafe axiom lcVoid : Type
unsafe axiom lcProof {α : Prop} : α
-- A complete fake core: `False` here has a constructor, so `main_theorem : False` is easy to prove.
inductive False : Prop where | intro : False
inductive Eq {α : Sort u} (a : α) : α → Prop where | refl : Eq a a
init_quot
inductive Iff (a b : Prop) : Prop where | intro (mp : a → b) (mpr : b → a) : Iff a b
inductive Nonempty (α : Sort u) : Prop where | intro (val : α) : Nonempty α
axiom propext {a b : Prop} : Iff a b → Eq a b
axiom Quot.sound {α : Sort u} {r : α → α → Prop} {a b : α} : r a b → Eq (Quot.mk r a) (Quot.mk r b)
axiom Classical.choice {α : Sort u} : Nonempty α → α
inductive Bool : Type where | false | true
inductive Nat : Type where | zero | succ (n : Nat)
inductive List (α : Type u) : Type u where | nil | cons (head : α) (tail : List α)
inductive Char : Type where | mk (val : Nat)
inductive String : Type where | mk (data : List Char)
noncomputable def Nat.add (a _ : Nat) : Nat := a
noncomputable def Nat.sub (a _ : Nat) : Nat := a
noncomputable def Nat.mul (a _ : Nat) : Nat := a
noncomputable def Nat.pow (a _ : Nat) : Nat := a
noncomputable def Nat.gcd (a _ : Nat) : Nat := a
noncomputable def Nat.div (a _ : Nat) : Nat := a
noncomputable def Nat.mod (a _ : Nat) : Nat := a
noncomputable def Nat.beq (_ _ : Nat) : Bool := Bool.true
noncomputable def Nat.ble (_ _ : Nat) : Bool := Bool.true
noncomputable def Nat.land (a _ : Nat) : Nat := a
noncomputable def Nat.lor (a _ : Nat) : Nat := a
noncomputable def Nat.xor (a _ : Nat) : Nat := a
noncomputable def Nat.shiftLeft (a _ : Nat) : Nat := a
noncomputable def Nat.shiftRight (a _ : Nat) : Nat := a
noncomputable def String.ofList (data : List Char) : String := String.mk data
noncomputable def Char.ofNat (n : Nat) : Char := Char.mk n
noncomputable def eagerReduce {α : Sort u} (a : α) : α := a
noncomputable def optParam (α : Sort u) (_ : α) : Sort u := α
noncomputable def autoParam (α : Sort u) (_ : Nat) : Sort u := α
noncomputable def semiOutParam (α : Sort u) : Sort u := α
noncomputable def outParam (α : Sort u) : Sort u := α
theorem main_theorem : False := False.intro
"""


# name, kind, Challenge source, Solution source, extra modules.
# control-pass and control-fail check the judge works at all; attack must fail; trust documents a limit.
CASES = [
    ("valid_proof", "control-pass", "theorem main_theorem : (2 : Nat) + 2 = 4 := sorry\n",
     "theorem main_theorem : (2 : Nat) + 2 = 4 := rfl\n", {}),
    ("solution_only_reexports_sorry", "attack", "theorem main_theorem : (2 : Nat) + 2 = 4 := sorry\n",
     "import Challenge\n", {}),
    ("weaker_statement", "control-fail", "theorem main_theorem : ∀ n : Nat, n + 0 = n ∧ 0 + n = n := sorry\n",
     "theorem main_theorem : ∀ n : Nat, n + 0 = n := fun _ => rfl\n", {}),
    ("weak_challenge_is_trusted", "trust", TRUE, "theorem main_theorem : True := trivial\n", {}),
    ("forged_audit", "attack", ONE_IS_TWO, fixture("fail_forged_audit.lean"), {}),
    ("kernel_skip", "attack", ONE_IS_TWO, fixture("fail_kernel_skip.lean"), {}),
    ("prelude_spoof", "attack", FALSE, fixture("fail_prelude_spoof.lean"), {}),
    ("midline_axiom", "attack", ONE_IS_TWO, fixture("fail_midline_axiom.lean"), {}),
    ("core_shadow", "attack", ONE_IS_TWO, fixture("fail_core_shadow.lean"), {}),
    ("native_decide", "attack", "theorem main_theorem : 1000 * 1000 = 1000000 := sorry\n",
     "theorem main_theorem : 1000 * 1000 = 1000000 := by native_decide\n", {}),
    ("sorry_proof", "attack", ONE_IS_TWO, "theorem main_theorem : (1 : Nat) = 2 := by sorry\n", {}),
    ("guarded_error", "attack", ONE_IS_TWO, fixture("fail_guarded_error.lean"), {}),
    ("notation_spoof", "attack", FALSE, 'notation "False" => True\ntheorem main_theorem : False := trivial\n', {}),
    ("instance_shadow", "attack", "theorem main_theorem : (1 : Nat) + 1 = 0 := sorry\n",
     fixture("pass_instance_shadow_is_listed.lean"), {}),
    ("hidden_import", "attack", ONE_IS_TWO, "import Helper\ntheorem main_theorem : (1 : Nat) = 2 := hidden_proof\n",
     {"Helper": fixture("helpers/HiddenBypass.lean")}),
    ("tamper_challenge", "attack", ONE_IS_TWO,
     'import Lean\nopen Lean Elab Command\nrun_cmd do\n'
     '  for f in ["Challenge.lean", "comparator.json"] do\n'
     '    try IO.FS.writeFile f "theorem main_theorem : True := sorry\\n" catch _ => pure ()\n'
     'theorem main_theorem : True := trivial\n', {}),
    ("escape_attempt", "escape", TRUE, escape_attempt(), {}),
    ("full_prelude_spoof", "attack", FALSE, FULL_PRELUDE, {}),
]

ONLY = os.environ.get("SPIKE_ONLY")
if ONLY:
    CASES = [c for c in CASES if c[0] in ONLY.split(",")]


def make_project(root: Path, challenge: str, solution: str, extra: dict[str, str]) -> None:
    libs = ["Challenge", "Solution", *extra]
    config = 'name = "spike"\ndefaultTargets = ["Solution"]\n' + "".join(f'\n[[lean_lib]]\nname = "{n}"\n' for n in libs)
    (root / "lean-toolchain").write_text(TOOLCHAIN + "\n", encoding="utf-8")
    (root / "lakefile.toml").write_text(config, encoding="utf-8")
    (root / "lake-manifest.json").write_text(json.dumps(
        {"version": "1.1.0", "packagesDir": ".lake/packages", "packages": [], "name": "spike", "lakeDir": ".lake"}),
        encoding="utf-8")
    (root / "Challenge.lean").write_text(challenge, encoding="utf-8")
    (root / "Solution.lean").write_text(solution, encoding="utf-8")
    for name, source in extra.items():
        (root / f"{name}.lean").write_text(source, encoding="utf-8")
    (root / "comparator.json").write_text(json.dumps(
        {"challenge_module": "Challenge", "solution_module": "Solution", "theorem_names": ["main_theorem"],
         "permitted_axioms": AXIOMS}), encoding="utf-8")


def run(cmd: list[str], cwd: Path, timeout: int = 900) -> dict:
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        rc, output = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        rc, output = "timeout", ""
    return {"rc": rc, "seconds": round(time.monotonic() - start, 1), "output": output[-3000:]}


def digest(root: Path, name: str) -> str:
    return hashlib.sha256((root / name).read_bytes()).hexdigest()


def run_case(name: str, kind: str, challenge: str, solution: str, extra: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        make_project(root, challenge, solution, extra)
        before = digest(root, "Challenge.lean"), digest(root, "comparator.json")
        for marker in ESCAPE_MARKERS:
            marker.unlink(missing_ok=True)
        result = {"name": name, "kind": kind,
                  "comparator": run(["lake", "comparator"], root),
                  "check": run(["lake", "check"], root)}
        result["host_challenge_unchanged"] = before == (digest(root, "Challenge.lean"), digest(root, "comparator.json"))
        result["escaped_to"] = [str(m) for m in ESCAPE_MARKERS if m.exists()]
        if name in ("valid_proof", "kernel_skip"):
            result["paranoid"] = run(["lake", "comparator", "--paranoid"], root)
    return result


def verdict(result: dict) -> str:
    """A surprise is anything the plan would have to change for."""
    passed = result["comparator"]["rc"] == 0
    kind = result["kind"]
    if result["escaped_to"] or not result["host_challenge_unchanged"]:
        return "SURPRISE: reached the host"
    if kind == "control-pass" and not passed:
        return "SURPRISE: valid proof rejected"
    if kind in ("control-fail", "attack") and passed:
        return "SURPRISE: passed"
    if kind == "trust" and not passed:
        return "SURPRISE: weak challenge rejected"
    return "as expected"


def main() -> int:
    results = []
    for case in CASES:
        result = run_case(*case)
        result["verdict"] = verdict(result)
        results.append(result)
        c = result["comparator"]
        print(f"\n===== {result['name']} [{result['kind']}] comparator rc={c['rc']} {c['seconds']}s, "
              f"check rc={result['check']['rc']} {result['check']['seconds']}s: {result['verdict']}", flush=True)
        print(c["output"], flush=True)
        if "paranoid" in result:
            print(f"--- paranoid rc={result['paranoid']['rc']} {result['paranoid']['seconds']}s\n{result['paranoid']['output']}")
    Path("spike_report.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

    print("\n===== SUMMARY")
    for r in results:
        print(f"{r['name']:32} {r['kind']:13} comparator={r['comparator']['rc']!s:8} check={r['check']['rc']!s:8} {r['verdict']}")
    return 1 if any(r["verdict"] != "as expected" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
