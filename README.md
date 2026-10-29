# MathProof Skill

[![Validate](https://github.com/Ztang-Yit-Xiaang/mathproof-skill/actions/workflows/validate.yml/badge.svg)](https://github.com/Ztang-Yit-Xiaang/mathproof-skill/actions/workflows/validate.yml)
[![Lean](https://github.com/Ztang-Yit-Xiaang/mathproof-skill/actions/workflows/lean.yml/badge.svg)](https://github.com/Ztang-Yit-Xiaang/mathproof-skill/actions/workflows/lean.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Have a well-defined problem? This skill helps you prove it or disprove it, and checks the answer in Lean.**
>
> A correctness-first AI skill that tries to break a mathematical proof before it accepts it.

**Website:** https://ztang-yit-xiaang.github.io/mathproof-skill/

AI-generated proofs often fail in a dangerous way: the algebra looks polished, but one unsupported implication is quietly buried in the middle. MathProof Skill changes the workflow from “reach the requested conclusion” to “verify that every dependency is earned.”

The reasoning is informal, and an informal audit does **not guarantee correctness**. To check results, the skill uses **Lean 4 with Mathlib**: it formalizes the claim (or its negation), checks that the formal statement says what the informal one says, proves it, and runs a checker that rejects `sorry`, custom axioms, and kernel bypasses. Only a check that passes counts as machine-checked.

<!-- BEGIN portfolio-project-animations -->
## Animated project guide

These self-contained SVG animations explain the project workflow. They are illustrative guides, not recorded experiments or new performance results. Static content remains available when reduced motion is requested.

### Audit the implication

![Audit the implication — illustrative animation](docs/portfolio-animations/mathproof-skill.svg)

A conceptual counterexample walkthrough. This animation does not call an agent or execute Lean.

<!-- END portfolio-project-animations -->

## Why not just ask an LLM?

A chatbot gives a fluent answer you must still check yourself, and rarely says it is unsure. MathProof Skill adds:

- **The exact first failing step plus a counterexample**, pinpointing where reasoning breaks down rather than offering vague skepticism.
- **A Lean 4 proof or refutation checked by the kernel**, where the checker rejects `sorry`, custom axioms, and `native_decide`.
- **A fidelity check comparing the Lean statement with the original question**, ensuring it cannot quietly prove an easier theorem.
- **Honest labels** (`LEAN-CHECKED (partial)`, `NOT FORMALIZED`, `UNVERIFIED`) instead of a confident guess.

In short: you trust the proof checker, not the prose.

## The core idea

```text
Claim -> Assumptions -> Adversarial audit -> Dependency map
      -> Proof or inspection -> Second audit -> Lean check -> Verdict
```

The distinctive rule is simple:

> When a step is challenged, freeze the proof immediately before that step and re-derive it using only facts already available. Later algebra cannot rescue an unsupported step.

## Ten-second example

**Proposed reasoning**

$$
f'(x)>0 \quad\Longrightarrow\quad f(x)>0.
$$

**Audit: `INVALID`**

The premise establishes that $f$ is increasing, not that its values are positive. Let $f(x)=x$ on $(-2,-1)$. Then $f'(x)=1>0$, while $f(x)<0$ throughout the domain.

## Examples

Each example below is an evaluation case. The Lean code is the file in `lean/MathProofSkill/Evals/`, and the output is from a real run of `skill/scripts/lean_check.py` (paths shortened).

### 1. Refuting a plausible claim: `INVALID` · `LEAN-CHECKED`

> *Claim.* Every continuous function on $(0,1)$ attains a maximum.

**First unsupported step:** applying the extreme value theorem, which needs a compact domain; $(0,1)$ is bounded but not closed. **Counterexample:** $f(x)=x$ has no maximum on $(0,1)$.

```lean
def Claim : Prop :=
  ∀ f : ℝ → ℝ, ContinuousOn f (Ioo 0 1) → ∃ x ∈ Ioo (0 : ℝ) 1, IsMaxOn f (Ioo 0 1) x

theorem claim_false : ¬ Claim := by
  intro h
  obtain ⟨x, ⟨hx0, hx1⟩, hmax⟩ := h id continuousOn_id
  have hy : (x + 1) / 2 ∈ Ioo (0 : ℝ) 1 := ⟨by linarith, by linarith⟩
  have : (x + 1) / 2 ≤ x := hmax hy
  linarith
```

```text
PASS: lean/MathProofSkill/Evals/Analysis001.lean
  MathProofSkill.Evals.Analysis001.Claim : Prop
    := ∀ (f : ℝ → ℝ), ContinuousOn f (Set.Ioo 0 1) → ∃ x ∈ Set.Ioo 0 1, IsMaxOn f (Set.Ioo 0 1) x
  MathProofSkill.Evals.Analysis001.claim_false : ¬MathProofSkill.Evals.Analysis001.Claim
    axioms: propext, Classical.choice, Quot.sound
```

The checker prints the full body of `Claim`, so the reader can confirm that the refuted statement is the informal one and not a weaker look-alike.

### 2. Accepting a correct proof: `VALID` · `LEAN-CHECKED`

> *Claim.* The square of an even integer is even. *Proof.* $n=2k\Rightarrow n^2=2(2k^2)$.

A skeptical auditor must also accept correct work. The Lean proof follows the informal witness argument, but with one encoding detail the fidelity check catches: Mathlib defines `Even n` as $\exists r,\ n=r+r$, not $n=2r$.

```lean
theorem even_sq (n : ℤ) (h : Even n) : Even (n ^ 2) := by
  obtain ⟨k, rfl⟩ := h          -- n = k + k
  exact ⟨2 * k ^ 2, by ring⟩    -- (k + k)^2 = 2k^2 + 2k^2
```

```text
PASS: lean/MathProofSkill/Evals/Number001.lean
  MathProofSkill.Evals.Number001.even_sq : ∀ (n : ℤ), Even n → Even (n ^ 2)
    axioms: propext
```

### 3. A probability trap: `INVALID` · `LEAN-CHECKED`

> *Claim.* For every square-integrable $X$, $\mathbb{E}[X^2]=(\mathbb{E}[X])^2$.

**Counterexample:** $X=\pm1$ with probability $1/2$ each, so $\mathbb{E}[X]=0$ but $\mathbb{E}[X^2]=1$. The Lean file builds that probability space (the uniform measure on `Bool`), proves `X` is in $L^2$, computes both moments, and derives `¬ Claim`:

```lean
theorem mean_X : ∫ b, X b ∂P = 0 := by rw [integral_P]; norm_num [X]
theorem second_moment_X : ∫ b, X b ^ 2 ∂P = 1 := by rw [integral_P]; norm_num [X]

theorem claim_false : ¬ Claim := by
  intro h
  have := h X X_memLp
  rw [mean_X, second_moment_X] at this
  norm_num at this
```

```text
PASS: lean/MathProofSkill/Evals/Probability003.lean
  MathProofSkill.Evals.Probability003.claim_false : ¬MathProofSkill.Evals.Probability003.Claim
    axioms: propext, Classical.choice, Quot.sound
```

### 4. Honest scope: `VALID` · `LEAN-CHECKED (partial: simple graphs)`

> *Claim.* In a finite undirected graph, the degrees sum to twice the number of edges.

Mathlib's `SimpleGraph` has no loops or multi-edges, so the Lean theorem covers only part of the informal claim. The skill reports that instead of claiming full coverage:

```text
PASS: lean/MathProofSkill/Evals/Combinatorics001.lean
  MathProofSkill.Evals.Combinatorics001.handshake : ∀ {V : Type u_1} [inst : Fintype V] [DecidableEq V]
      (G : SimpleGraph V) [inst_2 : DecidableRel G.Adj], ∑ v, G.degree v = 2 * G.edgeFinset.card
```

| Informal | Lean | Match |
| --- | --- | --- |
| finite graph | `[Fintype V]` | faithful |
| undirected graph | `SimpleGraph V` | **partial**: excludes loops and multi-edges |
| sum of degrees = 2·edges | `∑ v, G.degree v = 2 * G.edgeFinset.card` | faithful |

### 5. Catching a fake proof: checker `FAIL`

A `sorry` hidden behind a custom tactic contains no literal `sorry`, so searching the source does not find it. The axiom audit does:

```lean
macro "trust_me" : tactic => `(tactic| exact sorryAx _ false)
theorem t (n : Nat) : n * 1 = n := by trust_me
```

```text
FAIL: tests/lean_check/fail_hidden_sorry.lean
  ✗ Lean warning: …fail_hidden_sorry.lean:3:8: warning: declaration uses `sorry`
  ✗ t depends on non-standard axioms: sorryAx
```

The same audit rejects custom `axiom`s and `native_decide` (which trusts compiled code). See [`tests/lean_check/`](tests/lean_check/) for every case.

### 6. Basic Optimization Example Proof: the $O(1/k)$ rate of gradient descent · `VALID` · `LEAN-CHECKED`

> *Theorem* (Nesterov, *Lectures on Convex Optimization*, Thm 2.1.14). Let $f$ be convex and differentiable on a real Hilbert space, with $L$-Lipschitz gradient. Gradient descent $x_{k+1}=x_k-\frac1L\nabla f(x_k)$ satisfies
> $$f(x_k)-f(x^\star)\le\frac{L\,\|x_0-x^\star\|^2}{2k}\qquad(k\ge1).$$

The skill proves it in **PROVE** mode as a chain of named lemmas, each mirrored by a Lean theorem:

| Step | Statement | Lean |
| --- | --- | --- |
| Descent lemma | $f(y)\le f(x)+\langle\nabla f(x),y-x\rangle+\frac L2\|y-x\|^2$ | `descent_lemma` |
| First-order convexity | $f(x)+\langle\nabla f(x),y-x\rangle\le f(y)$ | `convex_first_order` |
| Sufficient decrease | $f(x_{k+1})\le f(x_k)-\frac1{2L}\|\nabla f(x_k)\|^2$ | `sufficient_decrease` |
| One-step progress | $f(x_{k+1})-f^\star\le\frac L2(\|x_k-x^\star\|^2-\|x_{k+1}-x^\star\|^2)$ | `one_step` |
| Lyapunov bound | $\Phi_k=k(f(x_k)-f^\star)+\frac L2\|x_k-x^\star\|^2$ is nonincreasing | `lyapunov` |
| Rate | $k(f(x_k)-f^\star)\le\frac L2\|x_0-x^\star\|^2$ | `gd_rate`, `gd_rate'` |

Nothing beyond Mathlib's definitions is assumed: the descent lemma is derived from `LipschitzWith L (∇ f)` with a mean-value argument along the segment, and first-order convexity from `ConvexOn` by restricting $f$ to a line.

```lean
theorem gd_rate' {f : E → ℝ} {L : ℝ≥0} (hL0 : 0 < L) (hf : Differentiable ℝ f)
    (hL : LipschitzWith L (∇ f)) (x : ℕ → E)
    (hx : ∀ k, x (k + 1) = x k - (1 / (L : ℝ)) • ∇ f (x k))
    (hconv : ConvexOn ℝ univ f) {xstar : E} (k : ℕ) (hk : 0 < k) :
    f (x k) - f xstar ≤ L * ‖x 0 - xstar‖ ^ 2 / (2 * k)
```

```text
PASS: lean/MathProofSkill/Evals/Optimization003.lean
  …Optimization003.gd_rate' : … → ConvexOn ℝ Set.univ f → ∀ {xstar : E} (k : ℕ), 0 < k →
      f (x k) - f xstar ≤ ↑L * ‖x 0 - xstar‖ ^ 2 / (2 * ↑k)
    axioms: propext, Classical.choice, Quot.sound
```

**What the formal proof found.** The hypothesis "$`x^\star`$ is a minimizer" is never used: Lean's linter flagged it as unused. The bound holds for every reference point $x^\star$; minimality only matters for reading $f(x_k)-f(x^\star)$ as the optimality gap. The formal theorem omits the hypothesis, which makes it strictly stronger. The fidelity check also caught a junk-value trap: Lean defines $a/0=0$, so the primary theorem is stated division-free and the textbook form is derived only for $k\ge1$.

The full write-up, with proofs of every lemma, the post-audit, and the fidelity table, is [Example 6](examples/06-gradient-descent-rate.md).

More worked audits, including fidelity tables, are in [`examples/`](examples/). [Example 7](examples/07-assumption-that-hurts.md) shows the assumption cost audit rejecting a tempting repair: "assume $A$ invertible" fixes the proof of "$A^2=0 \implies A=0$" only by making its hypotheses unsatisfiable.

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

**Claude Code (plugin, one step):**

```text
/plugin install mathproof-skill --marketplace Ztang-Yit-Xiaang/mathproof-skill
```

On older Claude Code versions, run `/plugin marketplace add Ztang-Yit-Xiaang/mathproof-skill` first, then `/plugin install mathproof-skill@mathproof`.

**Every agent on the machine (Claude Code, Codex, Antigravity) plus the Lean project:**

```bash
git clone https://github.com/Ztang-Yit-Xiaang/mathproof-skill.git
cd mathproof-skill && ./scripts/install.sh
```

The installer also links `~/.mathproof/lean`, so the Lean checker works outside the repository. `scripts/uninstall.sh` reverses it.

**Manually:** Copy the `skill/` directory into your agent's personal skills directory and name the destination `mathproof-skill`. The resulting install should have `SKILL.md` at its root:

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
