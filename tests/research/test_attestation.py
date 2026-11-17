"""S2.3.T3: human signatures on judgments, verified against keys kept outside the ledger.

These tests make real SSH keys with `ssh-keygen` in a temporary directory and sign with them, so
they exercise the same `ssh-keygen -Y sign` and `-Y verify` the commands use.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _paths import ROOT
from mathproof_core import signature as sig
from mathproof_core import statement as st
from mathproof_core.ledger import Ledger
from mathproof_core.status import HUMAN_AUDITED, derive_status

ACTOR = {"context_id": "t", "role": "cli", "kind": "self-declared"}
GATE = {"context_id": "t", "role": "gate", "kind": "runner"}
CLAIM, OTHER = "inv/c1", "inv/c2"
H = "c" * 64


def keygen(directory: Path, name: str) -> tuple[Path, str]:
    key = directory / name
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", name, "-f", str(key)], check=True)
    return key, (directory / f"{name}.pub").read_text().strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.dir = root / "ledger"
        self.ledger = Ledger.init(self.dir)
        self.keys = root / "keys"
        self.keys.mkdir()
        self.alice, alice_pub = keygen(self.keys, "alice")
        self.mallory, _ = keygen(self.keys, "mallory")
        self.signers = root / "allowed_signers"
        self.signers.write_text(f'alice@example.com namespaces="{sig.NAMESPACE}" {alice_pub}\n')
        for claim in (CLAIM, OTHER):
            self.ledger.append("claim_created", claim, {"text": f"Claim {claim}.", "kind": "theorem"}, ACTOR)
            st.record_statement(self.ledger, claim, "foo", "1 = 1", actor=ACTOR)

    def tearDown(self):
        self.tmp.cleanup()

    def seq(self, kind, claim=CLAIM):
        return next(e["seq"] for e in self.ledger.read() if e["kind"] == kind and e["claim"] == claim)

    def sign(self, seq, key=None, identity="alice@example.com"):
        return sig.sign(self.ledger, seq, key or self.alice, identity, ACTOR)

    def verified(self):
        return sig.verify(self.ledger.read(), self.signers, self.dir)


class SignatureTests(Base):
    def test_a_valid_statement_signature_verifies_and_marks_the_statement_signed(self):
        self.sign(self.seq("statement_frozen"))
        verified, notes = self.verified()
        self.assertEqual(notes, [])
        self.assertEqual([(v["claim"], v["judgment"], v["identity"]) for v in verified],
                         [(CLAIM, "statement", "alice@example.com")])
        s = derive_status(self.ledger.read(), CLAIM, {"signed": verified})
        self.assertTrue(s["formal_statement"]["signed"])
        self.assertFalse(derive_status(self.ledger.read(), OTHER, {"signed": verified})["formal_statement"]["signed"])
        self.assertFalse(derive_status(self.ledger.read(), CLAIM, {})["formal_statement"]["signed"])

    def test_payload_covers_claim_text_statement_event_and_head(self):
        events = self.ledger.read()
        payload = sig.payload(events, self.seq("statement_frozen"), "alice@example.com")
        self.assertEqual(payload["identity"], "alice@example.com")
        self.assertEqual(payload["informal_text"], Ledger.artifact_hash(f"Claim {CLAIM}.".encode()))
        self.assertEqual(payload["statement"], events[self.seq("statement_frozen")]["data"]["artifact"])
        self.assertEqual(payload["target_event"], Ledger.event_hash(events[self.seq("statement_frozen")]))
        self.assertEqual((payload["ledger_seq"], payload["ledger_head"]), (len(events) - 1, Ledger.event_hash(events[-1])))
        with self.assertRaises(sig.SignatureError):
            sig.payload(events, self.seq("claim_created"), "alice@example.com")

    def test_a_signer_not_allowed_or_a_wrong_identity_does_not_verify(self):
        self.sign(self.seq("statement_frozen"), key=self.mallory, identity="alice@example.com")
        self.sign(self.seq("statement_frozen"), identity="mallory@example.com")
        verified, notes = self.verified()
        self.assertEqual(verified, [])
        self.assertEqual(len(notes), 2)
        self.assertTrue(all("did not verify" in n for n in notes), notes)

    def test_a_copied_signature_does_not_verify_for_another_claim(self):
        event = self.sign(self.seq("statement_frozen"))
        forged = json.loads(json.dumps(event["data"]))
        forged["payload"]["claim"] = OTHER
        forged["payload"]["target_seq"] = self.seq("statement_frozen", OTHER)
        self.ledger.append("signature", OTHER, forged, ACTOR)
        self.ledger.append("signature", OTHER, event["data"], ACTOR)
        verified, notes = self.verified()
        self.assertEqual([v["claim"] for v in verified], [CLAIM])
        self.assertEqual(len(notes), 2, notes)

    def test_an_edited_payload_or_signature_does_not_verify(self):
        event = self.sign(self.seq("statement_frozen"))
        tampered = json.loads(json.dumps(event["data"]))
        tampered["payload"]["ledger_seq"] -= 1
        tampered["payload"]["ledger_head"] = Ledger.event_hash(self.ledger.read()[tampered["payload"]["ledger_seq"]])
        self.ledger.append("signature", CLAIM, tampered, ACTOR)
        bad = dict(event["data"], signature=event["data"]["signature"].replace("A", "B", 1))
        self.ledger.append("signature", CLAIM, bad, ACTOR)
        verified, notes = self.verified()
        self.assertEqual(len(verified), 1)
        self.assertEqual(len(notes), 2, notes)

    def test_the_allowed_signers_file_must_be_outside_the_ledger(self):
        inside = self.dir / "allowed_signers"
        inside.write_text(self.signers.read_text())
        with self.assertRaisesRegex(sig.SignatureError, "outside the ledger"):
            sig.verify(self.ledger.read(), inside, self.dir)
        with self.assertRaisesRegex(sig.SignatureError, "not found"):
            sig.verify(self.ledger.read(), self.dir.parent / "none", self.dir)

    def test_a_signature_on_a_rewritten_ledger_does_not_verify(self):
        self.sign(self.seq("statement_frozen"))
        events = self.ledger.read()
        # The same signature event, in a ledger whose informal text for the claim differs.
        other = Ledger.init(Path(self.tmp.name) / "other")
        other.append("claim_created", CLAIM, {"text": "A different claim.", "kind": "theorem"}, ACTOR)
        st.record_statement(other, CLAIM, "foo", "1 = 1", actor=ACTOR)
        other.append("claim_created", OTHER, {"text": f"Claim {OTHER}.", "kind": "theorem"}, ACTOR)
        st.record_statement(other, OTHER, "foo", "1 = 1", actor=ACTOR)
        other.append("signature", CLAIM, events[-1]["data"], ACTOR)
        verified, notes = sig.verify(other.read(), self.signers, other.directory)
        self.assertEqual(verified, [])
        self.assertTrue(notes)

    def test_a_signature_filed_under_another_claim_does_not_verify(self):
        event = self.sign(self.seq("statement_frozen"))
        self.ledger.append("signature", OTHER, event["data"], ACTOR)
        verified, notes = self.verified()
        self.assertEqual(len(verified), 1)
        self.assertIn("filed under another claim", notes[0])

    def test_a_signature_relabeled_with_another_allowed_identity_does_not_verify(self):
        with open(self.signers, "a") as f:
            pub = (self.keys / "alice.pub").read_text().strip()
            f.write(f'bob@example.com namespaces="{sig.NAMESPACE}" {pub}\n')
        event = self.sign(self.seq("statement_frozen"))
        self.ledger.append("signature", CLAIM, dict(event["data"], identity="bob@example.com"), ACTOR)
        verified, notes = self.verified()
        self.assertEqual([v["identity"] for v in verified], ["alice@example.com"])
        self.assertEqual(len(notes), 1)

    def test_signing_never_uses_an_ssh_agent_and_needs_a_sound_ledger(self):
        calls = []

        def runner(cmd, data, no_agent=False):
            calls.append((cmd, no_agent))
            Path(cmd[-1] + ".sig").write_text("-----BEGIN SSH SIGNATURE-----\nAAAA\n-----END SSH SIGNATURE-----\n")
            return 0, ""
        sig.sign(self.ledger, self.seq("statement_frozen"), self.alice, "alice@example.com", ACTOR, runner=runner)
        self.assertEqual(calls[0][0][:3], ["ssh-keygen", "-Y", "sign"])
        self.assertTrue(calls[0][1])
        lines = self.ledger.events_path.read_text().splitlines()
        self.ledger.events_path.write_text("\n".join(lines[:1] + lines[2:]) + "\n")
        with self.assertRaisesRegex(sig.SignatureError, "does not verify"):
            sig.sign(self.ledger, 0, self.alice, "alice@example.com", ACTOR, runner=runner)

    def test_a_retraction_payload_names_its_target(self):
        frozen = self.ledger.read()[self.seq("statement_frozen")]
        retraction = self.ledger.append("retraction", CLAIM, {"target_event": Ledger.event_hash(frozen), "reason": "x"}, ACTOR)
        subject = sig.payload(self.ledger.read(), retraction["seq"], "alice@example.com")["subject"]
        self.assertEqual((subject["target_kind"], subject["target_seq"]), ("statement_frozen", frozen["seq"]))
        stray = self.ledger.append("retraction", CLAIM, {"target_event": H, "reason": "x"}, ACTOR)
        with self.assertRaisesRegex(sig.SignatureError, "names no earlier event"):
            sig.payload(self.ledger.read(), stray["seq"], "alice@example.com")
        other = self.ledger.read()[self.seq("statement_frozen", OTHER)]
        cross = self.ledger.append("retraction", CLAIM, {"target_event": Ledger.event_hash(other), "reason": "x"}, ACTOR)
        with self.assertRaises(sig.SignatureError):
            sig.payload(self.ledger.read(), cross["seq"], "alice@example.com")

    def test_ssh_keygen_runs_without_the_agent_socket_when_signing(self):
        seen = {}
        original = sig.subprocess.run

        def fake(cmd, **kwargs):
            seen["env"] = kwargs.get("env")
            return original(["true"], **kwargs)
        sig.subprocess.run = fake
        self.addCleanup(setattr, sig.subprocess, "run", original)
        os.environ["SSH_AUTH_SOCK"] = "/tmp/fake-agent"
        self.addCleanup(os.environ.pop, "SSH_AUTH_SOCK", None)
        sig._run(["ssh-keygen"], b"", True)
        self.assertIsNotNone(seen["env"])
        self.assertNotIn("SSH_AUTH_SOCK", seen["env"])

    def test_a_signature_whose_head_is_not_before_it_is_refused(self):
        event = self.sign(self.seq("statement_frozen"))
        late = json.loads(json.dumps(event["data"]))
        late["payload"]["ledger_seq"] = event["seq"] + 1
        self.ledger.append("signature", CLAIM, late, ACTOR)
        _, notes = self.verified()
        self.assertTrue(any("not before the signature" in n for n in notes), notes)

    def test_a_signature_event_cannot_be_added_by_hand(self):
        run = subprocess.run([sys.executable, str(ROOT / "skill/scripts/mathproof.py"), "event", "add", "--dir",
                              str(self.dir), "--kind", "signature", "--claim", CLAIM, "--data", "{}"],
                             capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("cannot be added by hand", run.stderr)


class StatusTests(Base):
    def setUp(self):
        super().setUp()
        self.proof = self.ledger.put_artifact(b"theorem foo_negation : True := trivial\n")
        self.check = self.ledger.append("check", CLAIM, {"artifact": self.proof, "target_decl": "foo_negation",
                                                         "polarity": "negation", "result": "pass", "report_hash": H,
                                                         "pins": {}, "tier": "local"}, GATE)
        self.judged = [{"claim": CLAIM, "seq": self.check["seq"], "artifact": self.proof, "target_decl": "foo_negation",
                        "polarity": "negation", "challenge_hash": H, "result": "pass"}]

    def fidelity(self, judge="signed-human"):
        return self.ledger.append("fidelity", CLAIM, {"statement_hash": self.proof, "class": "faithful", "direction": "I=>F",
                                                      "judge": judge, "rows": []}, ACTOR)

    def status(self, signed=None):
        return derive_status(self.ledger.read(), CLAIM, {"judged": self.judged, "signed": signed or []})

    def test_an_unsigned_judgment_claiming_human_is_self_declared(self):
        self.fidelity()
        s = self.status()
        self.assertEqual(s["axes"]["fidelity"]["provenance"], "self-declared")
        self.assertFalse(s["axes"]["fidelity"]["signed"])
        self.assertIn("fidelity signature", s["missing"])
        self.assertEqual(s["headline"], "judged-unreviewed")

    def test_signed_statement_and_fidelity_show_human_reviewed_but_stay_below_the_top(self):
        judgment = self.fidelity(judge="agent-judge")
        self.sign(self.seq("statement_frozen"))
        self.sign(judgment["seq"])
        verified, notes = self.verified()
        self.assertEqual(notes, [])
        s = self.status(verified)
        self.assertEqual((s["axes"]["fidelity"]["provenance"], s["axes"]["fidelity"]["signed"]), ("signed-human", True))
        self.assertTrue(s["formal_statement"]["signed"])
        self.assertEqual(s["missing"], ["assumption audit"])
        self.assertEqual(s["headline"], "judged-unreviewed")
        self.assertTrue(s["verdict"].startswith("UNVERIFIED"))

    def test_a_signed_judgment_beats_an_unsigned_one(self):
        self.ledger.append("fidelity", CLAIM, {"statement_hash": self.proof, "class": "partial", "direction": "I=>F",
                                               "judge": "agent-judge", "rows": []}, ACTOR)
        judgment = self.fidelity()
        self.sign(judgment["seq"])
        s = self.status(self.verified()[0])
        self.assertEqual(s["axes"]["fidelity"]["class"], "faithful")

    def test_an_entry_for_another_kind_of_event_counts_for_nothing(self):
        s = self.status([{"claim": CLAIM, "judgment": "statement", "target_seq": self.check["seq"], "identity": "x"},
                         {"claim": OTHER, "judgment": "statement", "target_seq": self.seq("statement_frozen"), "identity": "x"}])
        self.assertFalse(s["formal_statement"]["signed"])

    def test_an_unsigned_retraction_has_no_effect_and_a_signed_one_removes_its_target(self):
        retraction = self.ledger.append("retraction", CLAIM, {"target_event": Ledger.event_hash(self.check),
                                                              "reason": "wrong file"}, ACTOR)
        self.assertEqual(self.status()["headline"], "judged-unreviewed")
        self.assertEqual(derive_status(self.ledger.read(), CLAIM, {})["headline"], "kernel-passed-local")
        self.sign(retraction["seq"])
        verified, _ = self.verified()
        s = derive_status(self.ledger.read(), CLAIM, {"signed": verified})
        self.assertEqual(s["headline"], "conjecture")
        self.assertEqual(s["axes"]["kernel"], "none")

    def retract(self, event):
        retraction = self.ledger.append("retraction", CLAIM, {"target_event": Ledger.event_hash(event), "reason": "x"},
                                        ACTOR)
        self.sign(retraction["seq"])
        return self.verified()[0]

    def test_a_signed_retraction_cannot_hide_a_rejection_a_failure_or_an_unfaithful_judgment(self):
        rejected = [dict(self.judged[0], result="fail")]
        signed = self.retract(self.check)
        s = derive_status(self.ledger.read(), CLAIM, {"judged": rejected, "signed": signed})
        self.assertEqual(s["headline"], "judge-rejected")
        failed = self.ledger.append("check", CLAIM, {"artifact": self.proof, "target_decl": "foo_negation",
                                                     "polarity": "negation", "result": "fail", "report_hash": H,
                                                     "pins": {}, "tier": "local"}, GATE)
        unfaithful = self.ledger.append("fidelity", CLAIM, {"statement_hash": self.proof, "class": "unfaithful",
                                                            "direction": "I=>F", "judge": "agent-judge", "rows": []}, ACTOR)
        before = derive_status(self.ledger.read(), CLAIM, {})
        self.retract(failed)
        signed = self.retract(unfaithful)
        after = derive_status(self.ledger.read(), CLAIM, {"signed": signed})
        self.assertEqual((after["axes"]["kernel"], after["axes"]["fidelity"]["class"]),
                         (before["axes"]["kernel"], before["axes"]["fidelity"]["class"]))
        self.assertIn("a judgment says a statement is unfaithful to the claim", after["warnings"])

    def test_a_forged_event_with_a_signed_seq_gets_nothing_and_a_broken_chain_counts_no_signature(self):
        judgment = self.fidelity()
        self.sign(judgment["seq"])
        verified, _ = self.verified()
        self.assertEqual(verified[0]["target_event"], Ledger.event_hash(judgment))
        forged = dict(judgment, data=dict(judgment["data"], **{"class": "partial"}))
        events = self.ledger.read() + [forged]
        self.assertFalse(derive_status(events, CLAIM, {"judged": self.judged, "signed": verified})["axes"]["fidelity"]["signed"])
        lines = self.ledger.events_path.read_text().splitlines()
        lines.insert(judgment["seq"] + 1, json.dumps(dict(forged, hash="0" * 64)))
        self.ledger.events_path.write_text("\n".join(lines) + "\n")
        verified, notes = sig.verify(self.ledger.read(), self.signers, self.dir)
        self.assertEqual(verified, [])
        self.assertIn("chain is broken", notes[0])

    def test_a_retraction_cannot_resolve_a_conflict_or_hide_counterevidence(self):
        claim_proof = self.ledger.put_artifact(b"theorem foo : True := trivial\n")
        self.ledger.append("check", CLAIM, {"artifact": claim_proof, "target_decl": "foo", "polarity": "claim",
                                            "result": "pass", "report_hash": H, "pins": {}, "tier": "local"}, GATE)
        experiment = self.ledger.append("experiment", CLAIM, {"code_hash": H, "outcome": "completed", "violations": [1]},
                                        ACTOR)
        before = derive_status(self.ledger.read(), CLAIM, {})
        self.assertEqual(before["headline"], "conflict")
        self.retract(self.check)
        signed = self.retract(experiment)
        after = derive_status(self.ledger.read(), CLAIM, {"signed": signed})
        self.assertEqual(after["headline"], "conflict")
        self.assertEqual(after["axes"]["computational"], before["axes"]["computational"])

    def test_a_retraction_cannot_upgrade_fidelity_or_drop_a_flaw_with_its_proof(self):
        self.fidelity(judge="agent-judge")
        partial = self.ledger.append("fidelity", CLAIM, {"statement_hash": self.proof, "class": "partial",
                                                         "direction": "I=>F", "judge": "agent-judge", "rows": []}, ACTOR)
        flawed = self.ledger.put_artifact(b"bad proof")
        proof_event = self.ledger.append("informal_proof", CLAIM, {"artifact": flawed, "author_context": "a"}, ACTOR)
        audit = self.ledger.append("informal_audit", CLAIM, {"proof_hash": flawed, "result": "flaw", "auditor": "me"}, ACTOR)
        self.sign(audit["seq"])
        self.retract(partial)
        signed = self.retract(proof_event)
        s = derive_status(self.ledger.read(), CLAIM, {"judged": self.judged, "signed": signed})
        self.assertEqual(s["axes"]["fidelity"]["class"], "partial")
        self.assertEqual(s["axes"]["informal"], "rejected")

    def test_a_signed_flaw_audit_cannot_be_retracted(self):
        proof = self.ledger.put_artifact(b"bad proof")
        self.ledger.append("informal_proof", CLAIM, {"artifact": proof, "author_context": "a"}, ACTOR)
        audit = self.ledger.append("informal_audit", CLAIM, {"proof_hash": proof, "result": "flaw", "auditor": "me"}, ACTOR)
        self.sign(audit["seq"])
        signed = self.retract(audit)
        self.assertEqual(derive_status(self.ledger.read(), CLAIM, {"signed": signed})["axes"]["informal"], "rejected")

    def test_a_verified_entry_counts_only_for_its_own_claim(self):
        frozen = self.ledger.read()[self.seq("statement_frozen")]
        entry = {"claim": OTHER, "judgment": "statement", "target_seq": frozen["seq"],
                 "target_event": Ledger.event_hash(frozen), "identity": "x"}
        self.assertFalse(self.status([entry])["formal_statement"]["signed"])
        self.assertTrue(self.status([dict(entry, claim=CLAIM)])["formal_statement"]["signed"])

    def test_only_the_first_frozen_statement_can_be_signed(self):
        record = st.build(CLAIM, "bar", "2 = 2")
        digest = self.ledger.put_artifact(st.encode(record))
        second = self.ledger.append("statement_frozen", CLAIM, {"artifact": digest, "name": "bar"}, ACTOR)
        with self.assertRaisesRegex(sig.SignatureError, "first frozen statement"):
            sig.payload(self.ledger.read(), second["seq"], "alice@example.com")

    def test_a_signed_retraction_cannot_remove_the_statement(self):
        frozen = self.ledger.read()[self.seq("statement_frozen")]
        retraction = self.ledger.append("retraction", CLAIM, {"target_event": Ledger.event_hash(frozen), "reason": "x"},
                                        ACTOR)
        self.sign(retraction["seq"])
        s = derive_status(self.ledger.read(), CLAIM, {"signed": self.verified()[0]})
        self.assertIsNotNone(s["formal_statement"])

    def test_a_signed_informal_audit_gives_the_human_audited_label(self):
        proof = self.ledger.put_artifact(b"informal proof")
        self.ledger.append("informal_proof", OTHER, {"artifact": proof, "author_context": "a"}, ACTOR)
        audit = self.ledger.append("informal_audit", OTHER, {"proof_hash": proof, "result": "no-flaw", "auditor": "me"},
                                   ACTOR)
        unsigned = derive_status(self.ledger.read(), OTHER, {})
        self.assertEqual((unsigned["axes"]["informal"], unsigned["verdict"]), ("self-audited", "INCOMPLETE"))
        self.sign(audit["seq"])
        s = derive_status(self.ledger.read(), OTHER, {"signed": self.verified()[0]})
        self.assertEqual((s["axes"]["informal"], s["verdict"]), ("signed-audited", HUMAN_AUDITED))

    def test_a_signed_flaw_marks_the_informal_proof_rejected(self):
        proof = self.ledger.put_artifact(b"informal proof")
        self.ledger.append("informal_proof", OTHER, {"artifact": proof, "author_context": "a"}, ACTOR)
        audit = self.ledger.append("informal_audit", OTHER, {"proof_hash": proof, "result": "flaw", "auditor": "me"}, ACTOR)
        self.sign(audit["seq"])
        s = derive_status(self.ledger.read(), OTHER, {"signed": self.verified()[0]})
        self.assertEqual(s["axes"]["informal"], "rejected")
        self.assertEqual(s["verdict"], "INCOMPLETE")


class CommandTests(Base):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "skill/scripts/mathproof.py"), *args], capture_output=True,
                              text=True, stdin=subprocess.DEVNULL, start_new_session=True)

    def test_signing_needs_a_terminal(self):
        run = self.run_cli("sign", "--dir", str(self.dir), "--event", str(self.seq("statement_frozen")), "--key",
                           str(self.alice), "--identity", "alice@example.com")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("needs a terminal", run.stderr)
        self.assertFalse(any(e["kind"] == "signature" for e in self.ledger.read()))

    def test_signers_need_an_authoritative_verify(self):
        run = self.run_cli("verify", str(self.dir), "--signers", str(self.signers))
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("--signers needs --authoritative", run.stderr)


if __name__ == "__main__":
    unittest.main()
