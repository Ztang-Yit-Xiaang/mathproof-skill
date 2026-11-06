"""Replay decisions, run against a stub checker so every path is fast and no Lean is needed."""

import contextlib
import io
import json
import stat
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from mathproof_core import cli
from mathproof_core.gate import EnvironmentFailure, record_check
from mathproof_core.ledger import Ledger
from mathproof_core.replay import verify_investigation

ACTOR = {"context_id": "x", "role": "r", "kind": "agent"}
CLAIM = "inv/c1"


def base_report(**changes):
    report = {"status": "PASS", "problems": [], "toolchain": "t1", "mathlib_rev": "m1", "pinned": True,
              "checker": {"version": "2", "sha256_checker": "a", "sha256_driver": "b"},
              "stages": {"compile": {"status": "pass"}},
              "declarations": [{"name": "main_theorem", "kind": "theorem", "type": "1 = 1", "type_explicit": "@Eq Nat 1 1",
                                "axioms": ["propext"], "nonstandard_axioms": [], "statement_uses": ["helper"]}],
              "statement_context": {"helper": {"type": "Nat", "definition": "0"}}}
    report.update(changes)
    return report


class StubTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.answer = self.root / "answer.json"
        self.checker = self.root / "stub_checker.py"
        self.calls = self.root / "calls.txt"
        self.checker.write_text(textwrap.dedent(f"""\
            import pathlib, sys
            pathlib.Path({str(self.calls)!r}).open("a").write("call\\n")
            answer = pathlib.Path({str(self.answer)!r}).read_text()
            if answer == "CRASH":
                sys.exit(2)
            print(answer)
            sys.exit(1 if '"FAIL"' in answer else 0)
            """), encoding="utf-8")
        self.set_answer(base_report())
        self.source = self.root / "F.lean"
        self.source.write_text("theorem main_theorem : 1 = 1 := rfl\n", encoding="utf-8")
        self.dir = self.root / "inv"
        self.ledger = Ledger.init(self.dir)
        self.ledger.append("claim_created", CLAIM, {"text": "A claim.", "kind": "theorem"}, ACTOR)

    def set_answer(self, report):
        self.answer.write_text(report if isinstance(report, str) else json.dumps(report), encoding="utf-8")

    def record(self, **kwargs):
        args = {"decl": "main_theorem", "polarity": "claim"}
        args.update(kwargs)
        return record_check(self.ledger, CLAIM, self.source, args["decl"], args["polarity"], self.project, checker=self.checker)

    def verify(self, **kwargs):
        return verify_investigation(self.dir, checker=self.checker, **kwargs)

    def rewrite(self, events):
        prev = "0" * 64
        out = []
        for index, event in enumerate(events):
            event["seq"], event["prev"] = index, prev
            event.pop("hash", None)
            event["hash"] = prev = Ledger.event_hash(event)
            out.append(json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
        (self.dir / "events.jsonl").write_text("".join(out), encoding="utf-8")

    def replace_stored_report(self, **changes):
        events = self.ledger.read()
        stored = json.loads(self.ledger.get_artifact(events[1]["data"]["report_hash"]))
        stored.update(changes)
        events[1]["data"]["report_hash"] = self.ledger.put_artifact(json.dumps(stored).encode())
        self.rewrite(events)

    def assert_differs(self, text=None):
        result = self.verify()
        self.assertFalse(result["ok"])
        if text:
            self.assertIn(text, json.dumps(result["differences"]))

    def test_clean_ledger_is_ok(self):
        self.record()
        result = self.verify()
        self.assertTrue(result["ok"], result["differences"])
        self.assertEqual(result["reruns"], 1)

    def test_rerun_output_is_not_trusted_from_the_stored_report_alone(self):
        self.record()
        self.set_answer(base_report(status="FAIL", problems=["boom"]))
        self.assert_differs("re-run says fail")

    def test_every_displayed_field_of_the_stored_report_must_reproduce(self):
        self.record()
        declaration = base_report()["declarations"][0]
        for changes in ({"declarations": [{**declaration, "type_explicit": "forged"}]},
                        {"declarations": [{**declaration, "statement_uses": []}]},
                        {"declarations": [{**declaration, "kind": "other"}]},
                        {"statement_context": {}},
                        {"toolchain": "t9"}, {"mathlib_rev": "m9"}, {"pinned": False},
                        {"environment_error": True}):
            with self.subTest(changes):
                good = self.ledger.read()
                self.replace_stored_report(**changes)
                self.assert_differs("stored report")
                self.rewrite(good)

    def test_a_different_environment_is_a_difference(self):
        self.record()
        for changes in ({"toolchain": "t9"}, {"mathlib_rev": "m9"}, {"pinned": False}):
            with self.subTest(changes):
                self.set_answer(base_report(**changes))
                self.assertFalse(self.verify()["ok"])

    def test_forged_event_fields_are_differences(self):
        self.record()
        good = self.ledger.read()
        for change in ({"tier": "authoritative"}, {"polarity": "negation"}, {"problems": ["forged"]},
                       {"pins": {"toolchain": "t9", "mathlib_rev": "m1", "pinned": True, "checker": base_report()["checker"]}}):
            with self.subTest(change):
                events = json.loads(json.dumps(good))
                events[1]["data"].update(change)
                self.rewrite(events)
                self.assertFalse(self.verify()["ok"])
        self.rewrite(good)

    def test_a_chain_break_is_a_difference_with_its_claim(self):
        self.record()
        path = self.dir / "events.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        path.write_text(lines[0].replace("A claim.", "A weaker claim.") + lines[1], encoding="utf-8")
        self.assert_differs(CLAIM)

    def test_the_rerun_cache_does_not_mix_up_artifacts(self):
        self.record()
        other = self.ledger.put_artifact(b"theorem main_theorem : 2 = 2 := rfl\n")
        events = self.ledger.read()
        events.append(json.loads(json.dumps(events[1])))
        events[2]["data"]["artifact"] = other
        self.rewrite(events)
        self.assertEqual(self.verify()["reruns"], 2)

    def test_stored_files_of_every_kind_are_checked(self):
        for kind, data in (("informal_proof", {"artifact": "d" * 64, "author_context": "x"}),
                           ("informal_audit", {"proof_hash": "d" * 64, "result": "no-flaw", "auditor": "y"}),
                           ("experiment", {"code_hash": "d" * 64, "outcome": "completed"}),
                           ("fidelity", {"statement_hash": "d" * 64, "rows": [], "class": "faithful", "direction": "F=>I", "judge": "none"})):
            with self.subTest(kind):
                directory = self.root / f"kind-{kind}"
                ledger = Ledger.init(directory)
                ledger.append("claim_created", CLAIM, {"text": "x", "kind": "theorem"}, ACTOR)
                ledger.append(kind, CLAIM, data, ACTOR)
                self.assertFalse(verify_investigation(directory, checker=self.checker)["ok"], kind)

    def test_a_check_on_a_claim_with_no_statement_is_a_difference(self):
        self.record()
        events = self.ledger.read()
        del events[0]
        self.rewrite(events)
        self.assert_differs("statement")

    def test_odd_stored_reports_are_differences_not_crashes(self):
        self.record()
        good = self.ledger.read()
        for stored in (b"[1]", b'{"declarations": [5]}', b'{"declarations": 5}', b"not json", b'{"declarations": [{"axioms": 5}]}'):
            with self.subTest(stored):
                events = json.loads(json.dumps(good))
                events[1]["data"]["report_hash"] = self.ledger.put_artifact(stored)
                self.rewrite(events)
                self.assertFalse(self.verify()["ok"])
        self.rewrite(good)

    def test_an_environment_failure_on_rerun_is_not_ok(self):
        self.record()
        self.set_answer("CRASH")
        result = self.verify()
        self.assertFalse(result["ok"])
        self.assertTrue(result["environment_errors"])

    def test_gate_records_nothing_for_failures_of_the_environment(self):
        for report in (base_report(status="FAIL", environment_error=True, problems=["x"]),
                       base_report(status="FAIL", problems=["Lean timed out after 900s"], stages={"compile": {"status": "timeout"}}),
                       base_report(status="FAIL", problems=["Lean error: x.lean:1:0: error: unknown module prefix 'Mathlib'"]),
                       base_report(status="FAIL", problems=["Lean error: x.lean:1:0: error: object file 'y.olean' of module Mathlib.Foo does not exist"]),
                       "CRASH"):
            with self.subTest(report):
                self.set_answer(report)
                with self.assertRaises(EnvironmentFailure):
                    self.record()
        self.assertEqual([e["kind"] for e in self.ledger.read()], ["claim_created"])

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_verify_exit_codes(self):
        cases = ((True, [], [], 0), (False, [{"claim": CLAIM, "seq": 1, "kind": "check", "detail": "d"}], [], 1),
                 (False, [], [{"claim": CLAIM, "seq": 1, "detail": "d"}], 2))
        for ok, differences, errors, want in cases:
            result = {"ok": ok, "differences": differences, "environment_errors": errors, "statuses": {}, "reruns": 0, "notes": ["n"]}
            with mock.patch.object(cli, "verify_investigation", return_value=result):
                self.assertEqual(self.run_cli("verify", str(self.dir))[0], want)

    def test_check_on_a_missing_file_is_an_environment_error(self):
        code, _, err = self.run_cli("check", "--dir", str(self.dir), "--claim", CLAIM, "--decl", "t", "--polarity", "claim",
                                    "--project", str(self.project), str(self.root / "missing.lean"))
        self.assertEqual(code, 2, err)
        self.assertEqual(len(self.ledger.read()), 1)

    def test_verify_text_cannot_be_forged_by_event_fields(self):
        self.record()
        events = self.ledger.read()
        events[1]["data"]["tier"] = "x\nOK: 2 checks re-run.\ninv/c1: established, VALID"
        self.rewrite(events)
        real = verify_investigation
        with mock.patch.object(cli, "verify_investigation", side_effect=lambda d, project=None: real(d, checker=self.checker, project=project)):
            code, out, _ = self.run_cli("verify", str(self.dir))
        self.assertEqual(code, 1)
        for line in out.splitlines():
            self.assertFalse(line.startswith(("OK:", "inv/c1: established")), line)

    def test_a_negation_check_reproduces_cleanly(self):
        self.record(polarity="negation")
        result = self.verify()
        self.assertTrue(result["ok"], result["differences"])

    def test_a_forged_checker_in_the_event_pins_alone_is_a_difference(self):
        self.record()
        events = self.ledger.read()
        events[1]["data"]["pins"]["checker"] = {"version": "forged"}
        self.rewrite(events)
        self.assert_differs("checker changed")

    def test_a_statement_is_required_before_an_event_on_a_claim(self):
        code, _, err = self.run_cli("event", "add", "--dir", str(self.dir), "--claim", "inv/typo", "--kind", "note", "--data", "{}")
        self.assertNotEqual(code, 0)
        self.assertIn("inv/typo", err)

    def test_verify_writes_nothing(self):
        self.record()
        before = {p: (p.read_bytes(), stat.S_IMODE(p.stat().st_mode)) for p in self.dir.rglob("*") if p.is_file()}
        self.verify()
        self.assertEqual(before, {p: (p.read_bytes(), stat.S_IMODE(p.stat().st_mode)) for p in self.dir.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
