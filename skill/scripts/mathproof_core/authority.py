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

What this trusts: GitHub's attestation service and branch protection on `main`, which is what makes
the workflow file reviewed. Branch protection is a repository setting, not code, and nothing here
can check it.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from .events import validate_event
from .judge import FORMAT, JUDGE_VERSION, PERMITTED_AXIOMS, JudgeError, load_challenges, pins
from .ledger import Ledger

WORKFLOW = ".github/workflows/authoritative.yml"
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
    try:
        challenges = load_challenges(ledger)
    except (JudgeError, ValueError, OSError) as error:
        return [], [f"the registered Challenges cannot be read: {error}"]
    judged: list[dict] = []
    notes: list[str] = []
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
        if challenges.get(event["claim"], {}).get(data["polarity"]) != result["challenge_hash"]:
            notes.append(f"ignored a result for event {where}: its Challenge is not the one registered now")
            continue
        if result["result"] not in ("pass", "fail"):
            notes.append(f"event {where}: the judge could not decide ({result['result']})")
            continue
        judged.append({"claim": event["claim"], "seq": where, "artifact": data["artifact"],
                       "target_decl": data["target_decl"],
                       "polarity": data["polarity"], "challenge_hash": result["challenge_hash"],
                       "result": result["result"]})
    return judged, notes


def load_authoritative(report_path: str | Path, repo: str, ledger: Ledger,
                       run: Runner = subprocess.run) -> tuple[list[dict], list[str]]:
    """Read the report once, verify its attestation, and match it. Returns (env judged, notes)."""
    try:
        content = Path(report_path).read_bytes()
    except OSError as error:
        return [], [f"judge report ignored: cannot read it: {error}"]
    reason = check_attestation(content, repo, run)
    if reason:
        return [], [f"judge report ignored: {reason}"]
    return tier_results(content, ledger)
