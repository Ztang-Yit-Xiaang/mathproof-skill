#!/usr/bin/env python3
"""Score a model on evals/cases.jsonl with and without the skill's instructions.

Each case is sent to `claude -p` in an isolated session: no user settings, CLAUDE.md,
skills, MCP servers, or tools. The two conditions get the same user prompt; the `skill`
condition also appends skill/SKILL.md to the system prompt. With tools disabled, Lean is
not run, so this measures the informal audit protocol alone.

    python3 scripts/run_benchmark.py --model haiku --model sonnet -j 4

Raw answers go to evals/results/raw/<model>/<condition>/<id>.txt and are reused on
rerun (delete them to refresh). The summary goes to evals/results/summary.json.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "cases.jsonl"
SKILL = ROOT / "skill" / "SKILL.md"
OUT = ROOT / "evals" / "results"
CONDITIONS = ("baseline", "skill")
VERDICTS = ("VALID", "INVALID", "CONDITIONALLY VALID", "INCOMPLETE", "UNVERIFIED")

PROMPT = """Audit the following proof. Decide whether it establishes the claim, and if not, identify the first step that is not justified by the claim's hypotheses and the earlier steps.

Claim: {claim}

Proof:
{steps}

End your answer with one line of JSON and nothing after it:
{{"verdict": one of {verdicts}, "first_bad_step": the number of the first unjustified step, or null if every step is justified}}"""


def prompt_for(case: dict) -> str:
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(case["proof_steps"], 1))
    return PROMPT.format(claim=case["claim"], steps=steps, verdicts=json.dumps(list(VERDICTS)))


def ask(model: str, condition: str, case: dict, timeout: int) -> str:
    path = OUT / "raw" / model / condition / f"{case['id']}.txt"
    if path.is_file() and path.stat().st_size:
        return path.read_text(encoding="utf-8")
    cmd = ["claude", "-p", "--model", model, "--setting-sources", "", "--strict-mcp-config",
           "--tools", "", "--no-session-persistence"]
    if condition == "skill":
        cmd += ["--append-system-prompt", SKILL.read_text(encoding="utf-8")]
    cmd.append(prompt_for(case))
    with tempfile.TemporaryDirectory() as cwd:
        result = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    text = result.stdout
    if result.returncode != 0 or not text.strip():
        raise RuntimeError(f"{model}/{condition}/{case['id']}: exit {result.returncode}: {result.stderr[:300]}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def parse(text: str) -> tuple[str | None, int | None]:
    """Read the last JSON object in the answer that has a `verdict` key."""
    for blob in reversed(re.findall(r"\{[^{}]*\"verdict\"[^{}]*\}", text)):
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        verdict = str(data.get("verdict", "")).strip().upper()
        step = data.get("first_bad_step")
        return (verdict if verdict in VERDICTS else None), (step if isinstance(step, int) else None)
    return None, None


def score(case: dict, verdict: str | None, step: int | None) -> dict:
    expected_verdict, expected_step = case["expected_verdict"], case["expected_first_bad_step"]
    verdict_ok = verdict == expected_verdict
    step_ok = step == expected_step
    return {
        "id": case["id"],
        "verdict": verdict,
        "first_bad_step": step,
        "verdict_ok": verdict_ok,
        "step_ok": step_ok,
        "both_ok": verdict_ok and step_ok,
        # The dangerous error: accepting a proof that should be rejected.
        "false_accept": expected_verdict != "VALID" and verdict == "VALID",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("-j", "--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    jobs = [(m, c, case) for m in args.model for c in CONDITIONS for case in cases]

    def run(job):
        model, condition, case = job
        try:
            return model, condition, score(case, *parse(ask(model, condition, case, args.timeout)))
        except Exception as exc:  # noqa: BLE001 - report and keep going
            print(f"error: {exc}")
            return model, condition, None

    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(run, jobs))

    summary: dict = {"cases": len(cases), "runs": {}}
    for model in args.model:
        for condition in CONDITIONS:
            rows = [r for m, c, r in results if m == model and c == condition and r is not None]
            totals = {k: sum(r[k] for r in rows) for k in ("verdict_ok", "step_ok", "both_ok", "false_accept")}
            summary["runs"][f"{model}/{condition}"] = {"completed": len(rows), **totals, "rows": rows}
            print(f"{model:>8} {condition:>8}: verdict {totals['verdict_ok']:>2}/{len(cases)}  "
                  f"first bad step {totals['step_ok']:>2}/{len(cases)}  both {totals['both_ok']:>2}/{len(cases)}  "
                  f"false accepts {totals['false_accept']}  ({len(rows)} completed)")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
