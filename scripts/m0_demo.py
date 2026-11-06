#!/usr/bin/env python3
"""M0 demo: one true claim, one refuted claim, and attacks, from check through replay.

Run it from the repository, with the Lean project built. If Mathlib is not there yet, get it with
`cd lean && lake exe cache get`, a one-time download of several GB. Expect several minutes here,
since each check loads Mathlib four times, and replay does the same again.

Exits 0 only if everything behaved as stated.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from mathproof_core.gate import record_check  # noqa: E402
from mathproof_core.ledger import Ledger  # noqa: E402
from mathproof_core.replay import verify_investigation  # noqa: E402
from mathproof_core.report import render_report  # noqa: E402
from mathproof_core.status import derive_status  # noqa: E402

PROJECT = ROOT / "lean"
ACTOR = {"context_id": "m0-demo", "role": "demo", "kind": "script"}
EVALS = ROOT / "lean" / "MathProofSkill" / "Evals"
FIXTURES = ROOT / "tests" / "lean_check"
failures: list[str] = []


def expect(label: str, actual, wanted) -> None:
    good = actual == wanted
    print(f"  {'ok ' if good else 'WRONG'} {label}: {actual}" + ("" if good else f" (wanted {wanted})"), flush=True)
    if not good:
        failures.append(label)


def main() -> int:
    if not (PROJECT / ".lake" / "packages" / "mathlib").exists():
        print("Mathlib is missing. Run: cd lean && lake exe cache get  (several GB, one time)", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as d:
        directory = Path(d, "demo")
        ledger = Ledger.init(directory)
        status = lambda claim: derive_status(ledger.read(), claim, {})  # noqa: E731

        print("1. A true claim, with a proof Lean accepts", flush=True)
        ledger.append("claim_created", "demo/even-square", {"text": "The square of an even integer is even.", "kind": "theorem"}, ACTOR)
        event = record_check(ledger, "demo/even-square", EVALS / "Number001.lean", "MathProofSkill.Evals.Number001.even_sq", "claim", PROJECT)
        expect("check", event["data"]["result"], "pass")
        expect("headline", status("demo/even-square")["headline"], "kernel-passed-local")
        expect("verdict", status("demo/even-square")["verdict"], "UNVERIFIED")

        print("2. A false claim, refuted", flush=True)
        ledger.append("claim_created", "demo/open-interval-max", {"text": "Every continuous function on (0,1) attains a maximum.", "kind": "theorem"}, ACTOR)
        event = record_check(ledger, "demo/open-interval-max", EVALS / "Analysis001.lean", "MathProofSkill.Evals.Analysis001.claim_false", "negation", PROJECT)
        expect("check", event["data"]["result"], "pass")
        print(f"  status line: {status('demo/open-interval-max')['lean_status']}")
        expect("verdict", status("demo/open-interval-max")["verdict"], "UNVERIFIED")

        print("3. An attack: a fake proof of 1 = 2 with the kernel check switched off", flush=True)
        ledger.append("claim_created", "demo/fake", {"text": "1 = 2", "kind": "theorem"}, ACTOR)
        event = record_check(ledger, "demo/fake", FIXTURES / "fail_kernel_skip.lean", "main_theorem", "claim", PROJECT)
        expect("check", event["data"]["result"], "fail")
        expect("kernel axis", status("demo/fake")["axes"]["kernel"], "failed")

        print("4. A clean ledger replays", flush=True)
        result = verify_investigation(directory)
        expect("replay ok", result["ok"], True)
        print(f"  note: {result['notes'][0]}")

        print("5. Forging a pass, and tampering, are caught by replay", flush=True)
        forged = Path(d, "forged")
        ledger2 = Ledger.init(forged)
        ledger2.append("claim_created", "demo/forged", {"text": "1 = 2", "kind": "theorem"}, ACTOR)
        artifact = ledger2.put_artifact((FIXTURES / "fail_sorry.lean").read_bytes())
        report_hash = ledger2.put_artifact(b'{"status": "PASS", "declarations": []}')
        ledger2.append("check", "demo/forged", {"artifact": artifact, "target_decl": "t", "polarity": "claim", "result": "pass",
                                                "report_hash": report_hash, "pins": {}, "tier": "authoritative",
                                                "project": str(PROJECT)}, ACTOR)
        result = verify_investigation(forged)
        expect("forged pass caught", result["ok"], False)
        print(f"  difference: {result['differences'][0]['claim']}: {result['differences'][0]['detail']}")
        artifact_path = forged / "artifacts" / artifact
        artifact_path.write_text("changed", encoding="utf-8")
        expect("tampered file caught", any(x["kind"] == "artifact" for x in verify_investigation(forged)["differences"]), True)

        print("\n6. The report for the true claim\n", flush=True)
        print(render_report(ledger, "demo/even-square"))

    print(f"\nDemo {'FAILED: ' + ', '.join(failures) if failures else 'behaved as stated'}.")
    print("Nothing here shows a claim is proved in the top sense: the verdicts stay UNVERIFIED by design.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
