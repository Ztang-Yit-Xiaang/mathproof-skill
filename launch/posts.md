# Launch posts (drafts)

Post one venue at a time, from your own accounts, and answer every reply. Links:

- Site: https://ztang-yit-xiaang.github.io/mathproof-skill/
- Repo: https://github.com/Ztang-Yit-Xiaang/mathproof-skill
- Benchmark: https://github.com/Ztang-Yit-Xiaang/mathproof-skill/blob/main/evals/results/README.md

---

## Lean Zulip — #Machine Learning for Theorem Proving

**Topic:** MathProof Skill: an agent skill that checks its own proof verdicts in Lean

Hi all. I've been building an open-source "skill" (a packaged instruction set plus scripts) that coding agents such as Claude Code, Codex, and Antigravity load when asked to prove or audit a proof. It does an informal adversarial audit first. Then it formalizes the claim, or its negation, and only calls the result machine-checked if a checker passes.

The part I'd most like feedback on is the trust boundary in `skill/scripts/lean_check.py`:

- it compiles with `lake env lean` against a pinned Mathlib (v4.32.0);
- it audits every declaration with `collectAxioms` and rejects anything beyond `propext`, `Classical.choice`, `Quot.sound` (so `sorryAx` hidden behind a macro and `native_decide` both fail);
- it statically rejects `implemented_by`, `@[extern]`, `unsafe`, and `debug.skipKernelTC`;
- it prints each required declaration's elaborated type, and the value for `Prop`-valued defs, so the agent has to fill in a fidelity table comparing the Lean statement with the informal one.

The benchmark has 21 cases, all formalized in the repo. The most substantial is Nesterov's Theorem 2.1.14, the $O(1/k)$ rate of gradient descent for convex functions with an $L$-Lipschitz gradient on a real Hilbert space, proved from `ConvexOn` and `LipschitzWith L (∇ f)` with no extra assumptions. While formalizing it, the linter flagged the minimizer hypothesis as unused: the inequality holds for any reference point, and minimality only matters for interpreting the left side as the optimality gap.

What I'm unsure about: are there other escape hatches the checker should catch? Are there better ways to make the fidelity comparison less dependent on the agent's honesty? Criticism welcome.

Repo: https://github.com/Ztang-Yit-Xiaang/mathproof-skill

---

## Hacker News — Show HN

**Title:** Show HN: An AI agent skill that won't accept a proof until Lean checks it

**URL:** https://ztang-yit-xiaang.github.io/mathproof-skill/

**First comment:**

LLMs are trained to reach the conclusion you asked for, so when you ask for a proof you usually get one, even for a false claim. The failure is rarely arithmetic. It is usually a theorem applied outside its hypotheses, buried in otherwise fluent text.

MathProof Skill is an open-source instruction set plus scripts that agents (Claude Code, Codex, Antigravity) load for proof work. It has three parts:

1. An adversarial audit protocol: type every object, list every hypothesis, look for counterexamples first, and find the *first* step that isn't justified by what comes before it. Later algebra can't rescue that step.
2. Lean 4 + Mathlib checking: formalize the claim (or its negation), prove it, and run a checker that rejects `sorry` (including one hidden behind a macro), custom axioms, `native_decide`, and kernel bypasses.
3. A fidelity table, because a correct proof of the wrong statement verifies nothing. Lean's junk values (`x/0 = 0`, truncated ℕ subtraction) are flagged explicitly.

Honest caveat: I also benchmarked Claude Haiku and Sonnet with and without the skill on the 21 cases, and both already score 19–21/21 either way. The informal set is too easy, and the skill even made the small model over-strict on two valid proofs. Every raw answer is in the repo. What the skill adds on easy cases is the Lean layer: all 21 cases are formalized and checked in CI. I'm collecting harder cases, so if you have a flawed proof that fools current models, please send it.

The showcase is Nesterov's O(1/k) gradient descent rate, formalized from Mathlib's definitions alone. Formalizing it showed that the "x* is a minimizer" hypothesis isn't needed for the inequality.

Happy to answer questions. I'm especially interested in ways to fool the checker.

---

## Reddit — r/ClaudeAI

**Title:** I made a Claude Code plugin that audits math proofs step by step and checks the verdict in Lean

Install: `/plugin install mathproof-skill --marketplace Ztang-Yit-Xiaang/mathproof-skill`

It makes Claude find the *first* unjustified step of a proof instead of polishing the conclusion, search for counterexamples, and, when Lean is available, formalize and machine-check the verdict (rejecting `sorry`, custom axioms, and `native_decide`). I also benchmarked it honestly: on the current 21 cases, Haiku and Sonnet already score 19–21/21 without it, so I'm looking for harder flawed proofs. Send me ones that fool Claude!

It also works in Codex and Antigravity (`./scripts/install.sh`). MIT licensed. Site with examples: https://ztang-yit-xiaang.github.io/mathproof-skill/

---

## Reddit — r/math (frame as math content, not promotion)

**Title:** Formalizing the O(1/k) rate of gradient descent in Lean: the minimizer hypothesis isn't needed

The classical bound $f(x_k)-f(x^\star)\le L\|x_0-x^\star\|^2/(2k)$ (Nesterov, Thm 2.1.14) for convex $f$ with an $L$-Lipschitz gradient is usually stated with $x^\star$ a minimizer. When I formalized it in Lean/Mathlib, on a real Hilbert space and with the descent lemma and first-order convexity derived from scratch, the linter flagged the minimality hypothesis as unused: the inequality holds for every reference point $x^\star$. Minimality only matters for reading the left side as the optimality gap, which is then nonnegative.

Another detail: Lean defines $a/0=0$, so the main theorem has to be stated division-free, $k\,(f(x_k)-f(x^\star))\le\frac L2\|x_0-x^\star\|^2$, and the textbook form derived for $k\ge1$.

Write-up with every lemma: https://github.com/Ztang-Yit-Xiaang/mathproof-skill/blob/main/examples/06-gradient-descent-rate.md
Lean file (~170 lines): https://github.com/Ztang-Yit-Xiaang/mathproof-skill/blob/main/lean/MathProofSkill/Evals/Optimization003.lean

(It's part of a project that makes AI agents check proofs in Lean, but the math stands on its own.)

---

## X / Bluesky / Mathstodon thread

1/ AI-written proofs fail quietly: the algebra looks polished, but one unsupported step is buried in the middle. I built an open-source agent skill that hunts for that step first, then machine-checks the verdict in Lean 4. 🧵 https://ztang-yit-xiaang.github.io/mathproof-skill/ [attach og.png]

2/ The rule: when a step is challenged, freeze the proof just before it and re-derive the step from facts already available. Later algebra can't rescue an unsupported step.

3/ Then Lean. The checker rejects `sorry`, even when hidden behind a macro, along with custom axioms, `native_decide`, and kernel bypasses. It prints the elaborated statement so you can check the theorem proved is the one claimed.

4/ Showcase: Nesterov's O(1/k) rate for gradient descent, proved from Mathlib's definitions. Lean flagged the "x* is a minimizer" hypothesis as unused: the bound holds for any reference point.

5/ Honest benchmark: on my 21 cases, current models already score 19–21/21 without the skill, so I need harder ones. Send me a flawed proof that fools your favorite model. Works in Claude Code (as a plugin), Codex, and Antigravity. MIT. https://github.com/Ztang-Yit-Xiaang/mathproof-skill

---

## LinkedIn

I released MathProof Skill, an open-source tool that makes AI coding agents (Claude Code, Codex, Antigravity) audit mathematical proofs adversarially and machine-check their verdicts in Lean 4 with Mathlib.

Why: language models are trained to reach the requested conclusion, so they produce fluent proofs of false claims. The skill looks for the first unsupported step, searches for counterexamples, and only calls a result machine-checked when a Lean checker passes with standard axioms only.

Highlights:
• An open benchmark with every raw model answer published, including the cases where the skill didn't help.
• All 21 benchmark cases are formalized and checked in Lean in CI.
• A graduate-level showcase: the O(1/k) convergence rate of gradient descent, formalized from first principles.

Site: https://ztang-yit-xiaang.github.io/mathproof-skill/
