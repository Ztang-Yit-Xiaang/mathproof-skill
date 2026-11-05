#!/usr/bin/env python3
"""Machine-check a Lean 4 file and audit what its proofs rest on.

A file PASSES only if every stage passes:

1. source scan: Lean's own parser reports no `prelude` or `module` header and only allow-listed
   imports, and no kernel-bypassing or trust-expanding construct appears outside comments (`sorry`,
   `axiom`, `debug.skipKernelTC`, `@[implemented_by]`, `@[extern]`, `unsafe`);
2. packages: each package in the project's manifest is at its recorded commit, with no edited files;
3. compile: the untouched file elaborates with no errors, in its own temporary directory;
4. audit: in a separate process (lean_audit.lean), every imported module comes from the toolchain or
   a package and belongs to a real library, every declaration depends only on the standard axioms
   `propext`, `Classical.choice`, and `Quot.sound`, the real ones from core Lean, and every
   `--require`d declaration exists;
5. replay: the toolchain's `leanchecker` re-checks the compiled file with the kernel.

Declarations come only from the audit stage. Nothing the file prints while compiling can add one.

This defends against accidents, agent shortcuts, and the known file-level attacks in
tests/lean_check. It is not adversarially sound: compiling a Lean file runs its code as you, and
such code can tamper with anything you can. See references/lean-verification.md, section 7.

It never checks that a Lean statement faithfully expresses the informal claim; that comparison
remains the auditor's job. For that comparison the script prints the elaborated type of each
declaration, ignoring notation defined by the file itself, and the file's definitions that each
statement depends on.

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
import signal
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}

# Version of the check report and stages (IF-check-report-v2).
CHECKER_VERSION = "2.2"

# First filter on imports, by name, before compiling: the Lean toolchain's own libraries, Mathlib,
# and Mathlib's dependencies. Imported files are never replayed, so one could hide a bypass. The
# audit then checks where each module really comes from (lean_audit.lean).
ALLOWED_IMPORT_ROOTS = {"Init", "Std", "Lean", "Mathlib", "Batteries", "Aesop", "Qq", "ProofWidgets",
                        "Plausible", "ImportGraph", "LeanSearchClient", "Cli"}

# Where each package may come from. Another source could add anything under a trusted name.
OFFICIAL_PACKAGES = {
    "mathlib": "https://github.com/leanprover-community/mathlib4.git",
    "plausible": "https://github.com/leanprover-community/plausible",
    "LeanSearchClient": "https://github.com/leanprover-community/LeanSearchClient",
    "importGraph": "https://github.com/leanprover-community/import-graph",
    "proofwidgets": "https://github.com/leanprover-community/ProofWidgets4",
    "aesop": "https://github.com/leanprover-community/aesop",
    "Qq": "https://github.com/leanprover-community/quote4",
    "batteries": "https://github.com/leanprover-community/batteries",
    "Cli": "https://github.com/leanprover/lean4-cli",
}

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


def parsed_header(file: Path, project: Path, deadline: float) -> dict | None:
    """Have Lean parse the file's header, so this script cannot disagree with Lean about it."""
    proc, _ = run_stage(["lake", "env", "lean", "--deps-json", str(file)], project, deadline)
    if proc is None or proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)["imports"][0]["result"]
    except (ValueError, KeyError, IndexError, TypeError):
        return None


def header_problems(header: dict) -> list[str]:
    problems: list[str] = []
    if header["isModule"]:
        problems.append("header-not-allowed: module")
    # Lean adds a meta import of Init to every file unless the file says `prelude`.
    if not any(i["module"] == "Init" and i["isMeta"] for i in header["imports"]):
        problems.append("header-not-allowed: prelude")
    for module in dict.fromkeys(i["module"] for i in header["imports"]):
        if not import_allowed(module):
            problems.append(f"import-not-allowed: {module}")
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


def package_problems(project: Path, deadline: float) -> tuple[list[str], list[str]]:
    """Compare each git package with the manifest. Returns (problems, package names checked).

    This sees edited sources, not the compiled .olean files, which are ignored by git and are what
    Lean actually loads. Only an authoritative rebuild or replay could check those.
    """
    try:
        manifest = json.loads((project / "lake-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], []
    packages_dir = project / manifest.get("packagesDir", ".lake/packages")
    problems: list[str] = []
    checked: list[str] = []
    for package in manifest.get("packages", []):
        name, rev = package.get("name"), package.get("rev")
        if package.get("url") != OFFICIAL_PACKAGES.get(name):
            problems.append(f"package-source-unknown: {name} comes from {package.get('url')}, not its official repository")
        if package.get("type") != "git" or not rev:
            problems.append(f"package-not-verifiable: {name} is not a pinned git package")
            continue
        directory = packages_dir / str(package.get("dir") or name)
        if not (directory / ".git").exists():
            problems.append(f"package-not-verifiable: {name} has no git checkout at {directory}")
            continue
        head, _ = run_stage(["git", "rev-parse", "HEAD"], directory, deadline)
        status, _ = run_stage(["git", "status", "--porcelain"], directory, deadline)
        if head is None or status is None or head.returncode != 0 or status.returncode != 0:
            problems.append(f"package-not-verifiable: git could not read {name}")
            continue
        checked.append(name)
        if head.stdout.strip() != rev:
            problems.append(f"package-not-at-manifest-rev: {name} is at {head.stdout.strip()}, manifest says {rev}")
        if status.stdout.strip():
            changed = status.stdout.strip().splitlines()
            problems.append(f"package-not-clean: {name} has {len(changed)} changed files, such as {changed[0].strip()}")
    return problems, checked


def run_stage(cmd: list[str], cwd: Path, deadline: float, **kwargs) -> tuple[subprocess.CompletedProcess | None, float]:
    """Run one stage, returning (None, seconds) if the time budget ran out.

    `lake env` starts Lean as a child, so a timeout has to kill the whole process group. Otherwise
    Lean keeps running, and a file that loops forever would use a CPU indefinitely.
    """
    start = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True, **kwargs)
    try:
        stdout, stderr = proc.communicate(timeout=max(1.0, deadline - start))
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return None, round(time.monotonic() - start, 1)
    return (subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr),
            round(time.monotonic() - start, 1))


def audit_problems(audit: dict, required: list[str]) -> tuple[list[dict], list[str]]:
    """Turn the audit driver's report into the report's declarations and problems."""
    problems: list[str] = list(audit["import_problems"])

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
                "type_explicit": raw["type_explicit"], "kind": raw["kind"],
                "statement_uses": raw["statement_uses"]}
        if raw.get("definition"):
            decl["definition"] = raw["definition"]
        decls.append(decl)
        if bad:
            problems.append(f"{raw['name']} depends on non-standard axioms: {', '.join(bad)}")

    if not decls:
        problems.append("audit produced no declarations; the file defines nothing to check")
    for raw in audit["declarations"]:
        for field in ("type", "type_explicit", "definition"):
            if raw.get(field, "").startswith("<could not print"):
                problems.append(f"{raw['name']}: {raw[field]}")

    def matches(name: str, r: str) -> bool:
        return name == r or name.endswith("." + r)

    found = [r for r in required if any(matches(d["name"], r) for d in decls)]
    for r in required:
        if r not in found:
            problems.append(f"required declaration `{r}` not found")
    # Requiring only definitions would pass while proving nothing.
    theorems = [d["name"] for d in audit["declarations"] if d["kind"] == "theorem"]
    if found and not any(matches(t, r) for t in theorems for r in found):
        problems.append(f"required-not-a-theorem: {', '.join(found)}")
    return decls, problems


def check(file: Path, project: Path, required: list[str], timeout: int) -> dict:
    src = file.read_text(encoding="utf-8")
    code = strip_strings(strip_comments(src))
    problems: list[str] = []
    decls: list[dict] = []
    statement_context: dict = {}
    environment_error = False
    toolchain, mathlib_rev = project_pins(project)
    stages: dict = {"source_scan": {"status": "not run"},
                    "packages": {"status": "not run", "seconds": 0.0, "checked": []},
                    "compile": {"status": "not run", "seconds": 0.0, "sandboxed": False},
                    "audit": {"status": "not run", "seconds": 0.0},
                    "replay": {"status": "not run", "seconds": 0.0}}

    deadline = time.monotonic() + timeout
    header = parsed_header(file, project, deadline)
    if header is None:
        return environment_report(file, "Lean could not report the file's header (`lean --deps-json`)",
                                  toolchain, mathlib_rev, stages)
    refused = header_problems(header)
    problems += refused
    for pattern, label in FORBIDDEN_SOURCE:
        for m in pattern.finditer(code):
            line = code.count("\n", 0, m.start()) + 1
            problems.append(f"line {line}: forbidden construct {label}")
    stages["source_scan"]["status"] = "fail" if problems else "pass"

    lean_output = ""

    def timed_out(stage: str) -> None:
        stages[stage]["status"] = "timeout"
        message = f"Lean timed out after {timeout}s"
        if message not in problems:
            problems.append(message)

    # A refused header is not compiled: `import` and `prelude` decide what code runs at all.
    if not refused:
        start = time.monotonic()
        found, checked = package_problems(project, deadline)
        problems += found
        stages["packages"].update(status="fail" if found else "pass", checked=checked,
                                  seconds=round(time.monotonic() - start, 1))

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
                # Lake puts its own paths first, so the temporary directory cannot shadow an import.
                module_env = {**os.environ, "LEAN_PATH": str(work_dir)}
                audit_cmd = ["lake", "env", "lean", "--run", str(AUDIT_DRIVER), TARGET_MODULE, str(olean), str(out)]
                proc, seconds = run_stage(audit_cmd, project, deadline, env=module_env)
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
                    audit = json.loads(out.read_text(encoding="utf-8"))
                    statement_context = audit["statement_context"]
                    decls, found = audit_problems(audit, required)
                    problems += found
                    stages["audit"]["status"] = "fail" if found else "pass"

                proc, _ = run_stage(["lake", "env", "lean", "--print-prefix"], project, deadline)
                prefix = proc.stdout.strip() if proc else ""
                leanchecker = Path(prefix, "bin", "leanchecker")
                if proc is None:
                    timed_out("replay")
                elif not leanchecker.exists():
                    environment_error = True
                    stages["replay"]["status"] = "unavailable"
                    problems.append(f"kernel replay unavailable: no leanchecker in toolchain at {prefix!r}")
                else:
                    proc, seconds = run_stage(["lake", "env", str(leanchecker), TARGET_MODULE],
                                              project, deadline, env=module_env)
                    stages["replay"]["seconds"] = seconds
                    if proc is None:
                        timed_out("replay")
                    elif proc.returncode != 0:
                        stages["replay"]["status"] = "fail"
                        problems.append("kernel replay rejected the file: " + (proc.stdout + proc.stderr).strip()[-1000:])
                    else:
                        stages["replay"]["status"] = "pass"

    report = base_report(file, toolchain, mathlib_rev, stages)
    report.update(status="PASS" if not problems else "FAIL", problems=problems, declarations=decls,
                  statement_context=statement_context, lean_output=lean_output)
    if environment_error:
        report["environment_error"] = True
    return report


def base_report(file: Path, toolchain: str | None, mathlib_rev: str | None, stages: dict) -> dict:
    return {
        "file": str(file),
        "status": "FAIL",
        "problems": [],
        "declarations": [],
        "statement_context": {},
        "lean_output": "",
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


def environment_report(file: Path, problem: str, toolchain: str | None,
                       mathlib_rev: str | None, stages: dict) -> dict:
    report = base_report(file, toolchain, mathlib_rev, stages)
    report.update(problems=[problem], environment_error=True)
    return report


def clean(text: str) -> str:
    """Escape control and line-breaking characters, so Lean names cannot forge report lines."""
    return "".join(f"\\u{{{ord(c):04x}}}" if unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp")
                   else c for c in text)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", type=Path, help="Lean file to check")
    ap.add_argument("--project", type=Path,
                    help="Lake project root (default: nearest above FILE, $MATHPROOF_LEAN_PROJECT, ~/.mathproof/lean)")
    ap.add_argument("--require", action="append", default=[], metavar="NAME",
                    help="declaration that must exist (repeatable; suffix match on the full name)")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds for the whole check (default 1800)")
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

    try:
        report = check(file, project, args.require, args.timeout)
    except Exception as error:  # Whatever went wrong, it must not look like a pass.
        print(f"checker error: {type(error).__name__}: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({k: v for k, v in report.items() if k != "lean_output"}, indent=2))
    else:
        print(f"{report['status']}: {report['file']}")
        if not report["pinned"]:
            print("  note: this project is not on the tested Lean and Mathlib versions")
        for d in report["declarations"]:
            axs = ", ".join(d["axioms"]) or "none"
            print(clean(f"  {d['name']} : {d['type']}"))
            print(clean(f"    explicit: {d['type_explicit']}"))
            if "definition" in d:
                print(clean(f"    := {d['definition']}"))
            if d["statement_uses"]:
                print(clean(f"    statement uses from this file: {', '.join(d['statement_uses'])}"))
            print(clean(f"    axioms: {axs}"))
        if report["statement_context"]:
            print("  From this file, what the statements above depend on:")
            for name, entry in report["statement_context"].items():
                print(clean(f"    {name} : {entry['type']}"))
                if "definition" in entry:
                    print(clean(f"      := {entry['definition']}"))
        for p in report["problems"]:
            print(clean(f"  ✗ {p}"))
        if report["status"] == "FAIL" and report["lean_output"].strip():
            print("--- Lean output ---")
            print("\n".join(clean(l) for l in report["lean_output"].strip()[:4000].splitlines()))
    if report.get("environment_error"):
        return 2
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
