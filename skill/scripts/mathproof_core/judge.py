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

The judge writes the project files itself, so neither Lean file can change the lakefile. Lean runs
only in sandboxes: `lake comparator`, which compiles the Solution inside its own (from its help text;
the order of builds inside the comparator has not been verified independently), and, before the
Solution exists, a bwrap sandbox that compiles the Challenge alone and, for a frozen statement, runs
the binding check (statement.py). The control case tells a broken environment apart from a rejection.

A claim with a frozen statement (statement.py) gets its Challenge generated from that statement,
and a check counts only if it targets the statement's theorem (claim) or its negation theorem. A claim
without one may still use a hand-registered Challenge in challenges.json. Until statements are
signed (S2.3.T3), no result here can reach above `judged-unreviewed`.
"""

from __future__ import annotations

import json
import posixpath
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import time
from pathlib import Path
from typing import Callable

from .events import validate_event
from .ledger import ArtifactCorrupt, Ledger
from . import statement as statements

FORMAT = "IF-judge-report-v0"
# Bump on any change to how the judge or its workflow decides, so older reports stop counting.
JUDGE_VERSION = 3
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


def load_challenges(ledger: Ledger, notes: list[str] | None = None) -> dict:
    """claim -> {polarity: Challenge hash}. A frozen statement's generated Challenge replaces any
    registered one; a claim whose statement cannot be read gets none. Malformed entries are dropped."""
    table = _registered(ledger)
    generated, broken = statements.statement_challenges(ledger)
    for claim, (_, content) in generated.items():
        if claim in table and notes is not None:
            notes.append(f"{claim}: the frozen statement replaces its entry in {CHALLENGES_FILE}")
        digest = Ledger.artifact_hash(content)
        table[claim] = {"claim": digest, "negation": digest}
    for claim, note in broken.items():
        table.pop(claim, None)
        if notes is not None:
            notes.append(note)
    return table


def challenge_content(ledger: Ledger, claim: str, digest: str) -> bytes:
    """The Challenge bytes for a planned job: generated from the statement if the claim has one."""
    record = statements.load(ledger, claim)
    if record is not None:
        content = statements.challenge(record)
        if Ledger.artifact_hash(content) != digest:
            raise ValueError("the Challenge no longer matches the claim's statement")
        return content
    return ledger.get_artifact(digest)


def _registered(ledger: Ledger) -> dict:
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
    notes: list[str] = []
    challenges = load_challenges(ledger, notes)
    records = {claim: record for claim, (record, _) in statements.statement_challenges(ledger)[0].items()}
    jobs: dict[tuple, dict] = {}
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
        record = records.get(event["claim"])
        if record is not None and data["target_decl"] != statements.target(record, polarity):
            notes.append(f"event {event['seq']}: a {polarity} check must target "
                         f"{statements.target(record, polarity)}, the statement's theorem")
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


SANDBOX_STEP_EXIT = 10


def sandboxed(steps: list[list[str]], project: Path, writable: list[Path],
              read_only: list[tuple[Path, Path]] = ()) -> list[str]:
    """One bwrap command that runs `steps` in order in `project`. Step k failing exits 10 + k.

    Everything is read-only except `writable` and a private /tmp; each (source, target) in
    `read_only` is mounted read-only at target, after the writable mounts. There is no network, and
    the sandbox dies with its parent, so nothing it starts outlives it.
    """
    script = "; ".join(f"{shlex.join(step)} || exit {SANDBOX_STEP_EXIT + k}" for k, step in enumerate(steps))
    binds = [arg for path in writable for arg in ("--bind", str(path), str(path))]
    binds += [arg for source, target in read_only for arg in ("--ro-bind", str(source), str(target))]
    return ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", *binds,
            "--unshare-all", "--die-with-parent", "--new-session", "--chdir", str(project), "--",
            "sh", "-c", script]


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
        challenge = challenge_content(ledger, job["claim"], job["challenge_hash"])
        solution = ledger.get_artifact(job["artifact"])
    except (ArtifactCorrupt, FileNotFoundError, ValueError, statements.StatementError) as error:
        return {"format": CASE_FORMAT, "index": index, **job, "result": "error", "seconds": 0,
                "note": f"artifact unavailable: {error}"}
    prepare_project(project, runner)
    write_case(project, CONTROL_CHALLENGE.encode(), CONTROL_SOLUTION.encode(), "judge_control")
    control = runner(["lake", "comparator"], project, timeout)
    if control["rc"] != 0:
        raise JudgeError(f"the control case did not pass (rc={control['rc']}): {control['output'][-500:]}")
    # Before the Solution exists, compile the Challenge alone and, for a frozen statement, run the
    # binding check and print the statement. A Challenge is Lean code, and elaborating it can run code,
    # so all of this runs in a bwrap sandbox with no network, in a scratch copy of the project that is
    # deleted afterwards: it can write only that copy and an output directory, and Mathlib's packages
    # are mounted read-only. Nothing it writes can reach the comparator's project. A Challenge that
    # fails here is an error, not a rejection of the proof.
    record = statements.load(ledger, job["claim"])
    scratch = project.parent / f"{project.name}-challenge"
    out_dir = project.parent / f"{project.name}-statement"
    scratch.mkdir()
    out_dir.mkdir()
    for name in ("lean-toolchain", "lakefile.toml", "lake-manifest.json"):
        if (project / name).exists():
            shutil.copyfile(project / name, scratch / name)
    (scratch / "Challenge.lean").write_bytes(challenge)
    (scratch / ".lake" / "packages").mkdir(parents=True)
    out = out_dir / "statements.json"
    steps = [["lake", "build", "Challenge"]]
    if record is not None:
        olean = scratch / ".lake" / "build" / "lib" / "lean" / "Challenge.olean"
        steps += [statements.binding_command(record), statements.statements_command(olean, out)]
    checked = runner(sandboxed(steps, scratch, [scratch, out_dir],
                               read_only=[(project / ".lake" / "packages", scratch / ".lake" / "packages")]),
                     scratch, timeout)
    shutil.rmtree(scratch)
    binding = None
    if checked["rc"] == 0 and record is not None:
        try:
            raw = out.read_bytes() if out.stat().st_size <= 1_000_000 else b""
            binding = statements.read_statements(json.loads(raw), record)
        except (OSError, ValueError, RecursionError, statements.StatementError):
            binding = None
    shutil.rmtree(out_dir)
    if checked["rc"] != 0 or (record is not None and not _binding_ok(binding)):
        notes = {SANDBOX_STEP_EXIT: "the Challenge does not compile", SANDBOX_STEP_EXIT + 1: "the statement binding check failed"}
        note = notes.get(checked["rc"], "the statement could not be printed" if record is not None and checked["rc"] in (0, SANDBOX_STEP_EXIT + 2)
                         else f"the Challenge step failed (rc={checked['rc']})")
        # The end of the sandbox's output, as inert printable text, so a failure can be diagnosed.
        tail = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in str(checked.get("output", "")))[-400:]
        return {"format": CASE_FORMAT, "index": index, **job, "result": "error", "seconds": checked["seconds"],
                "note": note, "output": " ".join(tail.split())}
    write_case(project, challenge, solution, job["target_decl"])
    outcome = runner(["lake", "comparator"], project, timeout)
    case = {"format": CASE_FORMAT, "index": index, **job, "result": _outcome(outcome["rc"]),
            "seconds": outcome["seconds"]}
    if binding is not None:
        case["binding"] = binding
    return case


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
    bound = set(statements.statement_challenges(Ledger(ledger_dir))[0])
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
        entry = {**job, "result": result, "seconds": seconds}
        if result != "error" and _binding_ok(case.get("binding")):
            entry["binding"] = {key: case["binding"][key] for key in
                                ("type", "type_explicit", "defined_in_statement", "definitions")}
        elif result != "error" and job["claim"] in bound:
            # A frozen statement's result counts only with the statement as Lean printed it.
            entry["result"] = "error"
            notes.append(f"event {job['seq']}: the case result has no printed statement")
        results.append(entry)
    return {"format": FORMAT, "judge_version": JUDGE_VERSION, "ledger_path": ledger_path(ledger_dir),
            "ledger_genesis": planned["ledger_genesis"],
            "ledger_seq": planned["ledger_seq"], "ledger_head": planned["ledger_head"],
            **pins(), "sandboxed": True, "permitted_axioms": PERMITTED_AXIOMS, "definition_names": [],
            "results": results, "notes": notes}


def _binding_ok(binding: object) -> bool:
    """A binding is the statement as printed: two types, local names, and their printed definitions."""
    def text(value: object) -> bool:
        return isinstance(value, str) and len(value) <= 20000
    if not isinstance(binding, dict) or not (text(binding.get("type")) and text(binding.get("type_explicit"))):
        return False
    names, definitions = binding.get("defined_in_statement"), binding.get("definitions")
    return (isinstance(names, list) and len(names) <= 1000 and all(text(n) for n in names)
            and isinstance(definitions, dict) and set(definitions) == set(names)
            and all(isinstance(d, dict) and set(d) <= {"type", "definition"} and all(text(v) for v in d.values())
                    for d in definitions.values()))


def sandbox_works(runner: Runner = run) -> bool:
    """Whether `bwrap` can create a sandbox here. Without it the comparator cannot be trusted."""
    return runner(["bwrap", "--ro-bind", "/", "/", "true"], Path("/"), 60)["rc"] == 0
