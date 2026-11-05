"""S1.1.T2: append-only hash-chained ledger and artifact store."""

import json
import multiprocessing
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import _paths  # noqa: F401
from mathproof_core.ledger import ArtifactCorrupt, ClaimExists, Ledger, TornTail

ACTOR = {"context_id": "ctx1", "role": "prover", "kind": "agent"}


def _append_many(directory, worker, count):
    ledger = Ledger(directory)
    for i in range(count):
        ledger.append("note", None, {"worker": worker, "i": i}, ACTOR)


def _add_claim(directory, worker):
    try:
        Ledger(directory).append("claim_created", "inv/c1", {"text": f"statement {worker}", "kind": "theorem"}, ACTOR)
    except ClaimExists:
        pass


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name, "inv")
        self.ledger = Ledger.init(self.dir)
        self.path = self.dir / "events.jsonl"

    def fill(self, n=4):
        return [self.ledger.append("note", None, {"i": i}, ACTOR) for i in range(n)]

    def lines(self):
        return self.path.read_text(encoding="utf-8").splitlines(keepends=True)

    def assert_breaks_at(self, line):
        result = self.ledger.verify()
        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0].line, line)

    def test_round_trip_and_chain(self):
        written = self.fill()
        self.assertEqual(self.ledger.read(), written)
        self.assertEqual([e["seq"] for e in written], [0, 1, 2, 3])
        self.assertEqual(written[0]["prev"], "0" * 64)
        self.assertEqual(written[1]["prev"], Ledger.event_hash(written[0]))
        self.assertEqual(written[0]["hash"], Ledger.event_hash(written[0]))
        self.assertTrue(self.ledger.verify().ok)

    def test_init_refuses_an_existing_ledger(self):
        with self.assertRaises(FileExistsError):
            Ledger.init(self.dir)

    def test_append_rejects_an_invalid_event(self):
        with self.assertRaises(ValueError):
            self.ledger.append("note", None, {"status": "VALID"}, ACTOR)
        self.assertEqual(self.ledger.read(), [])

    def test_edited_line_fails_with_its_line_number(self):
        self.fill()
        lines = self.lines()
        event = json.loads(lines[1])
        event["data"]["i"] = 99
        lines[1] = json.dumps(event) + "\n"
        self.path.write_text("".join(lines), encoding="utf-8")
        self.assert_breaks_at(2)

    def test_deleted_line_fails_with_its_line_number(self):
        self.fill()
        lines = self.lines()
        del lines[1]
        self.path.write_text("".join(lines), encoding="utf-8")
        self.assert_breaks_at(2)

    def test_reordered_lines_fail(self):
        self.fill()
        lines = self.lines()
        lines[1], lines[2] = lines[2], lines[1]
        self.path.write_text("".join(lines), encoding="utf-8")
        self.assert_breaks_at(2)

    def test_edited_first_line_fails_at_line_one(self):
        self.fill()
        lines = self.lines()
        event = json.loads(lines[0])
        event["data"]["i"] = 99
        lines[0] = json.dumps(event) + "\n"
        self.path.write_text("".join(lines), encoding="utf-8")
        self.assert_breaks_at(1)

    def test_edited_last_line_is_detected_and_not_sealed_by_the_next_append(self):
        self.fill()
        lines = self.lines()
        self.path.write_text("".join(lines[:-1]) + lines[-1].replace('"i":3', '"i":99'), encoding="utf-8")
        self.assert_breaks_at(4)
        self.ledger.append("note", None, {}, ACTOR)
        self.assert_breaks_at(4)

    def test_byte_edits_that_parse_the_same_are_detected(self):
        self.fill()
        lines = self.lines()
        for edited in (lines[1].replace(",", ", ", 1), lines[1].rstrip("\n") + "\r\n",
                       lines[1].replace('"data":{', '"data":{"i":"FORGED",')):
            self.path.write_text("".join(lines[:1] + [edited] + lines[2:]), encoding="utf-8", newline="")
            self.assert_breaks_at(2)

    def test_a_second_statement_for_a_claim_is_refused_under_concurrency(self):
        context = multiprocessing.get_context("spawn")
        workers = [context.Process(target=_add_claim, args=(self.dir, w)) for w in range(6)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()
        self.assertEqual(len([e for e in self.ledger.read() if e["kind"] == "claim_created"]), 1)

    def test_recovery_keeps_the_torn_text_if_the_recovery_event_is_invalid(self):
        self.fill(1)
        with self.path.open("a", encoding="utf-8") as f:
            f.write('{"partial')
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.ledger.recover_torn_tail({"role": "bad"})
        self.assertEqual(self.path.read_bytes(), before)

    def test_recovery_keeps_file_mode_and_symlinks(self):
        self.fill(1)
        real = self.dir / "real.jsonl"
        self.path.rename(real)
        self.path.symlink_to(real)
        real.chmod(0o640)
        with real.open("a", encoding="utf-8") as f:
            f.write('{"partial')
        self.ledger.recover_torn_tail(ACTOR)
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(real.stat().st_mode & 0o777, 0o640)
        self.assertTrue(self.ledger.verify().ok)

    def test_artifacts_are_not_private_to_the_writer_by_accident(self):
        digest = self.ledger.put_artifact(b"x")
        self.assertEqual((self.dir / "artifacts" / digest).stat().st_mode & 0o777, self.path.stat().st_mode & 0o777)

    def test_put_artifact_needs_bytes(self):
        for bad in (5, "text", None):
            with self.assertRaises(TypeError):
                self.ledger.put_artifact(bad)

    def test_append_reports_a_corrupt_ledger_as_value_error(self):
        with self.path.open("a", encoding="utf-8") as f:
            f.write("[1]\n")
        with self.assertRaises(ValueError):
            self.ledger.append("claim_created", "inv/c1", {"text": "x", "kind": "theorem"}, ACTOR)

    def test_only_newline_ends_a_line(self):
        self.fill(2)
        with self.path.open("ab") as f:
            f.write(b'{"partial\r')
        result = self.ledger.verify()
        self.assertTrue(result.torn_tail)
        self.ledger.recover_torn_tail(ACTOR)
        self.assertEqual(len(self.ledger.read()), 3)
        self.assertTrue(self.ledger.verify().ok)

    def test_text_that_cannot_be_stored_is_refused(self):
        with self.assertRaises(ValueError):
            self.ledger.append("note", None, {"text": "\ud800"}, ACTOR)
        self.assertEqual(self.ledger.read(), [])

    def test_put_artifact_repairs_a_corrupt_copy_and_survives_threads(self):
        digest = self.ledger.put_artifact(b"x")
        (self.dir / "artifacts" / digest).write_bytes(b"changed")
        self.assertEqual(self.ledger.put_artifact(b"x"), digest)
        self.assertEqual(self.ledger.get_artifact(digest), b"x")
        with ThreadPoolExecutor(8) as pool:
            self.assertEqual(set(pool.map(self.ledger.put_artifact, [b"same"] * 32)), {Ledger.artifact_hash(b"same")})

    def rewrite(self, events):
        """Write events in canonical form with self-consistent hashes, as a careful edit would."""
        for event in events:
            event["hash"] = Ledger.event_hash(event)
        text = "".join(json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for e in events)
        self.path.write_text(text, encoding="utf-8")

    def test_a_broken_link_is_caught_even_when_seq_and_hash_are_consistent(self):
        events = self.fill()
        del events[1]
        for index, event in enumerate(events):
            event["seq"] = index
        self.rewrite(events)
        self.assert_breaks_at(2)

    def test_a_wrong_seq_is_caught_even_when_hash_and_link_are_consistent(self):
        events = self.fill(2)
        events[1]["seq"] = 7
        self.rewrite(events)
        self.assert_breaks_at(2)

    def test_edited_sequence_number_on_the_last_line_fails(self):
        self.fill()
        lines = self.lines()
        event = json.loads(lines[-1])
        event["seq"] = 40
        lines[-1] = json.dumps(event) + "\n"
        self.path.write_text("".join(lines), encoding="utf-8")
        self.assert_breaks_at(4)

    def test_artifact_round_trip_and_tamper(self):
        digest = self.ledger.put_artifact(b"theorem x : True := trivial\n")
        self.assertEqual(len(digest), 64)
        self.assertEqual(self.ledger.get_artifact(digest), b"theorem x : True := trivial\n")
        self.assertEqual(self.ledger.put_artifact(b"theorem x : True := trivial\n"), digest)
        (self.dir / "artifacts" / digest).write_bytes(b"changed")
        with self.assertRaises(ArtifactCorrupt):
            self.ledger.get_artifact(digest)

    def test_artifact_lookup_cannot_leave_the_store(self):
        for bad in ("../events.jsonl", "a" * 63, "A" * 64):
            with self.assertRaises(ValueError):
                self.ledger.get_artifact(bad)

    def test_concurrent_appends_do_not_fork_the_chain(self):
        context = multiprocessing.get_context("spawn")
        workers = [context.Process(target=_append_many, args=(self.dir, w, 25)) for w in range(4)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()
            self.assertEqual(w.exitcode, 0)
        result = self.ledger.verify()
        self.assertTrue(result.ok, result.errors)
        self.assertEqual([e["seq"] for e in self.ledger.read()], list(range(100)))

    def test_torn_tail_is_recoverable_with_an_explicit_event(self):
        self.fill(3)
        with self.path.open("a", encoding="utf-8") as f:
            f.write('{"seq": 3, "prev": "abc')
        result = self.ledger.verify()
        self.assertFalse(result.ok)
        self.assertTrue(result.torn_tail)
        self.assertEqual(len(self.ledger.read()), 3)
        with self.assertRaises(TornTail):
            self.ledger.append("note", None, {}, ACTOR)
        recovered = self.ledger.recover_torn_tail(ACTOR)
        self.assertEqual(recovered["kind"], "ledger_recovery")
        self.assertEqual(recovered["seq"], 3)
        self.assertIn("abc", recovered["data"]["discarded"])
        self.assertTrue(self.ledger.verify().ok)

    def test_recovery_refuses_any_other_break(self):
        self.fill(3)
        lines = self.lines()
        del lines[0]
        self.path.write_text("".join(lines), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.ledger.recover_torn_tail(ACTOR)

    def test_a_complete_but_bad_last_line_is_fatal_not_torn(self):
        self.fill(2)
        with self.path.open("a", encoding="utf-8") as f:
            f.write('{"not": "an event"}\n')
        result = self.ledger.verify()
        self.assertFalse(result.ok)
        self.assertFalse(result.torn_tail)


if __name__ == "__main__":
    unittest.main()
