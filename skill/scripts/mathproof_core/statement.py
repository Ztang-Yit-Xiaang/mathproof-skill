"""Immutable statements and the comparator Challenge generated from them (S2.2.T1).

A statement (IF-statement-v1) is a small canonical JSON artifact: the claim it belongs to, a theorem
name, a preamble of local definitions, and the proposition. It is recorded once per claim by a
`statement_frozen` event and never changes; a revision is a new claim that names the old one in
`revises`, so the old claim keeps its evidence and judgments.

The Challenge is generated, never written by hand: the preamble, then `NAME : (PROP)` and
`NAME_negation : ¬ (PROP)`, both proved by `sorry`. The preamble is untrusted code, so two
defenses stand between it and a judgment:

1. `build` refuses text that can change how Lean reads later commands: commands such as `macro`,
   `notation`, `set_option`, `variable`, `namespace`, `run_cmd`, attributes, and `#` commands, and a
   proposition containing `:=`. This is a word list, so it is a first layer only.
2. The binding check (`lean_binding.lean`) is a fixed Lean program that loads the compiled Challenge
   at run time with `importModules`, extensions off, so nothing the statement defines can change
   how the check is parsed or run. It requires `NAME` and `NAME_negation` to be root theorems of
   the Challenge declared on the generated lines, and the negation's type to be exactly `Not`
   applied to the claim's type. Then `lean_audit.lean statements` prints the claim's type without
   the Challenge's own notation, and every definition of the Challenge that the type reaches, for
   the person who reads the statement. The `statement` command and the authoritative judge both
   run these; the judge's run is the one that counts, and its report carries what was printed.

`lake comparator` follows every constant the target theorem's type reaches and compares it in full,
value included, between the Challenge and the Solution. So a Solution that changes a local
definition under the same name, or proves a weaker statement, fails. `definition_names` stays
empty: in the comparator it marks definition holes, whose values the Solution may choose freely.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from .events import validate_event
from .ledger import ArtifactCorrupt, Ledger

FORMAT = "IF-statement-v1"
NEGATION_SUFFIX = "_negation"
BINDING_DRIVER = Path(__file__).resolve().parents[1] / "lean_binding.lean"
AUDIT_DRIVER = Path(__file__).resolve().parents[1] / "lean_audit.lean"
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")
_IMPORT = re.compile(r"^\s*import\b", re.M)
# A preamble is a list of these commands. Each starts at column 0; everything else is indented.
_COMMAND = re.compile(r"(?:(?:noncomputable|private|protected)\s+)*(?:def|theorem|lemma|abbrev|structure|"
                      r"inductive|class|instance)(?![\w.'])|/--|--|-/")
_OPEN = re.compile(r"open(?:\s+[A-Za-z_][\w.']*)+\s*")
# Words that can change how Lean reads or elaborates what follows, or run code while it elaborates.
# `by` is refused too: a tactic can elaborate differently on each compile (a randomized tactic), and
# the judge prints the statement from one compile while the comparator checks another.
# This is a first layer only: the judge also compiles the Challenge in a sandbox, and the binding check
# loads it with its extensions off.
_FORBIDDEN = re.compile(
    r"(?<![\w.'])(?:macro|macro_rules|syntax|declare_syntax_cat|elab|elab_rules|notation|notation3|infix|infixl|"
    r"infixr|prefix|postfix|set_option|attribute|variable|include|omit|namespace|section|end|local|scoped|"
    r"initialize|builtin_initialize|unsafe|implemented_by|extern|export|universe|run_cmd|run_meta|run_tac|"
    r"run_elab|by_elab|mutual|opaque|axiom|simproc|dsimproc|simproc_decl|native_decide|binder_predicate|"
    r"unif_hint|renaming|hiding|add_aesop_rules|declare_aesop_rule_sets|unsafeBaseIO|unsafeIO|unsafeEIO|"
    r"ofReduceBool|IO|EIO|BaseIO|MetaM|TacticM|CoreM|CommandElabM|TermElabM|Lean|Elab|Meta|"
    r"register_\w+|declare_\w+|by)(?![\w.'!?])|(?<![\w.'])(?:Lean|IO)\.|@\[|(?<![\w.'])#[A-Za-z]|eval%|elab%|«")


class StatementError(Exception):
    """The statement cannot be recorded or used."""


def _printable(text: str) -> bool:
    return all(ch in "\n\t" or unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co", "Cn") for ch in text)


def build(claim: str, name: str, prop: str, preamble: str = "", revises: str | None = None) -> dict:
    """The statement record. Raises StatementError on a shape the Challenge cannot be built from."""
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise StatementError("the theorem name must be a plain identifier, with no dots")
    if not isinstance(prop, str) or not prop.strip():
        raise StatementError("the proposition is empty")
    if not isinstance(preamble, str):
        raise StatementError("the preamble must be text")
    if _IMPORT.search(preamble) or _IMPORT.search(prop):
        raise StatementError("the statement cannot import anything; the Challenge imports Mathlib")
    if not _printable(preamble) or not _printable(prop):
        raise StatementError("the statement contains control or formatting characters")
    for line in preamble.splitlines():
        if line[:1].strip() and not (_COMMAND.match(line) or (_OPEN.fullmatch(line.rstrip())
                                                               and "in" not in line.split()[1:])):
            raise StatementError(f"the preamble line {line.strip()[:40]!r} does not start an allowed command; "
                                 "allowed: def, theorem, lemma, abbrev, structure, inductive, class, instance, "
                                 "and `open` of plain names, each at column 0, with continuation lines indented")
    for part, text in (("preamble", preamble), ("proposition", prop)):
        found = _FORBIDDEN.search(text)
        if found:
            raise StatementError(f"the {part} uses `{found.group(0)}`, which can change how Lean reads "
                                 "the Challenge or run code while it compiles")
    if ":=" in prop:
        raise StatementError("the proposition cannot contain `:=`")
    record = {"format": FORMAT, "claim": claim, "name": name, "preamble": preamble.strip("\n"),
              "prop": prop.strip()}
    if revises is not None:
        record["revises"] = revises
    return record


def encode(record: dict) -> bytes:
    return (json.dumps(record, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def decode(content: bytes) -> dict:
    """Parse and re-validate a stored statement. Raises StatementError."""
    try:
        raw = json.loads(content)
    except (ValueError, RecursionError) as error:
        raise StatementError(f"the statement is not JSON: {type(error).__name__}") from None
    if not isinstance(raw, dict) or raw.get("format") != FORMAT:
        raise StatementError(f"the statement is not {FORMAT}")
    extra = set(raw) - {"format", "claim", "name", "preamble", "prop", "revises"}
    if extra or not isinstance(raw.get("claim"), str):
        raise StatementError("the statement has unknown or missing fields")
    record = build(raw["claim"], raw.get("name"), raw.get("prop"), raw.get("preamble", ""), raw.get("revises"))
    if record != raw:
        raise StatementError("the statement is not in canonical form")
    return record


def negation_name(record: dict) -> str:
    return record["name"] + NEGATION_SUFFIX


def target(record: dict, polarity: str) -> str:
    """The declaration a check of this polarity must prove."""
    return record["name"] if polarity == "claim" else negation_name(record)


def _parts(record: dict) -> tuple[str, str, str]:
    preamble = "import Mathlib\n\n" + (record["preamble"] + "\n\n" if record["preamble"] else "")
    claim = f"theorem {record['name']} : ({record['prop']}) := by\n  sorry\n\n"
    negation = f"theorem {negation_name(record)} : ¬ ({record['prop']}) := by\n  sorry\n"
    return preamble, claim, negation


def challenge(record: dict) -> bytes:
    """The Challenge module for both polarities. Deterministic in the record."""
    return "".join(_parts(record)).encode("utf-8")


def lines(record: dict) -> tuple[int, int]:
    """The 1-based lines on which the Challenge declares the claim and negation theorems."""
    preamble, claim, _ = _parts(record)
    first = preamble.count("\n") + 1
    return first, first + claim.count("\n")


def binding_command(record: dict) -> list[str]:
    """Run, in a Lean project where the compiled Challenge is on the search path, the binding check."""
    first, second = lines(record)
    return ["lake", "env", "lean", "--run", str(BINDING_DRIVER), record["name"], negation_name(record),
            str(first), str(second)]


def statements_command(olean: str | Path, out: str | Path) -> list[str]:
    """Print the compiled Challenge's statements without its own notation (lean_audit.lean)."""
    return ["lake", "env", "lean", "--run", str(AUDIT_DRIVER), "statements", str(olean), str(out)]


def read_statements(report: object, record: dict) -> dict:
    """What a person reads: the claim theorem's type, also with every instance and numeric type shown,
    and each definition of the Challenge that it reaches, with its type and body as printed.

    Raises StatementError if the report does not describe the claim theorem.
    """
    declarations = report.get("declarations") if isinstance(report, dict) else None
    context = report.get("statement_context") if isinstance(report, dict) else None
    for entry in declarations if isinstance(declarations, list) else []:
        if not isinstance(entry, dict) or entry.get("name") != record["name"]:
            continue
        shown, explicit, uses = entry.get("type"), entry.get("type_explicit"), entry.get("statement_uses")
        if not (isinstance(shown, str) and isinstance(explicit, str) and isinstance(uses, list)
                and all(isinstance(u, str) for u in uses) and isinstance(context, dict)):
            break
        definitions = {}
        for name in uses:
            item = context.get(name)
            if not isinstance(item, dict) or not all(isinstance(v, str) for v in item.values()):
                raise StatementError(f"the audit did not print the local definition {name}")
            definitions[name] = {k: item[k] for k in ("type", "definition") if k in item}
        return {"type": shown, "type_explicit": explicit, "defined_in_statement": uses, "definitions": definitions}
    raise StatementError("the audit did not print the claim theorem")


def frozen(ledger: Ledger, claim: str) -> list[dict]:
    """The well-formed statement_frozen events of this claim, oldest first. The first one stands."""
    return [e for e in ledger.read() if isinstance(e, dict) and e.get("kind") == "statement_frozen"
            and e.get("claim") == claim and not validate_event(e)]


def load(ledger: Ledger, claim: str) -> dict | None:
    """The claim's statement, or None if it has none. Raises StatementError if it cannot be read."""
    events = frozen(ledger, claim)
    if not events:
        return None
    try:
        record = decode(ledger.get_artifact(events[0]["data"]["artifact"]))
    except (ArtifactCorrupt, FileNotFoundError, ValueError) as error:
        raise StatementError(f"the statement artifact is unavailable: {error}") from None
    if record["claim"] != claim:
        raise StatementError(f"the statement artifact belongs to {record['claim']}, not {claim}")
    data = events[0]["data"]
    if data.get("name") != record["name"] or data.get("revises") != record.get("revises"):
        raise StatementError("the statement event's name or revises does not match its artifact")
    return record


def statement_challenges(ledger: Ledger) -> tuple[dict, dict]:
    """claim -> (record, Challenge bytes) for every claim with a usable statement, and
    claim -> note for every claim whose statement cannot be used."""
    claims = sorted({e["claim"] for e in ledger.read() if isinstance(e, dict)
                     and e.get("kind") == "statement_frozen" and isinstance(e.get("claim"), str)})
    table, broken = {}, {}
    for claim in claims:
        try:
            record = load(ledger, claim)
        except StatementError as error:
            broken[claim] = f"{claim}: {error}"
            continue
        if record is not None:
            table[claim] = (record, challenge(record))
    return table, broken


def _run(cmd: list[str], cwd: Path, env: dict, timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StatementError(f"Lean could not run: {error}") from None
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def compile_challenge(record: dict, project: str | Path, timeout: int = 1800) -> dict:
    """Compile the Challenge in a Lean project, run the binding check, and print its statement.

    Returns {"type", "defined_in_statement"}. Raises StatementError if any step fails.
    """
    project = Path(project).resolve()
    if not project.is_dir():
        raise StatementError(f"Lean project not found: {project}")
    with tempfile.TemporaryDirectory(prefix="mps_statement_") as directory:
        tmp = Path(directory)
        (tmp / "Challenge.lean").write_bytes(challenge(record))
        rc, output = _run(["lake", "env", "lean", f"--root={tmp}", "-o", str(tmp / "Challenge.olean"), "-i",
                           str(tmp / "Challenge.ilean"), str(tmp / "Challenge.lean")], project, dict(os.environ), timeout)
        if rc != 0:
            raise StatementError("the Challenge does not compile: " + _tail(output, directory))
        # Lake puts its own paths first, so the temporary directory cannot shadow an import.
        env = {**os.environ, "LEAN_PATH": str(tmp)}
        rc, output = _run(binding_command(record), project, env, timeout)
        if rc != 0:
            raise StatementError("the binding check failed: " + _tail(output, directory))
        out = tmp / "statements.json"
        rc, output = _run(statements_command(tmp / "Challenge.olean", out), project, env, timeout)
        if rc != 0 or not out.exists():
            raise StatementError("the statement could not be printed: " + _tail(output, directory))
        try:
            report = json.loads(out.read_text(encoding="utf-8"))
        except ValueError as error:
            raise StatementError(f"the statement could not be printed: {error}") from None
    return read_statements(report, record)


def _tail(output: str, directory: str) -> str:
    return " ".join(output.replace(directory, "<tmp>").split())[-800:]


def record_statement(ledger: Ledger, claim: str, name: str, prop: str, preamble: str = "",
                     revises: str | None = None, project: str | Path | None = None,
                     actor: dict | None = None, compiler=compile_challenge) -> tuple[dict, dict]:
    """Freeze a claim's statement. Returns (event, binding). Raises StatementError.

    The claim must exist and have no statement. With `revises`, the old claim must have a statement
    and the new one must differ from it. With `project`, the Challenge must compile and pass the
    binding check first; `binding` is then its type and local constants, and is recorded with the
    event. The judge runs the same check again, and only its result counts.
    """
    events = ledger.read()
    created = {e.get("claim") for e in events if isinstance(e, dict) and e.get("kind") == "claim_created"}
    if claim not in created:
        raise StatementError(f"unknown claim: {claim}; add it with `claim add` first")
    if frozen(ledger, claim):
        raise StatementError(f"{claim} already has a statement; a revision is a new claim with --revises {claim}")
    record = build(claim, name, prop, preamble, revises)
    if revises is not None:
        if revises == claim:
            raise StatementError("a claim cannot revise itself")
        old = load(ledger, revises)
        if old is None:
            raise StatementError(f"{revises} has no statement to revise")
        if (old["name"], old["preamble"], old["prop"]) == (record["name"], record["preamble"], record["prop"]):
            raise StatementError(f"the statement is the same as {revises}'s")
    content = challenge(record)
    binding = compiler(record, project) if project is not None else {"type": None, "defined_in_statement": []}
    digest = ledger.put_artifact(encode(record))
    ledger.put_artifact(content)
    data = {"artifact": digest, "challenge_hash": Ledger.artifact_hash(content), "name": name,
            "elaborated_type": binding["type"], "defined_in_statement": binding["defined_in_statement"]}
    if revises is not None:
        data["revises"] = revises
    actor = actor or {"context_id": "unknown", "role": "cli", "kind": "self-declared"}
    return ledger.append("statement_frozen", claim, data, actor), binding
