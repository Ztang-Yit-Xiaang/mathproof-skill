#!/usr/bin/env python3
"""Regression tests for skill/scripts/lean_check.py: each fixture must PASS or FAIL as named."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHECKER = ROOT / "skill" / "scripts" / "lean_check.py"
PROJECT = ROOT / "lean"
EXTRA = {"fail_missing_required.lean": ["--require", "main_theorem"]}


def main() -> None:
    failures = []
    fixtures = sorted(HERE.glob("*.lean"))
    for f in fixtures:
        expected = 0 if f.name.startswith("pass_") else 1
        cmd = [sys.executable, str(CHECKER), str(f), "--project", str(PROJECT), *EXTRA.get(f.name, [])]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        verdict = "ok" if proc.returncode == expected else "WRONG"
        print(f"{verdict:5} {f.name}: exit {proc.returncode} (expected {expected})")
        if proc.returncode != expected:
            failures.append(f.name)
            print(proc.stdout[-2000:], proc.stderr[-2000:], sep="\n")
    if failures:
        raise SystemExit(f"{len(failures)} checker test(s) failed: {', '.join(failures)}")
    print(f"All {len(fixtures)} checker tests behaved as expected.")


if __name__ == "__main__":
    main()
