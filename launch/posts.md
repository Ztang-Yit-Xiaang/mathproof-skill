# Launch posts

Core message: **Have a well-defined problem? This skill helps you prove it or disprove it, and checks the answer in Lean.**

- Site: https://ztang-yit-xiaang.github.io/mathproof-skill/
- Repo: https://github.com/Ztang-Yit-Xiaang/mathproof-skill
- Claude Code: `/plugin install mathproof-skill --marketplace Ztang-Yit-Xiaang/mathproof-skill`

---

## Lean Zulip — #Machine Learning for Theorem Proving

**Topic:** MathProof Skill: prove or disprove a well-defined claim, checked in Lean

Hi all. I've built an open-source "skill" (a packaged instruction set plus scripts) for coding agents such as Claude Code, Codex, and Antigravity. Give it a well-defined claim and it helps you prove it or disprove it. It does an adversarial informal pass first: list the hypotheses, look for counterexamples, and find the first unjustified step of a proof. Then it formalizes the claim, or its negation, in Lean 4 + Mathlib, and only calls the result machine-checked if a checker passes.

The part I'd most like feedback on is the trust boundary in `skill/scripts/lean_check.py`:

- it compiles with `lake env lean` against a pinned Mathlib (v4.32.0);
- it audits every declaration with `collectAxioms` and rejects anything beyond `propext`, `Classical.choice`, `Quot.sound` (so `sorryAx` hidden behind a macro and `native_decide` both fail);
- it statically rejects `implemented_by`, `@[extern]`, `unsafe`, and `debug.skipKernelTC`;
- it prints each required declaration's elaborated type, and the value for `Prop`-valued defs, so the agent has to fill in a fidelity table comparing the Lean statement with the informal one.

All 21 example cases are formalized in the repo: proofs of the true claims and formal refutations of the false ones. The most substantial is Nesterov's Theorem 2.1.14, the $O(1/k)$ rate of gradient descent for convex functions with an $L$-Lipschitz gradient on a real Hilbert space, proved from `ConvexOn` and `LipschitzWith L (∇ f)` with no extra assumptions. While formalizing it, the linter flagged the minimizer hypothesis as unused: the inequality holds for any reference point.

Are there other escape hatches the checker should catch? Are there better ways to make the fidelity comparison less dependent on the agent? Criticism welcome.

https://github.com/Ztang-Yit-Xiaang/mathproof-skill

---

## Hacker News — Show HN

**Title:** Show HN: Have a well-defined math problem? Prove or disprove it, checked in Lean

**URL:** https://ztang-yit-xiaang.github.io/mathproof-skill/

**First comment:**

If you have a well-defined problem, this skill helps your AI agent prove it or disprove it, and then checks the answer in Lean 4.

LLMs are trained to reach the conclusion you asked for, so when you ask for a proof you usually get one, even for a false claim. The failure is rarely arithmetic. It is usually a theorem applied outside its hypotheses, buried in fluent text. MathProof Skill is an open-source instruction set plus scripts that agents (Claude Code, Codex, Antigravity) load for proof work:

1. It decides whether to prove or refute: type every object, list every hypothesis, and look for counterexamples first. When auditing, it finds the *first* step that isn't justified by what comes before it.
2. It formalizes the claim, or its negation, in Lean 4 + Mathlib and runs a checker that rejects `sorry` (including one hidden behind a macro), custom axioms, `native_decide`, and kernel bypasses.
3. It fills in a fidelity table, because a correct proof of the wrong statement verifies nothing. Lean's junk values (`x/0 = 0`, truncated ℕ subtraction) are flagged explicitly.

The showcase is Nesterov's O(1/k) gradient descent rate, formalized from Mathlib's definitions alone. Formalizing it showed that the "x* is a minimizer" hypothesis isn't needed for the inequality.

Happy to answer questions, and especially interested in ways to fool the checker.

---

## Reddit — r/ClaudeAI

**Title:** Have a well-defined math problem? This Claude Code plugin helps you prove or disprove it, then checks the answer in Lean

Install: `/plugin install mathproof-skill --marketplace Ztang-Yit-Xiaang/mathproof-skill`

Give Claude a well-defined claim and it decides whether to prove or disprove it. It lists the hypotheses, hunts for counterexamples, finds the *first* unjustified step in a proof instead of polishing the conclusion, and, when Lean is installed, formalizes and machine-checks the answer (rejecting `sorry`, custom axioms, and `native_decide`).

It also works in Codex and Antigravity (`./scripts/install.sh`). MIT licensed. Site with examples, including a Lean-checked proof of the O(1/k) rate of gradient descent: https://ztang-yit-xiaang.github.io/mathproof-skill/

---

## Reddit — r/math (frame as math content, not promotion)

**Title:** Formalizing the O(1/k) rate of gradient descent in Lean: the minimizer hypothesis isn't needed

The classical bound $f(x_k)-f(x^\star)\le L\|x_0-x^\star\|^2/(2k)$ (Nesterov, Thm 2.1.14) for convex $f$ with an $L$-Lipschitz gradient is usually stated with $x^\star$ a minimizer. When I formalized it in Lean/Mathlib, on a real Hilbert space and with the descent lemma and first-order convexity derived from scratch, the linter flagged the minimality hypothesis as unused: the inequality holds for every reference point $x^\star$. Minimality only matters for reading the left side as the optimality gap, which is then nonnegative.

Another detail: Lean defines $a/0=0$, so the main theorem has to be stated division-free, $k\,(f(x_k)-f(x^\star))\le\frac L2\|x_0-x^\star\|^2$, and the textbook form derived for $k\ge1$.

Write-up with every lemma: https://github.com/Ztang-Yit-Xiaang/mathproof-skill/blob/main/examples/06-gradient-descent-rate.md
Lean file (~170 lines): https://github.com/Ztang-Yit-Xiaang/mathproof-skill/blob/main/lean/MathProofSkill/Evals/Optimization003.lean

(It comes from a tool I built that helps AI agents prove or disprove well-defined claims and check them in Lean, but the math stands on its own.)

---

## X / Bluesky / Mathstodon thread

1/ Have a well-defined math problem? I built an open-source AI agent skill that helps you prove it or disprove it, then checks the answer in Lean 4. 🧵 https://ztang-yit-xiaang.github.io/mathproof-skill/ [attach og.png]

2/ It starts adversarially: list every hypothesis, hunt for counterexamples, and find the first step of a proof that isn't earned. Later algebra can't rescue an unsupported step.

3/ Then Lean. The checker rejects `sorry`, even when hidden behind a macro, along with custom axioms, `native_decide`, and kernel bypasses. It prints the elaborated statement so you can confirm the theorem proved is the one claimed.

4/ Showcase: Nesterov's O(1/k) rate for gradient descent, proved from Mathlib's definitions. Lean flagged the "x* is a minimizer" hypothesis as unused: the bound holds for any reference point.

5/ Works in Claude Code (as a plugin), Codex, and Antigravity. MIT. https://github.com/Ztang-Yit-Xiaang/mathproof-skill

---

## LinkedIn

Have a well-defined math problem? I released MathProof Skill, an open-source tool that helps AI coding agents (Claude Code, Codex, Antigravity) prove it or disprove it, and then machine-checks the answer in Lean 4 with Mathlib.

Why: language models are trained to reach the requested conclusion, so they can produce fluent proofs of false claims. The skill lists every hypothesis, searches for counterexamples, finds the first unsupported step in a proof, and only calls a result machine-checked when a Lean checker passes with standard axioms only.

Highlights:
• 21 example problems, each proved or refuted and checked in Lean in CI.
• A graduate-level showcase: the O(1/k) convergence rate of gradient descent, formalized from first principles.
• Installs as a Claude Code plugin in one command.

Site: https://ztang-yit-xiaang.github.io/mathproof-skill/
