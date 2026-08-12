# MathProof Skill

[![Validate](https://github.com/Ztang-Yit-Xiaang/mathproof-skill/actions/workflows/validate.yml/badge.svg)](https://github.com/Ztang-Yit-Xiaang/mathproof-skill/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A correctness-first AI skill that tries to break a mathematical proof before it accepts it.

AI-generated proofs often fail in a dangerous way: the algebra looks polished, but one unsupported implication is quietly buried in the middle. MathProof Red Team changes the workflow from “reach the requested conclusion” to “verify that every dependency is earned.”

It is **not a formal theorem prover** and does **not guarantee correctness**. It is a structured system for reducing hidden logical errors, locating the first failure, and separating diagnosis from repair.

## The core idea

```text
Claim -> Assumptions -> Adversarial audit -> Dependency map
      -> Proof or inspection -> Second audit -> Verdict
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

Possible verdicts are `VALID`, `INVALID`, `CONDITIONALLY VALID`, `INCOMPLETE`, and `UNVERIFIED`.

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
│   └── references/
├── examples/               # Human-readable demonstrations
├── evals/                  # Adversarial benchmark cases
├── scripts/                # Deterministic benchmark validation
└── launch/                 # Xiaohongshu launch materials
```

## Install

Copy the `skill/` directory into your agent's personal skills directory and name the destination `mathproof-red-team`. The resulting install should have `SKILL.md` at its root:

```text
mathproof-red-team/
├── SKILL.md
└── references/
```

Then ask the agent to use `@mathproof-red-team` on a proof problem or proof audit.

## Try it

```text
Use @mathproof-red-team in AUDIT mode. Number the material steps,
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

The benchmark tests whether an agent localizes the right failure; it is not evidence that every future verdict is correct.

## Project status

This is an experimental `v0.1.0` release. The immediate goal is to expand the benchmark with independently reviewed valid proofs and subtle research-math failure cases.

Contributions are welcome, especially minimal counterexamples, missing-assumption cases, and valid proofs that prevent the auditor from becoming reflexively negative. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Author

**Yit Xiaang Ztang** — [ztangyitxiaang@gmail.com](mailto:ztangyitxiaang@gmail.com)

## License

MIT License. See [`LICENSE`](LICENSE).
