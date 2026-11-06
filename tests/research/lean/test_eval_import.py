"""S8.1.T1: import the 22 eval cases and check the mapping. Needs Lean and Mathlib.

This is a mapping consistency test, not validation. It shows the table, the repo's labels, and the
derivation agree. It says nothing about whether a statement is faithful beyond what `read_note` records.
"""

import json
import re
import unittest
from pathlib import Path

from _lean_support import ACTOR, REPO_PROJECT, temp_dir
from _paths import ROOT
from mathproof_core.gate import record_check
from mathproof_core.ledger import Ledger
from mathproof_core.status import derive_status

CASES = {c["id"]: c for c in map(json.loads, (ROOT / "evals" / "cases.jsonl").read_text(encoding="utf-8").splitlines())}
TABLE = json.loads((Path(__file__).parent / "eval_table.json").read_text(encoding="utf-8"))["rows"]
DIRECTION = {"claim": "F=>I", "negation": "I=>F"}


def full_name(path: Path, short: str) -> str:
    module = ".".join(path.relative_to(REPO_PROJECT).with_suffix("").parts)
    namespaced = re.search(r"^namespace (\S+)", path.read_text(encoding="utf-8"), re.M)
    return f"{namespaced.group(1) if namespaced else module}.{short}"


class TableTests(unittest.TestCase):
    def test_the_table_covers_every_case_once(self):
        self.assertEqual(sorted(r["id"] for r in TABLE), sorted(CASES))

    def test_targets_are_declarations_the_repo_requires(self):
        for row in TABLE:
            self.assertLessEqual(set(row["targets"]), set(CASES[row["id"]]["lean"]["declarations"]), row["id"])

    def test_polarity_agrees_with_the_expected_verdict(self):
        for row in TABLE:
            verdict = CASES[row["id"]]["expected_verdict"]
            if row["polarity"] == "step":
                self.assertEqual(verdict, "INVALID", row["id"])
            else:
                self.assertEqual(row["polarity"], "negation" if verdict == "INVALID" else "claim", row["id"])

    def test_fidelity_agrees_with_the_repo_label(self):
        for row in TABLE:
            self.assertEqual(row["fidelity"], CASES[row["id"]]["lean"]["formalization"], row["id"])

    def test_step_rows_are_stated_explicitly(self):
        self.assertEqual({r["id"] for r in TABLE if r["polarity"] == "step"}, {"algebra-001", "analysis-002"})


class ImportTests(unittest.TestCase):
    def test_every_row_derives_what_the_table_says(self):
        with temp_dir() as d:
            ledger = Ledger.init(Path(d, "evals"))
            for row in TABLE:
                with self.subTest(row["id"]):
                    case, claim = CASES[row["id"]], f"evals/{row['id']}"
                    source = ROOT / case["lean"]["file"]
                    ledger.append("claim_created", claim, {"text": case["claim"], "kind": "eval"}, ACTOR)
                    for target in row["targets"]:
                        event = record_check(ledger, claim, source, full_name(source, target), row["polarity"], REPO_PROJECT)
                        self.assertEqual(event["data"]["result"], "pass", event["data"].get("problems"))
                    if row["polarity"] != "step":
                        ledger.append("fidelity", claim, {
                            "statement_hash": event["data"]["artifact"], "class": row["fidelity"],
                            "direction": DIRECTION[row["polarity"]], "judge": "repo-label",
                            "scope_note": case["lean"].get("scope_note") or ""}, ACTOR)
                    status = derive_status(ledger.read(), claim, {})
                    self.assertEqual(status["verdict"], "UNVERIFIED")
                    if row["polarity"] == "step":
                        self.assertEqual(status["headline"], "step-passed")
                        self.assertEqual(status["lean_status"], "KERNEL-PASSED (step only)")
                    else:
                        self.assertEqual(status["headline"], "kernel-passed-local")
                        self.assertTrue(status["lean_status"].startswith(f"KERNEL-PASSED (local; {row['polarity']}, fidelity: "))
                        self.assertIn("repo-label", status["lean_status"])
                        self.assertEqual(status["axes"]["fidelity"]["class"], row["fidelity"])
            self.assertTrue(ledger.verify().ok)


if __name__ == "__main__":
    unittest.main()
