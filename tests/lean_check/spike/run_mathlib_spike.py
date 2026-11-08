#!/usr/bin/env python3
"""Spike S2.1.T11: run mathlib cases through `lake comparator` in its sandbox and record what happens.

Uses Python standard library only.
Supports --dry-run DIR to scaffold the Mathlib project and cases without executing Lake.
Without --dry-run, sets up the Mathlib project in a temporary directory, runs `lake update`
and `lake exe cache get` once, cleans the project directory before each case, then copies
each case's files to the project root and runs `lake comparator` with a 40-minute timeout per case.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MATHLIB_CASES_FILE = HERE / os.environ.get("SPIKE_CASES", "mathlib_cases.json")
MATHLIB_GIT_URL = "https://github.com/leanprover-community/mathlib4.git"
TIMEOUT_SECONDS = 40 * 60  # 40 minutes


def load_spec() -> dict:
    with open(MATHLIB_CASES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_lakefile_toml(mathlib_rev: str) -> str:
    return (
        'name = "spike_mathlib"\n'
        'defaultTargets = ["Solution"]\n\n'
        '[[require]]\n'
        'name = "mathlib"\n'
        f'git = "{MATHLIB_GIT_URL}"\n'
        f'rev = "{mathlib_rev}"\n\n'
        '[[lean_lib]]\n'
        'name = "Challenge"\n\n'
        '[[lean_lib]]\n'
        'name = "Solution"\n'
    )


def verdict(kind: str, rc: int | str) -> str:
    """Return a verdict string starting with 'as expected' or 'SURPRISE'.

    A timeout rc is always a surprise.
    control-pass and trust expect rc 0.
    control-fail and attack expect nonzero.
    Any unknown kind returns a string starting with 'SURPRISE'.
    """
    if rc == "timeout":
        return "SURPRISE: timeout"
    if not isinstance(rc, int):
        return f"SURPRISE: unexpected return code type {rc}"

    if kind in ("control-pass", "trust"):
        if rc == 0:
            return "as expected"
        return f"SURPRISE: expected 0, got rc={rc}"
    elif kind in ("control-fail", "attack"):
        if rc != 0:
            return "as expected"
        return f"SURPRISE: expected nonzero, got rc={rc}"
    else:
        return f"SURPRISE: unknown kind '{kind}'"


def write_case_files(case_dir: Path, case: dict, theorem_names: list[str], permitted_axioms: list[str]) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "Challenge.lean").write_text(case["challenge"], encoding="utf-8")
    (case_dir / "Solution.lean").write_text(case["solution"], encoding="utf-8")

    case_theorems = case.get("theorem_names", theorem_names)
    case_axioms = case.get("permitted_axioms", permitted_axioms)

    comparator_data = {
        "challenge_module": "Challenge",
        "solution_module": "Solution",
        "theorem_names": case_theorems,
        "permitted_axioms": case_axioms,
    }
    (case_dir / "comparator.json").write_text(json.dumps(comparator_data, indent=2) + "\n", encoding="utf-8")


def write_dry_run(target_dir: Path, spec: dict) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    toolchain = spec["toolchain"]
    mathlib_rev = spec["mathlib_rev"]
    theorem_names = spec.get("theorem_names", ["main_theorem"])
    permitted_axioms = spec.get("permitted_axioms", ["propext", "Quot.sound", "Classical.choice"])

    (target_dir / "lean-toolchain").write_text(f"{toolchain}\n", encoding="utf-8")
    (target_dir / "lakefile.toml").write_text(build_lakefile_toml(mathlib_rev), encoding="utf-8")

    cases_dir = target_dir / "cases"
    for case in spec.get("cases", []):
        c_dir = cases_dir / case["name"]
        write_case_files(c_dir, case, theorem_names, permitted_axioms)


def clean_project_dir_for_case(root: Path) -> None:
    """Before each case, delete root's .lake/build directory and every file or directory

    in root except lakefile.toml, lean-toolchain, lake-manifest.json, and .lake/packages.
    """
    lake_build = root / ".lake" / "build"
    if lake_build.is_dir():
        shutil.rmtree(lake_build)
    elif lake_build.exists():
        lake_build.unlink()

    preserved_root_entries = {"lakefile.toml", "lean-toolchain", "lake-manifest.json", ".lake"}
    for item in root.iterdir():
        if item.name not in preserved_root_entries:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    # Inside .lake, preserve only 'packages'
    lake_dir = root / ".lake"
    if lake_dir.is_dir():
        for item in lake_dir.iterdir():
            if item.name != "packages":
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()


def run(cmd: list[str], cwd: Path, timeout: int = TIMEOUT_SECONDS) -> dict:
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        rc, output = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        rc, output = "timeout", ""
    return {"rc": rc, "seconds": round(time.monotonic() - start, 1), "output": output[-3000:]}


def setup_case_in_project(root: Path, case: dict, theorem_names: list[str], permitted_axioms: list[str]) -> None:
    clean_project_dir_for_case(root)

    (root / "Challenge.lean").write_text(case["challenge"], encoding="utf-8")
    (root / "Solution.lean").write_text(case["solution"], encoding="utf-8")

    case_theorems = case.get("theorem_names", theorem_names)
    case_axioms = case.get("permitted_axioms", permitted_axioms)

    comparator_data = {
        "challenge_module": "Challenge",
        "solution_module": "Solution",
        "theorem_names": case_theorems,
        "permitted_axioms": case_axioms,
    }
    (root / "comparator.json").write_text(json.dumps(comparator_data, indent=2) + "\n", encoding="utf-8")


def run_case(project_dir: Path, case: dict, theorem_names: list[str], permitted_axioms: list[str]) -> dict:
    name = case["name"]
    kind = case["kind"]
    setup_case_in_project(project_dir, case, theorem_names, permitted_axioms)

    comp = run(["lake", "comparator"], project_dir, timeout=TIMEOUT_SECONDS)
    v = verdict(kind, comp["rc"])

    return {
        "name": name,
        "kind": kind,
        "comparator": comp,
        "verdict": v,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Mathlib spike tests or scaffold dry-run")
    parser.add_argument("--dry-run", type=Path, metavar="DIR", help="Write scaffold files to DIR and exit")
    args = parser.parse_args()

    spec = load_spec()

    if args.dry_run:
        write_dry_run(args.dry_run, spec)
        print(f"Dry run complete: scaffolded to {args.dry_run}")
        return 0

    toolchain = spec["toolchain"]
    mathlib_rev = spec["mathlib_rev"]
    theorem_names = spec.get("theorem_names", ["main_theorem"])
    permitted_axioms = spec.get("permitted_axioms", ["propext", "Quot.sound", "Classical.choice"])
    all_cases = spec.get("cases", [])
    all_case_names = {c["name"] for c in all_cases}

    only = os.environ.get("SPIKE_ONLY")
    if only:
        requested = [name.strip() for name in only.split(",") if name.strip()]
        missing = [name for name in requested if name not in all_case_names]
        if missing:
            for m in missing:
                print(f"Case '{m}' not found in mathlib cases", flush=True)
            return 1
        cases = [c for c in all_cases if c["name"] in requested]
    else:
        cases = list(all_cases)

    if not cases:
        print("No cases to run", flush=True)
        return 1

    results = []
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "lean-toolchain").write_text(f"{toolchain}\n", encoding="utf-8")
        (root / "lakefile.toml").write_text(build_lakefile_toml(mathlib_rev), encoding="utf-8")

        print("Updating Lake project dependencies...", flush=True)
        upd = run(["lake", "update"], root, timeout=1200)
        print(f"lake update exited with rc={upd['rc']} in {upd['seconds']}s", flush=True)
        if upd["rc"] != 0:
            print(f"lake update failed:\n{upd['output']}", flush=True)
            return 1

        print("Fetching Mathlib cache...", flush=True)
        cache = run(["lake", "exe", "cache", "get"], root, timeout=1200)
        print(f"lake exe cache get exited with rc={cache['rc']} in {cache['seconds']}s", flush=True)
        if cache["rc"] != 0:
            print(f"lake exe cache get failed:\n{cache['output']}", flush=True)
            return 1

        for case in cases:
            res = run_case(root, case, theorem_names, permitted_axioms)
            results.append(res)
            c = res["comparator"]
            print(
                f"\n===== {res['name']} [{res['kind']}] comparator rc={c['rc']} {c['seconds']}s: {res['verdict']}",
                flush=True,
            )
            if c.get("output"):
                print(c["output"], flush=True)

    Path("spike_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n===== SUMMARY")
    for r in results:
        print(
            f"{r['name']:32} {r['kind']:13} comparator={str(r['comparator']['rc']):8} "
            f"{r['verdict']}"
        )

    return 1 if any(r["verdict"] != "as expected" or not r["verdict"].startswith("as expected") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
