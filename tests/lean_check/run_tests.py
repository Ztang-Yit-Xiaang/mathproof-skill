#!/usr/bin/env python3
"""Regression tests for skill/scripts/lean_check.py.

Each fixture must PASS or FAIL as named, and a failing fixture must fail for its stated reason,
so an unresolved import cannot count as an attack caught. Pass --checker to run the fixtures
against another version of the checker, for example to show that a known-bad one fails them.
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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHECKER = ROOT / "skill" / "scripts" / "lean_check.py"
PROJECT = ROOT / "lean"
EXTRA = {"fail_missing_required.lean": ["--require", "main_theorem"],
         "fail_require_definition.lean": ["--require", "main_theorem"]}

# The reason each failing fixture must fail for: a regex that one reported problem must match.
REASONS = {
    "fail_auto_implicit.lean": r"Lean error",
    "fail_axiom.lean": r"axiom",
    "fail_core_shadow.lean": r"main_theorem depends on non-standard axioms: Evil\.propext",
    "fail_error.lean": r"Lean error",
    "fail_exit_only.lean": r"no declarations",
    "fail_forged_audit.lean": r"main_theorem depends on non-standard axioms: hidden_assumption",
    "fail_guarded_error.lean": r"main_theorem depends on non-standard axioms: sorryAx",
    "fail_hidden_sorry.lean": r"sorry",
    "fail_import_hides_bypass.lean": r"import-not-allowed: HiddenBypass",
    "fail_internal_axiom.lean": r"_hidden_axiom depends on non-standard axioms: _hidden_axiom",
    "fail_kernel_skip.lean": r"kernel replay rejected",
    "fail_midline_axiom.lean": r"bad",
    "fail_missing_required.lean": r"required declaration `main_theorem` not found",
    "fail_module_header.lean": r"header-not-allowed: module",
    "fail_native_decide.lean": r"non-standard axioms: .*native_decide",
    "fail_prelude_spoof.lean": r"header-not-allowed: prelude",
    "fail_require_definition.lean": r"required-not-a-theorem: main_theorem",
    "fail_sorry.lean": r"sorry",
}

# Statements a passing fixture must print exactly: the check on the printer itself.
PRINTED_TYPES = {
    "pass_print_spoof_shows_truth.lean": {
        "main_theorem": "True",
        "succ_statement": "∀ (n : Nat), n.succ = n + 1",
    },
}

# Text the explicit form of a statement must contain, which the short form hides.
EXPLICIT_CONTAINS = {
    "pass_explicit_line_shows_truth.lean": {"inline_le": "fun", "inline_add": "fun", "small_type": "Fin"},
}

# Text the short form must contain, for statements that try to hide from the printer.
PRINTED_CONTAINS = {"pass_hidden_by_mdata_is_shown.lean": {"main_theorem": "true = true"}}

# File-local constants a fixture's statement must be reported as using.
STATEMENT_USES = {
    "pass_instance_shadow_is_listed.lean": {"main_theorem": ["evilAdd"]},
    "pass_core.lean": {"claim_true": ["Claim"]},
    "pass_claim_instance_is_listed.lean": {"main_theorem": ["Claim", "evilAdd"]},
    "pass_aux_name_is_printed.lean": {"main_theorem": ["Foo.casesOn"]},
    "pass_private_claim_is_printed.lean": {"main_theorem": ["_private.MpsTarget.0.Claim"]},
}

# Bodies that must appear in the report's statement_context, whatever the constant's name.
STATEMENT_CONTEXT = {
    "pass_claim_instance_is_listed.lean": {"Claim": "1 + 1 = 0"},
    "pass_aux_name_is_printed.lean": {"Foo.casesOn": "True"},
    "pass_private_claim_is_printed.lean": {"_private.MpsTarget.0.Claim": "True"},
}

# Keys of the check report that consumers rely on (IF-check-report-v2).
REPORT_KEYS = {"file", "status", "problems", "declarations", "statement_context", "checker", "toolchain",
               "mathlib_rev", "pinned", "tier", "stages"}


def run_checker(checker: Path, file: Path, project: Path, extra: list[str] | None = None) -> tuple[int, dict]:
    cmd = [sys.executable, str(checker), str(file), "--project", str(project), "--json", *(extra or [])]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, {"problems": [f"no JSON report: {proc.stderr[-500:]}"]}


def check_fixture(checker: Path, f: Path) -> str | None:
    """Return None if the fixture behaved as named, else what went wrong."""
    expected = 0 if f.name.startswith("pass_") else 1
    code, report = run_checker(checker, f, PROJECT, EXTRA.get(f.name))
    if code != expected:
        return f"exit {code}, expected {expected}: {report.get('problems')}"
    if expected:
        reason = REASONS.get(f.name)
        if reason is None:
            return "no expected reason listed in REASONS"
        if not any(re.search(reason, p) for p in report.get("problems", [])):
            return f"failed, but not for the reason /{reason}/: {report.get('problems')}"
    printed = {d["name"]: d["type"] for d in report.get("declarations", [])}
    for name, want in PRINTED_TYPES.get(f.name, {}).items():
        if printed.get(name) != want:
            return f"printed `{name} : {printed.get(name)}`, expected `{want}`"
    explicit = {d["name"]: d.get("type_explicit", "") for d in report.get("declarations", [])}
    for name, want in EXPLICIT_CONTAINS.get(f.name, {}).items():
        if want not in explicit.get(name, ""):
            return f"explicit form of `{name}` is `{explicit.get(name)}`, wanted it to contain `{want}`"
    for name, want in PRINTED_CONTAINS.get(f.name, {}).items():
        if want not in printed.get(name, ""):
            return f"printed `{name} : {printed.get(name)}`, wanted it to contain `{want}`"
    uses = {d["name"]: d.get("statement_uses") for d in report.get("declarations", [])}
    for name, want in STATEMENT_USES.get(f.name, {}).items():
        if uses.get(name) != want:
            return f"`{name}` reported as using {uses.get(name)}, expected {want}"
    context = report.get("statement_context", {})
    for name, want in STATEMENT_CONTEXT.get(f.name, {}).items():
        if context.get(name, {}).get("definition") != want:
            return f"context for `{name}` is {context.get(name)}, expected definition `{want}`"
    return None


def check_same_name_parallel(checker: Path) -> str | None:
    """Two simultaneous checks of files with one name must not see each other's work."""
    with tempfile.TemporaryDirectory() as d:
        good, bad = Path(d, "a", "Same.lean"), Path(d, "b", "Same.lean")
        good.parent.mkdir()
        bad.parent.mkdir()
        good.write_text("theorem good_one : True := trivial\n", encoding="utf-8")
        bad.write_text("theorem bad_one : (1 : Nat) = 2 := by sorry\n", encoding="utf-8")
        with ThreadPoolExecutor(2) as pool:
            good_run, bad_run = pool.map(lambda f: run_checker(checker, f, PROJECT), [good, bad])
    names = [d["name"] for d in good_run[1].get("declarations", [])]
    if good_run[0] != 0 or names != ["good_one"]:
        return f"good file: exit {good_run[0]}, declarations {names}"
    if bad_run[0] != 1:
        return f"bad file: exit {bad_run[0]}"
    return None


def check_report_shape(checker: Path) -> str | None:
    code, report = run_checker(checker, HERE / "pass_core.lean", PROJECT)
    missing = REPORT_KEYS - report.keys()
    if code != 0 or missing:
        return f"exit {code}, missing keys {sorted(missing)}"
    stages = report["stages"]
    if any(stages.get(s, {}).get("status") != "pass" for s in ("source_scan", "packages", "compile", "audit", "replay")):
        return f"not every stage passed: {stages}"
    if report["pinned"] is not True or report["tier"] != "local":
        return f"pinned={report['pinned']} tier={report['tier']}"
    return None


def check_installed_copy_unpinned(checker: Path) -> str | None:
    """A copy of skill/ elsewhere must work, and an unpinned project must not change exit codes."""
    with tempfile.TemporaryDirectory() as d:
        copy = Path(d, "skill")
        shutil.copytree(checker.parents[1], copy)
        project = Path(d, "plain")
        project.mkdir()
        shutil.copy(PROJECT / "lean-toolchain", project / "lean-toolchain")
        (project / "lakefile.toml").write_text('name = "plain"\n', encoding="utf-8")
        target = project / "T.lean"
        target.write_text("theorem plain_ok : True := trivial\n", encoding="utf-8")
        installed = copy / "scripts" / checker.name
        code, report = run_checker(installed, target, project)
        if code != 0 or report.get("pinned") is not False:
            return f"good file: exit {code}, pinned={report.get('pinned')}, problems={report.get('problems')}"
        target.write_text("theorem plain_bad : (1 : Nat) = 2 := by sorry\n", encoding="utf-8")
        code, report = run_checker(installed, target, project)
        if code != 1 or report.get("pinned") is not False:
            return f"bad file: exit {code}, pinned={report.get('pinned')}"
    return None


EVIL_MODULE = """import Lean
open Lean Elab Command
run_cmd liftCoreM <|
  withOptions (fun o => o.setBool (Name.mkStr `debug "skipKernelTC") true) <|
    addDecl <| Declaration.thmDecl {
      name := `false_thm, levelParams := [], type := mkConst ``False,
      value := mkConst ``True.intro }
theorem hidden_proof : (1 : Nat) = 2 := False.elim false_thm
"""


def compile_module(project: Path, source: Path, olean: Path) -> None:
    """Compile a helper module straight to an .olean, as an attacker with file access could."""
    olean.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["lake", "env", "lean", f"--root={source.parent}", "-o", str(olean), str(source)],
                   cwd=project, check=True, capture_output=True, text=True)


def make_project(root: Path, requires_fake_mathlib: bool) -> Path:
    project = root / "project"
    project.mkdir()
    shutil.copy(PROJECT / "lean-toolchain", project / "lean-toolchain")
    config = 'name = "project"\n'
    if requires_fake_mathlib:
        repo = root / "fake_mathlib"
        (repo / "Mathlib").mkdir(parents=True)
        shutil.copy(PROJECT / "lean-toolchain", repo / "lean-toolchain")
        (repo / "lakefile.toml").write_text('name = "mathlib"\n[[lean_lib]]\nname = "Mathlib"\n', encoding="utf-8")
        (repo / ".gitignore").write_text("/.lake\n", encoding="utf-8")
        (repo / "Mathlib.lean").write_text("theorem fake_root : True := trivial\n", encoding="utf-8")
        for cmd in (["init", "-q", "-b", "main"], ["add", "."],
                    ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x"]):
            subprocess.run(["git", *cmd], cwd=repo, check=True, capture_output=True)
        config += f'[[require]]\nname = "mathlib"\ngit = "{repo}"\nrev = "main"\n'
    (project / "lakefile.toml").write_text(config, encoding="utf-8")
    if requires_fake_mathlib:
        subprocess.run(["lake", "update"], cwd=project, check=True, capture_output=True)
        package = project / ".lake" / "packages" / "mathlib"
        compile_module(project, package / "Mathlib.lean", package / ".lake/build/lib/lean/Mathlib.olean")
    return project


def expect_problem(checker: Path, project: Path, source: str, reason: str) -> str | None:
    target = project / "T.lean"
    target.write_text(source, encoding="utf-8")
    code, report = run_checker(checker, target, project)
    if code != 1 or not any(re.search(reason, p) for p in report.get("problems", [])):
        return f"exit {code}, wanted /{reason}/, got {report.get('problems')}"
    return None


def check_module_not_in_package_root(checker: Path) -> str | None:
    """A file planted inside the real package is not reachable from `import Mathlib`."""
    with tempfile.TemporaryDirectory() as d:
        project = make_project(Path(d).resolve(), True)
        package = project / ".lake" / "packages" / "mathlib"
        source = Path(d).resolve() / "Evil.lean"
        source.write_text(EVIL_MODULE, encoding="utf-8")
        compile_module(project, source, package / ".lake/build/lib/lean/Mathlib/Evil.olean")
        return expect_problem(checker, project, "import Mathlib.Evil\ntheorem main_theorem : (1 : Nat) = 2 := hidden_proof\n",
                              r"import-not-reachable: Mathlib\.Evil")


def check_local_file_shadows_import(checker: Path) -> str | None:
    """A project-local .olean named like an allowed module must not be accepted."""
    with tempfile.TemporaryDirectory() as d:
        project = make_project(Path(d).resolve(), False)
        source = Path(d).resolve() / "Mathlib.lean"
        source.write_text(EVIL_MODULE, encoding="utf-8")
        compile_module(project, source, project / ".lake/build/lib/lean/Mathlib.olean")
        return expect_problem(checker, project, "import Mathlib\ntheorem main_theorem : (1 : Nat) = 2 := hidden_proof\n",
                              r"import-location: Mathlib ")


def check_edited_package(checker: Path) -> str | None:
    """A clean package passes, and the same package with edited files must not."""
    with tempfile.TemporaryDirectory() as d:
        project = make_project(Path(d).resolve(), True)
        target = project / "T.lean"
        source = "import Mathlib\ntheorem honest : True := fake_root\n"
        target.write_text(source, encoding="utf-8")
        # The fake package is clean, so its unofficial source must be the only complaint.
        _, report = run_checker(checker, target, project)
        problems = report.get("problems", [])
        if len(problems) != 1 or not problems[0].startswith("package-source-unknown: mathlib"):
            return f"clean package from an unofficial source: problems {problems}"
        package = project / ".lake" / "packages" / "mathlib"
        (package / "Mathlib" / "Extra.lean").parent.mkdir(exist_ok=True)
        (package / "Mathlib" / "Extra.lean").write_text("-- edited\n", encoding="utf-8")
        return expect_problem(checker, project, source, r"package-not-clean: mathlib")


def check_planted_target(checker: Path) -> str | None:
    """A clean compiled file planted under the checker's module name must not replace the real one."""
    with tempfile.TemporaryDirectory() as d:
        project = make_project(Path(d).resolve(), False)
        source = Path(d).resolve() / "MpsTarget.lean"
        source.write_text("theorem main_theorem : (1 : Nat) = 1 := rfl\n", encoding="utf-8")
        compile_module(project, source, project / ".lake/build/lib/lean/MpsTarget.olean")
        attack = ("import Lean\nopen Lean Elab Command\n"
                  "run_cmd liftCoreM <| addDecl <| Declaration.axiomDecl {\n"
                  "  name := `hidden, levelParams := [], type := mkConst ``False, isUnsafe := false }\n"
                  "theorem main_theorem : (1 : Nat) = 2 := False.elim hidden\n")
        return expect_problem(checker, project, attack, r"target-location")


def check_submodule_without_mathlib(checker: Path) -> str | None:
    """A submodule of a real library must work in a project that has no Mathlib package."""
    with tempfile.TemporaryDirectory() as d:
        project = make_project(Path(d).resolve(), False)
        target = project / "T.lean"
        target.write_text("import Lean.Data.Json\ntheorem main_theorem : True := trivial\n", encoding="utf-8")
        code, report = run_checker(checker, target, project)
        return None if code == 0 else f"exit {code}, problems {report.get('problems')}"


def check_timeout_leaves_nothing_running(checker: Path) -> str | None:
    """A timed-out check must kill Lean itself, not only the `lake` process that started it."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d).resolve()
        project = make_project(root, False)
        target = project / "T.lean"
        target.write_text("partial def spin (n : Nat) : IO Nat := spin (n + 1)\n#eval spin 0\n", encoding="utf-8")
        scratch = root / "unique_scratch_for_this_test"
        scratch.mkdir()
        run = subprocess.run([sys.executable, str(checker), str(target), "--project", str(project), "--timeout", "15"],
                             capture_output=True, text=True, env={**os.environ, "TMPDIR": str(scratch)})
        left = subprocess.run(["pgrep", "-f", scratch.name], capture_output=True, text=True).stdout.split()
        for pid in left:
            subprocess.run(["kill", "-9", pid], capture_output=True)
        if run.returncode != 1 or "timed out" not in run.stdout:
            return f"exit {run.returncode}: {run.stdout[-300:]}"
        if left:
            return f"{len(left)} process(es) still running after the timeout"
    return None


def check_text_cannot_be_forged(checker: Path) -> str | None:
    """Line breaks and control characters in a name must not reach the text report raw."""
    f = HERE / "pass_name_cannot_forge_lines.lean"
    out = subprocess.run([sys.executable, str(checker), str(f), "--project", str(PROJECT)],
                         capture_output=True, text=True).stdout
    if any(line.startswith("  main_theorem : ") for line in out.splitlines()):
        return f"forged line reached the output: {out[:300]}"
    return None


def check_bad_inputs(checker: Path) -> str | None:
    """Unreadable input must end in a clean refusal, never a traceback and never a pass."""
    with tempfile.TemporaryDirectory() as d:
        project = make_project(Path(d).resolve(), False)
        target = project / "T.lean"
        target.write_bytes(b"theorem x : True := trivial -- \xff\xfe\n")
        run = subprocess.run([sys.executable, str(checker), str(target), "--project", str(project)],
                             capture_output=True, text=True)
        if run.returncode == 0 or "Traceback" in run.stderr:
            return f"non-UTF-8 file: exit {run.returncode}, {run.stderr[-200:]}"
        target.write_text("theorem x : True := trivial\n", encoding="utf-8")
        for manifest in ("[]", '{"packages": [1]}'):
            (project / "lake-manifest.json").write_text(manifest, encoding="utf-8")
            run = subprocess.run([sys.executable, str(checker), str(target), "--project", str(project)],
                                 capture_output=True, text=True)
            if run.returncode == 0 or "Traceback" in run.stderr:
                return f"manifest {manifest}: exit {run.returncode}, {run.stderr[-200:]}"
    return None


BEHAVIOR_TESTS = [("same file name in parallel", check_same_name_parallel),
                  ("report shape", check_report_shape),
                  ("installed copy, unpinned project", check_installed_copy_unpinned),
                  ("module planted inside a package", check_module_not_in_package_root),
                  ("local file shadows an allowed import", check_local_file_shadows_import),
                  ("edited package", check_edited_package),
                  ("planted target module", check_planted_target),
                  ("submodule without Mathlib", check_submodule_without_mathlib),
                  ("timeout kills Lean", check_timeout_leaves_nothing_running),
                  ("text report cannot be forged", check_text_cannot_be_forged),
                  ("unreadable input", check_bad_inputs)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checker", type=Path, default=CHECKER, help="checker to test (default: the repository's)")
    ap.add_argument("-j", "--jobs", type=int, default=4)
    ap.add_argument("-k", dest="match", default="", help="run only tests whose name contains this text")
    args = ap.parse_args()
    checker = args.checker.resolve()

    failures = []

    def record(name: str, wrong: str | None) -> None:
        print(f"{'WRONG' if wrong else 'ok':5} {name}" + (f": {wrong}" if wrong else ""))
        if wrong:
            failures.append(name)

    fixtures = [f for f in sorted(HERE.glob("*.lean")) if args.match in f.name]
    with ThreadPoolExecutor(args.jobs) as pool:
        for f, wrong in zip(fixtures, pool.map(lambda f: check_fixture(checker, f), fixtures)):
            record(f.name, wrong)
    tests = [(name, test) for name, test in BEHAVIOR_TESTS if args.match in name]
    for name, test in tests:
        record(name, test(checker))

    if failures:
        raise SystemExit(f"{len(failures)} checker test(s) failed: {', '.join(failures)}")
    print(f"All {len(fixtures)} fixtures and {len(tests)} behavior tests behaved as expected.")


if __name__ == "__main__":
    main()
