"""Check an investigation: its chain, its stored files, and every check, re-run from scratch.

This writes nothing inside the investigation. It trusts only the installed checker and toolchain,
so a recorded PASS counts for nothing until the re-run agrees. A changed checker is reported as a
difference, not passed over. If a check cannot be re-run, that is an environment error and never a
pass.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .events import STATUS_BEARING_KINDS, validate_event
from .gate import CHECKER, EnvironmentFailure, _target, normalized, outcome, run_checker, summarize
from .ledger import ArtifactCorrupt, Ledger
from .status import derive_status

DELETION_NOTE = ("This does not detect deletion of events from the end of the ledger, or a whole "
                 "ledger rewritten consistently with honest checks removed, because the ledger's head "
                 "is not anchored anywhere outside it yet.")

# Fields that must name a stored file.
_ARTIFACT_FIELDS = {"check": ("artifact", "report_hash"), "fidelity": ("statement_hash",),
                    "informal_proof": ("artifact",), "informal_audit": ("proof_hash",),
                    "experiment": ("code_hash",), "statement_frozen": ("artifact",), "witness": ("artifact",)}


def compare_rerun(event_data: dict, stored: dict, fresh: dict) -> list[str]:
    """Differences between what was recorded and what a fresh run says."""
    decl = event_data.get("target_decl", "")
    differences = []
    result, reasons = outcome(fresh, decl)
    if event_data.get("result") != result:
        differences.append(f"event says {event_data.get('result')}, re-run says {result}")
    try:
        same = normalized(stored) == normalized(fresh)
    except (AttributeError, TypeError):
        same = False
    if not same:
        differences.append("stored report differs from the re-run")
    if stored.get("request") != {"target_decl": decl, "polarity": event_data.get("polarity")}:
        differences.append("stored report was made for a different target or polarity")
    target = _target(fresh, decl) or {}
    if event_data.get("type") != target.get("type"):
        differences.append("event's statement differs from the re-run")
    if event_data.get("axioms") != sorted(target.get("axioms", [])):
        differences.append("event's axioms differ from the re-run")
    if event_data.get("tier") != "local":
        differences.append(f"event claims tier {event_data.get('tier')}, and this re-run is local")
    if event_data.get("problems") != summarize(reasons):
        differences.append("event's stated problems differ from the re-run")
    pins = event_data.get("pins")
    for key in ("toolchain", "mathlib_rev", "pinned"):
        if not isinstance(pins, dict) or pins.get(key) != fresh.get(key):
            differences.append(f"{key} differs from the re-run")
    if stored.get("checker") != fresh.get("checker") or not isinstance(pins, dict) or pins.get("checker") != fresh.get("checker"):
        differences.append("checker changed since this was recorded, so this result was not reproduced by the same checker")
    return differences


def _readable_events(ledger: Ledger) -> list:
    """Every line that parses, keeping position. Unreadable lines are None and verify reports them."""
    if not ledger.events_path.exists():
        return []
    events = []
    for line in ledger.events_path.read_bytes().split(b"\n")[:-1]:
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            event = None
        events.append(event if isinstance(event, dict) else None)
    return events


def _claim_of(event) -> str | None:
    claim = event.get("claim") if isinstance(event, dict) else None
    return claim if isinstance(claim, str) else None


def verify_investigation(directory: str | os.PathLike[str], project: str | os.PathLike[str] | None = None,
                         checker: Path = CHECKER) -> dict:
    """Returns {ok, differences, environment_errors, statuses, reruns, notes}. Writes nothing."""
    ledger = Ledger(directory)
    events = _readable_events(ledger)
    differences: list[dict] = []
    environment_errors: list[dict] = []

    def differ(claim, seq, kind, detail):
        differences.append({"claim": claim, "seq": seq, "kind": kind, "detail": detail})

    chain = ledger.verify()
    for error in chain.errors:
        index = error.line - 1
        event = events[index] if index < len(events) else None
        differ(_claim_of(event), index, "chain", f"line {error.line}: {error.message}")

    usable = [e for e in events if e is not None and not validate_event(e)]
    reruns = 0
    cache: dict[tuple, dict] = {}
    for event in usable:
        claim, seq, kind, data = event["claim"], event["seq"], event["kind"], event["data"]
        for field in _ARTIFACT_FIELDS.get(kind, ()):
            try:
                ledger.get_artifact(data[field])
            except (ArtifactCorrupt, FileNotFoundError, ValueError, KeyError) as error:
                differ(claim, seq, "artifact", f"{kind}.{field}: {error}")
        if kind != "check":
            continue
        try:
            source = ledger.get_artifact(data["artifact"])
        except (ArtifactCorrupt, FileNotFoundError, ValueError):
            continue
        try:
            stored = json.loads(ledger.get_artifact(data["report_hash"]))
            if not isinstance(stored, dict):
                raise ValueError("stored report is not an object")
        except (ArtifactCorrupt, FileNotFoundError, ValueError):
            stored = {}
        chosen = project if project is not None else data.get("project")
        key = (data["artifact"], data["target_decl"], str(chosen))
        try:
            if chosen is None:
                raise EnvironmentFailure("no Lean project recorded; pass --project")
            if key not in cache:
                cache[key] = run_checker(source, data["target_decl"], chosen, checker)
                reruns += 1
            for detail in compare_rerun(data, stored, cache[key]):
                differ(claim, seq, "check", detail)
        except EnvironmentFailure as error:
            environment_errors.append({"claim": claim, "seq": seq, "detail": str(error)})

    claims = sorted({e["claim"] for e in usable if e["claim"] and e["kind"] in STATUS_BEARING_KINDS})
    with_statement = {e["claim"] for e in usable if e["kind"] == "claim_created"}
    for claim in claims:
        if claim not in with_statement:
            differ(claim, None, "claim", "this claim has records but no statement")
    return {"ok": not differences and not environment_errors,
            "differences": differences,
            "environment_errors": environment_errors,
            "statuses": {claim: derive_status(usable, claim, {}) for claim in claims},
            "reruns": reruns,
            "notes": [DELETION_NOTE]}
