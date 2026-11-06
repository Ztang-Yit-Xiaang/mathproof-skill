"""Run the Lean checker on a file and record what happened as a `check` event.

The checker runs as a subprocess, on a temporary copy of the stored bytes. An environment failure
records nothing: "could not check" is not a result. A pass needs the exact target name, which must
be a theorem, because the checker's own `--require` also accepts a suffix or a definition.

This is the local tier. It defends against accidents and shortcuts, and never gives more than
kernel-passed-local. See the trust boundary in references/lean-verification.md.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .ledger import Ledger

CHECKER = Path(__file__).resolve().parents[1] / "lean_check.py"
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
GATE_ACTOR_ROLE = "gate"

# Lean could not start on the file at all: these say nothing about the proof.
_ENVIRONMENT_PROBLEM = re.compile(r"unknown module prefix|object file .* does not exist")


class EnvironmentFailure(Exception):
    """The check could not run, so there is no result to record."""


def _target(report: dict, decl: str) -> dict | None:
    for declaration in report.get("declarations", []):
        if declaration.get("name") == decl:
            return declaration
    return None


def outcome(report: dict, decl: str) -> tuple[str, list[str]]:
    """Decide pass or fail from a checker report, with the reasons for a failure."""
    reasons = list(report.get("problems", []))
    timed_out = any(isinstance(s, dict) and s.get("status") == "timeout" for s in (report.get("stages") or {}).values())
    if report.get("environment_error") or timed_out or any(_ENVIRONMENT_PROBLEM.search(str(r)) for r in reasons):
        raise EnvironmentFailure("; ".join(str(r) for r in reasons) or "checker could not run")
    if report.get("status") != "PASS" and not reasons:
        reasons.append("checker did not report PASS")
    target = _target(report, decl)
    if target is None:
        reasons.append(f"no declaration with the exact name `{decl}`")
    else:
        if target.get("kind") != "theorem":
            reasons.append(f"`{decl}` is not a theorem")
        bad = sorted(set(target.get("axioms", [])) - ALLOWED_AXIOMS)
        if bad:
            reasons.append(f"`{decl}` depends on non-standard axioms: {', '.join(bad)}")
    return ("pass" if report.get("status") == "PASS" and not reasons else "fail"), reasons


def normalized(report: dict) -> dict:
    """Everything a report shows that must reproduce. Timing and paths never count."""
    return {"status": report.get("status"),
            "environment": {key: report.get(key) for key in ("toolchain", "mathlib_rev", "pinned", "environment_error")},
            "declarations": sorted((json.dumps({"name": d.get("name"), "kind": d.get("kind"), "type": d.get("type"),
                                                "type_explicit": d.get("type_explicit"), "definition": d.get("definition"),
                                                "axioms": sorted(d.get("axioms", [])),
                                                "statement_uses": d.get("statement_uses")}, sort_keys=True)
                                    for d in report.get("declarations", []))),
            "statement_context": report.get("statement_context")}


def summarize(reasons: list[str]) -> list[str]:
    """The failure reasons as stored in an event."""
    return [reason[:300] for reason in reasons[:5]]


def without_paths(report: dict, *directories: str) -> dict:
    """Replace temporary paths, which are noise in a stored report and differ on every run."""
    text = json.dumps(report, ensure_ascii=False)
    for directory in directories:
        text = text.replace(json.dumps(directory, ensure_ascii=False)[1:-1], "<check>")
    return json.loads(text)


def run_checker(source: bytes, decl: str, project: str | os.PathLike[str], checker: Path = CHECKER) -> dict:
    """Run the checker on a temporary copy of `source`. Raises EnvironmentFailure if it cannot run."""
    if not Path(project).is_dir():
        raise EnvironmentFailure(f"Lean project not found: {project}")
    if not Path(checker).is_file():
        raise EnvironmentFailure(f"checker not found: {checker}")
    with tempfile.TemporaryDirectory(prefix="mps_gate_") as directory:
        path = Path(directory, "Check.lean")
        path.write_bytes(source)
        proc = subprocess.run([sys.executable, str(checker), str(path), "--project", str(project),
                               "--require", decl, "--json"], capture_output=True, text=True)
        if proc.returncode not in (0, 1):
            raise EnvironmentFailure((proc.stderr or proc.stdout).strip()[-500:] or f"checker exited {proc.returncode}")
        try:
            report = json.loads(proc.stdout)
        except ValueError as error:
            raise EnvironmentFailure(f"checker gave no report: {error}") from error
        return without_paths(report, str(Path(directory).resolve()), directory)


def _actor() -> dict[str, str]:
    return {"context_id": os.environ.get("MATHPROOF_CONTEXT_ID", "unknown"), "role": GATE_ACTOR_ROLE, "kind": "runner"}


def record_check(ledger: Ledger, claim: str, file: str | os.PathLike[str], decl: str, polarity: str,
                 project: str | os.PathLike[str], checker: Path = CHECKER) -> dict:
    """Check a Lean file and append the result. Raises EnvironmentFailure, recording nothing."""
    if not any(e.get("kind") == "claim_created" and e.get("claim") == claim for e in ledger.read()):
        raise ValueError(f"unknown claim: {claim}")
    source = Path(file).read_bytes()
    project = Path(project).resolve()
    report = run_checker(source, decl, project, checker)
    result, reasons = outcome(report, decl)
    target = _target(report, decl) or {}
    report["request"] = {"target_decl": decl, "polarity": polarity}
    data = {
        "artifact": ledger.put_artifact(source),
        "target_decl": decl,
        "polarity": polarity,
        "result": result,
        "report_hash": ledger.put_artifact(json.dumps(report, sort_keys=True, ensure_ascii=False).encode("utf-8")),
        "pins": {key: report.get(key) for key in ("toolchain", "mathlib_rev", "pinned", "checker")},
        "tier": "local",
        "project": str(project),
        "type": target.get("type"),
        "axioms": sorted(target.get("axioms", [])),
        "problems": summarize(reasons),
    }
    return ledger.append("check", claim, data, _actor())
