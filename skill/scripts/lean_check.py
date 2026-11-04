#!/usr/bin/env python3
"""Machine-check a Lean 4 file and audit what its proofs rest on.

A file PASSES only if every stage passes:

1. source scan: no `prelude` or `module` header, only allow-listed imports, and no kernel-bypassing
   or trust-expanding construct outside comments (`sorry`, `axiom`, `debug.skipKernelTC`,
   `@[implemented_by]`, `@[extern]`, `unsafe`);
2. compile: the untouched file elaborates with no errors, in its own temporary directory;
3. audit: in a separate process that reads the compiled file as data (lean_audit.lean), every
   declaration depends only on the standard axioms `propext`, `Classical.choice`, and `Quot.sound`,
   the real ones from core Lean, and every `--require`d declaration exists;
4. replay: the toolchain's `leanchecker` re-checks the compiled file with the kernel.

Declarations come only from the audit stage. Nothing the file prints while compiling can add one.

This defends against accidents, agent shortcuts, and the known file-level attacks in
tests/lean_check. It is not adversarially sound: compiling a Lean file runs its code as you, and
such code can tamper with anything you can. See references/lean-verification.md, section 7.

It never checks that a Lean statement faithfully expresses the informal claim; that comparison
remains the auditor's job. For that comparison the script prints the elaborated type of each
declaration, ignoring notation defined by the file itself.

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
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}

# Version of the check report and stages (IF-check-report-v2).
CHECKER_VERSION = "2.0"

# Imports are refused unless their first component is here. These are the Lean toolchain's own
# libraries, Mathlib, and Mathlib's dependencies. A sibling module could hide a bypass in a file
# that is never replayed.
ALLOWED_IMPORT_ROOTS = {"Init", "Std", "Lean", "Mathlib", "Batteries", "Aesop", "Qq", "ProofWidgets",
                        "Plausible", "ImportGraph", "LeanSearchClient", "Cli"}

AUDIT_DRIVER = Path(__file__).resolve().parent / "lean_audit.lean"

# The checked file's module name inside its private temporary directory.
TARGET_MODULE = "MpsTarget"

# Fallback Lake project when FILE is not inside one: $MATHPROOF_LEAN_PROJECT, then this path
# (scripts/install.sh links it to the repository's lean/ project).
DEFAULT_PROJECT = Path.home() / ".mathproof" / "lean"

# Kept in sync with lean/lean-toolchain and lean/lakefile.toml in the repository.
LEAN_TOOLCHAIN = "leanprover/lean4:v4.32.0"
MATHLIB_REV = "v4.32.0"

FORBIDDEN_SOURCE = [
    (re.compile(r"\bsorry\b"), "`sorry`"),
    (re.compile(r"\badmit\b"), "`admit`"),
    (re.compile(r"(?<![\w.'])axiom(?![\w'])"), "`axiom` declaration"),
    (re.compile(r"\bdebug\.skipKernelTC\b"), "`debug.skipKernelTC`"),
    (re.compile(r"\bimplemented_by\b"), "`@[implemented_by]`"),
    (re.compile(r"@\[\s*extern\b"), "`@[extern]`"),
    (re.compile(r"\bunsafe\b"), "`unsafe`"),
]

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


def scan_header(code: str) -> list[str]:
    """Check the header of comment-free source, before anything is compiled."""
    problems: list[str] = []
    pos = 0
    word = re.compile(r"\s*(\S+)")
    while m := word.match(code, pos):
        token = m.group(1)
        if token in ("prelude", "module"):
            problems.append(f"header-not-allowed: {token}")
            pos = m.end()
            continue
        if token != "import":
            break
        name = word.match(code, m.end())
        module = name.group(1) if name else ""
        if not import_allowed(module):
            problems.append(f"import-not-allowed: {module}")
        pos = name.end() if name else m.end()
    return problems


def import_allowed(module: str) -> bool:
    return (re.fullmatch(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*", module) is not None
            and module.split(".")[0] in ALLOWED_IMPORT_ROOTS)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_pins(project: Path) -> tuple[str | None, str | None]:
    """The toolchain and Mathlib revision a project declares, or None where it declares none."""
    toolchain_file = project / "lean-toolchain"
    toolchain = toolchain_file.read_text(encoding="utf-8").strip() if toolchain_file.exists() else None
    mathlib = None
    try:
        manifest = json.loads((project / "lake-manifest.json").read_text(encoding="utf-8"))
        for package in manifest.get("packages", []):
            if package.get("name") == "mathlib":
                mathlib = package.get("inputRev") or package.get("rev")
    except (OSError, ValueError):
        pass
    return toolchain, mathlib


def run_stage(cmd: list[str], project: Path, deadline: float, **kwargs) -> tuple[subprocess.CompletedProcess | None, float]:
    """Run one stage in the project, returning (None, seconds) if the time budget ran out."""
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=project, capture_output=True, text=True,
                              timeout=max(1.0, deadline - start), **kwargs)
    except subprocess.TimeoutExpired:
        proc = None
    return proc, round(time.monotonic() - start, 1)


def audit_problems(audit: dict, required: list[str]) -> tuple[list[dict], list[str]]:
    """Turn the audit driver's report into the report's declarations and problems."""
    problems: list[str] = []

    if audit["is_module"]:
        problems.append("header-not-allowed: module")
    # A file without `prelude` always imports Init, so its absence means core was left out.
    if "Init" not in audit["imports"]:
        problems.append("header-not-allowed: prelude (compiled file does not import Init)")
    for module in audit["imports"]:
        if not import_allowed(module):
            problems.append(f"import-not-allowed: {module}")
    for name in audit["core_mismatches"]:
        problems.append(f"axiom `{name}` is not the one from core Lean")
    for name in audit["unresolved"]:
        problems.append(f"audit could not resolve constant `{name}`")
    for name in audit["unsafe"]:
        problems.append(f"{name} is declared `unsafe`")
    for hidden in audit["hidden"]:
        bad = sorted(set(hidden["axioms"]) - ALLOWED_AXIOMS)
        if bad:
            problems.append(f"{hidden['name']} depends on non-standard axioms: {', '.join(bad)}")

    decls = []
    for raw in audit["declarations"]:
        bad = sorted(set(raw["axioms"]) - ALLOWED_AXIOMS)
        decl = {"name": raw["name"], "axioms": raw["axioms"], "nonstandard_axioms": bad, "type": raw["type"],
                "statement_uses": raw["statement_uses"]}
        if raw.get("definition"):
            decl["definition"] = raw["definition"]
        decls.append(decl)
        if bad:
            problems.append(f"{raw['name']} depends on non-standard axioms: {', '.join(bad)}")

    if not decls:
        problems.append("audit produced no declarations; the file defines nothing to check")
    names = {d["name"] for d in decls}
    for r in required:
        if r not in names and not any(n.endswith("." + r) for n in names):
            problems.append(f"required declaration `{r}` not found")
    return decls, problems


def check(file: Path, project: Path, required: list[str], timeout: int) -> dict:
    src = file.read_text(encoding="utf-8")
    no_comments = strip_comments(src)
    code = strip_strings(no_comments)
    problems: list[str] = []
    decls: list[dict] = []
    environment_error = False
    toolchain, mathlib_rev = project_pins(project)
    stages: dict = {"source_scan": {"status": "not run"},
                    "compile": {"status": "not run", "seconds": 0.0, "sandboxed": False},
                    "audit": {"status": "not run", "seconds": 0.0},
                    "replay": {"status": "not run", "seconds": 0.0}}

    header_problems = scan_header(no_comments)
    problems += header_problems
    for pattern, label in FORBIDDEN_SOURCE:
        for m in pattern.finditer(code):
            line = code.count("\n", 0, m.start()) + 1
            problems.append(f"line {line}: forbidden construct {label}")
    stages["source_scan"]["status"] = "fail" if problems else "pass"

    lean_output = ""
    deadline = time.monotonic() + timeout

    def timed_out(stage: str) -> None:
        stages[stage]["status"] = "timeout"
        problems.append(f"Lean timed out after {timeout}s")

    # A refused header is not compiled: `import` and `prelude` decide what code runs at all.
    if not header_problems:
        with tempfile.TemporaryDirectory(prefix="mps_check_") as work:
            work_dir = Path(work).resolve()
            target = work_dir / f"{TARGET_MODULE}.lean"
            olean = work_dir / f"{TARGET_MODULE}.olean"
            target.write_bytes(file.read_bytes())

            # `lake env lean` ignores the lakefile's leanOptions, so set these here. Otherwise a
            # typo in a statement silently becomes a universally quantified variable.
            compile_cmd = ["lake", "env", "lean", "-DautoImplicit=false", "-DrelaxedAutoImplicit=false",
                           f"--root={work_dir}", "-o", str(olean),
                           "-i", str(work_dir / f"{TARGET_MODULE}.ilean"), str(target)]
            proc, seconds = run_stage(compile_cmd, project, deadline)
            stages["compile"]["seconds"] = seconds
            compiled = False
            if proc is None:
                timed_out("compile")
            else:
                lean_output = (proc.stdout + proc.stderr).replace(str(target), str(file))
                lines = lean_output.splitlines()
                errors = [l for l in lines if re.search(r":\d+:\d+: error", l) or l.startswith("error:")]
                problems += [f"Lean error: {e}" for e in errors]
                if proc.returncode != 0 and not errors:
                    problems.append(f"Lean exited with code {proc.returncode}")
                for l in lines:
                    if "declaration uses 'sorry'" in l or "declaration uses `sorry`" in l:
                        problems.append(f"Lean warning: {l.strip()}")
                compiled = proc.returncode == 0 and not errors and olean.exists()
                stages["compile"]["status"] = "pass" if compiled else "fail"

            if compiled:
                out = work_dir / "audit.json"
                audit_cmd = ["lake", "env", "lean", "--run", str(AUDIT_DRIVER), str(olean), str(out)]
                proc, seconds = run_stage(audit_cmd, project, deadline)
                stages["audit"]["seconds"] = seconds
                if proc is None:
                    timed_out("audit")
                elif proc.returncode != 0 or not out.exists():
                    # A driver that cannot run is an environment fault (for example a toolchain
                    # with a different API). It must never read as a pass.
                    environment_error = True
                    stages["audit"]["status"] = "error"
                    problems.append("audit driver failed: " + (proc.stdout + proc.stderr).strip()[-1000:])
                else:
                    decls, found = audit_problems(json.loads(out.read_text(encoding="utf-8")), required)
                    problems += found
                    stages["audit"]["status"] = "fail" if found else "pass"

                # Lake puts its own paths first, so the temporary directory cannot shadow an import.
                replay_env = {**os.environ, "LEAN_PATH": str(work_dir)}
                prefix = subprocess.run(["lake", "env", "lean", "--print-prefix"], cwd=project,
                                        capture_output=True, text=True).stdout.strip()
                leanchecker = Path(prefix, "bin", "leanchecker")
                if not leanchecker.exists():
                    environment_error = True
                    stages["replay"]["status"] = "unavailable"
                    problems.append(f"kernel replay unavailable: no leanchecker in toolchain at {prefix!r}")
                else:
                    proc, seconds = run_stage(["lake", "env", str(leanchecker), TARGET_MODULE],
                                              project, deadline, env=replay_env)
                    stages["replay"]["seconds"] = seconds
                    if proc is None:
                        timed_out("replay")
                    elif proc.returncode != 0:
                        stages["replay"]["status"] = "fail"
                        problems.append("kernel replay rejected the file: " + (proc.stdout + proc.stderr).strip()[-1000:])
                    else:
                        stages["replay"]["status"] = "pass"

    report = {
        "file": str(file),
        "status": "PASS" if not problems else "FAIL",
        "problems": problems,
        "declarations": decls,
        "lean_output": lean_output,
        "checker": {
            "version": CHECKER_VERSION,
            "sha256_checker": sha256(Path(__file__).resolve()),
            "sha256_driver": sha256(AUDIT_DRIVER),
        },
        "toolchain": toolchain,
        "mathlib_rev": mathlib_rev,
        "pinned": toolchain == LEAN_TOOLCHAIN and mathlib_rev == MATHLIB_REV,
        "tier": "local",
        "stages": stages,
    }
    if environment_error:
        report["environment_error"] = True
    return report


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

    if not AUDIT_DRIVER.is_file():
        print(f"audit driver missing: {AUDIT_DRIVER}", file=sys.stderr)
        return 2

    report = check(file, project, args.require, args.timeout)

    if args.json:
        print(json.dumps({k: v for k, v in report.items() if k != "lean_output"}, indent=2))
    else:
        print(f"{report['status']}: {report['file']}")
        for d in report["declarations"]:
            axs = ", ".join(d["axioms"]) or "none"
            print(f"  {d['name']} : {d['type']}")
            if d["statement_uses"]:
                print(f"    statement uses from this file: {', '.join(d['statement_uses'])}")
            if "definition" in d:
                print(f"    := {d['definition']}")
            print(f"    axioms: {axs}")
        for p in report["problems"]:
            print(f"  ✗ {p}")
        if report["status"] == "FAIL" and report["lean_output"].strip():
            print("--- Lean output ---")
            print(report["lean_output"].strip()[:4000])
    if report.get("environment_error"):
        return 2
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
