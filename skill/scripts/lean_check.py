#!/usr/bin/env python3
"""Machine-check a Lean 4 file and audit what its proofs rest on.

A file PASSES only if all of the following hold:

1. it elaborates with no errors (Lean's exit code is 0);
2. no declaration uses `sorry` (directly or through a dependency);
3. every declaration defined in the file depends only on the standard axioms
   `propext`, `Classical.choice`, and `Quot.sound` (so no custom `axiom`,
   no `native_decide`/`Lean.ofReduceBool`, no `sorryAx`);
4. the source contains no kernel-bypassing or trust-expanding constructs
   (`set_option debug.skipKernelTC`, `@[implemented_by]`, `@[extern]`,
   `unsafe`, `axiom` declarations) outside comments;
5. every `--require`d declaration exists in the file.

It never checks that a Lean statement faithfully expresses the informal claim;
that comparison remains the auditor's job (see references/lean-verification.md).
For that comparison the script prints the elaborated type of each required
declaration.

Usage:
    lean_check.py FILE.lean [--project DIR] [--require NAME ...] [--json]

Project: --project, else the nearest lakefile above FILE, else $MATHPROOF_LEAN_PROJECT,
else ~/.mathproof/lean.
    lean_check.py --init DIR      # scaffold a Mathlib-backed project in DIR

Exit status: 0 PASS, 1 FAIL, 2 usage or environment error.
Standard library only; requires `lake` (via elan) on PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}

# Fallback Lake project when FILE is not inside one: $MATHPROOF_LEAN_PROJECT, then this path
# (scripts/install.sh links it to the repository's lean/ project).
DEFAULT_PROJECT = Path.home() / ".mathproof" / "lean"

# Kept in sync with lean/lean-toolchain and lean/lakefile.toml in the repository.
LEAN_TOOLCHAIN = "leanprover/lean4:v4.32.0"
MATHLIB_REV = "v4.32.0"

FORBIDDEN_SOURCE = [
    (re.compile(r"\bsorry\b"), "`sorry`"),
    (re.compile(r"\badmit\b"), "`admit`"),
    (re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+)?axiom\b", re.M), "`axiom` declaration"),
    (re.compile(r"\bdebug\.skipKernelTC\b"), "`debug.skipKernelTC`"),
    (re.compile(r"\bimplemented_by\b"), "`@[implemented_by]`"),
    (re.compile(r"@\[\s*extern\b"), "`@[extern]`"),
    (re.compile(r"\bunsafe\b"), "`unsafe`"),
]

# Appended to a temporary copy of the checked file. It reports, for every
# non-internal constant added by this file, the axioms it depends on and its
# elaborated type.
AUDIT_SNIPPET = r"""

section MathProofSkillAudit
open Lean Elab Command in
#eval show CommandElabM Unit from do
  let env ← getEnv
  let mut names : Array Name := #[]
  for (n, _) in env.constants.map₂.toList do
    unless n.isInternal || isAuxRecursor env n || isNoConfusion env n do
      names := names.push n
  for n in names.qsort Name.lt do
    let axs ← Lean.collectAxioms n
    let some ci := env.find? n | continue
    let ty ← liftTermElabM <| Meta.ppExpr ci.type
    let axStr := ", ".intercalate (axs.qsort Name.lt |>.toList.map toString)
    let tyStr := (toString ty).replace "\n" " "
    let valStr ← match ci with
      | .defnInfo d =>
        if d.type.isProp || d.type.isSort then
          pure ((toString (← liftTermElabM <| Meta.ppExpr d.value)).replace "\n" " ")
        else pure ""
      | _ => pure ""
    logInfo m!"@@MPS_DECL {n} @@AXIOMS [{axStr}] @@TYPE {tyStr} @@VALUE {valStr}"
end MathProofSkillAudit
"""

DECL_RE = re.compile(r"@@MPS_DECL (\S+) @@AXIOMS \[([^\]]*)\] @@TYPE (.*?) @@VALUE ?(.*)")


def strip_comments(src: str) -> str:
    """Remove Lean line comments and (nested) block comments, keep string literals."""
    out: list[str] = []
    i, depth, n = 0, 0, len(src)
    in_string = False
    while i < n:
        if depth == 0 and in_string:
            if src[i] == "\\" and i + 1 < n:
                out.append(src[i : i + 2])
                i += 2
                continue
            if src[i] == '"':
                in_string = False
            out.append(src[i])
            i += 1
            continue
        if src.startswith("/-", i):
            depth += 1
            i += 2
            continue
        if depth and src.startswith("-/", i):
            depth -= 1
            i += 2
            continue
        if depth:
            if src[i] == "\n":
                out.append("\n")
            i += 1
            continue
        if src.startswith("--", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src[i] == '"':
            in_string = True
        out.append(src[i])
        i += 1
    return "".join(out)


def strip_strings(src: str) -> str:
    return re.sub(r'"(?:\\.|[^"\\])*"', '""', src)


def is_project(d: Path) -> bool:
    return (d / "lakefile.toml").exists() or (d / "lakefile.lean").exists()


def find_project(start: Path) -> Path | None:
    for d in [start, *start.parents]:
        if is_project(d):
            return d
    env = os.environ.get("MATHPROOF_LEAN_PROJECT")
    for d in ([Path(env).expanduser()] if env else []) + [DEFAULT_PROJECT]:
        if is_project(d):
            return d.resolve()
    return None


def init_project(target: Path) -> int:
    if shutil.which("lake") is None:
        print("lake not found on PATH. Install elan: https://lean-lang.org/install", file=sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    if (target / "lakefile.toml").exists() or (target / "lakefile.lean").exists():
        print(f"{target} already contains a Lake project; leaving it unchanged.")
        return 0
    (target / "lean-toolchain").write_text(LEAN_TOOLCHAIN + "\n", encoding="utf-8")
    (target / "lakefile.toml").write_text(
        'name = "proofcheck"\nversion = "0.1.0"\ndefaultTargets = ["ProofCheck"]\n\n'
        "[leanOptions]\nautoImplicit = false\nrelaxedAutoImplicit = false\n\n"
        '[[require]]\nname = "mathlib"\ngit = "https://github.com/leanprover-community/mathlib4.git"\n'
        f'rev = "{MATHLIB_REV}"\n\n[[lean_lib]]\nname = "ProofCheck"\n',
        encoding="utf-8",
    )
    (target / "ProofCheck.lean").write_text("import Mathlib\n", encoding="utf-8")
    (target / ".gitignore").write_text("/.lake\n", encoding="utf-8")
    for cmd in (["lake", "update"], ["lake", "exe", "cache", "get"]):
        print("$", " ".join(cmd), flush=True)
        if subprocess.run(cmd, cwd=target).returncode != 0:
            print(f"`{' '.join(cmd)}` failed in {target}", file=sys.stderr)
            return 2
    print(f"Initialized Mathlib-backed Lean project at {target}")
    return 0


def check(file: Path, project: Path, required: list[str], timeout: int) -> dict:
    src = file.read_text(encoding="utf-8")
    code = strip_strings(strip_comments(src))
    problems: list[str] = []

    for pattern, label in FORBIDDEN_SOURCE:
        for m in pattern.finditer(code):
            line = code.count("\n", 0, m.start()) + 1
            problems.append(f"line {line}: forbidden construct {label}")

    with tempfile.NamedTemporaryFile(
        "w", suffix=".lean", prefix=".mps_check_", dir=project, delete=False, encoding="utf-8"
    ) as tmp:
        # The audit needs `import Lean`; put it on line 1 so reported line numbers stay unchanged.
        header = "" if src.lstrip().startswith("module") else "import Lean "
        tmp.write(header + src.rstrip() + "\n" + AUDIT_SNIPPET)
        tmp_path = Path(tmp.name)
    try:
        proc = subprocess.run(
            ["lake", "env", "lean", str(tmp_path)],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        tmp_path.unlink(missing_ok=True)
        return {"file": str(file), "status": "FAIL", "problems": [f"Lean timed out after {timeout}s"],
                "declarations": [], "lean_output": ""}
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    output = (proc.stdout + proc.stderr).replace(str(tmp_path), str(file))
    lines = output.splitlines()

    errors = [l for l in lines if re.search(r":\d+:\d+: error", l) or l.startswith("error:")]
    problems += [f"Lean error: {e}" for e in errors]
    if proc.returncode != 0 and not errors:
        problems.append(f"Lean exited with code {proc.returncode}")
    for l in lines:
        if "declaration uses 'sorry'" in l or "declaration uses `sorry`" in l:
            problems.append(f"Lean warning: {l.strip()}")

    decls = []
    for l in lines:
        m = DECL_RE.search(l)
        if not m:
            continue
        name, axs, ty = m.group(1), [a.strip() for a in m.group(2).split(",") if a.strip()], m.group(3)
        bad = sorted(set(axs) - ALLOWED_AXIOMS)
        decl = {"name": name, "axioms": axs, "nonstandard_axioms": bad, "type": ty}
        if m.group(4).strip():
            decl["definition"] = m.group(4).strip()
        decls.append(decl)
        if bad:
            problems.append(f"{name} depends on non-standard axioms: {', '.join(bad)}")

    if not errors and proc.returncode == 0 and not decls:
        problems.append("audit produced no declarations; the file defines nothing to check")

    names = {d["name"] for d in decls}
    for r in required:
        if r not in names and not any(n.endswith("." + r) for n in names):
            problems.append(f"required declaration `{r}` not found")

    return {
        "file": str(file),
        "status": "PASS" if not problems else "FAIL",
        "problems": problems,
        "declarations": decls,
        "lean_output": "\n".join(l for l in lines if "@@MPS_DECL" not in l),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", type=Path, help="Lean file to check")
    ap.add_argument("--project", type=Path,
                    help="Lake project root (default: nearest above FILE, $MATHPROOF_LEAN_PROJECT, ~/.mathproof/lean)")
    ap.add_argument("--require", action="append", default=[], metavar="NAME",
                    help="declaration that must exist (repeatable; suffix match on the full name)")
    ap.add_argument("--timeout", type=int, default=900, help="seconds (default 900)")
    ap.add_argument("--json", action="store_true", help="print a JSON report")
    ap.add_argument("--init", type=Path, metavar="DIR", help="scaffold a Mathlib-backed project and exit")
    args = ap.parse_args()

    if args.init:
        return init_project(args.init.resolve())
    if not args.file:
        ap.print_usage(sys.stderr)
        return 2
    file = args.file.resolve()
    if not file.is_file():
        print(f"no such file: {file}", file=sys.stderr)
        return 2
    project = (args.project.resolve() if args.project else find_project(file.parent))
    if project is None:
        print("No Lake project found above the file. Pass --project DIR, or create one with "
              f"`{Path(sys.argv[0]).name} --init DIR`.", file=sys.stderr)
        return 2
    if shutil.which("lake") is None:
        print("lake not found on PATH. Install elan: https://lean-lang.org/install", file=sys.stderr)
        return 2

    report = check(file, project, args.require, args.timeout)

    if args.json:
        print(json.dumps({k: v for k, v in report.items() if k != "lean_output"}, indent=2))
    else:
        print(f"{report['status']}: {report['file']}")
        for d in report["declarations"]:
            axs = ", ".join(d["axioms"]) or "none"
            print(f"  {d['name']} : {d['type']}")
            if "definition" in d:
                print(f"    := {d['definition']}")
            print(f"    axioms: {axs}")
        for p in report["problems"]:
            print(f"  ✗ {p}")
        if report["status"] == "FAIL" and report["lean_output"].strip():
            print("--- Lean output ---")
            print(report["lean_output"].strip()[:4000])
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
