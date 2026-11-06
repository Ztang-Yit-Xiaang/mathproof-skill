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
SUITES = ["test_status", "test_fidelity", "test_ledger", "test_events", "test_gate_logic", "test_report", "test_replay_stub"]

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
    "report.py": [
        (r"""return [f"> \\{line}" if line[:1] in ("=", "-", "+") else f"> {line}" for line in lines] or [">"]""", "return lines"),
        (r"""return _MARKUP.sub(r"\\\1", _clean(text).replace("\n", " "))""", r"""return _clean(text).replace("\n", " ")"""),
        (r"""lines = [_MARKUP.sub(r"\\\1", line) for line in _clean(text).splitlines()]""", "lines = _clean(text).splitlines()"),
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
