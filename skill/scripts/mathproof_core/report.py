"""Render a claim as Markdown. A report is a view of derived status, never stored as truth.

Status lines come only from `derive_status`, and hold only values from closed lists. Everything an
agent or a Lean file wrote is escaped, quoted, or indented, so it cannot render as a heading, a
status line, or HTML. A report reads stored results, and only `verify` re-runs them.
"""

from __future__ import annotations

import json
import re
import shlex
import unicodedata
from pathlib import Path

from .events import is_status_bearing
from .ledger import ArtifactCorrupt, Ledger
from .status import derive_status, usable_events

_SCRIPT = Path(__file__).resolve().parents[1] / "mathproof.py"
_MARKUP = re.compile(r"([\\`*_{}\[\]<>#|~&])")


def _clean(text: object) -> str:
    """Escape control characters, keeping newlines for the caller to handle."""
    return "".join(c if c == "\n" else f"\\u{{{ord(c):04x}}}"
                   if unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp") else c
                   for c in str(text))


def _text(text: object) -> str:
    """One line of inert Markdown."""
    return _MARKUP.sub(r"\\\1", _clean(text).replace("\n", " "))


def _quoted(text: object) -> list[str]:
    # Leading spaces are dropped, so a line of `=` or `-` can't turn the one above into a heading.
    lines = [_MARKUP.sub(r"\\\1", line.lstrip()) for line in _clean(text).splitlines()]
    return [f"> \\{line}" if line[:1] in ("=", "-", "+") else f"> {line}" for line in lines] or [">"]


def _indented(text: object) -> list[str]:
    """A code block: nothing in it renders."""
    return [f"    {line}" for line in _clean(text).splitlines()]


def _stored_report(ledger: Ledger, data: dict) -> dict | None:
    try:
        report = json.loads(ledger.get_artifact(data["report_hash"]))
    except (ArtifactCorrupt, FileNotFoundError, ValueError, KeyError):
        return None
    return report if isinstance(report, dict) else None


def _target_in(report: dict | None, name: str) -> dict | None:
    declarations = (report or {}).get("declarations")
    if not isinstance(declarations, list):
        return None
    return next((d for d in declarations if isinstance(d, dict) and d.get("name") == name), None)


def _proved_section(ledger: Ledger, checks: list[dict]) -> list[str]:
    key = lambda c: (c["artifact"], c["target_decl"], c["polarity"])  # noqa: E731
    failed = {key(c) for c in checks if c["result"] == "fail"}
    passing = [c for c in checks if c["result"] == "pass" and key(c) not in failed]
    lines = ["## What Lean checked", ""]
    if not passing:
        return lines + ["No passing check is recorded.", ""]
    for check in passing:
        axioms = check.get("axioms") if isinstance(check.get("axioms"), list) else []
        lines += [f"{_text(check['target_decl'])}, polarity {_text(check['polarity'])}, axioms: "
                  f"{_text(', '.join(str(a) for a in axioms) or 'none')}", ""]
        report = _stored_report(ledger, check)
        target = _target_in(report, check["target_decl"])
        if target is None:
            lines += ["The stored report is not available, so the statement cannot be shown from it.", ""]
            continue
        lines += ["Statement:", ""] + _indented(target.get("type")) + [""]
        lines += ["Explicit form:", ""] + _indented(target.get("type_explicit")) + [""]
        uses = target.get("statement_uses") if isinstance(target.get("statement_uses"), list) else []
        context = report.get("statement_context") if isinstance(report.get("statement_context"), dict) else {}
        for name in uses:
            entry = context.get(name) if isinstance(name, str) else None
            entry = entry if isinstance(entry, dict) else {}
            lines += [f"Depends on this file's {_text(name)}:", ""] + _indented(entry.get("type"))
            if "definition" in entry:
                lines += _indented(f":= {entry['definition']}")
            lines.append("")
    return lines


def render_report(ledger: Ledger, claim: str, env: dict | None = None) -> str:
    events = ledger.read()
    status = derive_status(events, claim, env or {})
    mine = [e for e in events if isinstance(e, dict) and e.get("claim") == claim]
    usable, _ = usable_events(events, claim)
    data_of = lambda kind: [e["data"] for e in usable if e["kind"] == kind]  # noqa: E731
    axes = status["axes"]

    lines = [f"# Claim {_text(claim)}", ""]
    lines += ["Statement as written:", ""] + _quoted(status["statement"] or "No statement is recorded.") + [""]
    lines += [f"**Headline:** `{status['headline']}`", "",
              f"**Verdict:** {status['verdict']}", "",
              f"**Lean status:** {status['lean_status']}", ""]

    fidelity = axes["fidelity"]
    lines += ["## Status axes", "",
              f"- Kernel: `{axes['kernel']}`",
              f"- Fidelity: `{fidelity['class'] or 'none'}`, direction `{fidelity['direction'] or 'none'}`, "
              f"provenance `{fidelity['provenance']}`, signed: {'yes' if fidelity['signed'] else 'no'}",
              f"- Informal proof: `{axes['informal']}`",
              f"- Experiments: {axes['computational']['runs']} runs, {axes['computational']['candidates']} candidate counterexamples",
              f"- Search: `{axes['search']}`", ""]
    if fidelity["scope"]:
        lines[-1:] = [f"- Scope, as written by the judge: {_text(fidelity['scope'])}", ""]
    lines += _proved_section(ledger, data_of("check"))

    judgments = data_of("fidelity")
    if judgments:
        lines += ["## Fidelity judgments", "", "These are labels, as written by their judge. None has a verified signature.", "",
                  "| Class | Direction | Judge |", "| --- | --- | --- |"]
        lines += [f"| {_text(j['class'])} | {_text(j['direction'])} | {_text(j['judge'])} |" for j in judgments] + [""]
        rows = [row for j in judgments for row in j.get("rows") or []]
        if rows:
            lines += ["| Informal | Lean | Match |", "| --- | --- | --- |"]
            lines += [f"| {_text(r.get('informal', ''))} | {_text(r.get('formal', ''))} | {_text(r.get('match', ''))} |"
                      if isinstance(r, dict) else f"| {_text(r)} | | |" for r in rows] + [""]

    open_items = [item for stop in data_of("budget_stop") for item in stop["open_items"]]
    lines += ["## Open items", ""]
    lines += [f"- {_text(item)}" for item in open_items + status["warnings"]] or ["None recorded."]
    if status["ignored_events"]:
        lines.append(f"- {status['ignored_events']} invalid events were ignored.")
    command = _clean(f"python3 {shlex.quote(str(_SCRIPT))} verify {shlex.quote(str(ledger.directory))}").replace("\n", "\\n")
    lines += ["", "## Replay", "",
              "This shows recorded results, which are unconfirmed until `verify` reproduces them:", "",
              f"    {command}", ""]

    notes = [e.get("data", {}) for e in mine if not is_status_bearing(str(e.get("kind"))) and isinstance(e.get("data"), dict)]
    if notes:
        lines += ["## Unverified notes", "", "These were written by agents. They are not evidence, and nothing here affects the status above.", ""]
        for note in notes:
            lines += _quoted(note.get("text", json.dumps(note, ensure_ascii=False))) + [""]
    return "\n".join(lines)
