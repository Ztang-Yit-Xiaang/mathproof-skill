"""S8.1.T2: deliberately broken copies of the trusted code must make the tests fail.

Each mutant is applied to a temporary copy of skill/scripts, and the tests run against that copy.
A surviving mutant means the tests would not notice that bug. A mutant whose text no longer matches
fails this test, so the list cannot go stale unnoticed.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from _paths import ROOT

HERE = Path(__file__).resolve().parent
SUITES = ["test_status", "test_fidelity", "test_ledger", "test_events", "test_gate_logic", "test_report", "test_replay_stub",
          "test_authority"]

MUTANTS = {
    "status.py": [
        ('if {"claim", "negation"} <= polarities:', "if False:"),
        ('proper = [c for c in passing if c["polarity"] != "step"]', "proper = list(passing)"),
        ('and key(c) not in failed]', "]"),
        ('provenance = "self-declared" if worst["judge"] in ("signed-human", "none") else worst["judge"]', 'provenance = worst["judge"]'),
        ("worst = min(combined,", "worst = max(combined,"),
        ("if target not in polarities:\n            continue", "if False:\n            continue"),
        ('if cls == "instance" and "negation" not in polarities[target]:', "if False:"),
        ('if not any(judgment["direction"] == _NEEDED_DIRECTION[p] for p in polarities[target]):', "if False:"),
        ('if cls != "unfaithful":', "if True:"),
        ("if validate_event(event):", "if False:"),
        ('event.get("claim") != claim or ', ""),
        ('not is_status_bearing(str(event.get("kind")))', "False"),
        ('return "VALID", "LEAN-CHECKED"', 'return "VALID", "LEAN-FAILED"'),
        ('return "UNVERIFIED", f"KERNEL-PASSED (local;', 'return "VALID", f"KERNEL-PASSED (local;'),
        ('return (HUMAN_AUDITED if signed_audit else "INCOMPLETE"), not_checked', 'return "VALID", not_checked'),
        ('elif budget_stopped:\n        headline = "unresolved"\n    elif abandoned:\n        headline = "abandoned"',
         'elif abandoned:\n        headline = "abandoned"\n    elif budget_stopped:\n        headline = "unresolved"'),
        ('e["data"]["proof_hash"] in proofs', "True"),
        ('elif kernel == "passed-local":', 'elif kernel == "passed-local" or kernel == "failed":'),
        ("if not combined or (not unfaithful and set(accepted) != set(polarities)):", "if not combined:"),
        ('if any(j["class"] == "unfaithful" for j in judgments):', "if False:"),
        ("if failed & claimed_pass:", "if False:"),
        ('if "claim" in {c["polarity"] for c in passing} and (computational["candidates"] or of_kind("certificate")):', "if False:"),
        ("if len(created) > 1:", "if False:"),
        ('"checker_version": env.get("checker_version")', '"checker_version": None'),
        ('"artifacts": sorted({r["code_hash"] for r in runs})', '"artifacts": []'),
        ('any(c["polarity"] == "step" for c in passing), bool(checks), warnings', 'any(c["polarity"] == "step" for c in passing), False, warnings'),
        ('"scope": worst.get("scope_note") or None, "signed": False}', '"scope": None, "signed": False}'),
        ('"signed": False}, warnings', '"signed": worst["judge"] == "signed-human"}, warnings'),
        ('search = "budget-stopped" if budget_stopped else "abandoned" if abandoned else "active"',
         'search = "abandoned" if abandoned else "budget-stopped" if budget_stopped else "active"'),
        # S2.1.T7: the authoritative judge's results
        ("return accepted - rejected, rejected", "return accepted, rejected"),
        # The claim check in _judged has no mutant: matching the seq of this claim's own event implies it.
        ("if (seq, entry) not in events:", "if False:"),
        ("if isinstance(seq, bool) or not isinstance(seq, int):", "if False:"),
        ("if not isinstance(challenge, str) or not _HEX64.fullmatch(challenge):", "if False:"),
        ('if result.get("result") == "pass":', 'if result.get("result") in ("pass", "error"):'),
        ('elif result.get("result") == "fail":', "elif False:"),
        ("if not all(isinstance(part, str) for part in entry):", "if False:"),
        ("    elif rejected:\n        headline = \"judge-rejected\"\n", ""),
        ('        headline = "judged-unreviewed"', '        headline = "established"'),
        ('            missing.append("vacuity witness")', "            pass"),
        ('if "claim" in {polarity for _, _, polarity in judged}:', "if True:"),
        ('            blocked.append("unfaithful")', "            pass"),
        ('    if rejected:\n        kernel = "judge-rejected"', '    if False:\n        kernel = "judge-rejected"'),
    ],
    "ledger.py": [
        ('if event["prev"] != expected_prev:', "if False:"),
        ('if event["seq"] != index:', "if False:"),
        ('if event.get("hash") != self.event_hash(event):', "if False:"),
        ("if _canonical(event) != raw_line:", "if False:"),
        ("if self.artifact_hash(content) != digest:", "if False:"),
        ("fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)", "pass"),
        ("            if tail:\n                raise TornTail", "            if False:\n                raise TornTail"),
        ('if kind == "claim_created" and any(', "if False and any("),
        ("if target.exists() and self.artifact_hash(target.read_bytes()) == digest:", "if target.exists():"),
    ],
    "events.py": [
        ("_HEX64_RE.fullmatch(prev)", "_HEX64_RE.match(prev)"),
        ("not _CLAIM_RE.fullmatch(claim)", "not _CLAIM_RE.match(claim)"),
        ("if not _storable(event):", "if False:"),
        ('if "status" in data:', 'if "status" in data and kind != "bridge":'),
    ],
    "gate.py": [
        ('if declaration.get("name") == decl:', 'if str(declaration.get("name")).endswith(decl):'),
        ('if target.get("kind") != "theorem":', "if False:"),
        ('report.get("environment_error") or ', ""),
        ('bad = sorted(set(target.get("axioms", [])) - ALLOWED_AXIOMS)', "bad = []"),
        ('s.get("status") == "timeout"', "False"),
        ('report["request"] = {"target_decl": decl, "polarity": polarity}', 'report["request"] = {"target_decl": decl, "polarity": "claim"}'),
        ('text = text.replace(json.dumps(directory, ensure_ascii=False)[1:-1], "<check>")', "pass"),
        ("any(_ENVIRONMENT_PROBLEM.search(str(r)) for r in reasons)", "False"),
        ('"type_explicit": d.get("type_explicit"), ', ""),
        ('"statement_uses": d.get("statement_uses")', '"statement_uses": None'),
        ('"statement_context": report.get("statement_context")}', '"statement_context": None}'),
        ('"environment": {key: report.get(key) for key in ("toolchain", "mathlib_rev", "pinned", "environment_error")},', ""),
        ('return ("pass" if report.get("status") == "PASS" and not reasons else "fail"), reasons', 'return "pass", reasons'),
    ],
    "replay.py": [
        ('if event_data.get("result") != result:', "if False:"),
        ("if not same:", "if False:"),
        ('if stored.get("request") != {"target_decl": decl, "polarity": event_data.get("polarity")}:', "if False:"),
        ('if event_data.get("type") != target.get("type"):', "if False:"),
        ('if event_data.get("axioms") != sorted(target.get("axioms", [])):', "if False:"),
        ('if event_data.get("tier") != "local":', "if False:"),
        ('if event_data.get("problems") != summarize(reasons):', "if False:"),
        ('if not isinstance(pins, dict) or pins.get(key) != fresh.get(key):', "if False:"),
        ('if stored.get("checker") != fresh.get("checker") or not isinstance(pins, dict) or pins.get("checker") != fresh.get("checker"):', "if False:"),
        ("for error in chain.errors:", "for error in []:"),
        ('key = (data["artifact"], data["target_decl"], str(chosen))', 'key = (data["target_decl"], str(chosen))'),
        ('"informal_proof": ("artifact",), ', ""),
        ('"informal_audit": ("proof_hash",),', ""),
        ('"experiment": ("code_hash",), ', ""),
        ('"fidelity": ("statement_hash",),', ""),
        ("if claim not in with_statement:", "if False:"),
        ('environment_errors.append({"claim": claim, "seq": seq, "detail": str(error)})', "pass"),
    ],
    "judge.py": [
        ('return posixpath.normpath(str(raw).replace("\\\\", "/"))', "return str(raw)"),
        ('"ledger_genesis": planned["ledger_genesis"],', ""),
        ('if polarity not in ("claim", "negation"):\n            continue', "if False:\n            continue"),
        ("if not _DECL.fullmatch(data[\"target_decl\"]):", "if False:"),
        ("if challenge is None:", "if False:"),
        ('key = (event["claim"], data["artifact"]', 'key = (data["artifact"]'),
        ("jobs.setdefault(key, {", "jobs.setdefault(len(jobs), {"),
        ('if control["rc"] != 0:', "if False:"),
        ('    if rc == 0:\n        return "pass"', '    if rc == 0 or rc == "timeout":\n        return "pass"'),
        ('if isinstance(rc, int) and not isinstance(rc, bool):\n        return "fail"', 'if False:\n        return "fail"'),
        ("if result.errors:\n        raise JudgeError", "if False:\n        raise JudgeError"),
        ('"theorem_names": [target]', '"theorem_names": []'),
        ("challenge, solution = ledger.get_artifact(job[\"challenge_hash\"]), ledger.get_artifact(job[\"artifact\"])",
         "challenge, solution = ledger.get_artifact(job[\"artifact\"]), ledger.get_artifact(job[\"artifact\"])"),
        ("return events[-1][\"seq\"], Ledger.event_hash(events[-1])", "return events[-1][\"seq\"], Ledger.event_hash(events[0])"),
        ("env = {key: os.environ[key] for key in _ENV_KEEP if key in os.environ} | _ENV_SET", "env = dict(os.environ)"),
        ("            os.killpg(proc.pid, signal.SIGKILL)", "            pass"),
        ("root.mkdir(parents=True, exist_ok=False)", "root.mkdir(parents=True, exist_ok=True)"),
        ("not 0 <= index < len(jobs):", "not 0 <= index:"),
        ("except (ValueError, RecursionError, OSError) as error:", "except (ValueError, OSError) as error:"),
        ("elif any(case.get(field) != job[field] for field in _JOB_FIELDS):", "elif False:"),
        ('elif case.get("result") not in ("pass", "fail", "error"):', "elif False:"),
        ("except (OSError, ValueError, RecursionError):\n        return None", "except (OSError, ValueError):\n        return None"),
        ("case = _read_case(Path(cases_dir), index)", "case = _read_case(Path(cases_dir), 0)"),
        ("        if not stat.S_ISDIR(directory.lstat().st_mode):\n            return None", "        pass"),
        ("if entries != [path] or not stat.S_ISREG(path.lstat().st_mode):", "if not path.exists():"),
        ("if entries != [path] or not stat.S_ISREG(path.lstat().st_mode):", "if not stat.S_ISREG(path.lstat().st_mode):"),
        ("if entries != [path] or not stat.S_ISREG(path.lstat().st_mode):", "if entries != [path]:"),
    ],
    "authority.py": [
        ('"--signer-workflow", f"{repo}/{WORKFLOW}", "--source-ref", SOURCE_REF,', ""),
        ('            "--deny-self-hosted-runners", "--format", "json"]', '            "--format", "json"]'),
        ('if not _REPO.fullmatch(repo) or ".." in repo:\n        return f"not a repository name', 'if False:\n        return f"not a repository name'),
        ('if not _REPO.fullmatch(repo) or ".." in repo:\n        return [], [f"not a repository name', 'if False:\n        return [], [f"not a repository name'),
        ("if proc.returncode != 0:", "if False:"),
        ('if report.get("sandboxed") is not True:', "if False:"),
        ('if type(report.get("judge_version")) is not int or report["judge_version"] != JUDGE_VERSION:', "if False:"),
        ('if type(report.get("judge_version")) is not int or report["judge_version"] != JUDGE_VERSION:',
         'if report.get("judge_version") != JUDGE_VERSION:'),
        ('if report.get("permitted_axioms") != PERMITTED_AXIOMS or report.get("definition_names") != []:', "if False:"),
        ('if report.get("toolchain") != pin["toolchain"] or report.get("mathlib_rev") != pin["mathlib_rev"]:', "if False:"),
        ('if report.get("format") != FORMAT:', "if False:"),
        ("if ledger.verify().errors:\n        return [], [", "if False:\n        return [], ["),
        ('if seq >= len(events) or Ledger.event_hash(events[seq]) != report["ledger_head"]:', "if seq >= len(events):"),
        ("not 0 <= where <= seq:", "not 0 <= where:"),
        ("if local != claimed:", "if False:"),
        ('if current != result["challenge_hash"]:', "if False:"),
        ('if result["result"] == "pass":\n                notes.append(f"ignored a pass', 'if True:\n                notes.append(f"ignored a pass'),
        ('and report["ledger_genesis"] != genesis:', ":"),
        ('if not isinstance(report.get("ledger_genesis"), str) or not _HEX64.fullmatch(report["ledger_genesis"]):', "if False:"),
        ("for order, report, content, where in sources:", "for order, report, content, where in [max(sources, key=lambda x: x[0])]:"),
        ("elif key not in seen:", "elif True:"),
        ("if by_path:\n            anchors.append", "if True:\n            anchors.append"),
        ('chosen = {e["challenge_hash"] for at, e in entries if at == latest}', 'chosen = {e["challenge_hash"] for at, e in entries}'),
        ("latest = max(at for at, _ in entries)", "latest = min(at for at, _ in entries)"),
        ('sources.append(((report["ledger_seq"], -position), report, content, where))',
         'sources.append(((report["ledger_seq"], 0), report, content, where))'),
        ("judged = _combine(sources, ledger, notes)",
         'judged = _combine([x for x in sources if ledger_path(x[1]["ledger_path"]) == want], ledger, notes)'),
        ('if result["result"] not in ("pass", "fail"):', "if False:"),
        ('if not isinstance(event, dict) or event.get("kind") != "check" or validate_event(event):', "if False:"),
        ("if reason:\n            notes.append", "if False:\n            notes.append"),
        # S1.3.T4 anchors
        ("if ledger.verify().errors:\n        return False", "if False:\n        return False"),
        ('return seq < len(events) and Ledger.event_hash(events[seq]) == report["ledger_head"]', "return seq < len(events)"),
        ("if not anchors_ok(report, ledger):", "if False:"),
        ('by_path = ledger_path(report["ledger_path"]) == want', "by_path = True"),
        ('newest = max(anchors, key=lambda a: a[0]["ledger_seq"])', "newest = anchors[0]"),
        ('newest = max(anchors, key=lambda a: a[0]["ledger_seq"])', "newest = anchors[-1]"),
        ('"--branch", "main",\n', "\n"),
        ('"--status", "success", ', ""),
        ("if len(ids) >= RUN_LIMIT", "if False"),
        ('if not isinstance(report.get("ledger_path"), str):', "if False:"),
        ("path.write_bytes(content)", 'path.write_bytes(b"{}")'),
    ],
    "cli.py": [
        ('if difference["kind"] in ("anchor", "no-anchor"):', "if False:"),
        ("anchor_violations=violations)", "anchor_violations=[])"),
        ('if not authority["anchors"]:', "if False:"),
        ("if not args.ledger_path:", "if False:"),
    ],
    "report.py": [
        (r"""return [f"> \\{line}" if line[:1] in ("=", "-", "+") else f"> {line}" for line in lines] or [">"]""", "return lines"),
        (r"""return _MARKUP.sub(r"\\\1", _clean(text).replace("\n", " "))""", r"""return _clean(text).replace("\n", " ")"""),
        (r"""lines = [_MARKUP.sub(r"\\\1", line.lstrip()) for line in _clean(text).splitlines()]""", "lines = _clean(text).splitlines()"),
        ("line.lstrip()", "line"),
        ('if c["result"] == "pass" and key(c) not in failed]', 'if c["result"] == "pass"]'),
        ('notes = [e.get("data", {}) for e in mine if not is_status_bearing(str(e.get("kind"))) and isinstance(e.get("data"), dict)]', 'notes = [e["data"] for e in mine if e.get("kind") == "note"]'),
        ('return [f"    {line}" for line in _clean(text).splitlines()]', "return _clean(text).splitlines()"),
        ("""f"**Verdict:** {status['verdict']}", "",""", """"**Verdict:** VALID", "","""),
        ('open_items + status["warnings"]', "[]"),
        ('if unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp") else c', "if False else c"),
        (r""".replace("\n", "\\n")""", ""),
    ],
}


def run_mutant(item):
    filename, old, new = item
    with tempfile.TemporaryDirectory() as d:
        copy = Path(d, "scripts")
        shutil.copytree(ROOT / "skill" / "scripts", copy, ignore=shutil.ignore_patterns("__pycache__"))
        path = copy / "mathproof_core" / filename
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            return f"{filename}: text not found exactly once: {old[:70]}"
        path.write_text(text.replace(old, new), encoding="utf-8")
        run = subprocess.run([sys.executable, "-m", "unittest", *SUITES], cwd=HERE, capture_output=True, text=True,
                             env={**os.environ, "MATHPROOF_TEST_SCRIPTS": str(copy), "PYTHONDONTWRITEBYTECODE": "1"})
        return None if run.returncode != 0 else f"{filename}: survived: {old[:70]}"


class MutantTests(unittest.TestCase):
    def test_every_mutant_is_caught(self):
        items = [(f, old, new) for f, pairs in MUTANTS.items() for old, new in pairs]
        self.assertGreaterEqual(len(items), 5)
        with ThreadPoolExecutor(4) as pool:
            problems = [p for p in pool.map(run_mutant, items) if p]
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
