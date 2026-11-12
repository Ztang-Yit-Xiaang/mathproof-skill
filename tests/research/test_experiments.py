"""Tests for S3.1.T1 (experiment runner) and S3.1.T4 (R adapter)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _paths  # noqa: F401
from _paths import ROOT
from mathproof_core.events import validate_event
from mathproof_core.experiments import record_experiment, rerun_experiment, run_experiment
from mathproof_core.ledger import Ledger
from mathproof_core.status import HEADLINES, derive_status

ACTOR = {"context_id": "test", "role": "runner", "kind": "runner"}


class ExperimentTests(unittest.TestCase):
    launcher = ROOT / "skill" / "scripts" / "mathproof.py"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.ledger_dir = self.tmp / "ledger"
        self.ledger = Ledger.init(self.ledger_dir)
        self.ledger.append("claim_created", "inv/c1", {"text": "Test claim.", "kind": "theorem"}, ACTOR)

    def _write_code(self, name: str, content: str) -> Path:
        path = self.tmp / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_1_seeded_python_experiment_record_and_rerun(self) -> None:
        code = self._write_code(
            "seeded.py",
            """import json, os, random
seed = int(os.environ["MP_SEED"])
params = json.loads(os.environ["MP_PARAMS"])
rng = random.Random(seed)
val = rng.randint(1, 100000) + params.get("offset", 0)
with open(os.environ["MP_OUT"], "w", encoding="utf-8") as f:
    json.dump({"val": val, "violations": []}, f)
""",
        )
        r1 = run_experiment(code, language="python", seed=42, params={"offset": 5})
        r2 = run_experiment(code, language="python", seed=42, params={"offset": 5})
        self.assertEqual(r1["outcome"], "completed")
        self.assertIsNotNone(r1["results_hash"])
        self.assertEqual(r1["results_hash"], r2["results_hash"])
        self.assertEqual(r1["diagnostics"]["env_lock_source"], "python-metadata")

        event = record_experiment(self.ledger, "inv/c1", code, r1, ACTOR)
        self.assertEqual(validate_event(event), [])
        stored_bytes = self.ledger.get_artifact(r1["code_hash"])
        self.assertEqual(Ledger.artifact_hash(stored_bytes), r1["code_hash"])
        self.assertEqual(rerun_experiment(self.ledger, event), [])

    def test_2_timeout_kills_process_group(self) -> None:
        code = self._write_code(
            "sleepy.py",
            """import time
time.sleep(10)
""",
        )
        rec = run_experiment(code, language="python", seed=0, params={}, timeout_s=1)
        self.assertEqual(rec["outcome"], "timeout")
        self.assertIsNone(rec["results"])
        self.assertIsNone(rec["results_hash"])
        self.assertEqual(rec["violations"], [])

    def test_3_error_nonzero_exit_and_non_json(self) -> None:
        code_exit = self._write_code(
            "exit3.py",
            """import sys
sys.stderr.write("failed with 3\\n")
sys.exit(3)
""",
        )
        rec_exit = run_experiment(code_exit, language="python", seed=0, params={})
        self.assertEqual(rec_exit["outcome"], "error")
        self.assertIsNone(rec_exit["results"])
        self.assertIsNone(rec_exit["results_hash"])
        self.assertEqual(rec_exit["diagnostics"]["returncode"], 3)

        code_bad_json = self._write_code(
            "badjson.py",
            """import os
with open(os.environ["MP_OUT"], "w", encoding="utf-8") as f:
    f.write("not valid json {{{")
""",
        )
        rec_bad = run_experiment(code_bad_json, language="python", seed=0, params={})
        self.assertEqual(rec_bad["outcome"], "error")
        self.assertIsNone(rec_bad["results"])
        self.assertIsNone(rec_bad["results_hash"])

    def test_4_violations_propagate_into_event_data(self) -> None:
        code = self._write_code(
            "viol.py",
            """import json, os
with open(os.environ["MP_OUT"], "w", encoding="utf-8") as f:
    json.dump({"checked": 10, "violations": [{"n": 4, "reason": "counterexample"}]}, f)
""",
        )
        rec = run_experiment(code, language="python", seed=1, params={})
        self.assertEqual(rec["outcome"], "completed")
        self.assertEqual(rec["violations"], [{"n": 4, "reason": "counterexample"}])
        event = record_experiment(self.ledger, "inv/c1", code, rec, ACTOR)
        self.assertEqual(event["data"]["violations"], [{"n": 4, "reason": "counterexample"}])
        self.assertNotIn("results", event["data"])

    def test_5_status_not_raised_by_completed_experiment_with_violations(self) -> None:
        proof_hash = self.ledger.put_artifact(b"Informal proof text.")
        self.ledger.append(
            "informal_proof",
            "inv/c1",
            {"artifact": proof_hash, "author_context": "ctx"},
            ACTOR,
        )
        before = derive_status(self.ledger.read(), "inv/c1", {})
        self.assertEqual(before["headline"], "argued")

        code = self._write_code(
            "exp_viol.py",
            """import json, os
with open(os.environ["MP_OUT"], "w", encoding="utf-8") as f:
    json.dump({"violations": [{"x": -1}]}, f)
""",
        )
        rec = run_experiment(code, language="python", seed=7, params={})
        record_experiment(self.ledger, "inv/c1", code, rec, ACTOR)
        after = derive_status(self.ledger.read(), "inv/c1", {})
        self.assertGreaterEqual(
            HEADLINES.index(after["headline"]),
            HEADLINES.index(before["headline"]),
        )
        self.assertEqual(after["axes"]["computational"]["runs"], 1)
        self.assertEqual(after["axes"]["computational"]["candidates"], 1)

    @unittest.skipIf(shutil.which("Rscript") is None, "Rscript is not installed")
    def test_6_r_round_trip(self) -> None:
        code = self._write_code(
            "seeded.R",
            """seed <- as.integer(Sys.getenv("MP_SEED"))
out_path <- Sys.getenv("MP_OUT")
set.seed(seed)
val <- sample.int(100000L, 1L)
if (requireNamespace("jsonlite", quietly = TRUE)) {
  jsonlite::write_json(list(val = val, violations = list()), out_path, auto_unbox = TRUE)
} else {
  cat(sprintf('{"val":%d,"violations":[]}', val), file = out_path)
}
""",
        )
        r1 = run_experiment(code, language="r", seed=99, params={"k": 2})
        r2 = run_experiment(code, language="r", seed=99, params={"k": 2})
        self.assertEqual(r1["outcome"], "completed", r1["diagnostics"])
        self.assertIsNotNone(r1["results_hash"])
        self.assertEqual(r1["results_hash"], r2["results_hash"])
        self.assertIn(r1["diagnostics"]["env_lock_source"], ("renv.lock", "r-installed"))

        event = record_experiment(self.ledger, "inv/c1", code, r1, ACTOR)
        self.assertEqual(rerun_experiment(self.ledger, event), [])

    @unittest.skipIf(shutil.which("Rscript") is None, "Rscript not installed")
    def test_6b_renv_lock_is_kept_for_rerun(self) -> None:
        code = self._write_code("locked.R", 'cat("{\\"v\\":1}", file = Sys.getenv("MP_OUT"))\n')
        (self.tmp / "renv.lock").write_text('{"R": {"Version": "test"}}', encoding="utf-8")
        record = run_experiment(code, language="r", seed=1, params={})
        self.assertEqual(record["outcome"], "completed", record["diagnostics"])
        self.assertEqual(record["diagnostics"]["env_lock_source"], "renv.lock")
        event = record_experiment(self.ledger, "inv/c1", code, record, ACTOR)
        self.assertEqual(rerun_experiment(self.ledger, event), [])

    def test_7_r_unavailable(self) -> None:
        code = self._write_code("noop.R", "cat('{}', file=Sys.getenv('MP_OUT'))\n")
        with patch("mathproof_core.experiments.shutil.which", return_value=None):
            rec = run_experiment(code, language="r", seed=0, params={})
        self.assertEqual(rec["outcome"], "error")
        self.assertTrue(rec["diagnostics"]["unavailable"])
        self.assertIsNone(rec["results"])
        self.assertIsNone(rec["results_hash"])
        self.assertEqual(
            rec["env_lock_hash"],
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_8_non_seeded_program_rerun_reports_difference(self) -> None:
        code = self._write_code(
            "time_dep.py",
            """import json, os, time
with open(os.environ["MP_OUT"], "w", encoding="utf-8") as f:
    json.dump({"ns": time.time_ns(), "pid": os.getpid()}, f)
""",
        )
        rec = run_experiment(code, language="python", seed=0, params={})
        self.assertEqual(rec["outcome"], "completed")
        event = record_experiment(self.ledger, "inv/c1", code, rec, ACTOR)
        diffs = rerun_experiment(self.ledger, event)
        self.assertTrue(any("results_hash" in d for d in diffs), diffs)

    def test_9_cli_experiment_run_and_rerun(self) -> None:
        code = self._write_code(
            "cli_exp.py",
            """import json, os, random
rng = random.Random(int(os.environ["MP_SEED"]))
with open(os.environ["MP_OUT"], "w", encoding="utf-8") as f:
    json.dump({"draw": rng.randint(1, 1000)}, f)
""",
        )
        proc_run = subprocess.run(
            [
                sys.executable,
                str(self.launcher),
                "experiment",
                "run",
                "--dir",
                str(self.ledger_dir),
                "--claim",
                "inv/c1",
                "--code",
                str(code),
                "--lang",
                "python",
                "--seed",
                "123",
                "--params",
                '{"a":1}',
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_run.returncode, 0, proc_run.stderr)
        event = json.loads(proc_run.stdout)
        self.assertEqual(event["kind"], "experiment")
        self.assertEqual(event["data"]["outcome"], "completed")

        proc_rerun = subprocess.run(
            [
                sys.executable,
                str(self.launcher),
                "experiment",
                "rerun",
                "--dir",
                str(self.ledger_dir),
                "--seq",
                str(event["seq"]),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_rerun.returncode, 0, proc_rerun.stderr)
        self.assertEqual(proc_rerun.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
