"""IF-event-v1 envelope validation and closed table of status-bearing kinds."""

from __future__ import annotations

import json
import re
from typing import Any

STATUS_BEARING_KINDS: dict[str, tuple[str, ...]] = {
    "claim_created": ("text", "kind"),
    "assumption": ("text", "standing", "origin", "change"),
    "check": ("artifact", "target_decl", "polarity", "result", "report_hash", "pins", "tier"),
    "fidelity": ("statement_hash", "class", "direction", "judge"),
    "informal_proof": ("artifact", "author_context"),
    "informal_audit": ("proof_hash", "result", "auditor"),
    "experiment": ("code_hash", "outcome"),
    "budget_stop": ("reason", "open_items"),
    "abandon": ("reason",),
    "resolution": ("events", "reason", "signature"),
    "retraction": ("target_event", "reason"),
    "statement_frozen": ("artifact",),
    "witness": ("goal", "artifact"),
    "waiver": ("what", "reason", "signature"),
    "audit": ("assumption", "cost_axes"),
    "challenge": ("target", "result", "runner_context"),
    "certificate": ("certificate",),
    "dependency": ("from", "to", "source_hash"),
    "bridge": ("card", "hypothesis", "match"),
}

_ENVELOPE_FIELDS = ("seq", "prev", "ts", "actor", "kind", "claim", "data")
_ACTOR_FIELDS = ("context_id", "role", "kind")
_HEX64_RE = re.compile(r"[0-9a-f]{64}")
_CLAIM_RE = re.compile(r"[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*")

_CHECK_POLARITIES = {"claim", "negation", "step"}
_CHECK_RESULTS = {"pass", "fail"}
_FIDELITY_CLASSES = {"faithful", "instance", "partial", "unfaithful"}
_FIDELITY_DIRECTIONS = {"F=>I", "I=>F"}
_FIDELITY_JUDGES = {
    "none",
    "repo-label",
    "self-declared",
    "runner-labeled",
    "agent-judge",
    "signed-human",
}
_EXPERIMENT_OUTCOMES = {"completed", "timeout", "error"}
_AUDIT_RESULTS = {"no-flaw", "flaw"}

# Derivation compares these fields by value, so a malformed one must be invalid, not a crash.
_HASH_FIELDS = {
    "check": ("artifact", "report_hash"),
    "fidelity": ("statement_hash",),
    "informal_proof": ("artifact",),
    "informal_audit": ("proof_hash",),
    "experiment": ("code_hash",),
    "statement_frozen": ("artifact",),
    "witness": ("artifact",),
}
_LIST_FIELDS = {"experiment": ("violations",), "fidelity": ("rows",), "budget_stop": ("open_items",)}


def _is_one_of(value: Any, allowed: set[str]) -> bool:
    return isinstance(value, str) and value in allowed


def _storable(event: dict) -> bool:
    """Whether the event can be written as UTF-8 JSON. Lone surrogates and extreme depth cannot."""
    try:
        json.dumps(event, ensure_ascii=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError):
        return False
    return True


def is_status_bearing(kind: str) -> bool:
    """Return True if kind is in the closed table of status-bearing kinds."""
    return kind in STATUS_BEARING_KINDS


def validate_event(event: Any) -> list[str]:
    """Validate an IF-event-v1 event dict and return a list of error strings."""
    if not isinstance(event, dict):
        return ["event must be an object"]

    errors: list[str] = []

    if not _storable(event):
        return ["event cannot be stored as UTF-8 JSON"]

    if "status" in event:
        errors.append("top-level status field is forbidden on event")

    for field in _ENVELOPE_FIELDS:
        if field not in event:
            errors.append(f"missing required envelope field: {field}")

    if "seq" in event:
        seq = event["seq"]
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            errors.append("seq must be an integer >= 0")

    if "prev" in event:
        prev = event["prev"]
        if not isinstance(prev, str) or not _HEX64_RE.fullmatch(prev):
            errors.append("prev must be 64 lowercase hex characters")

    if "ts" in event:
        if not isinstance(event["ts"], str):
            errors.append("ts must be a string")

    if "actor" in event:
        actor = event["actor"]
        if not isinstance(actor, dict):
            errors.append("actor must be an object")
        else:
            for afield in _ACTOR_FIELDS:
                if afield not in actor or not isinstance(actor[afield], str):
                    errors.append(f"actor.{afield} must be a string")

    kind = event.get("kind")
    if "kind" in event:
        if not isinstance(kind, str) or not kind:
            errors.append("kind must be a non-empty string")

    if "claim" in event:
        claim = event["claim"]
        if claim is not None and (not isinstance(claim, str) or not _CLAIM_RE.fullmatch(claim)):
            errors.append("claim must be null or match <investigation>/<claim> in lowercase")

    if kind == "claim_created" and event.get("claim") is None:
        errors.append("claim_created needs a claim id")

    data = event.get("data")
    if "data" in event:
        if not isinstance(data, dict):
            errors.append("data must be an object")
        else:
            if "status" in data:
                errors.append("status field inside data is forbidden")
            if isinstance(kind, str) and kind in STATUS_BEARING_KINDS:
                for req in STATUS_BEARING_KINDS[kind]:
                    if req not in data:
                        errors.append(f"{kind} missing required data field: {req}")

                for name in _HASH_FIELDS.get(kind, ()):
                    value = data.get(name)
                    if name in data and (not isinstance(value, str) or not _HEX64_RE.fullmatch(value)):
                        errors.append(f"{kind}.{name} must be 64 lowercase hex characters")
                for name in _LIST_FIELDS.get(kind, ()):
                    if name in data and not isinstance(data[name], list):
                        errors.append(f"{kind}.{name} must be a list")

                if kind == "claim_created":
                    text = data.get("text")
                    if not isinstance(text, str) or not text.strip():
                        errors.append("claim_created.text must be non-empty text")

                elif kind == "check":
                    target_decl = data.get("target_decl")
                    if not isinstance(target_decl, str) or not target_decl:
                        errors.append("check.target_decl must be a non-empty string")
                    if not _is_one_of(data.get("polarity"), _CHECK_POLARITIES):
                        errors.append("check.polarity must be claim, negation, or step")
                    if not _is_one_of(data.get("result"), _CHECK_RESULTS):
                        errors.append("check.result must be pass or fail")

                elif kind == "fidelity":
                    scope = data.get("scope_note", "")
                    if not isinstance(scope, str) or len(scope) > 500 or not scope.isprintable():
                        errors.append("fidelity.scope_note must be one line of text, at most 500 characters")
                    if not _is_one_of(data.get("class"), _FIDELITY_CLASSES):
                        errors.append("fidelity.class is not a valid closed value")
                    if not _is_one_of(data.get("direction"), _FIDELITY_DIRECTIONS):
                        errors.append("fidelity.direction must be F=>I or I=>F")
                    judge = data.get("judge")
                    if not _is_one_of(judge, _FIDELITY_JUDGES):
                        errors.append("fidelity.judge is not a valid closed value")
                    if judge != "repo-label" and "rows" not in data:
                        errors.append("fidelity.rows is required unless judge is repo-label")

                elif kind == "informal_audit":
                    if not _is_one_of(data.get("result"), _AUDIT_RESULTS):
                        errors.append("informal_audit.result must be no-flaw or flaw")

                elif kind == "experiment":
                    if not _is_one_of(data.get("outcome"), _EXPERIMENT_OUTCOMES):
                        errors.append("experiment.outcome must be completed, timeout, or error")

    return errors
