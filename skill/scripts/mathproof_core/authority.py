"""Turn an attested judge report into `env["judged"]` for status derivation.

A report counts only if all of these hold, and verify says which failed otherwise:

1. `gh attestation verify` accepts the exact bytes read, pinned to the named repository, to the
   workflow `.github/workflows/authoritative.yml` in it, to `refs/heads/main`, and to GitHub-hosted
   runners. The repository comes from the person running verify, never from the report.
2. The report has the IF-judge-report-v0 shape, says it ran sandboxed, and names this checker's pins,
   this judge's version, and its permitted axioms. Bumping JUDGE_VERSION retires older reports.
3. Its ledger head is the hash of the local event at its `ledger_seq`. Events after that head are
   not covered by the report.
4. Each result matches the local check event it names: claim, artifact, target, polarity, and the
   Challenge currently registered for that claim and polarity.

Each attested report is also an anchor (S1.3.T4): it records, outside agent-writable storage, the
head of the ledger it judged. With `latest`, verify fetches every attested report for this ledger
from the repository's successful runs, and the local ledger must extend each one. A report for this
ledger whose head is not in it means events it covered were changed or deleted: that is reported as
an anchor violation, not dropped as a note. Events after the newest anchor are not covered.

What this trusts: GitHub's attestation service and branch protection on `main`, which is what makes
the workflow file reviewed. Branch protection is a repository setting, not code, and nothing here
can check it. Anchors last as long as their run's artifact: deleting runs, or artifact expiry,
removes them (RISK-023).
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from .events import validate_event
from .judge import FORMAT, JUDGE_VERSION, PERMITTED_AXIOMS, JudgeError, ledger_path, load_challenges, pins
from .ledger import Ledger

WORKFLOW = ".github/workflows/authoritative.yml"
REPORT_ARTIFACT = "judge-report"
RUN_LIMIT = 1000
SOURCE_REF = "refs/heads/main"
_REPO = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_RESULT_FIELDS = ("seq", "claim", "artifact", "target_decl", "polarity", "challenge_hash", "result")

Runner = Callable[..., subprocess.CompletedProcess]


def attestation_command(path: Path, repo: str) -> list[str]:
    return ["gh", "attestation", "verify", str(path), "--repo", repo,
            "--signer-workflow", f"{repo}/{WORKFLOW}", "--source-ref", SOURCE_REF,
            "--deny-self-hosted-runners", "--format", "json"]


def check_attestation(content: bytes, repo: str, run: Runner = subprocess.run) -> str | None:
    """None if the attestation verifies for exactly these bytes; otherwise the reason."""
    if not _REPO.fullmatch(repo) or ".." in repo:
        return f"not a repository name: {repo!r}"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "judge-report.json"
        path.write_bytes(content)
        try:
            proc = run(attestation_command(path, repo), capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired) as error:
            return f"could not run gh attestation verify: {error}"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return "attestation did not verify" + (f": {detail[-1]}" if detail else "")
    return None


def _shape_problem(report: object) -> str | None:
    if not isinstance(report, dict):
        return "report is not an object"
    if report.get("format") != FORMAT:
        return f"report format is not {FORMAT}"
    if type(report.get("judge_version")) is not int or report["judge_version"] != JUDGE_VERSION:
        return f"report is from judge version {report.get('judge_version')!r}, not {JUDGE_VERSION}"
    if report.get("permitted_axioms") != PERMITTED_AXIOMS or report.get("definition_names") != []:
        return "report's permitted axioms or definition names differ from this judge's"
    if report.get("sandboxed") is not True:
        return "report does not say the comparator ran sandboxed"
    pin = pins()
    if report.get("toolchain") != pin["toolchain"] or report.get("mathlib_rev") != pin["mathlib_rev"]:
        return "report pins differ from this checker's"
    if not isinstance(report.get("ledger_path"), str):
        return "report does not name its ledger"
    if not isinstance(report.get("ledger_genesis"), str) or not _HEX64.fullmatch(report["ledger_genesis"]):
        return "report ledger_genesis is not a hash"
    seq = report.get("ledger_seq")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        return "report ledger_seq is not a non-negative integer"
    if not isinstance(report.get("ledger_head"), str) or not _HEX64.fullmatch(report["ledger_head"]):
        return "report ledger_head is not a hash"
    if not isinstance(report.get("results"), list):
        return "report results is not a list"
    return None


def tier_results(content: bytes, ledger: Ledger) -> tuple[list[dict], list[str]]:
    """Results that match the local ledger, and a note for each one that does not."""
    try:
        report = json.loads(content)
    except ValueError:
        return [], ["report is not JSON"]
    problem = _shape_problem(report)
    if problem:
        return [], [problem]
    # The head's hash covers earlier events only through the chain, so the chain must hold.
    if ledger.verify().errors:
        return [], ["the local ledger does not verify, so the report's head cannot vouch for it"]
    events = ledger.read()
    seq = report["ledger_seq"]
    if seq >= len(events) or Ledger.event_hash(events[seq]) != report["ledger_head"]:
        return [], [f"report's ledger head (event {seq}) is not in this ledger"]
    judged: list[dict] = []
    notes: list[str] = []
    try:
        challenges: dict | None = load_challenges(ledger)
    except (JudgeError, ValueError, OSError) as error:
        challenges = None
        notes.append(f"the registered Challenges cannot be read: {error}; only rejections are kept")
    for result in report["results"]:
        if not isinstance(result, dict) or any(f not in result for f in _RESULT_FIELDS):
            notes.append("ignored a malformed result")
            continue
        where = result["seq"]
        if isinstance(where, bool) or not isinstance(where, int) or not 0 <= where <= seq:
            notes.append(f"ignored a result for event {where!r}: not covered by the report's head")
            continue
        event = events[where]
        if not isinstance(event, dict) or event.get("kind") != "check" or validate_event(event):
            notes.append(f"ignored a result for event {where}: not a valid check event")
            continue
        data = event["data"]
        local = (event["claim"], data["artifact"], data["target_decl"], data["polarity"])
        claimed = (result["claim"], result["artifact"], result["target_decl"], result["polarity"])
        if local != claimed:
            notes.append(f"ignored a result for event {where}: it names a different check")
            continue
        if result["result"] not in ("pass", "fail"):
            notes.append(f"event {where}: the judge could not decide ({result['result']})")
            continue
        # The Challenge registry is outside the chain, so changing it may drop a pass but never a fail.
        current = None if challenges is None else challenges.get(event["claim"], {}).get(data["polarity"])
        if current != result["challenge_hash"]:
            if result["result"] == "pass":
                notes.append(f"ignored a pass for event {where}: its Challenge is not the one registered now")
                continue
            notes.append(f"kept a rejection for event {where} although its Challenge is not the one registered now")
        judged.append({"claim": event["claim"], "seq": where, "artifact": data["artifact"],
                       "target_decl": data["target_decl"],
                       "polarity": data["polarity"], "challenge_hash": result["challenge_hash"],
                       "result": result["result"]})
    return judged, notes


def anchors_ok(report: dict, ledger: Ledger) -> bool:
    """Whether the local ledger verifies and holds the report's head at its sequence number."""
    if ledger.verify().errors:
        return False
    events = ledger.read()
    seq = report["ledger_seq"]
    return seq < len(events) and Ledger.event_hash(events[seq]) == report["ledger_head"]


def fetch_reports(repo: str, run: Runner = subprocess.run) -> tuple[list[tuple[str, bytes]], list[str]]:
    """The judge report of every successful authoritative run on main: ([(run id, bytes)], notes)."""
    if not _REPO.fullmatch(repo) or ".." in repo:
        return [], [f"not a repository name: {repo!r}"]
    listing = ["gh", "run", "list", "--repo", repo, "--workflow", Path(WORKFLOW).name, "--branch", "main",
               "--status", "success", "--json", "databaseId", "--limit", str(RUN_LIMIT)]
    try:
        proc = run(listing, capture_output=True, text=True, timeout=300)
        ids = [str(item["databaseId"]) for item in json.loads(proc.stdout)] if proc.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError) as error:
        return [], [f"could not list the authoritative runs: {error}"]
    if ids is None:
        return [], ["could not list the authoritative runs: " + (proc.stderr or "").strip()[-200:]]
    notes = [f"listed {RUN_LIMIT} runs, the most gh returns: older anchors were not checked"] if len(ids) >= RUN_LIMIT else []
    reports: list[tuple[str, bytes]] = []
    for run_id in ids:
        if not run_id.isdigit():
            continue
        with tempfile.TemporaryDirectory() as tmp:
            command = ["gh", "run", "download", run_id, "--repo", repo, "-n", REPORT_ARTIFACT, "-D", tmp]
            try:
                proc = run(command, capture_output=True, text=True, timeout=300)
                content = (Path(tmp) / "judge-report.json").read_bytes() if proc.returncode == 0 else None
            except (OSError, subprocess.TimeoutExpired) as error:
                content, proc = None, None
                notes.append(f"run {run_id}: could not download its report: {error}")
        if content is None:
            if proc is not None:
                notes.append(f"run {run_id}: no judge report to download (expired or deleted)")
            continue
        reports.append((run_id, content))
    return reports, notes


def load_authoritative(source: str | Path, repo: str, ledger: Ledger, path: str,
                       run: Runner = subprocess.run) -> dict:
    """Verify, anchor and match judge reports for the ledger at repo-relative `path`.

    `source` is a report file, or "latest" for every attested report of this ledger in `repo`.
    Returns {judged, notes, anchors, violations, newest}. Only reports naming this path are anchors
    and supply results; one sharing only the first event must still be extended. No anchor means
    the caller must fail closed.
    """
    notes: list[str] = []
    if str(source) == "latest":
        candidates, notes = fetch_reports(repo, run)
    else:
        try:
            candidates = [(str(source), Path(source).read_bytes())]
        except OSError as error:
            return {"judged": [], "notes": [f"judge report ignored: cannot read it: {error}"], "anchors": [], "violations": []}
    want = ledger_path(path)
    try:
        events = ledger.read()
        genesis = Ledger.event_hash(events[0]) if events else None
    except Exception as error:  # an unreadable ledger has no genesis; the chain check reports it
        genesis, events = None, []
        notes.append(f"cannot read this ledger's first event: {type(error).__name__}")
    if str(source) != "latest":
        notes.append("a single report file: earlier anchors were not checked; use `latest` for that")
    anchors: list[tuple[dict, bytes, str]] = []
    sources: list[tuple[tuple, dict, bytes, str]] = []
    violations: list[str] = []
    # gh lists runs newest first, so a lower position is a later run.
    for position, (where, content) in enumerate(candidates):
        reason = check_attestation(content, repo, run)
        if reason:
            notes.append(f"{where}: judge report ignored: {reason}")
            continue
        try:
            report = json.loads(content)
        except ValueError:
            notes.append(f"{where}: judge report ignored: not JSON")
            continue
        problem = _shape_problem(report)
        if problem:
            notes.append(f"{where}: judge report ignored: {problem}")
            continue
        # A report for this path anchors the ledger and supplies results. One that shares only the
        # first event (a copy or a graft) adds an obligation but supplies nothing and covers nothing.
        by_path = ledger_path(report["ledger_path"]) == want
        if not by_path and report["ledger_genesis"] != genesis:
            if str(source) != "latest":
                notes.append(f"{where}: judge report is for ledger {report['ledger_path']!r}, not {want!r}")
            continue
        if not anchors_ok(report, ledger):
            hint = "" if by_path else (f" (it is for {report['ledger_path']!r} and shares this ledger's first event;"
                                       " a diverged copy also shows this)")
            violations.append(f"{where}: this ledger does not extend the anchored head, event {report['ledger_seq']} "
                              f"{report['ledger_head']}: events it covered were changed or deleted{hint}")
            continue
        # Every report this ledger extends judged these very events, so its results count; only one for
        # this path counts as coverage, so a graft cannot borrow another ledger's anchors.
        sources.append(((report["ledger_seq"], -position), report, content, where))
        if by_path:
            anchors.append((report, content, where))
    if not anchors:
        notes.append(f"no attested judge report for ledger {want!r} anchors it")
        return {"judged": [], "notes": notes, "anchors": [], "violations": violations}
    newest = max(anchors, key=lambda a: a[0]["ledger_seq"])
    judged = _combine(sources, ledger, notes)
    return {"judged": judged, "notes": notes, "violations": violations,
            "anchors": [{"source": w, "ledger_path": r["ledger_path"], "ledger_seq": r["ledger_seq"],
                         "ledger_head": r["ledger_head"]} for r, _, w in anchors],
            "newest": newest[2]}


def _combine(sources: list[tuple[tuple, dict, bytes, str]], ledger: Ledger, notes: list[str]) -> list[dict]:
    """Results from every extended report, per check: those under the Challenge of the newest report
    that decided it (by ledger_seq, then run order). So a newer `error` hides nothing, and a fail is withdrawn only by an attested result
    under a different Challenge. Within one Challenge every result is kept, and a fail beats a pass."""
    groups: dict[tuple, list[tuple[tuple, dict]]] = {}
    for order, report, content, where in sources:
        found, match_notes = tier_results(content, ledger)
        notes.extend(f"{where}: {note}" for note in match_notes)
        for entry in found:
            check = (entry["claim"], entry["seq"], entry["artifact"], entry["target_decl"], entry["polarity"])
            groups.setdefault(check, []).append((order, entry))
    judged: list[dict] = []
    for check, entries in groups.items():
        latest = max(at for at, _ in entries)
        chosen = {e["challenge_hash"] for at, e in entries if at == latest}
        seen: set[str] = set()
        for _, entry in entries:
            key = json.dumps(entry, sort_keys=True)
            if entry["challenge_hash"] not in chosen:
                notes.append(f"event {check[1]}: a {entry['result']} under an earlier Challenge was superseded")
            elif key not in seen:
                seen.add(key)
                judged.append(entry)
    return judged
