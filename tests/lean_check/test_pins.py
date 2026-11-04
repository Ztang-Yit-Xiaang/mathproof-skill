#!/usr/bin/env python3
"""The Lean version must agree across lean-toolchain, lakefile.toml, and lean_check.py."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    toolchain = (ROOT / "lean" / "lean-toolchain").read_text(encoding="utf-8").strip()
    lakefile = (ROOT / "lean" / "lakefile.toml").read_text(encoding="utf-8")
    checker = (ROOT / "skill" / "scripts" / "lean_check.py").read_text(encoding="utf-8")

    mathlib = re.search(r'name = "mathlib".*?rev = "([^"]+)"', lakefile, re.S).group(1)
    checker_toolchain = re.search(r'^LEAN_TOOLCHAIN = "([^"]+)"', checker, re.M).group(1)
    checker_mathlib = re.search(r'^MATHLIB_REV = "([^"]+)"', checker, re.M).group(1)

    problems = []
    if toolchain != checker_toolchain:
        problems.append(f"lean-toolchain {toolchain} != lean_check.py {checker_toolchain}")
    if mathlib != checker_mathlib:
        problems.append(f"lakefile.toml {mathlib} != lean_check.py {checker_mathlib}")
    if not toolchain.endswith(":" + mathlib):
        problems.append(f"Mathlib {mathlib} does not match Lean {toolchain}")
    if problems:
        sys.exit("\n".join(problems))
    print(f"Pins agree: {toolchain}, Mathlib {mathlib}.")


if __name__ == "__main__":
    main()
