"""The authoritative judge: run `lake comparator` on every recorded check and write a judge report.

This runs only in the authoritative workflow (.github/workflows/authoritative.yml), on clean
checkouts of `main`, never on a user's machine: the comparator's sandbox needs Linux `bwrap`.
`authority.py` checks the workflow's attestation before any result reaches status derivation.

The workflow has three stages, so untrusted Lean never shares a machine with anything that matters:

1. `plan` (no Lean): verify the ledger and list one job per recorded check of polarity `claim` or
   `negation` that has a registered Challenge.
2. `judge_case`, once per job, each on a fresh runner with no tokens: run a control case, then
   `lake comparator` with the registered Challenge against the checked artifact. A process that
   escaped the comparator's sandbox could change only this job's result, which the sandbox exists
   to prevent; it cannot reach other jobs, the report, or the signing token.
3. `assemble` (no Lean): recompute the plan from the same checkout, accept each case result only
   if it is the job that index was assigned, and write the IF-judge-report-v0 that is attested.

The judge writes the project files itself, so neither Lean file can change the lakefile, and its
only Lean command is `lake comparator`, which compiles the Solution inside its sandbox (from its
help text; the order of builds inside the comparator has not been verified independently). The
control case tells a broken environment apart from a rejection.

Until S2.2.T1, Challenges are unsigned files that anyone with write access to the ledger can
register, which is why no result here can reach above `judged-unreviewed`.
"""

from __future__ import annotations

import json
import posixpath
import os
import re
import signal
import stat
import subprocess
import time
from pathlib import Path
from typing import Callable

from .events import validate_event
from .ledger import ArtifactCorrupt, Ledger

FORMAT = "IF-judge-report-v0"
# Bump on any change to how the judge or its workflow decides, so older reports stop counting.
JUDGE_VERSION = 2
CASE_FORMAT = "IF-judge-case-v0"
CHALLENGES_FILE = "challenges.json"
PERMITTED_AXIOMS = ["propext", "Quot.sound", "Classical.choice"]
MATHLIB_GIT_URL = "https://github.com/leanprover-community/mathlib4.git"
TIMEOUT_SECONDS = 40 * 60
CHECKER = Path(__file__).resolve().parents[1] / "lean_check.py"
_HEX64 = re.compile(r"[0-9a-f]{64}")
_DECL = re.compile(r"[A-Za-z_][A-Za-z0-9_'.]*")
_JOB_FIELDS = ("seq", "claim", "artifact", "target_decl", "polarity", "challenge_hash")

# The comparator gets only these variables: no tokens, and no Git configuration from the runner.
_ENV_KEEP = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "ELAN_HOME")
_ENV_SET = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}

CONTROL_CHALLENGE = "theorem judge_control : 1 + 1 = 2 := by\n  sorry\n"
CONTROL_SOLUTION = "theorem judge_control : 1 + 1 = 2 := by\n  rfl\n"

Runner = Callable[[list[str], Path, int], dict]


class JudgeError(Exception):
    """The judge could not run. Nothing was written."""


def pins() -> dict:
    """The toolchain and Mathlib revision, read from the checker so there is one source."""
    text = CHECKER.read_text(encoding="utf-8")
    toolchain = re.search(r'^LEAN_TOOLCHAIN = "([^"]+)"', text, re.M).group(1)
    mathlib = re.search(r'^MATHLIB_REV = "([^"]+)"', text, re.M).group(1)
    return {"toolchain": toolchain, "mathlib_rev": mathlib}


def load_challenges(ledger: Ledger) -> dict:
    """claim -> {polarity: artifact hash}. Malformed entries are dropped."""
    path = ledger.directory / CHALLENGES_FILE
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, RecursionError, OSError) as error:
        raise JudgeError(f"{CHALLENGES_FILE} cannot be read: {type(error).__name__}") from None
    if not isinstance(raw, dict):
        raise JudgeError(f"{CHALLENGES_FILE} must be an object")
    table: dict[str, dict[str, str]] = {}
    for claim, entry in raw.items():
        if not isinstance(claim, str) or not isinstance(entry, dict):
            continue
        for polarity in ("claim", "negation"):
            digest = entry.get(polarity)
            if isinstance(digest, str) and _HEX64.fullmatch(digest):
                table.setdefault(claim, {})[polarity] = digest
    return table


def register_challenge(ledger: Ledger, claim: str, polarity: str, content: bytes) -> str:
    """Store a Challenge file and point the claim's polarity at it. Returns its hash."""
    if polarity not in ("claim", "negation"):
        raise ValueError("polarity must be claim or negation")
    digest = ledger.put_artifact(content)
    path = ledger.directory / CHALLENGES_FILE
    raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    raw.setdefault(claim, {})[polarity] = digest
    path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return digest


def head(ledger: Ledger) -> tuple[int, str]:
    """(seq, hash) of the last event. The chain must verify."""
    result = ledger.verify()
    if result.errors:
        raise JudgeError("the ledger does not verify: " + "; ".join(e.message for e in result.errors))
    events = ledger.read()
    if not events:
        raise JudgeError("the ledger has no events")
    return events[-1]["seq"], Ledger.event_hash(events[-1])


def plan_jobs(ledger: Ledger) -> tuple[list[dict], list[str]]:
    """One job per distinct (artifact, target, polarity, Challenge). Returns (jobs, notes)."""
    challenges = load_challenges(ledger)
    jobs: dict[tuple, dict] = {}
    notes: list[str] = []
    for event in ledger.read():
        if not isinstance(event, dict) or event.get("kind") != "check" or validate_event(event):
            continue
        data = event["data"]
        polarity = data["polarity"]
        if polarity not in ("claim", "negation"):
            continue
        if not _DECL.fullmatch(data["target_decl"]):
            notes.append(f"event {event['seq']}: target name is not a plain declaration name")
            continue
        challenge = challenges.get(event["claim"], {}).get(polarity)
        if challenge is None:
            notes.append(f"event {event['seq']}: no Challenge registered for {event['claim']} ({polarity})")
            continue
        key = (event["claim"], data["artifact"], data["target_decl"], polarity, challenge)
        jobs.setdefault(key, {"seq": event["seq"], "claim": event["claim"], "artifact": data["artifact"],
                              "target_decl": data["target_decl"], "polarity": polarity,
                              "challenge_hash": challenge})
    return list(jobs.values()), notes


def plan(ledger_dir: str | Path) -> dict:
    """Stage 1. The ledger head and the jobs. Deterministic for a given checkout."""
    ledger = Ledger(ledger_dir)
    seq, digest = head(ledger)
    jobs, notes = plan_jobs(ledger)
    genesis = Ledger.event_hash(ledger.read()[0])
    return {"ledger_seq": seq, "ledger_head": digest, "ledger_genesis": genesis, "jobs": jobs, "notes": notes}


def lakefile(mathlib_rev: str) -> str:
    return ('name = "judge"\n\n[[require]]\nname = "mathlib"\n'
            f'git = "{MATHLIB_GIT_URL}"\nrev = "{mathlib_rev}"\n\n'
            '[[lean_lib]]\nname = "Challenge"\n\n[[lean_lib]]\nname = "Solution"\n')


def write_case(root: Path, challenge: bytes, solution: bytes, target: str) -> None:
    (root / "Challenge.lean").write_bytes(challenge)
    (root / "Solution.lean").write_bytes(solution)
    config = {"challenge_module": "Challenge", "solution_module": "Solution",
              "theorem_names": [target], "permitted_axioms": PERMITTED_AXIOMS}
    (root / "comparator.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def run(cmd: list[str], cwd: Path, timeout: int) -> dict:
    """Run in a new process group with a minimal environment, and kill the whole group after."""
    start = time.monotonic()
    env = {key: os.environ[key] for key in _ENV_KEEP if key in os.environ} | _ENV_SET
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            env=env, start_new_session=True)
    try:
        output, _ = proc.communicate(timeout=timeout)
        rc: int | str = proc.returncode
    except subprocess.TimeoutExpired:
        rc, output = "timeout", ""
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
    return {"rc": rc, "seconds": round(time.monotonic() - start, 1), "output": (output or "")[-3000:]}


def _outcome(rc: int | str) -> str:
    if rc == 0:
        return "pass"
    if isinstance(rc, int) and not isinstance(rc, bool):
        return "fail"
    return "error"


def prepare_project(root: Path, runner: Runner = run) -> None:
    """Create the Lake project and fetch Mathlib's cache, before any untrusted file exists."""
    pin = pins()
    root.mkdir(parents=True, exist_ok=False)
    (root / "lean-toolchain").write_text(pin["toolchain"] + "\n", encoding="utf-8")
    (root / "lakefile.toml").write_text(lakefile(pin["mathlib_rev"]), encoding="utf-8")
    for cmd in (["lake", "update"], ["lake", "exe", "cache", "get"]):
        outcome = runner(cmd, root, 1800)
        if outcome["rc"] != 0:
            raise JudgeError(f"{' '.join(cmd)} failed: {outcome['output'][-500:]}")


def judge_case(ledger_dir: str | Path, index: int, project: Path, runner: Runner = run,
               timeout: int = TIMEOUT_SECONDS) -> dict:
    """Stage 2, on a fresh runner: judge job `index` of the plan in `project`."""
    ledger = Ledger(ledger_dir)
    jobs = plan(ledger_dir)["jobs"]
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(jobs):
        raise JudgeError(f"no job {index!r}")
    job = jobs[index]
    try:
        challenge, solution = ledger.get_artifact(job["challenge_hash"]), ledger.get_artifact(job["artifact"])
    except (ArtifactCorrupt, FileNotFoundError, ValueError) as error:
        return {"format": CASE_FORMAT, "index": index, **job, "result": "error", "seconds": 0,
                "note": f"artifact unavailable: {error}"}
    prepare_project(project, runner)
    write_case(project, CONTROL_CHALLENGE.encode(), CONTROL_SOLUTION.encode(), "judge_control")
    control = runner(["lake", "comparator"], project, timeout)
    if control["rc"] != 0:
        raise JudgeError(f"the control case did not pass (rc={control['rc']}): {control['output'][-500:]}")
    write_case(project, challenge, solution, job["target_decl"])
    outcome = runner(["lake", "comparator"], project, timeout)
    return {"format": CASE_FORMAT, "index": index, **job, "result": _outcome(outcome["rc"]),
            "seconds": outcome["seconds"]}


def _read_case(cases_dir: Path, index: int) -> object:
    """Case N must be the only entry of its own artifact directory, a regular file named case-N.json.

    Each artifact downloads into its own directory, so one runner's upload cannot replace another's
    file; requiring exactly one regular file there stops an upload that carries extra files.
    """
    directory = cases_dir / f"case-{index}"
    try:
        if not stat.S_ISDIR(directory.lstat().st_mode):
            return None
        entries = list(directory.iterdir())
        path = directory / f"case-{index}.json"
        if entries != [path] or not stat.S_ISREG(path.lstat().st_mode):
            return None
        return json.loads(path.read_bytes())
    except (OSError, ValueError, RecursionError):
        return None


def ledger_path(raw: str | Path) -> str:
    """The repo-relative form of a ledger path, as reports record it and verify compares it."""
    return posixpath.normpath(str(raw).replace("\\", "/"))


def assemble(ledger_dir: str | Path, cases_dir: str | Path) -> dict:
    """Stage 3 (no Lean): the report. A case counts only as the job its index was assigned.

    In the workflow `ledger_dir` is the repo-relative input, so the report names the ledger it judged.
    """
    planned = plan(ledger_dir)
    notes = list(planned["notes"])
    results = []
    for index, job in enumerate(planned["jobs"]):
        case = _read_case(Path(cases_dir), index)
        result = "error"
        seconds = 0
        if not isinstance(case, dict) or case.get("format") != CASE_FORMAT:
            notes.append(f"event {job['seq']}: no usable case result")
        elif any(case.get(field) != job[field] for field in _JOB_FIELDS):
            notes.append(f"event {job['seq']}: the case result names a different job")
        elif case.get("result") not in ("pass", "fail", "error"):
            notes.append(f"event {job['seq']}: the case result is not pass, fail, or error")
        else:
            result = case["result"]
            seconds = case.get("seconds") if isinstance(case.get("seconds"), (int, float)) else 0
        results.append({**job, "result": result, "seconds": seconds})
    return {"format": FORMAT, "judge_version": JUDGE_VERSION, "ledger_path": ledger_path(ledger_dir),
            "ledger_genesis": planned["ledger_genesis"],
            "ledger_seq": planned["ledger_seq"], "ledger_head": planned["ledger_head"],
            **pins(), "sandboxed": True, "permitted_axioms": PERMITTED_AXIOMS, "definition_names": [],
            "results": results, "notes": notes}


def sandbox_works(runner: Runner = run) -> bool:
    """Whether `bwrap` can create a sandbox here. Without it the comparator cannot be trusted."""
    return runner(["bwrap", "--ro-bind", "/", "/", "true"], Path("/"), 60)["rc"] == 0
