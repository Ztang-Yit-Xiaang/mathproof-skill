#!/usr/bin/env python3
"""Machine-check every Lean formalization referenced by evals/cases.jsonl.

Runs skill/scripts/lean_check.py on each case's `lean.file`, requiring each listed
declaration, and fails if any case does not pass. Usage:

    python3 scripts/check_lean_evals.py [-j JOBS] [CASE_ID ...]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "cases.jsonl"
CHECKER = ROOT / "skill" / "scripts" / "lean_check.py"
PROJECT = ROOT / "lean"


def run(case: dict) -> tuple[str, dict]:
    lean = case["lean"]
    cmd = [sys.executable, str(CHECKER), str(ROOT / lean["file"]), "--project", str(PROJECT), "--json"]
    for d in lean["declarations"]:
        cmd += ["--require", d]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        report = {"status": "FAIL", "problems": [proc.stderr.strip() or proc.stdout.strip()]}
    return case["id"], report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-j", "--jobs", type=int, default=4)
    ap.add_argument("ids", nargs="*")
    args = ap.parse_args()

    cases = [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    cases = [c for c in cases if "lean" in c and (not args.ids or c["id"] in args.ids)]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run, cases))

    failed = []
    for (case_id, report), case in zip(results, cases):
        kind = case["lean"]["formalization"]
        print(f"{report['status']:4}  {case_id:18} {case['expected_verdict']:20} {kind}")
        for p in report.get("problems", []):
            print(f"      ✗ {p}")
        if report["status"] != "PASS":
            failed.append(case_id)
    if failed:
        raise SystemExit(f"{len(failed)} of {len(cases)} Lean formalizations failed: {', '.join(failed)}")
    print(f"All {len(cases)} Lean formalizations passed the checker.")


if __name__ == "__main__":
    main()
