#!/usr/bin/env python3
"""Regression tests for skill/scripts/lean_check.py.

Each fixture must PASS or FAIL as named, and a failing fixture must fail for its stated reason,
so an unresolved import cannot count as an attack caught. Pass --checker to run the fixtures
against another version of the checker, for example to show that a known-bad one fails them.
"""

from __future__ import annotations

import argparse
import json
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
EXTRA = {"fail_missing_required.lean": ["--require", "main_theorem"]}

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
    "fail_sorry.lean": r"sorry",
}

# Statements a passing fixture must print exactly: the check on the printer itself.
PRINTED_TYPES = {
    "pass_print_spoof_shows_truth.lean": {
        "main_theorem": "True",
        "succ_statement": "∀ (n : Nat), n.succ = n + 1",
    },
}

# File-local constants a fixture's statement must be reported as using.
STATEMENT_USES = {
    "pass_instance_shadow_is_listed.lean": {"main_theorem": ["evilAdd"]},
    "pass_core.lean": {"claim_true": ["Claim"]},
}

# Keys of the check report that consumers rely on (IF-check-report-v2).
REPORT_KEYS = {"file", "status", "problems", "declarations", "checker", "toolchain", "mathlib_rev",
               "pinned", "tier", "stages"}


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
    uses = {d["name"]: d.get("statement_uses") for d in report.get("declarations", [])}
    for name, want in STATEMENT_USES.get(f.name, {}).items():
        if uses.get(name) != want:
            return f"`{name}` reported as using {uses.get(name)}, expected {want}"
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
    if any(stages.get(s, {}).get("status") != "pass" for s in ("source_scan", "compile", "audit", "replay")):
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checker", type=Path, default=CHECKER, help="checker to test (default: the repository's)")
    ap.add_argument("-j", "--jobs", type=int, default=4)
    args = ap.parse_args()
    checker = args.checker.resolve()

    failures = []

    def record(name: str, wrong: str | None) -> None:
        print(f"{'WRONG' if wrong else 'ok':5} {name}" + (f": {wrong}" if wrong else ""))
        if wrong:
            failures.append(name)

    fixtures = sorted(HERE.glob("*.lean"))
    with ThreadPoolExecutor(args.jobs) as pool:
        for f, wrong in zip(fixtures, pool.map(lambda f: check_fixture(checker, f), fixtures)):
            record(f.name, wrong)
    for name, test in [("same file name in parallel", check_same_name_parallel),
                       ("report shape", check_report_shape),
                       ("installed copy, unpinned project", check_installed_copy_unpinned)]:
        record(name, test(checker))

    if failures:
        raise SystemExit(f"{len(failures)} checker test(s) failed: {', '.join(failures)}")
    print(f"All {len(fixtures)} fixtures and 3 behavior tests behaved as expected.")


if __name__ == "__main__":
    main()
