"""Command-line interface for mathproof records and ledger management."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .ledger import Ledger

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
