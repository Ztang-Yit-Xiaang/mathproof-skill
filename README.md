# MathProof Skill

[![Validate](https://github.com/Ztang-Yit-Xiaang/mathproof-skill/actions/workflows/validate.yml/badge.svg)](https://github.com/Ztang-Yit-Xiaang/mathproof-skill/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A correctness-first AI skill that tries to break a mathematical proof before it accepts it.

AI-generated proofs often fail in a dangerous way: the algebra looks polished, but one unsupported implication is quietly buried in the middle. MathProof Skill changes the workflow from “reach the requested conclusion” to “verify that every dependency is earned.”

The reasoning is informal, and an informal audit does **not guarantee correctness**. To check results, the skill uses **Lean 4 with Mathlib**: it formalizes the claim (or its negation), checks that the formal statement says what the informal one says, proves it, and runs a checker that rejects `sorry`, custom axioms, and kernel bypasses. Only a check that passes counts as machine-checked.

## The core idea

```text
Claim -> Assumptions -> Adversarial audit -> Dependency map
      -> Proof or inspection -> Second audit -> Lean check -> Verdict
```

The distinctive rule is simple:

> When a step is challenged, freeze the proof immediately before that step and re-derive it using only facts already available. Later algebra cannot rescue an unsupported step.

## Ten-second example

**Proposed reasoning**

\[
f'(x)>0 \quad\Longrightarrow\quad f(x)>0.
\]

**Audit: `INVALID`**

The premise establishes that \(f\) is increasing, not that its values are positive. Let \(f(x)=x\) on \((-2,-1)\). Then \(f'(x)=1>0\), while \(f(x)<0\) throughout the domain.

## Four modes

| Mode | Purpose | Typical output |
| --- | --- | --- |
| `PROVE` | Construct and then attack a proof | Strategy, lemmas, proof, post-audit |
| `AUDIT` | Inspect a supplied proof without silently repairing it | First bad step, diagnosis, verdict, optional repair |
| `EXPLAIN` | Teach a proof while preserving its logic | Typed notation, intuition, step-by-step dependencies |
| `RESEARCH` | Verify named, recent, or uncertain external results | Exact theorem, hypothesis bridge, primary citation |

Possible verdicts are `VALID`, `INVALID`, `CONDITIONALLY VALID`, `INCOMPLETE`, and `UNVERIFIED`. Each one also carries a Lean status: `LEAN-CHECKED`, `LEAN-CHECKED (partial: …)`, `LEAN-FAILED`, or `NOT FORMALIZED`.

## Lean verification

```bash
python3 skill/scripts/lean_check.py path/to/File.lean --require main_theorem
```

The checker passes only if the file compiles, nothing uses `sorry`, every declaration depends only on `propext`, `Classical.choice`, and `Quot.sound` (so no custom `axiom` and no `native_decide`), and no kernel-bypassing construct appears. It prints each declaration's elaborated statement for comparison with the informal claim, because a passing proof of the wrong statement verifies nothing. The skill records that comparison in a fidelity table and flags Lean's junk values (`x / 0 = 0`, truncated `ℕ` subtraction, `deriv` of a non-differentiable function) and Mathlib definitions that bundle extra content.

Without a Lean project at hand, create a pinned one (one-time Mathlib download of several GB):

```bash
python3 skill/scripts/lean_check.py --init ~/proofcheck
```

Requires [elan](https://lean-lang.org/install). The full protocol is in [`skill/references/lean-verification.md`](skill/references/lean-verification.md).

## What it checks

- reversed implications and one-sided “if and only if” proofs;
- missing existence, nonzero, compactness, rank, convexity, or independence assumptions;
- circular dependencies and use of downstream facts;
- approximation or asymptotic claims silently treated as equality;
- invalid exchanges of limits, integrals, derivatives, and expectations;
- matrix-analysis traps such as symmetric versus PSD;
- optimization traps such as stationarity versus global optimality;
- citations whose theorem hypotheses do not match the current problem.

## Repository layout

```text
mathproof-skill/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── CITATION.cff
├── skill/                  # Installable, runtime-only skill
│   ├── SKILL.md
│   ├── references/         # Includes lean-verification.md
│   └── scripts/            # lean_check.py
├── lean/                   # Lean 4 + Mathlib project; machine-checks every eval case
├── examples/               # Human-readable demonstrations
├── evals/                  # Adversarial benchmark cases, linked to Lean files
├── scripts/                # Eval validation and Lean eval checking
├── tests/lean_check/       # Regression fixtures for the checker
└── launch/                 # Xiaohongshu launch materials
```

## Install

Copy the `skill/` directory into your agent's personal skills directory and name the destination `mathproof-skill`. The resulting install should have `SKILL.md` at its root:

```text
mathproof-skill/
├── SKILL.md
├── references/
└── scripts/
```

Then ask the agent to use `@mathproof-skill` on a proof problem or proof audit.

## Try it

```text
Use @mathproof-skill in AUDIT mode. Number the material steps,
identify the first unsupported step, and do not repair it until after
you give a verdict:

[paste proof]
```

See [`examples/`](examples/) for complete demonstrations.

## Evaluation

The initial benchmark contains valid and invalid proofs across logic, calculus, linear algebra, optimization, probability, approximation, and set reasoning. Each case records:

- expected verdict;
- expected first bad step;
- missing assumption, if any;
- counterexample, if any.

Run the deterministic schema and consistency checks:

```bash
python3 scripts/validate_evals.py
```

Every case is also formalized in `lean/`: valid claims are proved and invalid ones are formally refuted (a few formalizations are explicitly marked `partial`, e.g. one-variable or simple-graph versions). Machine-check them all:

```bash
cd lean && lake exe cache get && cd ..
python3 scripts/check_lean_evals.py
python3 tests/lean_check/run_tests.py   # checker regression tests
```

The benchmark tests whether an agent localizes the right failure; it is not evidence that every future verdict is correct.

## Project status

This is an experimental `v0.2.0` release. The immediate goal is to expand the benchmark with independently reviewed valid proofs and subtle research-math failure cases.

Contributions are welcome, especially minimal counterexamples, missing-assumption cases, and valid proofs that prevent the auditor from becoming reflexively negative. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Author

**Yit Xiaang Ztang** — [ztangyitxiaang@gmail.com](mailto:ztangyitxiaang@gmail.com)

## License

MIT License. See [`LICENSE`](LICENSE).
