"""Human signatures on judgments (S2.3.T3, DEC-008).

A person signs one event of a claim: its frozen statement, a fidelity judgment, an informal audit, a
waiver, or a retraction. The signature is an SSH signature (`ssh-keygen -Y sign`, namespace
`mathproof-review`) made with a key protected by a passphrase that agent sessions never hold. It is
stored as a `signature` event, but the event alone proves nothing: a signature counts only when
`verify --authoritative --signers FILE` checks it against an allowed-signers file kept outside the
ledger.

What is signed (IF-signature-v1) is canonical JSON that names the claim, the hash of its informal
text, the hash of its frozen statement, the signed event's seq and hash, what that event judged, and
the ledger head when it was signed. So a signature copied to another claim, to another event, or to
a ledger where the statement or the informal text differs, does not verify.

Residual risk (RISK-008): a person can still sign what an agent wrote without reading it, and a key
loaded into an ssh-agent that agent sessions reach can sign without its passphrase (`sign` itself
never uses an agent; a hardware key that needs a touch closes this). The `sign` command shows what is
being signed and asks for the claim id; that is a check against mistakes, not a security control.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from .events import validate_event
from .ledger import Ledger

FORMAT = "IF-signature-v1"
NAMESPACE = "mathproof-review"
# The event kinds a person can sign, and the name of the judgment each one is.
SIGNABLE = {"statement_frozen": "statement", "fidelity": "fidelity", "informal_audit": "informal_audit",
            "waiver": "waiver", "retraction": "retraction"}
_IDENTITY = re.compile(r"[A-Za-z0-9._@+-]{1,128}")
_ARMOR = re.compile(r"-----BEGIN SSH SIGNATURE-----\n[A-Za-z0-9+/=\n]+-----END SSH SIGNATURE-----\n?")

Runner = Callable[..., tuple[int, str]]


class SignatureError(Exception):
    """A signature cannot be made or does not verify."""


def _run(cmd: list[str], data: bytes, no_agent: bool = False) -> tuple[int, str]:
    # Signing never goes through an ssh-agent: an agent session could reach a key loaded there, so
    # only the key file and its passphrase can sign.
    env = {k: v for k, v in os.environ.items() if k != "SSH_AUTH_SOCK"} if no_agent else None
    proc = subprocess.run(cmd, input=data, capture_output=True, env=env)
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", "replace")


def _subject(event: dict) -> dict:
    """What the signed event judged, from its own data."""
    data = event["data"]
    keys = {"statement_frozen": ("artifact", "challenge_hash"),
            "fidelity": ("statement_hash", "class", "direction", "scope_note"),
            "informal_audit": ("proof_hash", "result"),
            "waiver": ("what", "reason"),
            "retraction": ("target_event", "reason")}[event["kind"]]
    return {key: data.get(key) for key in keys}


def _context(events: list[dict], claim: str) -> tuple[str | None, str | None]:
    """The hash of the claim's informal text and of its frozen statement, as of these events."""
    created = [e for e in events if e.get("kind") == "claim_created" and e.get("claim") == claim
               and not validate_event(e)]
    frozen = [e for e in events if e.get("kind") == "statement_frozen" and e.get("claim") == claim
              and not validate_event(e)]
    text = Ledger.artifact_hash(created[0]["data"]["text"].encode("utf-8")) if created else None
    return text, (frozen[0]["data"]["artifact"] if frozen else None)


def payload(events: list[dict], seq: int, identity: str, head: int | None = None) -> dict:
    """What `identity`'s signature of event `seq` covers, given the ledger up to `head` (default: the end)."""
    if isinstance(seq, bool) or not isinstance(seq, int) or not 0 <= seq < len(events):
        raise SignatureError(f"no event {seq!r}")
    head = len(events) - 1 if head is None else head
    if isinstance(head, bool) or not isinstance(head, int) or not seq <= head < len(events):
        raise SignatureError("the ledger head must be at or after the signed event")
    event = events[seq]
    if not isinstance(event, dict) or validate_event(event) or event.get("kind") not in SIGNABLE:
        raise SignatureError(f"event {seq} is not a signable judgment ({', '.join(SIGNABLE)})")
    claim = event.get("claim")
    if not isinstance(claim, str):
        raise SignatureError(f"event {seq} belongs to no claim")
    if event["kind"] == "statement_frozen" and _context(events[:seq + 1], claim)[1] != event["data"]["artifact"]:
        raise SignatureError("only a claim's first frozen statement stands, so only it can be signed")
    text, statement = _context(events[:head + 1], claim)
    if text is None:
        raise SignatureError(f"{claim} has no informal text to sign against")
    subject = _subject(event)
    if event["kind"] == "retraction":
        # Name what is retracted, so the signature says what it removes, not only a hash.
        target = next((e for e in events[:seq] if isinstance(e, dict) and Ledger.event_hash(e) == subject["target_event"]), None)
        if target is None or target.get("claim") != claim:
            raise SignatureError("the retraction names no earlier event of this claim")
        subject["target_kind"], subject["target_seq"] = target["kind"], target["seq"]
    return {"format": FORMAT, "namespace": NAMESPACE, "identity": identity, "claim": claim, "informal_text": text,
            "statement": statement, "judgment": SIGNABLE[event["kind"]], "target_seq": seq,
            "target_event": Ledger.event_hash(event), "subject": subject,
            "ledger_seq": head, "ledger_head": Ledger.event_hash(events[head])}


def encode(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sign(ledger: Ledger, seq: int, key: str | Path, identity: str, actor: dict,
         runner: Runner = _run) -> dict:
    """Sign event `seq` with an SSH key and append the signature event. Raises SignatureError."""
    if not _IDENTITY.fullmatch(identity or ""):
        raise SignatureError("the identity must be a short name such as an email address")
    if ledger.verify().errors:
        raise SignatureError("the ledger does not verify; fix it before signing anything in it")
    signed = payload(ledger.read(), seq, identity)
    with tempfile.TemporaryDirectory(prefix="mps_sign_") as directory:
        message = Path(directory, "payload.json")
        message.write_bytes(encode(signed))
        rc, output = runner(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", NAMESPACE, str(message)], b"", True)
        armored = Path(str(message) + ".sig")
        if rc != 0 or not armored.exists():
            raise SignatureError(f"ssh-keygen could not sign: {' '.join(output.split())[-300:]}")
        text = armored.read_text(encoding="ascii")
    return ledger.append("signature", signed["claim"], {"payload": signed, "signature": text, "identity": identity},
                         actor)


def verify(events: list[dict], signers: str | Path, ledger_dir: str | Path | None = None,
           runner: Runner = _run) -> tuple[list[dict], list[str]]:
    """The signatures that verify, as {claim, judgment, target_seq, identity}, and notes on the rest.

    Each one must name an event of this ledger with the same hash, a ledger head that is in this
    ledger, and the claim's current informal text and statement; and `ssh-keygen -Y verify` must
    accept it for its identity under `signers`, which must not be inside the ledger directory.
    """
    signers = Path(signers).resolve()
    if ledger_dir is not None and Path(ledger_dir).resolve() in signers.parents:
        raise SignatureError("the allowed-signers file must be kept outside the ledger")
    if not signers.is_file():
        raise SignatureError(f"allowed-signers file not found: {signers}")
    # A broken chain means events can stand at the wrong seq, so no signature is trusted in it.
    if [e.get("seq") for e in events] != list(range(len(events))) or any(
            i and events[i].get("prev") != Ledger.event_hash(events[i - 1]) for i in range(len(events))):
        return [], ["the ledger's chain is broken, so no signature counts"]
    verified, notes = [], []
    for event in events:
        if not isinstance(event, dict) or event.get("kind") != "signature" or validate_event(event):
            continue
        where = event["seq"]
        data = event["data"]
        signed, armored, identity = data.get("payload"), data.get("signature"), data.get("identity")
        if not (isinstance(signed, dict) and isinstance(armored, str) and _ARMOR.fullmatch(armored)
                and isinstance(identity, str) and _IDENTITY.fullmatch(identity)):
            notes.append(f"signature event {where}: malformed")
            continue
        try:
            target, head = signed.get("target_seq"), signed.get("ledger_seq")
            if isinstance(head, int) and not isinstance(head, bool) and head >= where:
                raise SignatureError("its ledger head is not before the signature")
            expected = payload(events, target, identity, head)
        except SignatureError as error:
            notes.append(f"signature event {where}: {error}")
            continue
        # The claim's informal text and statement must be what they are now, not only at signing.
        if expected != signed or _context(events, expected["claim"]) != (signed["informal_text"], signed["statement"]):
            notes.append(f"signature event {where}: it does not match event {target} of this ledger")
            continue
        if event.get("claim") != signed["claim"]:
            notes.append(f"signature event {where}: filed under another claim")
            continue
        with tempfile.TemporaryDirectory(prefix="mps_verify_") as directory:
            sig = Path(directory, "payload.sig")
            sig.write_text(armored, encoding="ascii")
            rc, output = runner(["ssh-keygen", "-Y", "verify", "-f", str(signers), "-I", identity, "-n", NAMESPACE,
                                 "-s", str(sig)], encode(signed))
        if rc != 0:
            notes.append(f"signature event {where}: ssh-keygen did not verify it for {identity}")
            continue
        verified.append({"claim": signed["claim"], "judgment": signed["judgment"], "target_seq": target,
                         "target_event": signed["target_event"], "identity": identity})
    return verified, notes
