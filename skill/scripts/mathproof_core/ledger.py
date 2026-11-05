"""Append-only hash-chained ledger and content-addressed artifact store.

Every line stores its own hash and the hash of the line before it, and must be in canonical form,
so an edit to any line is detected, including the last. This detects accidents and simple edits
only. An agent running as the user can rewrite a whole ledger, and deleting lines from the end is
not detectable until the head is anchored outside the ledger (S1.3.T4).
"""

from __future__ import annotations

import dataclasses
import fcntl
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .events import validate_event

_HEX64_RE = re.compile(r"[0-9a-f]{64}")
_GENESIS_PREV = "0" * 64


class ArtifactCorrupt(Exception):
    """An artifact file's content does not match its SHA-256 digest."""


class TornTail(Exception):
    """The ledger ends in an unterminated line, so it must be recovered before appending."""


class ClaimExists(ValueError):
    """A claim's statement is set once. A revised statement is a new claim."""


@dataclasses.dataclass(frozen=True)
class LedgerError:
    """One error at a 1-based line of events.jsonl."""

    line: int
    message: str


@dataclasses.dataclass(frozen=True)
class VerifyResult:
    """Result of verifying a ledger."""

    ok: bool
    errors: list[LedgerError]
    torn_tail: bool


def _canonical(event: dict[str, Any]) -> bytes:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _split(raw: bytes) -> tuple[list[bytes], bytes]:
    """Split into complete lines and any unterminated tail. Only a newline ends a line."""
    *lines, tail = raw.split(b"\n")
    return lines, tail


class Ledger:
    """Append-only hash-chained event ledger and artifact store."""

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self.directory = Path(directory)
        self.events_path = self.directory / "events.jsonl"
        self.artifacts_dir = self.directory / "artifacts"
        self.lock_path = self.directory / "events.lock"

    @classmethod
    def init(cls, directory: str | os.PathLike[str]) -> "Ledger":
        """Create a new ledger, raising FileExistsError if one exists."""
        ledger = cls(directory)
        ledger.artifacts_dir.mkdir(parents=True, exist_ok=True)
        with ledger.events_path.open("xb") as f:
            os.fsync(f.fileno())
        return ledger

    @staticmethod
    def event_hash(event: dict[str, Any]) -> str:
        """SHA-256 of the event's canonical form, leaving out its own stored hash."""
        body = {k: v for k, v in event.items() if k != "hash"}
        return hashlib.sha256(_canonical(body)).hexdigest()

    @staticmethod
    def artifact_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _raw(self) -> bytes:
        return self.events_path.read_bytes() if self.events_path.exists() else b""

    def _new_event(self, lines: list[bytes], kind: str, claim: str | None, data: dict[str, Any],
                   actor: dict[str, str]) -> tuple[dict[str, Any], bytes]:
        """Build and validate the next event. Nothing is written here."""
        prev = self.event_hash(json.loads(lines[-1])) if lines else _GENESIS_PREV
        event: dict[str, Any] = {
            "seq": len(lines),
            "prev": prev,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "actor": actor,
            "kind": kind,
            "claim": claim,
            "data": data,
        }
        errors = validate_event(event)
        if errors:
            raise ValueError("; ".join(errors))
        event["hash"] = self.event_hash(event)
        return event, _canonical(event) + b"\n"

    def append(self, kind: str, claim: str | None, data: dict[str, Any], actor: dict[str, str]) -> dict[str, Any]:
        """Append a validated event under an exclusive lock, and fsync."""
        with self._exclusive_lock():
            lines, tail = _split(self._raw())
            if tail:
                raise TornTail("events.jsonl ends with an unterminated line")
            existing = [json.loads(line) for line in lines]
            if any(not isinstance(e, dict) for e in existing):
                raise ValueError("ledger has a line that is not an event; run verify")
            if kind == "claim_created" and any(e.get("kind") == kind and e.get("claim") == claim for e in existing):
                raise ClaimExists(f"claim {claim} already exists, and its statement cannot change")
            event, encoded = self._new_event(lines, kind, claim, data, actor)
            with self.events_path.open("ab") as f:
                f.write(encoded)
                f.flush()
                os.fsync(f.fileno())
            return event

    def read(self) -> list[dict[str, Any]]:
        """All complete events in order, ignoring a torn last line."""
        return [json.loads(line) for line in _split(self._raw())[0]]

    def verify(self) -> VerifyResult:
        """Check each line's form, schema, sequence number, own hash, and link to the line before."""
        if not self.events_path.exists():
            return VerifyResult(False, [LedgerError(1, "events.jsonl does not exist")], False)

        def broken(line: int, message: str) -> VerifyResult:
            return VerifyResult(False, [LedgerError(line, message)], False)

        lines, tail = _split(self._raw())
        expected_prev = _GENESIS_PREV
        for index, raw_line in enumerate(lines):
            line = index + 1
            try:
                event = json.loads(raw_line)
                errors = validate_event(event)
                if errors:
                    return broken(line, "; ".join(errors))
                if _canonical(event) != raw_line:
                    return broken(line, "line is not in canonical form")
            except (ValueError, RecursionError) as error:
                return broken(line, f"unreadable line: {error}")
            if event["seq"] != index:
                return broken(line, f"seq mismatch: expected {index}, got {event['seq']}")
            if event["prev"] != expected_prev:
                return broken(line, "link to the previous line does not match")
            if event.get("hash") != self.event_hash(event):
                return broken(line, "line does not match its own hash")
            expected_prev = event["hash"]
        if tail:
            return VerifyResult(False, [LedgerError(len(lines) + 1, "torn tail: missing trailing newline")], True)
        return VerifyResult(True, [], False)

    def recover_torn_tail(self, actor: dict[str, str]) -> dict[str, Any]:
        """Replace a torn last line with a recovery event holding its text, in one atomic step."""
        with self._exclusive_lock():
            status = self.verify()
            if not status.torn_tail or len(status.errors) != 1:
                raise ValueError("ledger does not have a clean torn tail to recover")
            lines, tail = _split(self._raw())
            event, encoded = self._new_event(lines, "ledger_recovery", None,
                                             {"discarded": tail.decode("utf-8", errors="replace")}, actor)
            prefix = b"".join(line + b"\n" for line in lines)
            real_path = self.events_path.resolve()
            fd, tmp = tempfile.mkstemp(dir=real_path.parent, prefix=".events.")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(prefix + encoded)
                    f.flush()
                    os.fchmod(f.fileno(), real_path.stat().st_mode & 0o777)
                    os.fsync(f.fileno())
                os.replace(tmp, real_path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
            return event

    def put_artifact(self, content: bytes) -> str:
        """Store bytes by SHA-256, replacing any corrupt copy, and return the digest."""
        if not isinstance(content, (bytes, bytearray, memoryview)):
            raise TypeError("artifact content must be bytes")
        raw = bytes(content)
        digest = self.artifact_hash(raw)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        target = self.artifacts_dir / digest
        if target.exists() and self.artifact_hash(target.read_bytes()) == digest:
            return digest
        fd, tmp = tempfile.mkstemp(dir=self.artifacts_dir, prefix=".tmp.")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
                f.flush()
                os.fchmod(f.fileno(), self.events_path.stat().st_mode & 0o777)
                os.fsync(f.fileno())
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return digest

    def get_artifact(self, digest: str) -> bytes:
        """Read an artifact by its digest, raising ArtifactCorrupt if it no longer matches."""
        if not isinstance(digest, str) or not _HEX64_RE.fullmatch(digest):
            raise ValueError("digest must be 64 lowercase hex characters")
        target = self.artifacts_dir / digest
        if not target.exists():
            raise FileNotFoundError(f"artifact not found: {digest}")
        content = target.read_bytes()
        if self.artifact_hash(content) != digest:
            raise ArtifactCorrupt(f"artifact {digest} does not match its digest")
        return content
