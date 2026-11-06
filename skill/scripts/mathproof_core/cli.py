"""Command-line interface for mathproof records and ledger management."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .gate import EnvironmentFailure, record_check
from .ledger import Ledger
from .replay import verify_investigation
from .report import render_report
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


def _cmd_verify(args: argparse.Namespace) -> int:
    _require_initialized_ledger(args.dir)
    result = verify_investigation(args.dir, project=args.project)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for difference in result["differences"]:
            print(f"DIFFERENCE {difference['claim']} (event {difference['seq']}, {difference['kind']}): {difference['detail']}")
        for error in result["environment_errors"]:
            print(f"COULD NOT RE-RUN {error['claim']} (event {error['seq']}): {' '.join(error['detail'].splitlines())}")
        for claim, status in result["statuses"].items():
            print(f"{claim}: {status['headline']}, {status['verdict']}")
        print(f"{'OK' if result['ok'] else 'NOT OK'}: {result['reruns']} checks re-run.")
        for note in result["notes"]:
            print(f"Note: {note}")
    if result["differences"]:
        return 1
    return 2 if result["environment_errors"] else 0


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
    verify.set_defaults(handler=_cmd_verify)

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
