"""S2.2.T1: frozen statements, the Challenge generated from them, and revisions.

No Lean runs here; `compile_challenge` is replaced where a command needs it. What the comparator does
with a Challenge (a weakened proof fails, a changed local definition fails) is checked on the
fixture ledger research/binding-fixtures/ledger by the authoritative workflow; see its README.
"""

import json
import shlex
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from mathproof_core import authority, judge
from mathproof_core import statement as st
from mathproof_core.ledger import Ledger
from mathproof_core.status import derive_status
from test_authority import fake_runner

ACTOR = {"context_id": "t", "role": "cli", "kind": "self-declared"}
GATE = {"context_id": "t", "role": "gate", "kind": "runner"}
CLAIM, NEW = "inv/c1", "inv/c2"
H = "c" * 64


def no_lean(record, project):
    return {"type": None, "defined_in_statement": []}


def check(artifact, target, polarity="claim", result="pass"):
    return {"artifact": artifact, "target_decl": target, "polarity": polarity, "result": result,
            "report_hash": H, "pins": {}, "tier": "local"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "ledger"
        self.ledger = Ledger.init(self.dir)
        self.ledger.append("claim_created", CLAIM, {"text": "Every n has f n > n.", "kind": "theorem"}, ACTOR)

    def tearDown(self):
        self.tmp.cleanup()

    def freeze(self, claim=CLAIM, name="foo", prop="∀ n : ℕ, f n > n", preamble="def f (n : ℕ) : ℕ := n + 1",
               revises=None, compiler=no_lean):
        return st.record_statement(self.ledger, claim, name, prop, preamble, revises, project="p",
                                   actor=ACTOR, compiler=compiler)


class ShapeTests(unittest.TestCase):
    def test_rejects_shapes_the_challenge_cannot_carry(self):
        for name, prop, preamble in (("a.b", "True", ""), ("1x", "True", ""), ("ok", "  ", ""),
                                     ("ok", "True", "import Foo"), ("ok", "True", "open Nat\n  import Foo"),
                                     ("ok", "True) := trivial\n\nexample : (True", ""),
                                     ("ok", "True", "def f := 1\u202e"), ("ok", "True\u200b", "")):
            with self.subTest(name=name, prop=prop, preamble=preamble), self.assertRaises(st.StatementError):
                st.build(CLAIM, name, prop, preamble)

    def test_preamble_cannot_change_how_lean_reads_the_challenge(self):
        for word in ("macro", "macro_rules", "syntax", "elab", "notation", "infixl", "prefix", "set_option",
                     "attribute", "variable", "include", "namespace", "section", "end", "local", "scoped",
                     "initialize", "unsafe", "run_cmd", "run_meta", "run_tac", "by_elab", "export", "universe",
                     "opaque", "axiom", "mutual"):
            with self.subTest(word=word), self.assertRaisesRegex(st.StatementError, "can change how Lean"):
                st.build(CLAIM, "foo", "True", f"def g := 1\n  {word} x")
        for word in ("simproc", "dsimproc", "native_decide", "unsafeBaseIO", "IO", "Lean", "Lean.Meta.foo",
                     "notation3", "renaming", "hiding", "unif_hint", "register_foo", "declare_bar", "«x»",
                     "by", "IO.FS.writeFile"):
            with self.subTest(word=word), self.assertRaises(st.StatementError):
                st.build(CLAIM, "foo", "True", f"def g := 1\n  {word} x")
        for text in ("@[simp] def g := 1", "#eval 1", "def g := eval% 1"):
            with self.subTest(text=text), self.assertRaises(st.StatementError):
                st.build(CLAIM, "foo", "True", text)
        with self.assertRaises(st.StatementError):
            st.build(CLAIM, "foo", "by run_tac pure ()")
        for ok in ("def endpoint (n : ℕ) := n\nopen Nat Real", "theorem Foo.local_max : True := trivial",
                   "structure P where\n  x : ℕ", "/-- doc\n  more -/\nnoncomputable def h : ℕ := 0",
                   "instance : Inhabited ℕ := ⟨0⟩\n\nlemma l : True := trivial", "-- note\nabbrev A := ℕ",
                   "def bypass := 1\ndef nearby := bypass"):
            st.build(CLAIM, "foo", "True", ok)

    def test_preamble_commands_come_from_an_allowlist(self):
        for text in ("simp_lemma x", "open Nat in\ndef g := 1", "open Nat (succ)", "example : True := trivial",
                     "def g := 1\nfoo bar", "  def g := 1\nbad"):
            with self.subTest(text=text), self.assertRaisesRegex(st.StatementError, "allowed command"):
                st.build(CLAIM, "foo", "True", text)

    def test_challenge_holds_both_theorems_on_the_generated_lines(self):
        record = st.build(CLAIM, "foo", "1 = 1", "def f := 3\ndef g := 4")
        text = st.challenge(record).decode()
        self.assertTrue(text.startswith("import Mathlib\n\ndef f := 3\ndef g := 4\n\n"))
        self.assertIn("theorem foo : (1 = 1) := by\n  sorry", text)
        self.assertIn("theorem foo_negation : ¬ (1 = 1) := by\n  sorry", text)
        lines = text.splitlines()
        first, second = st.lines(record)
        self.assertTrue(lines[first - 1].startswith("theorem foo :"))
        self.assertTrue(lines[second - 1].startswith("theorem foo_negation :"))
        multi = st.build(CLAIM, "foo", "∀ n : ℕ,\n  n = n")
        first, second = st.lines(multi)
        lines = st.challenge(multi).decode().splitlines()
        self.assertEqual((lines[first - 1][:13], lines[second - 1][:22]), ("theorem foo :", "theorem foo_negation :"))

    def test_binding_runs_fixed_drivers_with_the_generated_lines(self):
        record = st.build(CLAIM, "foo", "1 = 1", "def f := 3")
        first, second = st.lines(record)
        cmd = st.binding_command(record)
        self.assertEqual(cmd[:4], ["lake", "env", "lean", "--run"])
        self.assertEqual(Path(cmd[4]).name, "lean_binding.lean")
        self.assertTrue(Path(cmd[4]).is_file())
        self.assertEqual(cmd[5:], ["foo", "foo_negation", str(first), str(second)])
        audit = st.statements_command("C.olean", "out.json")
        self.assertEqual((Path(audit[4]).name, audit[5:]), ("lean_audit.lean", ["statements", "C.olean", "out.json"]))

    def test_driver_checks_root_theorems_lines_and_exact_negation(self):
        text = st.BINDING_DRIVER.read_text(encoding="utf-8")
        self.assertIn("importModules #[{ module := `Challenge }] {} (trustLevel := 0) (loadExts := false)", text)
        self.assertIn("unless ci matches .thmInfo _ do", text)
        self.assertIn("unless env.getModuleIdxFor? n == some idx do", text)
        self.assertIn("unless ranges.range.pos.line == line do", text)
        self.assertIn("unless neg.type == mkApp (mkConst ``Not) claim.type do", text)
        self.assertNotIn("import Challenge", text)

    def test_read_statements(self):
        record = st.build(CLAIM, "foo", "1 = 1")
        context = {"f": {"type": "ℕ → ℕ", "definition": "fun n => n + 1"}, "Foo.g": {"type": "Prop"}}
        report = {"declarations": [{"name": "foo_negation", "type": "¬T", "type_explicit": "¬T", "statement_uses": []},
                                   {"name": "foo", "type": "∀ n, f n > n", "type_explicit": "∀ (n : ℕ), f n > n",
                                    "statement_uses": ["f", "Foo.g"]}],
                  "statement_context": context}
        self.assertEqual(st.read_statements(report, record),
                         {"type": "∀ n, f n > n", "type_explicit": "∀ (n : ℕ), f n > n",
                          "defined_in_statement": ["f", "Foo.g"], "definitions": context})
        good = report["declarations"][1]
        for bad in ({}, {"declarations": [{**good, "type": 1}], "statement_context": context},
                    {"declarations": [{**good, "statement_uses": [2]}], "statement_context": context},
                    {"declarations": [{**good, "type_explicit": None}], "statement_context": context},
                    {"declarations": [good], "statement_context": {"f": context["f"]}},
                    {"declarations": [good], "statement_context": {**context, "f": {"type": 3}}},
                    {"declarations": [good]}, [], None):
            with self.subTest(bad=bad), self.assertRaises(st.StatementError):
                st.read_statements(bad, record)


    def test_challenge_is_deterministic_and_depends_on_every_field_that_matters(self):
        base = st.build(CLAIM, "foo", "1 = 1", "def f := 3")
        self.assertEqual(st.challenge(base), st.challenge(st.build(CLAIM, "foo", "1 = 1\n", "\ndef f := 3\n")))
        for other in (st.build(CLAIM, "foo", "1 = 2", "def f := 3"), st.build(CLAIM, "bar", "1 = 1", "def f := 3"),
                      st.build(CLAIM, "foo", "1 = 1", "def f := 4")):
            self.assertNotEqual(st.challenge(base), st.challenge(other))

    def test_decode_accepts_only_the_canonical_record(self):
        record = st.build(CLAIM, "foo", "1 = 1")
        self.assertEqual(st.decode(st.encode(record)), record)
        for bad in ({**record, "extra": 1}, {**record, "format": "x"}, {**record, "prop": " 1 = 1 "},
                    {**record, "name": "a.b"}, {**record, "claim": 5}, {**record, "claim": None}):
            with self.subTest(bad=bad), self.assertRaises(st.StatementError):
                st.decode(json.dumps(bad).encode())
        with self.assertRaises(st.StatementError):
            st.decode(b"{")

    def test_compile_challenge_stops_at_each_failed_step(self):
        record = st.build(CLAIM, "foo", "1 = 1")
        original = st._run
        self.addCleanup(setattr, st, "_run", original)
        for failing, message in ((0, "does not compile"), (1, "binding check failed"), (2, "could not be printed")):
            calls = []

            def fake(cmd, cwd, env, timeout, failing=failing, calls=calls):
                calls.append(cmd)
                return (1 if len(calls) - 1 == failing else 0), "boom"
            st._run = fake
            with self.subTest(step=failing), self.assertRaisesRegex(st.StatementError, message):
                st.compile_challenge(record, tempfile.gettempdir())
            self.assertEqual(len(calls), failing + 1)


class RecordTests(Base):
    def test_records_event_statement_and_challenge(self):
        event, _ = self.freeze()
        data = event["data"]
        self.assertEqual(event["kind"], "statement_frozen")
        record = st.decode(self.ledger.get_artifact(data["artifact"]))
        self.assertEqual((record["claim"], record["name"]), (CLAIM, "foo"))
        self.assertEqual(self.ledger.get_artifact(data["challenge_hash"]), st.challenge(record))
        self.assertEqual(st.load(self.ledger, CLAIM), record)

    def test_unknown_claim_and_second_statement_are_refused(self):
        with self.assertRaises(st.StatementError):
            self.freeze(claim="inv/none")
        self.freeze()
        with self.assertRaisesRegex(st.StatementError, "already has a statement"):
            self.freeze(prop="∀ n : ℕ, f n ≥ n")
        self.assertEqual(len(st.frozen(self.ledger, CLAIM)), 1)

    def test_compile_failure_records_nothing(self):
        def broken(record, project):
            raise st.StatementError("the Challenge does not compile")
        before = len(self.ledger.read())
        with self.assertRaises(st.StatementError):
            self.freeze(compiler=broken)
        self.assertEqual(len(self.ledger.read()), before)

    def test_binding_is_returned_and_recorded(self):
        found = {"type": "∀ n, f n > n", "defined_in_statement": ["f"]}
        event, binding = self.freeze(compiler=lambda record, project: found)
        self.assertEqual(binding, found)
        self.assertEqual((event["data"]["elaborated_type"], event["data"]["defined_in_statement"]), ("∀ n, f n > n", ["f"]))

    def test_event_fields_must_match_the_artifact(self):
        event, _ = self.freeze()
        self.ledger.append("claim_created", NEW, {"text": "Other.", "kind": "theorem"}, ACTOR)
        record = st.build(NEW, "foo", "True")
        digest = self.ledger.put_artifact(st.encode(record))
        self.ledger.append("statement_frozen", NEW, {"artifact": digest, "name": "bar"}, ACTOR)
        with self.assertRaisesRegex(st.StatementError, "does not match its artifact"):
            st.load(self.ledger, NEW)

    def test_statement_copied_to_another_claim_does_not_load(self):
        self.ledger.append("claim_created", NEW, {"text": "Other.", "kind": "theorem"}, ACTOR)
        event, _ = self.freeze()
        self.ledger.append("statement_frozen", NEW, dict(event["data"]), ACTOR)
        with self.assertRaisesRegex(st.StatementError, "belongs to inv/c1"):
            st.load(self.ledger, NEW)
        table, broken = st.statement_challenges(self.ledger)
        self.assertIn(CLAIM, table)
        self.assertIn(NEW, broken)

    def test_later_statement_events_are_ignored(self):
        self.freeze()
        other = st.build(CLAIM, "foo", "False")
        digest = self.ledger.put_artifact(st.encode(other))
        self.ledger.append("statement_frozen", CLAIM, {"artifact": digest}, ACTOR)
        self.assertEqual(st.load(self.ledger, CLAIM)["prop"], "∀ n : ℕ, f n > n")
        s = derive_status(self.ledger.read(), CLAIM, {})
        self.assertIn("this claim has more than one frozen statement; the first one stands", s["warnings"])


class RevisionTests(Base):
    def setUp(self):
        super().setUp()
        self.freeze()
        self.proof = self.ledger.put_artifact(b"theorem foo : True := trivial\n")
        self.ledger.append("check", CLAIM, check(self.proof, "foo"), GATE)
        self.ledger.append("claim_created", NEW, {"text": "Every n has f n ≥ n.", "kind": "theorem"}, ACTOR)

    def test_revision_is_a_new_claim_and_the_old_one_keeps_its_record(self):
        before = derive_status(self.ledger.read(), CLAIM, {})
        self.freeze(claim=NEW, prop="∀ n : ℕ, f n ≥ n", revises=CLAIM)
        after = derive_status(self.ledger.read(), CLAIM, {})
        self.assertEqual(after["headline"], before["headline"])
        self.assertEqual(after["axes"], before["axes"])
        self.assertEqual(after["formal_statement"]["revised_by"], [NEW])
        new = derive_status(self.ledger.read(), NEW, {})
        self.assertEqual(new["formal_statement"]["revises"], CLAIM)
        self.assertEqual(new["headline"], "conjecture")
        self.assertEqual(st.load(self.ledger, CLAIM)["prop"], "∀ n : ℕ, f n > n")

    def test_revision_rules(self):
        with self.assertRaisesRegex(st.StatementError, "cannot revise itself"):
            self.freeze(claim=NEW, revises=NEW)
        with self.assertRaisesRegex(st.StatementError, "has no statement"):
            self.freeze(claim=NEW, revises="inv/none")
        with self.assertRaisesRegex(st.StatementError, "the same as"):
            self.freeze(claim=NEW, revises=CLAIM)
        self.assertEqual(st.frozen(self.ledger, NEW), [])


class JudgeTests(Base):
    def setUp(self):
        super().setUp()
        self.freeze()
        self.record = st.load(self.ledger, CLAIM)
        self.challenge = st.challenge(self.record)
        self.digest = Ledger.artifact_hash(self.challenge)
        self.proof = self.ledger.put_artifact(b"def f (n : Nat) : Nat := n + 1\ntheorem foo : True := trivial\n")
        self.project = Path(self.tmp.name) / "project"

    def test_statement_challenge_is_planned_for_both_polarities(self):
        self.ledger.append("check", CLAIM, check(self.proof, "foo"), GATE)
        self.ledger.append("check", CLAIM, check(self.proof, "foo_negation", "negation"), GATE)
        planned = judge.plan(self.dir)
        self.assertEqual([(j["polarity"], j["target_decl"], j["challenge_hash"]) for j in planned["jobs"]],
                         [("claim", "foo", self.digest), ("negation", "foo_negation", self.digest)])

    def test_check_of_another_theorem_is_not_judged(self):
        self.ledger.append("check", CLAIM, check(self.proof, "foo_weak"), GATE)
        self.ledger.append("check", CLAIM, check(self.proof, "foo", "negation"), GATE)
        planned = judge.plan(self.dir)
        self.assertEqual(planned["jobs"], [])
        self.assertEqual(len(planned["notes"]), 2)
        self.assertIn("must target foo, the statement's theorem", planned["notes"][0])
        self.assertIn("must target foo_negation", planned["notes"][1])

    def test_statement_replaces_a_registered_challenge(self):
        judge.register_challenge(self.ledger, CLAIM, "claim", b"theorem foo : True := sorry\n")
        notes = []
        self.assertEqual(judge.load_challenges(self.ledger, notes), {CLAIM: {"claim": self.digest,
                                                                              "negation": self.digest}})
        self.assertIn("replaces its entry", notes[0])

    def test_unreadable_statement_gives_no_challenge(self):
        judge.register_challenge(self.ledger, CLAIM, "claim", b"theorem foo : True := sorry\n")
        artifact = st.frozen(self.ledger, CLAIM)[0]["data"]["artifact"]
        (self.dir / "artifacts" / artifact).write_bytes(b"tampered")
        notes = []
        self.assertEqual(judge.load_challenges(self.ledger, notes), {})
        self.assertIn("unavailable", notes[0])

    def test_case_uses_the_generated_challenge_and_no_definition_holes(self):
        self.ledger.append("check", CLAIM, check(self.proof, "foo"), GATE)
        log = []
        case = judge.judge_case(self.dir, 0, self.project, runner=fake_runner(log, [0, 1]))
        sandbox, checked = log[3], log[4][1]
        steps = [shlex.split(step.split(" || ")[0]) for step in sandbox[0][-1].split("; ")]
        self.assertEqual(steps[0], ["lake", "build", "Challenge"])
        self.assertEqual(steps[1], st.binding_command(self.record))
        scratch = Path(str(self.project) + "-challenge")
        self.assertEqual(steps[2][5:7], ["statements", str(scratch / ".lake/build/lib/lean/Challenge.olean")])
        cmd = sandbox[0]
        self.assertEqual(cmd[cmd.index("--chdir") + 1], str(scratch))
        writable = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--bind"]
        self.assertEqual(writable, [str(scratch), str(Path(str(self.project) + "-statement"))])
        i = cmd.index("--ro-bind", cmd.index("--ro-bind") + 1)
        self.assertEqual(cmd[i + 1:i + 3], [str(self.project / ".lake" / "packages"), str(scratch / ".lake" / "packages")])
        self.assertGreater(i, max(j for j, arg in enumerate(cmd) if arg == "--bind"))
        self.assertFalse(sandbox[1]["Solution.lean"])
        self.assertFalse(scratch.exists())
        self.assertFalse((self.project / ".lake" / "build").exists())
        self.assertFalse(Path(str(self.project) + "-statement").exists())
        self.assertEqual(case["binding"], {"type": "∀ n, f n > n", "type_explicit": "∀ (n : ℕ), f n > n",
                                           "defined_in_statement": ["f"],
                                           "definitions": {"f": {"type": "ℕ → ℕ", "definition": "fun n => n + 1"}}})
        self.assertEqual(checked["Challenge.lean"], self.challenge)
        config = json.loads(checked["comparator.json"])
        self.assertNotIn("definition_names", config)
        self.assertEqual(config["theorem_names"], ["foo"])
        self.assertEqual(case["result"], "fail")

    def step_fails(self, rc, write=None):
        self.ledger.append("check", CLAIM, check(self.proof, "foo"), GATE)

        def runner(cmd, cwd, timeout):
            if cmd[0] == "bwrap":
                self.assertFalse((Path(cwd) / "Solution.lean").exists())
                if write is not None:
                    out = [w for w in shlex.split(cmd[-1].split("; ")[-1].split(" || ")[0])][-1]
                    Path(out).write_text(write)
                return {"rc": rc, "seconds": 1.0, "output": "error"}
            return {"rc": 0, "seconds": 0.1, "output": ""}
        return judge.judge_case(self.dir, 0, self.project, runner=runner)

    def test_each_failed_challenge_step_is_an_error_not_a_rejection(self):
        for rc, write, note in ((10, None, "the Challenge does not compile"), (11, None, "the statement binding check failed"),
                                (12, None, "the statement could not be printed"),
                                (0, json.dumps({"declarations": []}), "the statement could not be printed"),
                                (0, "x" * 1_000_001, "the statement could not be printed"),
                                (137, None, "the Challenge step failed (rc=137)")):
            with self.subTest(rc=rc, note=note):
                self.setUp()
                case = self.step_fails(rc, write)
                self.assertEqual((case["result"], case["note"]), ("error", note))
                if rc:
                    self.assertEqual(case["output"], "error")
                self.assertNotIn("binding", case)

    def test_legacy_challenge_runs_no_binding_check(self):
        self.ledger.append("claim_created", NEW, {"text": "Other.", "kind": "theorem"}, ACTOR)
        legacy = judge.register_challenge(self.ledger, NEW, "claim", b"theorem bar : True := sorry\n")
        self.ledger.append("check", NEW, check(self.proof, "bar"), GATE)
        log = []
        case = judge.judge_case(self.dir, 0, self.project, runner=fake_runner(log, [0, 0]))
        self.assertEqual(case["challenge_hash"], legacy)
        self.assertFalse(any(cmd[:4] == ["lake", "env", "lean", "--run"] for cmd, _ in log))
        self.assertNotIn("binding", case)

    def test_assembled_report_carries_a_valid_binding_only(self):
        self.ledger.append("check", CLAIM, check(self.proof, "foo"), GATE)
        cases = Path(self.tmp.name) / "cases"
        good = {"type": "T", "type_explicit": "T", "defined_in_statement": ["f"], "definitions": {"f": {"type": "ℕ"}}}
        for binding, kept in ((good, True), ({**good, "type": 3}, False), ({**good, "type_explicit": None}, False),
                              ({**good, "defined_in_statement": [1]}, False), ({**good, "definitions": {}}, False),
                              ({**good, "definitions": {"f": {"body": "x"}}}, False), (None, False)):
            with self.subTest(binding=binding):
                case = judge.judge_case(self.dir, 0, Path(tempfile.mkdtemp(dir=self.tmp.name)) / "p",
                                        runner=fake_runner([], [0, 0]))
                case["binding"] = binding
                (cases / "case-0").mkdir(parents=True, exist_ok=True)
                (cases / "case-0" / "case-0.json").write_text(json.dumps(case))
                result = judge.assemble(self.dir, cases)["results"][0]
                self.assertEqual("binding" in result, kept)
                self.assertEqual(result["result"], "pass" if kept else "error")
                if kept:
                    self.assertEqual(result["binding"], binding)

    def test_case_content_must_match_the_statement(self):
        self.assertEqual(judge.challenge_content(self.ledger, CLAIM, self.digest), self.challenge)
        with self.assertRaises(ValueError):
            judge.challenge_content(self.ledger, CLAIM, "d" * 64)

    def test_assembled_report_has_no_definition_holes(self):
        self.ledger.append("check", CLAIM, check(self.proof, "foo"), GATE)
        cases = Path(self.tmp.name) / "cases"
        cases.mkdir()
        self.assertEqual(judge.assemble(self.dir, cases)["definition_names"], [])


class StatusTests(Base):
    def setUp(self):
        super().setUp()
        self.freeze()
        self.digest = Ledger.artifact_hash(st.challenge(st.load(self.ledger, CLAIM)))
        self.proof = self.ledger.put_artifact(b"theorem foo : True := trivial\n")
        self.ledger.append("check", CLAIM, check(self.proof, "foo"), GATE)

    def judged(self, **overrides):
        entry = {"claim": CLAIM, "seq": 2, "artifact": self.proof, "target_decl": "foo", "polarity": "claim",
                 "challenge_hash": self.digest, "result": "pass"}
        return entry | overrides

    def test_unsigned_statement_stays_at_judged_unreviewed(self):
        s = derive_status(self.ledger.read(), CLAIM, {"judged": [self.judged()]})
        self.assertEqual(s["headline"], "judged-unreviewed")
        self.assertIn("statement signature", s["missing"])
        self.assertFalse(s["formal_statement"]["signed"])
        self.assertTrue(s["verdict"].startswith("UNVERIFIED"))

    def report(self, results, seq=None):
        events = self.ledger.read()
        seq = events[-1]["seq"] if seq is None else seq
        return json.dumps({"format": judge.FORMAT, "judge_version": judge.JUDGE_VERSION, "ledger_path": "ledger",
                           "ledger_genesis": Ledger.event_hash(events[0]), "ledger_seq": seq,
                           "ledger_head": Ledger.event_hash(events[seq]), **judge.pins(), "sandboxed": True,
                           "permitted_axioms": judge.PERMITTED_AXIOMS, "definition_names": [], "notes": [],
                           "results": results}).encode()

    def test_pass_needs_the_statement_inside_the_report(self):
        other = Base.setUp  # noqa: F841
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ledger = Ledger.init(Path(tmp.name) / "l")
        ledger.append("claim_created", CLAIM, {"text": "c", "kind": "theorem"}, ACTOR)
        record = st.build(CLAIM, "foo", "True")
        digest = Ledger.artifact_hash(st.challenge(record))
        ledger.put_artifact(st.challenge(record))
        judge.register_challenge(ledger, CLAIM, "claim", st.challenge(record))
        proof = ledger.put_artifact(b"theorem foo_negation : True := trivial\n")
        ledger.append("check", CLAIM, check(proof, "foo_negation"), GATE)
        entry = {"claim": CLAIM, "seq": 1, "artifact": proof, "target_decl": "foo_negation", "polarity": "claim",
                 "challenge_hash": digest, "result": "pass", "seconds": 1.0}
        content = self.report.__func__(type("R", (), {"ledger": ledger})(), [entry])
        st.record_statement(ledger, CLAIM, "foo", "True", actor=ACTOR)
        judged, notes = authority.tier_results(content, ledger)
        self.assertEqual(judged, [])
        self.assertTrue(any("frozen after the report" in n for n in notes), notes)

    def test_pass_must_target_the_statement_theorem_but_a_rejection_stays(self):
        wrong = self.ledger.put_artifact(b"theorem foo_negation : True := trivial\n")
        self.ledger.append("check", CLAIM, check(wrong, "foo_negation"), GATE)
        self.ledger.append("check", CLAIM, check(wrong, "foo_negation", result="pass"), GATE)
        results = [self.judged(seq=3, artifact=wrong, target_decl="foo_negation", seconds=1.0),
                   self.judged(seq=2, result="fail", seconds=1.0)]
        judged, notes = authority.tier_results(self.report(results), self.ledger)
        self.assertEqual([(r["seq"], r["result"]) for r in judged], [(2, "fail")])
        self.assertTrue(any("does not target the statement's theorem" in n for n in notes), notes)

    def test_pass_counts_only_with_the_printed_statement(self):
        printed = {"type": "T", "type_explicit": "T", "defined_in_statement": [], "definitions": {}}
        with_binding = self.judged(seconds=1.0, binding=printed)
        judged, _ = authority.tier_results(self.report([with_binding]), self.ledger)
        self.assertEqual([r["result"] for r in judged], ["pass"])
        for binding in (None, {**printed, "type": 5}):
            entry = self.judged(seconds=1.0, binding=binding) if binding else self.judged(seconds=1.0)
            judged, notes = authority.tier_results(self.report([entry]), self.ledger)
            self.assertEqual(judged, [])
            self.assertTrue(any("does not show the statement" in n for n in notes), notes)

    def test_authority_drops_a_pass_against_an_older_challenge(self):
        self.ledger.append("claim_created", NEW, {"text": "Other.", "kind": "theorem"}, ACTOR)
        events = self.ledger.read()
        report = {"format": judge.FORMAT, "judge_version": judge.JUDGE_VERSION, "ledger_path": "ledger",
                  "ledger_genesis": Ledger.event_hash(events[0]), "ledger_seq": events[-1]["seq"],
                  "ledger_head": Ledger.event_hash(events[-1]), **judge.pins(), "sandboxed": True,
                  "permitted_axioms": judge.PERMITTED_AXIOMS, "definition_names": [], "notes": [],
                  "results": [self.judged(seconds=1.0, challenge_hash="d" * 64),
                              self.judged(seconds=1.0, result="fail", challenge_hash="d" * 64)]}
        judged, notes = authority.tier_results(json.dumps(report).encode(), self.ledger)
        self.assertEqual([r["result"] for r in judged], ["fail"])
        self.assertTrue(any("ignored a pass" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
