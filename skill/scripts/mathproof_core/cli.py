"""Command-line interface for mathproof records and ledger management."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .experiments import record_experiment, rerun_experiment, run_experiment
from .authority import load_authoritative
from .gate import EnvironmentFailure, record_check
from .ledger import Ledger
from .judge import JudgeError, assemble, judge_case, plan, register_challenge, sandbox_works
from .replay import verify_investigation
from .report import _clean, render_report
from .status import derive_status

GATED_KINDS = frozenset({
    "check",
    "statement_frozen",
    "witness",
    "challenge",
    "certificate",
})

# Kinds with their own route: a claim's statement is set once, and recovery is the ledger's job.
RESERVED_KINDS = frozenset({"claim_created", "ledger_recovery"})


def _actor() -> dict[str, str]:
    return {
        "context_id": os.environ.get("MATHPROOF_CONTEXT_ID", "unknown"),
        "role": "cli",
        "kind": "self-declared",
    }


def _fail(message: str) -> int:
    one_line = " ".join(str(message).splitlines()).strip()
    print(f"error: {one_line}", file=sys.stderr)
    return 1


def _require_initialized_ledger(directory: str | os.PathLike[str]) -> Ledger:
    ledger = Ledger(directory)
    if not ledger.events_path.exists():
        raise FileNotFoundError(f"Ledger not initialized at {ledger.events_path}")
    return ledger


def _cmd_init(args: argparse.Namespace) -> int:
    Ledger.init(args.dir)
    return 0


def _cmd_claim_add(args: argparse.Namespace) -> int:
    ledger = _require_initialized_ledger(args.dir)
    ledger.append(
        kind="claim_created",
        claim=args.id,
        data={"text": args.text, "kind": args.kind},
        actor=_actor(),
    )
    return 0


def _cmd_event_add(args: argparse.Namespace) -> int:
    if args.kind in GATED_KINDS:
        return _fail(
            f"event kind '{args.kind}' cannot be added by hand; only verification gates may record it"
        )
    if args.kind in RESERVED_KINDS:
        return _fail(f"event kind '{args.kind}' cannot be added here; use `claim add` for a new claim")
    ledger = _require_initialized_ledger(args.dir)
    if args.claim is not None and not any(
            e.get("kind") == "claim_created" and e.get("claim") == args.claim for e in ledger.read()):
        return _fail(f"unknown claim: {args.claim}; add it with `claim add` first")
    try:
        parsed_data = json.loads(args.data)
    except Exception as exc:
        return _fail(f"invalid JSON for --data: {exc}")
    if not isinstance(parsed_data, dict):
        return _fail("--data must decode to a JSON object")

    ledger.append(
        kind=args.kind,
        claim=args.claim,
        data=parsed_data,
        actor=_actor(),
    )
    return 0


def _cmd_artifact_add(args: argparse.Namespace) -> int:
    ledger = _require_initialized_ledger(args.dir)
    print(ledger.put_artifact(Path(args.file).read_bytes()))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    ledger = _require_initialized_ledger(args.dir)
    try:
        event = record_check(ledger, args.claim, args.file, args.decl, args.polarity, args.project)
    except (EnvironmentFailure, OSError) as error:
        print(f"environment error, nothing recorded: {' '.join(str(error).splitlines())}", file=sys.stderr)
        return 2
    data = event["data"]
    print(json.dumps({"claim": args.claim, "seq": event["seq"], "result": data["result"], "type": data["type"],
                      "axioms": data["axioms"], "problems": data["problems"]}, ensure_ascii=False, indent=2))
    return 0 if data["result"] == "pass" else 1


def _cmd_status(args: argparse.Namespace) -> int:
    ledger = _require_initialized_ledger(args.dir)
    print(json.dumps(derive_status(ledger.read(), args.claim, {}), ensure_ascii=False, indent=2))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    print(render_report(_require_initialized_ledger(args.dir), args.claim))
    return 0


def _line(text: object) -> str:
    """One line of inert text, so a recorded value cannot pass as a line of this output."""
    return _clean(text).replace("\n", " ")


def _cmd_verify(args: argparse.Namespace) -> int:
    ledger = _require_initialized_ledger(args.dir)
    judged, judge_notes = None, None
    if args.authoritative:
        if not args.repo:
            return _fail("--authoritative needs --repo OWNER/NAME, the repository whose workflow judged it")
        judged, judge_notes = load_authoritative(args.authoritative, args.repo, ledger)
        judge_notes = [f"authoritative: {note}" for note in judge_notes]
        judge_notes.append(f"authoritative: {len(judged)} judge results matched, attested by {args.repo}")
    result = verify_investigation(args.dir, project=args.project, judged=judged, judge_notes=judge_notes)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for difference in result["differences"]:
            print(f"DIFFERENCE {_line(difference['claim'])} (event {difference['seq']}, {difference['kind']}): {_line(difference['detail'])}")
        for error in result["environment_errors"]:
            print(f"COULD NOT RE-RUN {_line(error['claim'])} (event {error['seq']}): {_line(error['detail'])}")
        for claim, status in result["statuses"].items():
            print(f"{_line(claim)}: {status['headline']}, {status['verdict']}")
        print(f"{'OK' if result['ok'] else 'NOT OK'}: {result['reruns']} checks re-run.")
        for note in result["notes"]:
            print(f"Note: {note}")
    if result["differences"]:
        return 1
    return 2 if result["environment_errors"] else 0


def _cmd_challenge_file(args: argparse.Namespace) -> int:
    ledger = _require_initialized_ledger(args.dir)
    if not any(e.get("kind") == "claim_created" and e.get("claim") == args.claim for e in ledger.read()):
        return _fail(f"no claim {args.claim} in this ledger")
    digest = register_challenge(ledger, args.claim, args.polarity, Path(args.file).read_bytes())
    print(digest)
    return 0


def _write_json(path: str, value: object) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _cmd_judge_plan(args: argparse.Namespace) -> int:
    try:
        planned = plan(args.dir)
    except JudgeError as error:
        return _fail(str(error))
    _write_json(args.out, planned)
    print(json.dumps(list(range(len(planned["jobs"])))))
    return 0


def _cmd_judge_case(args: argparse.Namespace) -> int:
    """Authoritative CI only: the comparator's sandbox needs Linux bwrap."""
    if not sandbox_works():
        return _fail("bwrap cannot create a sandbox here; the judge runs only in the authoritative CI job")
    try:
        case = judge_case(args.dir, args.index, Path(args.project))
    except JudgeError as error:
        return _fail(str(error))
    _write_json(args.out, case)
    print(f"{case['claim']} event {case['seq']} ({case['polarity']}): {case['result']} in {case['seconds']}s")
    return 0


def _cmd_judge_assemble(args: argparse.Namespace) -> int:
    try:
        report = assemble(args.dir, args.cases)
    except JudgeError as error:
        return _fail(str(error))
    _write_json(args.out, report)
    for result in report["results"]:
        print(f"{result['claim']} event {result['seq']} ({result['polarity']}): {result['result']}")
    for note in report["notes"]:
        print(f"Note: {note}")
    return 0


def _cmd_experiment_run(args: argparse.Namespace) -> int:
    ledger = _require_initialized_ledger(args.dir)
    try:
        params = json.loads(args.params)
    except Exception as exc:
        return _fail(f"invalid JSON for --params: {exc}")
    if not isinstance(params, dict):
        return _fail("--params must decode to a JSON object")
    if not Path(args.code).is_file():
        return _fail(f"no such code file: {args.code}")
    record = run_experiment(
        args.code,
        language=args.lang,
        seed=args.seed,
        params=params,
        timeout_s=args.timeout,
        memory_mb=args.memory_mb,
    )
    try:
        event = record_experiment(ledger, args.claim, args.code, record, _actor())
    except ValueError as exc:
        return _fail(str(exc))
    print(json.dumps(event, ensure_ascii=False, indent=2))
    return 0


def _cmd_experiment_rerun(args: argparse.Namespace) -> int:
    ledger = _require_initialized_ledger(args.dir)
    events = ledger.read()
    matching = [e for e in events if e.get("seq") == args.seq]
    if not matching:
        return _fail(f"no event with seq {args.seq}")
    event = matching[0]
    if event.get("kind") != "experiment":
        return _fail(f"event {args.seq} is not an experiment event")
    diffs = rerun_experiment(ledger, event)
    for d in diffs:
        print(d)
    return 0 if not diffs else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mathproof", description="Mathproof records CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init DIR
    init_parser = subparsers.add_parser("init", help="Initialize a new ledger directory.")
    init_parser.add_argument("dir", metavar="DIR", help="Ledger directory path.")
    init_parser.set_defaults(handler=_cmd_init)

    # claim ...
    claim_parser = subparsers.add_parser("claim", help="Manage claims.")
    claim_sub = claim_parser.add_subparsers(dest="claim_command", required=True)

    claim_add = claim_sub.add_parser("add", help="Create a new claim in the ledger.")
    claim_add.add_argument("--dir", required=True, metavar="DIR", help="Ledger directory path.")
    claim_add.add_argument("--id", required=True, metavar="INV/CLAIM", help="Claim identifier (INV/CLAIM).")
    claim_add.add_argument("--text", required=True, metavar="T", help="Claim statement text.")
    claim_add.add_argument("--kind", required=True, metavar="K", help="Claim kind (e.g., theorem, lemma).")
    claim_add.set_defaults(handler=_cmd_claim_add)

    # event ...
    event_parser = subparsers.add_parser("event", help="Manage ledger events.")
    event_sub = event_parser.add_subparsers(dest="event_command", required=True)

    event_add = event_sub.add_parser(
        "add",
        help="Append an event to the ledger.",
        description=(
            "Append an event to the ledger. Note: gated kinds (check, statement_frozen, "
            "witness, challenge, certificate) cannot be added by hand because only "
            "verification gates may record them."
        ),
        epilog=(
            "Gated event kinds (check, statement_frozen, witness, challenge, certificate) "
            "cannot be added by hand because only verification gates may record them."
        ),
    )
    event_add.add_argument("--dir", required=True, metavar="DIR", help="Ledger directory path.")
    event_add.add_argument("--claim", default=None, metavar="ID", help="Optional claim identifier.")
    event_add.add_argument(
        "--kind",
        required=True,
        metavar="K",
        help=(
            "Event kind. Kinds check, statement_frozen, witness, challenge, certificate "
            "cannot be added by hand because only verification gates may record them."
        ),
    )
    event_add.add_argument("--data", required=True, metavar="JSON", help="Event payload as a JSON object.")
    event_add.set_defaults(handler=_cmd_event_add)

    # artifact add
    artifact_parser = subparsers.add_parser("artifact", help="Manage stored files.")
    artifact_sub = artifact_parser.add_subparsers(dest="artifact_command", required=True)
    artifact_add = artifact_sub.add_parser("add", help="Store a file and print its hash.")
    artifact_add.add_argument("--dir", required=True, metavar="DIR", help="Ledger directory path.")
    artifact_add.add_argument("file", metavar="FILE", help="File to store.")
    artifact_add.set_defaults(handler=_cmd_artifact_add)

    # check
    check = subparsers.add_parser(
        "check", help="Run the Lean checker on a file and record the result.",
        description="Run the Lean checker on a file and record the result. Exit: 0 pass, 1 fail, 2 could not run.")
    check.add_argument("--dir", required=True, metavar="DIR", help="Ledger directory path.")
    check.add_argument("--claim", required=True, metavar="ID", help="Claim identifier.")
    check.add_argument("--decl", required=True, metavar="NAME", help="Exact full name of the theorem.")
    check.add_argument("--polarity", required=True, choices=("claim", "negation", "step"),
                       help="Whether the theorem is exactly the claim, exactly its negation, or only a step.")
    check.add_argument("--project", required=True, metavar="DIR", help="Lean project with Mathlib.")
    check.add_argument("file", metavar="FILE", help="Lean file.")
    check.set_defaults(handler=_cmd_check)

    # status, report
    for name, handler, text in (("status", _cmd_status, "Print a claim's derived status as JSON."),
                                ("report", _cmd_report, "Print a claim's report as Markdown.")):
        command = subparsers.add_parser(name, help=text)
        command.add_argument("--dir", required=True, metavar="DIR", help="Ledger directory path.")
        command.add_argument("--claim", required=True, metavar="ID", help="Claim identifier.")
        command.set_defaults(handler=handler)

    # verify
    verify = subparsers.add_parser(
        "verify", help="Check the ledger and re-run every check.",
        description="Check the ledger and re-run every check. Exit: 0 clean, 1 a difference, 2 could not re-run.")
    verify.add_argument("dir", metavar="DIR", help="Ledger directory path.")
    verify.add_argument("--project", metavar="DIR", help="Use this Lean project, not the recorded one.")
    verify.add_argument("--json", action="store_true", help="Print a JSON report.")
    verify.add_argument("--authoritative", metavar="REPORT",
                        help="An attested judge report from the authoritative workflow.")
    verify.add_argument("--repo", metavar="OWNER/NAME", help="The repository whose workflow must have attested it.")
    verify.set_defaults(handler=_cmd_verify)

    # challenge-file
    challenge_file = subparsers.add_parser(
        "challenge-file", help="Register the comparator Challenge for a claim (unsigned until S2.2.T1).")
    challenge_file.add_argument("--dir", required=True, metavar="DIR", help="Ledger directory path.")
    challenge_file.add_argument("--claim", required=True, metavar="ID", help="Claim identifier.")
    challenge_file.add_argument("--polarity", required=True, choices=("claim", "negation"),
                                help="Whether the file states the claim or exactly its negation.")
    challenge_file.add_argument("file", metavar="FILE", help="Lean file with the statement, proved by sorry.")
    challenge_file.set_defaults(handler=_cmd_challenge_file)

    # judge plan | case | assemble (authoritative workflow only)
    judge_parser = subparsers.add_parser("judge", help="Authoritative workflow only: the comparator judge's stages.")
    judge_sub = judge_parser.add_subparsers(dest="judge_command", required=True)
    judge_plan = judge_sub.add_parser("plan", help="List the jobs; prints their indices as JSON.")
    judge_plan.add_argument("dir", metavar="DIR", help="Ledger directory path.")
    judge_plan.add_argument("--out", required=True, metavar="FILE", help="Where to write the plan.")
    judge_plan.set_defaults(handler=_cmd_judge_plan)
    judge_case_parser = judge_sub.add_parser("case", help="Judge one job on this runner.")
    judge_case_parser.add_argument("dir", metavar="DIR", help="Ledger directory path.")
    judge_case_parser.add_argument("--index", required=True, type=int, metavar="N", help="Job index from the plan.")
    judge_case_parser.add_argument("--project", required=True, metavar="DIR", help="New directory for the Lake project.")
    judge_case_parser.add_argument("--out", required=True, metavar="FILE", help="Where to write the case result.")
    judge_case_parser.set_defaults(handler=_cmd_judge_case)
    judge_assemble = judge_sub.add_parser("assemble", help="Build the report from case results; runs no Lean.")
    judge_assemble.add_argument("dir", metavar="DIR", help="Ledger directory path.")
    judge_assemble.add_argument("--cases", required=True, metavar="DIR", help="Directory of case-N.json files.")
    judge_assemble.add_argument("--out", required=True, metavar="FILE", help="Where to write the report.")
    judge_assemble.set_defaults(handler=_cmd_judge_assemble)

    # experiment ...
    experiment_parser = subparsers.add_parser("experiment", help="Run and re-run experiments.")
    experiment_sub = experiment_parser.add_subparsers(dest="experiment_command", required=True)

    exp_run = experiment_sub.add_parser("run", help="Run an experiment and record the event.")
    exp_run.add_argument("--dir", required=True, metavar="DIR", help="Ledger directory path.")
    exp_run.add_argument("--claim", required=True, metavar="C", help="Claim identifier.")
    exp_run.add_argument("--code", required=True, metavar="FILE", help="Experiment program file.")
    exp_run.add_argument("--lang", required=True, choices=("python", "r"), help="Experiment language.")
    exp_run.add_argument("--seed", type=int, default=0, metavar="N", help="Integer seed.")
    exp_run.add_argument("--params", default="{}", metavar="JSON", help="Parameters as JSON object.")
    exp_run.add_argument("--timeout", type=float, default=60, metavar="S", help="Timeout in seconds.")
    exp_run.add_argument("--memory-mb", type=int, default=2048, metavar="M", help="Memory limit in MB.")
    exp_run.set_defaults(handler=_cmd_experiment_run)

    exp_rerun = experiment_sub.add_parser("rerun", help="Re-run a recorded experiment event.")
    exp_rerun.add_argument("--dir", required=True, metavar="DIR", help="Ledger directory path.")
    exp_rerun.add_argument("--seq", required=True, type=int, metavar="N", help="Event sequence number.")
    exp_rerun.set_defaults(handler=_cmd_experiment_rerun)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        handler = getattr(args, "handler", None)
        if handler is None:
            parser.print_help(sys.stderr)
            return 2
        return int(handler(args))
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return _fail(str(code))
    except Exception as exc:
        return _fail(str(exc))
