"""S2.1.T7: the authoritative judge, its report, and what derivation does with it.

No Lean runs here: the comparator is replaced by a fake runner, and `gh` by a fake command. What is
tested is everything around them: which jobs are planned, what files the comparator sees, how a
report is matched to the ledger, and that nothing reaches above judged-unreviewed.
"""

import io
import json
import random
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import _paths  # noqa: F401
from mathproof_core import authority, judge
from mathproof_core.ledger import Ledger
from mathproof_core.status import derive_status

ACTOR = {"context_id": "t", "role": "gate", "kind": "runner"}
CLAIM = "inv/c1"
H = "c" * 64


def check_data(artifact, polarity="claim", result="pass", target="main_theorem"):
    return {"artifact": artifact, "target_decl": target, "polarity": polarity, "result": result,
            "report_hash": H, "pins": {}, "tier": "local"}


class LedgerCase(unittest.TestCase):
    """A ledger with one claim, a proof, and a registered Challenge."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "ledger"
        self.ledger = Ledger.init(self.dir)
        self.ledger.append("claim_created", CLAIM, {"text": "A claim.", "kind": "theorem"}, ACTOR)
        self.proof = self.ledger.put_artifact(b"theorem main_theorem : True := trivial\n")
        self.statement = judge.register_challenge(self.ledger, CLAIM, "claim", b"theorem main_theorem : True := sorry\n")
        self.ledger.append("check", CLAIM, check_data(self.proof), ACTOR)

    def tearDown(self):
        self.tmp.cleanup()

    def report(self, results=None, **overrides):
        events = self.ledger.read()
        base = {"format": judge.FORMAT, "judge_version": judge.JUDGE_VERSION, "ledger_path": "ledger", "ledger_genesis": Ledger.event_hash(events[0]), "ledger_seq": events[-1]["seq"], "ledger_head": Ledger.event_hash(events[-1]),
                **judge.pins(), "sandboxed": True, "permitted_axioms": judge.PERMITTED_AXIOMS,
                "definition_names": [], "notes": [],
                "results": results if results is not None else [self.result()]}
        base.update(overrides)
        return json.dumps(base).encode()

    def result(self, **overrides):
        base = {"seq": 1, "claim": CLAIM, "artifact": self.proof, "target_decl": "main_theorem", "polarity": "claim",
                "challenge_hash": self.statement, "result": "pass", "seconds": 1.0}
        base.update(overrides)
        return base


def status(ledger, env):
    return derive_status(ledger.read(), CLAIM, env)


class StatusTests(LedgerCase):
    def judged(self, **overrides):
        entry = {"claim": CLAIM, "seq": 1, "artifact": self.proof, "target_decl": "main_theorem", "polarity": "claim",
                 "challenge_hash": self.statement, "result": "pass"}
        entry.update(overrides)
        return entry

    def test_no_env_stays_local(self):
        self.assertEqual(status(self.ledger, {})["headline"], "kernel-passed-local")

    def test_judged_pass_is_judged_unreviewed_and_never_valid(self):
        s = status(self.ledger, {"judged": [self.judged()]})
        self.assertEqual(s["headline"], "judged-unreviewed")
        self.assertEqual(s["axes"]["kernel"], "judged")
        self.assertEqual(s["verdict"], "UNVERIFIED")
        self.assertEqual(s["missing"], ["statement signature", "fidelity signature", "vacuity witness"])
        self.assertIn("missing: statement signature, fidelity signature, vacuity witness", s["lean_status"])

    def test_negation_needs_no_vacuity_witness(self):
        self.ledger.append("check", CLAIM, check_data(self.proof, polarity="negation"), ACTOR)
        self.ledger.append("check", CLAIM, check_data(self.proof, result="fail"), ACTOR)
        s = status(self.ledger, {"judged": [self.judged(polarity="negation", seq=2)]})
        self.assertEqual(s["headline"], "judged-unreviewed")
        self.assertEqual(s["missing"], ["statement signature", "fidelity signature"])

    def test_judged_fail_is_judge_rejected(self):
        s = status(self.ledger, {"judged": [self.judged(result="fail")]})
        self.assertEqual(s["headline"], "judge-rejected")
        self.assertEqual(s["axes"]["kernel"], "judge-rejected")
        self.assertEqual((s["verdict"], s["lean_status"]), ("UNVERIFIED", "LEAN-FAILED"))

    def test_rejection_beats_acceptance(self):
        s = status(self.ledger, {"judged": [self.judged(), self.judged(result="fail")]})
        self.assertEqual(s["headline"], "judge-rejected")
        self.assertEqual(s["missing"], [])

    def test_rejection_of_one_artifact_beats_another_accepted(self):
        other = self.ledger.put_artifact(b"other proof")
        self.ledger.append("check", CLAIM, check_data(other), ACTOR)
        s = status(self.ledger, {"judged": [self.judged(), self.judged(artifact=other, seq=2, result="fail")]})
        self.assertEqual(s["headline"], "judge-rejected")

    def test_result_must_match_a_passing_local_check(self):
        for entry in (self.judged(artifact="d" * 64), self.judged(target_decl="other"),
                      self.judged(polarity="negation")):
            self.assertEqual(status(self.ledger, {"judged": [entry]})["headline"], "kernel-passed-local", entry)

    def test_local_failure_of_same_artifact_is_not_judged(self):
        self.ledger.append("check", CLAIM, check_data(self.proof, result="fail"), ACTOR)
        self.assertNotIn(status(self.ledger, {"judged": [self.judged()]})["headline"],
                         ("judged-unreviewed",))

    def test_step_checks_are_never_judged(self):
        self.ledger.append("check", CLAIM, check_data(self.proof, polarity="step", target="lemma1"), ACTOR)
        s = status(self.ledger, {"judged": [self.judged(polarity="step", target_decl="lemma1")]})
        self.assertEqual(s["headline"], "kernel-passed-local")

    def test_malformed_env_is_ignored(self):
        for env in ({"judged": "yes"}, {"judged": [1, None, "x"]}, {"judged": [self.judged(challenge_hash="x")]},
                    {"judged": [self.judged(challenge_hash=None)]}, {"judged": [self.judged(result="PASS")]},
                    {"judged": [self.judged(artifact=None)]}, {"judged": [self.judged(result="error")]}, None,
                    {"judged": [self.judged(artifact=[self.proof])]}, {"judged": [self.judged(polarity={"claim": 1})]},
                    {"judged": [self.judged(seq=True)]}, {"judged": [self.judged(seq="1")]},
                    {"judged": [self.judged(seq=0)]}, {"judged": [self.judged(seq=7)]}):
            self.assertEqual(status(self.ledger, env)["headline"], "kernel-passed-local", env)

    def test_a1_result_does_not_carry_to_another_claim(self):
        other = "inv/c2"
        self.ledger.append("claim_created", other, {"text": "Hard.", "kind": "theorem"}, ACTOR)
        self.ledger.append("check", other, check_data(self.proof), ACTOR)
        for result in ("pass", "fail"):
            env = {"judged": [self.judged(result=result)]}
            self.assertEqual(derive_status(self.ledger.read(), other, env)["headline"], "kernel-passed-local", result)
            forged = {"judged": [self.judged(result=result, claim=other)]}
            self.assertEqual(derive_status(self.ledger.read(), other, forged)["headline"], "kernel-passed-local")

    def test_result_counts_only_for_the_event_it_names(self):
        self.ledger.append("check", CLAIM, check_data(self.proof), ACTOR)
        self.assertEqual(status(self.ledger, {"judged": [self.judged(seq=2)]})["headline"], "judged-unreviewed")
        self.assertEqual(status(self.ledger, {"judged": [self.judged(seq=0)]})["headline"], "kernel-passed-local")

    def test_conflict_beats_judgment(self):
        self.ledger.append("check", CLAIM, check_data(self.proof, polarity="negation"), ACTOR)
        self.assertEqual(status(self.ledger, {"judged": [self.judged()]})["headline"], "conflict")

    def test_unfaithful_judgment_is_blocked(self):
        self.ledger.append("fidelity", CLAIM, {"statement_hash": self.proof, "rows": [], "class": "unfaithful",
                                                "direction": "F=>I", "scope_note": "", "judge": "self-declared"}, ACTOR)
        s = status(self.ledger, {"judged": [self.judged()]})
        self.assertEqual((s["headline"], s["blocked"]), ("judged-unreviewed", ["unfaithful"]))

    def test_no_env_can_reach_valid_or_invalid(self):
        rng = random.Random(7)
        other = self.ledger.put_artifact(b"x")
        for _ in range(300):
            entries = [self.judged(artifact=rng.choice([self.proof, other]), polarity=rng.choice(["claim", "negation"]),
                                   result=rng.choice(["pass", "fail"])) for _ in range(rng.randint(0, 4))]
            s = status(self.ledger, {"judged": entries})
            self.assertTrue(s["verdict"].startswith("UNVERIFIED") or s["verdict"] == "INCOMPLETE", s)


def fake_runner(log, rcs):
    """Record each call and the project files the comparator would see; return the next rc.

    `lake update` and `lake exe cache get` always succeed and take no rc from the list.
    """
    def run(cmd, cwd, timeout):
        if cmd[:2] == ["lake", "update"] or cmd[:3] == ["lake", "exe", "cache"]:
            log.append((cmd, {}))
            return {"rc": 0, "seconds": 0.1, "output": ""}
        files = {name: (Path(cwd) / name).read_bytes() for name in ("Challenge.lean", "Solution.lean", "comparator.json")
                 if (Path(cwd) / name).exists()}
        log.append((cmd, files))
        return {"rc": rcs.pop(0), "seconds": 0.5, "output": "out"}
    return run


class JudgeTests(LedgerCase):
    def setUp(self):
        super().setUp()
        self.project = Path(self.tmp.name) / "project"
        self.cases = Path(self.tmp.name) / "cases"
        self.cases.mkdir()

    def case(self, rcs, index=0):
        return judge.judge_case(self.dir, index, self.project, runner=fake_runner([], rcs))

    def test_plan_skips_steps_and_unregistered_and_dedupes(self):
        self.ledger.append("check", CLAIM, check_data(self.proof), ACTOR)
        self.ledger.append("check", CLAIM, check_data(self.proof, polarity="step", target="lemma1"), ACTOR)
        self.ledger.append("check", CLAIM, check_data(self.proof, polarity="negation"), ACTOR)
        planned = judge.plan(self.dir)
        self.assertEqual([(j["seq"], j["polarity"]) for j in planned["jobs"]], [(1, "claim")])
        self.assertEqual(len(planned["notes"]), 1)
        self.assertIn("no Challenge registered", planned["notes"][0])
        events = self.ledger.read()
        self.assertEqual((planned["ledger_seq"], planned["ledger_head"]), (4, Ledger.event_hash(events[-1])))

    def test_plan_keeps_one_job_per_claim(self):
        self.ledger.append("claim_created", "inv/c2", {"text": "Other.", "kind": "theorem"}, ACTOR)
        (self.dir / judge.CHALLENGES_FILE).write_text(json.dumps({CLAIM: {"claim": self.statement},
                                                                  "inv/c2": {"claim": self.statement}}))
        self.ledger.append("check", "inv/c2", check_data(self.proof), ACTOR)
        self.assertEqual([j["claim"] for j in judge.plan(self.dir)["jobs"]], [CLAIM, "inv/c2"])

    def test_plan_rejects_odd_target_names(self):
        self.ledger.append("check", CLAIM, check_data(self.proof, target="x; rm -rf /"), ACTOR)
        planned = judge.plan(self.dir)
        self.assertEqual(len(planned["jobs"]), 1)
        self.assertIn("not a plain declaration name", planned["notes"][0])

    def test_case_prepares_then_control_then_only_comparator_with_exact_files(self):
        log = []
        case = judge.judge_case(self.dir, 0, self.project, runner=fake_runner(log, [0, 0]))
        self.assertEqual([cmd for cmd, _ in log], [["lake", "update"], ["lake", "exe", "cache", "get"],
                                                   ["lake", "comparator"], ["lake", "comparator"]])
        control, checked = log[2][1], log[3][1]
        self.assertIn(b"judge_control", control["Challenge.lean"])
        self.assertEqual(checked["Challenge.lean"], self.ledger.get_artifact(self.statement))
        self.assertEqual(checked["Solution.lean"], self.ledger.get_artifact(self.proof))
        config = json.loads(checked["comparator.json"])
        self.assertEqual(config["theorem_names"], ["main_theorem"])
        self.assertEqual(config["permitted_axioms"], judge.PERMITTED_AXIOMS)
        self.assertEqual((case["index"], case["seq"], case["result"]), (0, 1, "pass"))
        self.assertIn("lakefile.toml", {p.name for p in self.project.iterdir()})

    def test_case_needs_a_fresh_project_directory(self):
        self.project.mkdir()
        with self.assertRaises(FileExistsError):
            self.case([0, 0])

    def test_outcomes(self):
        for n, (rc, want) in enumerate(((1, "fail"), (137, "fail"), ("timeout", "error"))):
            self.project = Path(self.tmp.name) / f"project{n}"
            self.assertEqual(self.case([0, rc])["result"], want, rc)

    def test_failed_control_writes_nothing(self):
        with self.assertRaises(judge.JudgeError):
            self.case([1])

    def test_bad_index(self):
        for index in (1, -1, True):
            with self.assertRaises(judge.JudgeError):
                self.case([0, 0], index=index)

    def test_broken_ledger_is_refused(self):
        lines = self.ledger.events_path.read_bytes().splitlines(keepends=True)
        self.ledger.events_path.write_bytes(lines[0] + lines[1].replace(b"theorem", b"Theorem"))
        with self.assertRaises(judge.JudgeError):
            judge.plan(self.dir)

    def test_a3_missing_challenge_artifact_is_an_error_result(self):
        (self.dir / judge.CHALLENGES_FILE).write_text(json.dumps({CLAIM: {"claim": "e" * 64}}))
        case = self.case([])
        self.assertEqual(case["result"], "error")
        self.assertFalse(self.project.exists())

    def test_r2_deep_challenges_file_is_a_judge_error(self):
        (self.dir / judge.CHALLENGES_FILE).write_text("[" * 100000 + "]" * 100000)
        with self.assertRaises(judge.JudgeError):
            judge.plan(self.dir)
        content = MatchTests.report(self)
        self.assertEqual(authority.tier_results(content, self.ledger)[0], [])

    def test_a5_comparator_gets_no_tokens_or_git_config(self):
        script = self.project.parent / "env.py"
        script.write_text("import json, os, sys; json.dump(dict(os.environ), open(sys.argv[1], 'w'))")
        out = self.project.parent / "env.json"
        saved = dict(judge.os.environ)
        try:
            judge.os.environ.update({"ACTIONS_ID_TOKEN_REQUEST_TOKEN": "secret", "GITHUB_TOKEN": "secret",
                                     "ACTIONS_RUNTIME_TOKEN": "secret"})
            judge.run([sys.executable, str(script), str(out)], self.project.parent, 30)
        finally:
            judge.os.environ.clear()
            judge.os.environ.update(saved)
        env = json.loads(out.read_text())
        self.assertNotIn("secret", env.values())
        self.assertEqual((env["GIT_CONFIG_GLOBAL"], env["GIT_CONFIG_NOSYSTEM"]), ("/dev/null", "1"))

    def test_r4_lingering_children_are_killed(self):
        started, marker = self.project.parent / "started.txt", self.project.parent / "late.txt"
        late = self.project.parent / "late.py"
        late.write_text(f"import time\nopen({str(started)!r}, 'w').write('x')\ntime.sleep(2)\n"
                        f"open({str(marker)!r}, 'w').write('late')\n")
        script = self.project.parent / "fork.py"
        # The child starts the grandchild and returns only once it is running.
        script.write_text("import os, subprocess, sys, time\n"
                          f"subprocess.Popen([sys.executable, {str(late)!r}], stdout=subprocess.DEVNULL,\n"
                          "                 stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)\n"
                          f"while not os.path.exists({str(started)!r}):\n    time.sleep(0.05)\n")
        judge.run([sys.executable, str(script)], self.project.parent, 60)
        self.assertTrue(started.exists())
        time.sleep(4)
        self.assertFalse(marker.exists())

    def write_case_file(self, index=0, **overrides):
        case = self.case([0, 0]) if not overrides.pop("_skip_run", False) else {}
        case.update(overrides)
        (self.cases / f"case-{index}").mkdir(exist_ok=True)
        (self.cases / f"case-{index}" / f"case-{index}.json").write_text(json.dumps(case))
        return case

    def test_assemble_accepts_the_assigned_job(self):
        self.write_case_file()
        report = judge.assemble(self.dir, self.cases)
        self.assertEqual([r["result"] for r in report["results"]], ["pass"])
        self.assertEqual(report["notes"], [])
        self.assertEqual(authority.tier_results(json.dumps(report).encode(), self.ledger)[0][0]["result"], "pass")

    def test_assemble_rejects_misassigned_or_malformed_cases(self):
        for overrides in ({"seq": 0}, {"artifact": "d" * 64}, {"claim": "inv/c2"}, {"polarity": "negation"},
                          {"challenge_hash": "d" * 64}, {"target_decl": "x"}, {"format": "x"},
                          {"result": "PASS"}, {"result": None}):
            self.project = Path(self.tmp.name) / f"p-{len(list(self.cases.iterdir()))}-{id(overrides)}"
            self.write_case_file(**overrides)
            report = judge.assemble(self.dir, self.cases)
            self.assertEqual(report["results"][0]["result"], "error", overrides)
            self.assertEqual(len(report["notes"]), 1, overrides)
        for raw in (b"", b"[]", b"{bad", b"[" * 100000):
            (self.cases / "case-0" / "case-0.json").write_bytes(raw)
            self.assertEqual(judge.assemble(self.dir, self.cases)["results"][0]["result"], "error", raw[:5])

    def test_assemble_matches_each_case_file_to_its_job(self):
        judge.register_challenge(self.ledger, CLAIM, "negation", b"theorem main_theorem : False := sorry\n")
        self.ledger.append("check", CLAIM, check_data(self.proof, polarity="negation"), ACTOR)
        self.write_case_file()
        self.project = Path(self.tmp.name) / "project-second"
        second = judge.judge_case(self.dir, 1, self.project, runner=fake_runner([], [0, 1]))
        (self.cases / "case-1").mkdir()
        (self.cases / "case-1" / "case-1.json").write_text(json.dumps(second))
        report = judge.assemble(self.dir, self.cases)
        self.assertEqual([(r["polarity"], r["result"]) for r in report["results"]], [("claim", "pass"), ("negation", "fail")])
        (self.cases / "case-1" / "case-1.json").write_text((self.cases / "case-0" / "case-0.json").read_text())
        self.assertEqual(judge.assemble(self.dir, self.cases)["results"][1]["result"], "error")

    def test_t1_case_directory_must_hold_exactly_its_own_file(self):
        self.write_case_file()
        good = (self.cases / "case-0" / "case-0.json").read_text()
        layouts = [
            lambda d: (d / "extra.json").write_text("{}"),
            lambda d: ((d / "case-0.json").unlink(), (d / "case-0.json").mkdir()),
            lambda d: ((d / "case-0.json").unlink(), (d / "real.json").write_text(good),
                       (d / "case-0.json").symlink_to(d / "real.json")),
            lambda d: ((d / "case-0.json").unlink(), (d / "nested").mkdir(), (d / "nested" / "case-0.json").write_text(good)),
            lambda d: ((d / "case-0.json").unlink(), (d.parent / "outside.json").write_text(good),
                       (d / "case-0.json").symlink_to(d.parent / "outside.json")),
        ]
        import shutil
        for layout in layouts:
            directory = self.cases / "case-0"
            shutil.rmtree(directory)
            directory.mkdir()
            (directory / "case-0.json").write_text(good)
            layout(directory)
            self.assertEqual(judge.assemble(self.dir, self.cases)["results"][0]["result"], "error")
        shutil.rmtree(self.cases / "case-0")
        (self.cases / "elsewhere").mkdir()
        (self.cases / "elsewhere" / "case-0.json").write_text(good)
        (self.cases / "case-0").symlink_to(self.cases / "elsewhere")
        self.assertEqual(judge.assemble(self.dir, self.cases)["results"][0]["result"], "error")
        (self.cases / "case-0").unlink()
        (self.cases / "case-0.json").write_text(good)  # the old merged layout no longer counts
        self.assertEqual(judge.assemble(self.dir, self.cases)["results"][0]["result"], "error")

    def test_assemble_reads_only_planned_case_files(self):
        self.write_case_file()
        (self.cases / "case-1").mkdir()
        (self.cases / "case-1" / "case-1.json").write_text((self.cases / "case-0" / "case-0.json").read_text())
        self.assertEqual(len(judge.assemble(self.dir, self.cases)["results"]), 1)


class AttestationTests(unittest.TestCase):
    def test_command_pins_workflow_ref_and_runners(self):
        cmd = authority.attestation_command(Path("r.json"), "own/repo")
        self.assertEqual(cmd[:4], ["gh", "attestation", "verify", "r.json"])
        joined = " ".join(cmd)
        for part in ("--repo own/repo", "--signer-workflow own/repo/.github/workflows/authoritative.yml",
                     "--source-ref refs/heads/main", "--deny-self-hosted-runners"):
            self.assertIn(part, joined)

    def test_bad_repo_names_never_reach_gh(self):
        calls = []
        for repo in ("own", "own/repo --x", "../x/y", "own/../repo", "-x/y", ""):
            reason = authority.check_attestation(b"{}", repo, run=lambda *a, **k: calls.append(a))
            self.assertIsNotNone(reason, repo)
        self.assertEqual(calls, [])

    def test_verifies_exactly_the_bytes_read(self):
        seen = []

        def run(cmd, **kwargs):
            seen.append(Path(cmd[3]).read_bytes())
            return subprocess.CompletedProcess(cmd, 0, "", "")
        self.assertIsNone(authority.check_attestation(b"exact bytes", "own/repo", run=run))
        self.assertEqual(seen, [b"exact bytes"])

    def test_failure_and_missing_gh(self):
        fail = lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, "", "no attestations found\n")  # noqa: E731
        self.assertIn("no attestations found", authority.check_attestation(b"x", "own/repo", run=fail))

        def missing(cmd, **k):
            raise FileNotFoundError("gh")
        self.assertIn("could not run", authority.check_attestation(b"x", "own/repo", run=missing))


class MatchTests(LedgerCase):
    def match(self, content):
        return authority.tier_results(content, self.ledger)

    def test_good_report_matches(self):
        judged, notes = self.match(self.report())
        self.assertEqual(notes, [])
        self.assertEqual(judged, [{"claim": CLAIM, "seq": 1, "artifact": self.proof, "target_decl": "main_theorem", "polarity": "claim",
                                   "challenge_hash": self.statement, "result": "pass"}])
        self.assertEqual(status(self.ledger, {"judged": judged})["headline"], "judged-unreviewed")

    def test_report_shape_problems(self):
        for content in (b"not json", b"[]", self.report(format="other"), self.report(sandboxed=False),
                        self.report(sandboxed="true"), self.report(toolchain="leanprover/lean4:v4.32.0"),
                        self.report(mathlib_rev="v4.32.0"), self.report(ledger_seq=True), self.report(ledger_seq=-1),
                        self.report(ledger_head="x"), self.report(results={}), self.report(judge_version=0),
                        self.report(judge_version=True), self.report(judge_version=float(judge.JUDGE_VERSION)), self.report(judge_version=str(judge.JUDGE_VERSION)), self.report(permitted_axioms=judge.PERMITTED_AXIOMS + ["sorryAx"]),
                        self.report(definition_names=["frob"])):
            judged, notes = self.match(content)
            self.assertEqual(judged, [], content)
            self.assertEqual(len(notes), 1, content)

    def test_head_must_be_in_this_ledger(self):
        for overrides in ({"ledger_head": "d" * 64}, {"ledger_seq": 9}, {"ledger_seq": 0}):
            judged, notes = self.match(self.report(**overrides))
            self.assertEqual(judged, [], overrides)

    def test_events_after_the_head_are_not_covered(self):
        content = self.report()
        self.ledger.append("check", CLAIM, check_data(self.proof), ACTOR)
        judged, notes = self.match(self.report(ledger_seq=1, ledger_head=json.loads(content)["ledger_head"],
                                               results=[self.result(), self.result(seq=2)]))
        self.assertEqual(len(judged), 1)
        self.assertIn("not covered", notes[0])

    def test_a1_report_does_not_judge_another_claim(self):
        content = self.report()
        self.ledger.append("claim_created", "inv/c2", {"text": "Hard.", "kind": "theorem"}, ACTOR)
        self.ledger.append("check", "inv/c2", check_data(self.proof), ACTOR)
        judged, _ = self.match(content)
        self.assertEqual(derive_status(self.ledger.read(), "inv/c2", {"judged": judged})["headline"],
                         "kernel-passed-local")
        self.assertEqual(status(self.ledger, {"judged": judged})["headline"], "judged-unreviewed")

    def test_broken_chain_is_refused(self):
        content = self.report()
        lines = self.ledger.events_path.read_bytes().splitlines(keepends=True)
        self.ledger.events_path.write_bytes(lines[0].replace(b"A claim.", b"B claim.") + lines[1])
        self.assertEqual(self.match(content)[0], [])

    def test_result_must_name_its_check(self):
        for overrides in ({"artifact": "d" * 64}, {"target_decl": "x"}, {"polarity": "negation"},
                          {"claim": "inv/c2"}, {"seq": 0}, {"seq": "1"}, {"seq": True}):
            judged, notes = self.match(self.report(results=[self.result(**overrides)]))
            self.assertEqual(judged, [], overrides)
            self.assertEqual(len(notes), 1, overrides)

    def test_challenge_must_be_the_registered_one(self):
        content = self.report()
        judge.register_challenge(self.ledger, CLAIM, "claim", b"theorem main_theorem : False := sorry\n")
        judged, notes = self.match(content)
        self.assertEqual(judged, [])
        self.assertIn("Challenge is not the one registered", notes[0])

    def test_report_must_name_its_ledger(self):
        report = json.loads(self.report())
        del report["ledger_path"]
        self.assertEqual(self.match(json.dumps(report).encode()), ([], ["report does not name its ledger"]))
        self.assertEqual(self.match(self.report(ledger_path=7)), ([], ["report does not name its ledger"]))
        self.assertEqual(self.match(self.report(ledger_genesis="x")), ([], ["report ledger_genesis is not a hash"]))

    def test_undecided_and_malformed_results(self):
        judged, notes = self.match(self.report(results=[self.result(result="error"), {"seq": 1}, "x"]))
        self.assertEqual(judged, [])
        self.assertEqual(len(notes), 3)

    def test_a2_bad_challenges_file_is_a_note(self):
        content = self.report()
        for raw in (b"[]", b"{not json", b"\xff\xfe"):
            (self.dir / judge.CHALLENGES_FILE).write_bytes(raw)
            judged, notes = self.match(content)
            self.assertEqual(judged, [], raw)
            self.assertIn("cannot be read", notes[0], raw)

    def test_a2b_missing_report_is_a_note(self):
        out = authority.load_authoritative(Path(self.tmp.name) / "none.json", "own/repo", self.ledger, "ledger")
        self.assertEqual(out["judged"], [])
        self.assertIn("cannot read it", out["notes"][0])

    def test_unattested_report_gives_nothing(self):
        path = Path(self.tmp.name) / "r.json"
        path.write_bytes(self.report())
        fail = lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, "", "bad\n")  # noqa: E731
        out = authority.load_authoritative(path, "own/repo", self.ledger, "ledger", run=fail)
        self.assertEqual(out["judged"], [])
        self.assertIn("judge report ignored", out["notes"][1])
        self.assertEqual(out["violations"], [])
        ok = lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "", "")  # noqa: E731
        self.assertEqual(len(authority.load_authoritative(path, "own/repo", self.ledger, "ledger", run=ok)["judged"]), 1)


def rechain(ledger, drop):
    """Rewrite the ledger without event `drop`, renumbered and re-hashed so the chain verifies."""
    kept = [e for e in ledger.read() if e["seq"] != drop]
    prev = "0" * 64
    lines = []
    for seq, event in enumerate(kept):
        event = {**event, "seq": seq, "prev": prev}
        event["hash"] = Ledger.event_hash(event)
        prev = event["hash"]
        lines.append(json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    ledger.events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class FakeGitHub:
    """`gh run list`, `gh run download` and `gh attestation verify`, over a dict of run id -> report bytes."""

    def __init__(self, runs, attested=None, list_rc=0):
        self.runs, self.attested, self.list_rc, self.calls = runs, attested, list_rc, []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        if cmd[:3] == ["gh", "run", "list"]:
            body = json.dumps([{"databaseId": int(i)} for i in self.runs])
            return subprocess.CompletedProcess(cmd, self.list_rc, body, "boom" if self.list_rc else "")
        if cmd[:3] == ["gh", "run", "download"]:
            content = self.runs[cmd[3]]
            if content is None:
                return subprocess.CompletedProcess(cmd, 1, "", "no artifact")
            Path(cmd[cmd.index("-D") + 1], "judge-report.json").write_bytes(content)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:3] == ["gh", "attestation", "verify"]:
            content = Path(cmd[3]).read_bytes()
            ok = self.attested is None or content in self.attested
            return subprocess.CompletedProcess(cmd, 0 if ok else 1, "", "" if ok else "no attestations found")
        raise AssertionError(cmd)


class AnchorTests(LedgerCase):
    """S1.3.T4: every attested report for this ledger is an anchor the ledger must extend."""

    def add_failed_check(self):
        self.ledger.append("check", CLAIM, check_data(self.proof, result="fail"), ACTOR)

    def latest(self, gh):
        return authority.load_authoritative("latest", "own/repo", self.ledger, "ledger", run=gh)

    def test_deleting_a_failed_check_after_an_anchor_is_detected(self):
        self.add_failed_check()
        anchored = self.report()
        rechain(self.ledger, 2)
        self.assertEqual(self.ledger.verify().errors, [])
        out = self.latest(FakeGitHub({"1": anchored}))
        self.assertEqual(out["judged"], [])
        self.assertEqual(len(out["violations"]), 1)
        self.assertIn("does not extend the anchored head, event 2", out["violations"][0])

    def test_deleting_a_middle_event_and_refilling_the_length_is_detected(self):
        self.add_failed_check()
        self.ledger.append("check", CLAIM, check_data(self.proof), ACTOR)
        anchored = self.report()
        rechain(self.ledger, 2)
        self.ledger.append("check", CLAIM, check_data(self.proof), ACTOR)
        self.assertEqual(len(self.ledger.read()), 4)
        out = self.latest(FakeGitHub({"1": anchored}))
        self.assertEqual(len(out["violations"]), 1)

    def test_editing_an_early_event_without_rechaining_is_a_violation(self):
        anchored = self.report()
        lines = self.ledger.events_path.read_text(encoding="utf-8").splitlines()
        first = json.loads(lines[0])
        first["data"]["text"] = "A different claim."
        lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.ledger.events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertNotEqual(self.ledger.verify().errors, [])
        out = self.latest(FakeGitHub({"1": anchored}))
        self.assertEqual(len(out["violations"]), 1)

    def test_a_later_anchor_on_the_rewritten_ledger_does_not_hide_the_old_one(self):
        self.add_failed_check()
        old = self.report()
        rechain(self.ledger, 2)
        new = self.report()
        out = self.latest(FakeGitHub({"2": new, "1": old}))
        self.assertEqual(len(out["violations"]), 1)
        self.assertIn("1:", out["violations"][0])
        self.assertEqual([a["source"] for a in out["anchors"]], ["2"])

    def test_a_given_report_file_is_checked_as_an_anchor_too(self):
        self.add_failed_check()
        path = Path(self.tmp.name) / "r.json"
        path.write_bytes(self.report())
        rechain(self.ledger, 2)
        out = authority.load_authoritative(path, "own/repo", self.ledger, "ledger", run=FakeGitHub({}))
        self.assertEqual(len(out["violations"]), 1)

    def test_events_after_the_newest_anchor_are_allowed(self):
        anchored = self.report()
        self.add_failed_check()
        out = self.latest(FakeGitHub({"1": anchored}))
        self.assertEqual(out["violations"], [])
        self.assertEqual(len(out["judged"]), 1)
        self.assertEqual(out["anchors"], [{"source": "1", "ledger_path": "ledger", "ledger_seq": 1, "ledger_head": json.loads(anchored)["ledger_head"]}])

    def test_an_older_rejection_is_not_hidden_by_a_newer_run(self):
        first = self.report(results=[self.result(result="fail")])
        self.ledger.append("check", CLAIM, check_data(self.ledger.put_artifact(b"other proof")), ACTOR)
        second = self.report()
        for runs in ({"1": first, "2": second}, {"2": second, "1": first}):
            out = self.latest(FakeGitHub(runs))
            self.assertEqual(out["violations"], [])
            self.assertEqual(out["newest"], "2")
            self.assertEqual(sorted(j["result"] for j in out["judged"]), ["fail", "pass"])
            self.assertEqual(status(self.ledger, {"judged": out["judged"]})["headline"],
                             "judge-rejected")

    def test_newer_error_does_not_hide_older_fail(self):
        first = self.report(results=[self.result(result="fail")])
        self.add_failed_check()
        second = self.report(results=[self.result(result="error")])
        out = self.latest(FakeGitHub({"2": second, "1": first}))
        self.assertEqual([j["result"] for j in out["judged"]], ["fail"])

    def test_the_same_result_in_two_anchors_counts_once(self):
        first = self.report()
        self.add_failed_check()
        out = self.latest(FakeGitHub({"2": self.report(), "1": first}))
        self.assertEqual(len(out["judged"]), 1)

    def test_a_moved_or_steered_path_still_finds_anchors_by_first_event(self):
        self.add_failed_check()
        anchored = self.report(ledger_path="research/real/ledger")
        rechain(self.ledger, 2)
        for path in (".", "INV/A", "inv/.a-real"):
            out = authority.load_authoritative("latest", "own/repo", self.ledger, path, run=FakeGitHub({"1": anchored}))
            self.assertEqual(len(out["violations"]), 1, path)

    def test_graft_onto_another_anchored_ledger_fails_closed(self):
        # Round 2 finding 1: only a report for this path anchors it; a genesis match covers nothing.
        foreign = self.report(ledger_path="inv/b")
        for path in ("ledger", "."):
            out = authority.load_authoritative("latest", "own/repo", self.ledger, path,
                                               run=FakeGitHub({"2": foreign}))
            self.assertEqual((out["anchors"], out["judged"]), ([], []), path)

    def test_genesis_only_report_still_adds_an_obligation(self):
        self.add_failed_check()
        copy = self.report(ledger_path="inv/a2")
        rechain(self.ledger, 2)
        out = self.latest(FakeGitHub({"1": copy, "2": self.report()}))
        self.assertEqual(len(out["violations"]), 1)
        self.assertIn("shares this ledger's first event", out["violations"][0])
        self.assertEqual([a["source"] for a in out["anchors"]], ["2"])

    def test_a_pass_under_a_corrected_challenge_supersedes_an_older_fail(self):
        old = self.report(results=[self.result(result="fail")])
        self.ledger.append("check", CLAIM, check_data(self.ledger.put_artifact(b"other proof")), ACTOR)
        fixed = judge.register_challenge(self.ledger, CLAIM, "claim", b"theorem main_theorem : True := by sorry\n")
        new = self.report(results=[self.result(challenge_hash=fixed)])
        out = self.latest(FakeGitHub({"2": new, "1": old}))
        self.assertEqual([j["result"] for j in out["judged"]], ["pass"])
        self.assertEqual(status(self.ledger, {"judged": out["judged"]})["headline"], "judged-unreviewed")

    def test_results_judged_at_an_old_path_still_count(self):
        # Round 3 finding 2: after a rename, a fail judged at the old path is not dropped.
        old = self.report(ledger_path="inv/old", results=[self.result(result="fail")])
        self.ledger.append("check", CLAIM, check_data(self.ledger.put_artifact(b"other proof")), ACTOR)
        out = self.latest(FakeGitHub({"2": self.report(), "1": old}))
        self.assertEqual(sorted(j["result"] for j in out["judged"]), ["fail", "pass"])
        self.assertEqual(status(self.ledger, {"judged": out["judged"]})["headline"], "judge-rejected")

    def test_a_graft_gets_no_results_from_the_other_ledger(self):
        other = self.report(ledger_path="inv/b", ledger_genesis="e" * 64)
        out = self.latest(FakeGitHub({"2": self.report(results=[]), "1": other}))
        self.assertEqual(out["judged"], [])

    def test_a_tie_is_broken_by_run_order(self):
        # Round 3 finding 3: a corrected Challenge rerun at the same head supersedes the earlier fail.
        old = self.report(results=[self.result(result="fail")])
        fixed = judge.register_challenge(self.ledger, CLAIM, "claim", b"theorem main_theorem : True := by sorry\n")
        new = self.report(results=[self.result(challenge_hash=fixed)])
        out = self.latest(FakeGitHub({"2": new, "1": old}))
        self.assertEqual([j["result"] for j in out["judged"]], ["pass"])

    def test_editing_challenges_keeps_a_rejection(self):
        content = self.report(results=[self.result(result="fail")])
        for raw in (b"{}", b"not json"):
            (self.dir / judge.CHALLENGES_FILE).write_bytes(raw)
            judged, notes = authority.tier_results(content, self.ledger)
            self.assertEqual([j["result"] for j in judged], ["fail"], raw)
            self.assertEqual(status(self.ledger, {"judged": judged})["headline"], "judge-rejected")

    def test_file_mode_says_older_anchors_were_not_checked(self):
        path = Path(self.tmp.name) / "r.json"
        path.write_bytes(self.report())
        out = authority.load_authoritative(path, "own/repo", self.ledger, "ledger", run=FakeGitHub({}))
        self.assertIn("earlier anchors were not checked", out["notes"][0])

    def test_other_ledgers_reports_are_skipped(self):
        other = self.report(ledger_path="research/other/ledger", ledger_genesis="e" * 64, ledger_head="d" * 64)
        out = self.latest(FakeGitHub({"1": other}))
        self.assertEqual(out["violations"], [])
        self.assertEqual(out["judged"], [])
        self.assertIn("no attested judge report for ledger 'ledger' anchors it", out["notes"][-1])

    def test_path_forms_compare_equal(self):
        out = authority.load_authoritative("latest", "own/repo", self.ledger, "./ledger/",
                                           run=FakeGitHub({"1": self.report(ledger_path="ledger")}))
        self.assertEqual(len(out["anchors"]), 1)

    def test_unattested_reports_are_neither_anchors_nor_violations(self):
        self.add_failed_check()
        forged = self.report()
        rechain(self.ledger, 2)
        out = self.latest(FakeGitHub({"1": forged}, attested=set()))
        self.assertEqual((out["anchors"], out["violations"]), ([], []))
        self.assertIn("judge report ignored", out["notes"][0])

    def test_expired_artifact_and_failed_listing_are_notes(self):
        out = self.latest(FakeGitHub({"1": None, "2": self.report()}))
        self.assertIn("run 1: no judge report", out["notes"][0])
        self.assertEqual(len(out["anchors"]), 1)
        out = self.latest(FakeGitHub({"1": self.report()}, list_rc=1))
        self.assertEqual(out["anchors"], [])
        self.assertIn("could not list", out["notes"][0])

    def test_listing_asks_for_successful_main_runs_of_this_workflow(self):
        gh = FakeGitHub({"1": self.report()})
        self.latest(gh)
        listing = gh.calls[0]
        for flag, value in (("--workflow", "authoritative.yml"), ("--branch", "main"), ("--status", "success"),
                            ("--repo", "own/repo")):
            self.assertEqual(listing[listing.index(flag) + 1], value)

    def test_truncated_listing_is_noted(self):
        old = authority.RUN_LIMIT
        authority.RUN_LIMIT = 2
        try:
            out = self.latest(FakeGitHub({"1": self.report(), "2": self.report()}))
        finally:
            authority.RUN_LIMIT = old
        self.assertIn("older anchors were not checked", out["notes"][0])

    def test_bad_repo_name_fetches_nothing(self):
        gh = FakeGitHub({"1": self.report()})
        out = authority.load_authoritative("latest", "../x", self.ledger, "ledger", run=gh)
        self.assertEqual(gh.calls, [])
        self.assertEqual(out["anchors"], [])

    def test_assembled_report_names_the_ledger(self):
        report = judge.assemble(self.dir, Path(self.tmp.name) / "no-cases")
        self.assertEqual(report["ledger_path"], judge.ledger_path(self.dir))
        self.assertEqual(report["ledger_genesis"], Ledger.event_hash(self.ledger.read()[0]))
        self.assertEqual(judge.ledger_path("./research/w/ledger/"), "research/w/ledger")


class VerifyCommandTests(LedgerCase):
    def run_verify(self, authority_result):
        from unittest import mock
        from mathproof_core import cli
        out = io.StringIO()
        with mock.patch.object(cli, "load_authoritative", return_value=authority_result), \
                mock.patch("sys.stdout", out):
            rc = cli.main(["verify", str(self.dir), "--authoritative", "latest", "--repo", "own/repo",
                           "--ledger-path", "ledger"])
        return rc, out.getvalue()

    def test_no_anchor_fails_closed(self):
        rc, text = self.run_verify({"judged": [], "notes": [], "anchors": [], "violations": []})
        self.assertEqual(rc, 1)
        self.assertIn("NO ANCHOR: no attested judge report anchors this ledger", text)
        self.assertIn("NOT OK", text)

    def test_anchor_violation_fails_verify(self):
        rc, text = self.run_verify({"judged": [], "notes": [], "anchors": [], "violations": ["1: bad head"]})
        self.assertEqual(rc, 1)
        self.assertIn("ANCHOR VIOLATED: 1: bad head", text)
        self.assertIn("NOT OK", text)

    def test_verified_head_is_printed(self):
        rc, text = self.run_verify({"judged": [], "notes": [], "violations": [], "newest": "9",
                                    "anchors": [{"source": "9", "ledger_path": "ledger", "ledger_seq": 2, "ledger_head": H}]})
        self.assertIn(f"anchored head event 2 {H} of ledger (9)", text)


class LedgerPathTests(LedgerCase):
    """Round 4: the ledger path is never derived from the checkout, which an agent can steer."""

    def test_authoritative_needs_an_explicit_ledger_path(self):
        from mathproof_core import cli
        from unittest import mock
        err = io.StringIO()
        with mock.patch.object(cli, "load_authoritative") as load, mock.patch("sys.stderr", err):
            rc = cli.main(["verify", str(self.dir), "--authoritative", "latest", "--repo", "own/repo"])
        self.assertNotEqual(rc, 0)
        load.assert_not_called()
        self.assertIn("--ledger-path", err.getvalue())


if __name__ == "__main__":
    unittest.main()
