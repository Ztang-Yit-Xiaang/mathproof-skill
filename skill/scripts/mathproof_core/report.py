"""Render a claim as Markdown. A report is a view of derived status, never stored as truth.

Status lines come only from `derive_status`. Everything an agent or a Lean file wrote is quoted or
indented, so it cannot form a heading or a status line of its own.
"""

from __future__ import annotations

import json
import shlex
import unicodedata

from .ledger import ArtifactCorrupt, Ledger
from .status import derive_status


def _clean(text: object) -> str:
    """Escape control characters, keeping newlines for the caller to handle."""
    return "".join(c if c == "\n" else f"\\u{{{ord(c):04x}}}"
                   if unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp") else c
                   for c in str(text))


def _quoted(text: object) -> list[str]:
    return [f"> {line}" for line in _clean(text).splitlines()] or [">"]


def _indented(text: object) -> list[str]:
    return [f"    {line}" for line in _clean(text).splitlines()]


def _cell(text: object) -> str:
    return _clean(text).replace("\n", " ").replace("|", "\\|")


def _stored_report(ledger: Ledger, data: dict) -> dict | None:
    try:
        report = json.loads(ledger.get_artifact(data["report_hash"]))
    except (ArtifactCorrupt, FileNotFoundError, ValueError, KeyError):
        return None
    return report if isinstance(report, dict) else None


def _proved_section(ledger: Ledger, checks: list[dict]) -> list[str]:
    lines = ["## What Lean checked", ""]
    passing = [c for c in checks if c["result"] == "pass"]
    if not passing:
        return lines + ["No passing check is recorded.", ""]
    for check in passing:
        lines += [f"`{_cell(check['target_decl'])}`, polarity `{_cell(check['polarity'])}`, axioms: "
                  f"{_cell(', '.join(check.get('axioms') or []) or 'none')}", ""]
        report = _stored_report(ledger, check)
        target = next((d for d in (report or {}).get("declarations", []) if d.get("name") == check["target_decl"]), None)
        if target is None:
            lines += ["The stored report is not available, so the statement cannot be shown from it.", ""]
            continue
        lines += ["Statement:", ""] + _indented(target.get("type")) + [""]
        lines += ["Explicit form:", ""] + _indented(target.get("type_explicit")) + [""]
        for name in target.get("statement_uses") or []:
            entry = (report.get("statement_context") or {}).get(name, {})
            lines += [f"Depends on this file's `{_cell(name)}`:", ""] + _indented(entry.get("type"))
            if "definition" in entry:
                lines += _indented(f":= {entry['definition']}")
            lines.append("")
    return lines


def render_report(ledger: Ledger, claim: str, env: dict | None = None) -> str:
    events = ledger.read()
    status = derive_status(events, claim, env or {})
    mine = [e for e in events if e.get("claim") == claim]
    data_of = lambda kind: [e["data"] for e in mine if e.get("kind") == kind]  # noqa: E731
    axes = status["axes"]

    lines = [f"# Claim `{_cell(claim)}`", ""]
    lines += ["Statement as written:", ""] + _quoted(status["statement"] or "No statement is recorded.") + [""]
    lines += [f"**Headline:** `{status['headline']}`", "",
              f"**Verdict:** {status['verdict']}", "",
              f"**Lean status:** {_clean(status['lean_status'])}", ""]

    fidelity = axes["fidelity"]
    lines += ["## Status axes", "",
              f"- Kernel: `{axes['kernel']}`",
              f"- Fidelity: `{fidelity['class'] or 'none'}`, direction `{fidelity['direction'] or 'none'}`, "
              f"provenance `{fidelity['provenance']}`, signed: {'yes' if fidelity['signed'] else 'no'}",
              f"- Informal proof: `{axes['informal']}`",
              f"- Experiments: {axes['computational']['runs']} runs, {axes['computational']['candidates']} candidate counterexamples",
              f"- Search: `{axes['search']}`", ""]
    lines += _proved_section(ledger, data_of("check"))

    judgments = data_of("fidelity")
    if judgments:
        lines += ["## Fidelity judgments", "", "These are labels, as written by their judge. None has a verified signature.", "",
                  "| Class | Direction | Judge |", "| --- | --- | --- |"]
        lines += [f"| {_cell(j['class'])} | {_cell(j['direction'])} | {_cell(j['judge'])} |" for j in judgments] + [""]
        rows = [row for j in judgments for row in j.get("rows") or []]
        if rows:
            lines += ["| Informal | Lean | Match |", "| --- | --- | --- |"]
            lines += [f"| {_cell(r.get('informal', ''))} | {_cell(r.get('formal', ''))} | {_cell(r.get('match', ''))} |"
                      if isinstance(r, dict) else f"| {_cell(r)} | | |" for r in rows] + [""]

    open_items = [item for stop in data_of("budget_stop") for item in stop["open_items"]]
    lines += ["## Open items", ""]
    lines += [f"- {_cell(item)}" for item in open_items + status["warnings"]] or ["None recorded."]
    if status["ignored_events"]:
        lines.append(f"- {status['ignored_events']} invalid events were ignored.")
    lines += ["", "## Replay", "",
              "Status is recomputed from the ledger, and each check can be re-run:", "",
              f"    python3 skill/scripts/mathproof.py verify {shlex.quote(str(ledger.directory))}", ""]

    notes = [e["data"] for e in mine if e.get("kind") == "note"]
    if notes:
        lines += ["## Unverified notes", "", "These were written by agents. They are not evidence, and nothing here affects the status above.", ""]
        for note in notes:
            lines += _quoted(note.get("text", json.dumps(note, ensure_ascii=False))) + [""]
    return "\n".join(lines)
