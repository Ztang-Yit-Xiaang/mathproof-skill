# Basic Proof Strategies

Read this when choosing the outer structure of a proof, and when auditing one. A proof's outer structure is fixed by the logical form of what it proves. Domain techniques (bounds, invariants, spectral arguments) fill in the steps; they are in [proof-techniques-and-heuristics.md](proof-techniques-and-heuristics.md).

Each strategy below gives:

- **Form:** the statement it proves.
- **Why it is valid:** the logical law behind it.
- **Use it when:** signals in the problem.
- **Skeleton:** the shape the written proof must have. Every line in the skeleton must appear in the proof, in some wording.
- **Example:** a short instance.
- **Audit:** what to check, in a proof that claims to use it.
- **Lean:** the matching tactics. Every Lean block here compiles against the project's Mathlib (`lean/`).

## Contents

1. Choosing a strategy
2. Direct proof
3. Contrapositive
4. Contradiction
5. Contrapositive versus contradiction
6. Proof by cases
7. Proof by exhaustion
8. Biconditionals and equivalence chains
9. Existence: constructive and nonconstructive
10. Uniqueness
11. Counterexamples and disproof
12. Induction
13. Strong induction
14. Well-ordering and minimal counterexamples
15. Pigeonhole and double counting
16. Combining strategies
17. Errors to check in any proof
18. Sources

---

## 1. Choosing a strategy

Before writing, rewrite the claim with every quantifier and connective explicit. "Squares of odd numbers are odd" becomes $\forall n \in \mathbb{Z},\ n \text{ odd} \Rightarrow n^2 \text{ odd}$. Then read the outermost symbol, and work inward.

| Outermost form | First choice | Switch when |
|---|---|---|
| $\forall x \in S,\ \dots$ | Fix an arbitrary $x \in S$; prove the body for it. | $S = \mathbb{N}$ and the case $n$ needs smaller cases: induction (Section 12, 13). |
| $P \Rightarrow Q$ | Direct (Section 2). | $\neg Q$ is concrete and $Q$ is not: contrapositive (Section 3). Neither $P$ nor $\neg Q$ gives anything: contradiction (Section 4). |
| $P \iff Q$ | Prove $P \Rightarrow Q$ and $Q \Rightarrow P$ separately (Section 8). | Every step is reversible: a chain of $\iff$, checked step by step. |
| $\exists x,\ P(x)$ | Exhibit $x$, verify $P(x)$ (Section 9). | No witness is in sight: nonconstructive existence (Section 9). |
| $\exists!\, x,\ P(x)$ | Existence, then uniqueness (Section 10). | |
| $\neg P$ (irrational, infinite, impossible, no solution) | Contradiction: assume $P$ (Section 4). | |
| $P \vee Q$ | Assume $\neg P$, prove $Q$. | One of the two follows from a case split: cases (Section 6). |
| $P \wedge Q$ | Prove each separately. | |
| A claim to refute | Counterexample (Section 11). | |

When the hypotheses, not the goal, split into a few kinds (sign, parity, residue, order), split on them: cases (Section 6).

**Negating a statement.** Contrapositive, contradiction, and counterexamples all need a correct negation. Push $\neg$ inward one symbol at a time:

- $\neg \forall x, P(x) \equiv \exists x, \neg P(x)$, and $\neg \exists x, P(x) \equiv \forall x, \neg P(x)$.
- $\neg(P \wedge Q) \equiv \neg P \vee \neg Q$, and $\neg(P \vee Q) \equiv \neg P \wedge \neg Q$.
- $\neg(P \Rightarrow Q) \equiv P \wedge \neg Q$. The negation of an implication is not an implication.
- $\neg(a < b) \equiv a \ge b$ in a linear order. In a partial order it is not.
- A bounded quantifier keeps its bound: $\neg(\forall x \in S, P(x)) \equiv \exists x \in S, \neg P(x)$.
- "For every $\varepsilon > 0$ there is $\delta > 0$ such that for all $x$, $|x - a| < \delta \Rightarrow |f(x) - L| < \varepsilon$" negates to "there is $\varepsilon > 0$ such that for every $\delta > 0$ there is $x$ with $|x - a| < \delta$ and $|f(x) - L| \ge \varepsilon$".

Write the negation out in full before using it.

---

## 2. Direct proof

- **Form:** $P \Rightarrow Q$, or $\forall x,\ P(x) \Rightarrow Q(x)$.
- **Why it is valid:** modus ponens. If every step follows from $P$ and earlier steps, then $Q$ follows from $P$.
- **Use it when:** $P$ gives a concrete object or equation to work with, such as "$n$ is even" gives $n = 2k$.
- **Skeleton:**
  1. Let $x$ be arbitrary (if the claim is universal). Assume $P(x)$.
  2. Unfold the definitions in $P(x)$ into usable facts.
  3. Derive facts until one of them is $Q(x)$ by definition.
  4. Conclude $Q(x)$; since $x$ was arbitrary, the universal claim holds.
- **Example:** if $a$ and $b$ are even, $a + b$ is even. Write $a = 2k$, $b = 2m$ with $k, m \in \mathbb{Z}$. Then $a + b = 2(k + m)$, and $k + m \in \mathbb{Z}$, so $a + b$ is even.
- **Audit:**
  - The variable is arbitrary: no step assumes a property of $x$ that $P$ does not give.
  - The proof starts from $P$ and ends at $Q$. A proof that starts from $Q$ and reaches a true statement (such as $0 = 0$) proves $Q \Rightarrow \text{true}$, which says nothing, unless every step is reversible and is stated as $\iff$.
  - Each fresh name gets a fresh letter: $a = 2k$ and $b = 2k$ would wrongly force $a = b$.

```lean
example (a b : ℤ) (ha : Even a) (hb : Even b) : Even (a + b) := by
  obtain ⟨k, hk⟩ := ha
  obtain ⟨m, hm⟩ := hb
  exact ⟨k + m, by rw [hk, hm]; ring⟩
```

---

## 3. Contrapositive

- **Form:** $P \Rightarrow Q$.
- **Why it is valid:** $P \Rightarrow Q$ and $\neg Q \Rightarrow \neg P$ are logically equivalent: both are false exactly when $P$ holds and $Q$ fails.
- **Use it when:** $\neg Q$ is a concrete statement and $Q$ is not. "If $n^2$ is even then $n$ is even": $P$ gives $n^2 = 2k$, which says little about $n$, but $\neg Q$ gives $n = 2k + 1$, which squares directly.
- **Skeleton:**
  1. "We prove the contrapositive: if $\neg Q$ then $\neg P$."
  2. Assume $\neg Q$, written out in positive form (for example "$n$ is odd", not "$n$ is not even").
  3. Prove $\neg P$ directly.
  4. Conclude $P \Rightarrow Q$.
- **Example:** if $n^2$ is even, $n$ is even. Contrapositive: if $n$ is odd, $n^2$ is odd. Write $n = 2k + 1$; then $n^2 = 2(2k^2 + 2k) + 1$ is odd.
- **Audit:**
  - The proof assumes $\neg Q$ and reaches $\neg P$. Two errors look similar:
    - the **converse** $Q \Rightarrow P$;
    - the **inverse** $\neg P \Rightarrow \neg Q$.

    Neither is equivalent to $P \Rightarrow Q$.
  - With quantifiers, only the implication is contraposed: $\forall x, (P(x) \Rightarrow Q(x))$ becomes $\forall x, (\neg Q(x) \Rightarrow \neg P(x))$. The quantifier stays.
  - With several hypotheses $P_1 \wedge P_2 \Rightarrow Q$, the contrapositive is $\neg Q \Rightarrow \neg P_1 \vee \neg P_2$. Usually you keep $P_1$ as a standing assumption and prove $P_1 \wedge \neg Q \Rightarrow \neg P_2$; say which hypothesis you keep.

```lean
example (n : ℕ) (h : Even (n ^ 2)) : Even n := by
  contrapose! h
  rw [Nat.not_even_iff_odd] at h ⊢
  exact h.pow
```

`contrapose! h` turns hypothesis `h : P` and goal `Q` into hypothesis `¬Q` and goal `¬P`, pushing negations inward.

---

## 4. Contradiction

- **Form:** any statement $P$. Most useful when $P$ is negative: irrational, infinite, impossible, no solution.
- **Why it is valid:** if $\neg P$ implies a falsehood, $\neg P$ is false, so $P$ holds (classical logic; see the note on constructive logic below).
- **Use it when:**
  - $P$ is a negative statement: its negation gives an object to work with. "$\sqrt 2$ is irrational" is hard to use directly; "$\sqrt 2 = a/b$" is an equation.
  - $P$ says something is infinite: its negation gives a finite list.
- **Skeleton:**
  1. "Suppose, for contradiction, that $\neg P$." Write $\neg P$ out in positive form.
  2. Derive consequences.
  3. Reach a specific statement $R$ and its negation $\neg R$. Name both.
  4. "This contradiction shows $P$."
- **Example:** $\sqrt 2$ is irrational. Suppose $\sqrt 2 = a/b$ with $a, b$ positive integers and $\gcd(a, b) = 1$. Then $a^2 = 2b^2$, so $a$ is even; write $a = 2c$. Then $b^2 = 2c^2$, so $b$ is even. Both are even, contradicting $\gcd(a, b) = 1$.
- **Audit:**
  - **The contradiction uses the assumption.** Find where $\neg P$ is used. If the contradiction can be reached without it, the hypotheses are inconsistent and the theorem is vacuous (see the consistency check in `SKILL.md`).
  - **The contradiction is named.** "This is absurd" without naming $R$ and $\neg R$ hides gaps.
  - **The assumption is the full negation.** In the example, "$\sqrt 2 = a/b$ in lowest terms" is allowed only because every rational has such a form; a proof that assumes extra properties of the counterexample must justify them.
  - **Every step is still checked.** Once the assumption is false, any wrong step also "leads to a contradiction", so an error in the middle is invisible from the conclusion.
- **Constructive logic:** proving $\neg P$ by assuming $P$ and deriving a falsehood is valid in every logic, since that is what $\neg P$ means. Proving $P$ by refuting $\neg P$ needs the law of excluded middle. Lean's Mathlib is classical, so both are available; say which one a proof uses when the distinction matters (for example, when an algorithm is to be extracted).

```lean
example : ¬ ∃ n : ℕ, ∀ m : ℕ, m ≤ n := by
  rintro ⟨n, hn⟩
  have := hn (n + 1)
  omega

example (p : Prop) (h : ¬¬p) : p := by
  by_contra hp
  exact h hp
```

`by_contra h` adds `h : ¬goal` and asks for `False`; `by_contra! h` also pushes the negation inward.

---

## 5. Contrapositive versus contradiction

The two are often confused, because both begin by assuming something false-looking.

| | Contrapositive | Contradiction |
|---|---|---|
| Proves | $P \Rightarrow Q$ | any $P$ |
| Assumes | $\neg Q$ | $\neg(\text{goal})$; for $P \Rightarrow Q$, that is $P \wedge \neg Q$ |
| Aims at | the specific statement $\neg P$ | any falsehood $R \wedge \neg R$ |
| A wrong step shows up | as not reaching $\neg P$ | rarely: everything after a false assumption looks "consistent with a contradiction" |

A proof of $P \Rightarrow Q$ "by contradiction" that assumes $P \wedge \neg Q$, never uses $P$, and ends with $\neg P$ (contradicting $P$) is a contrapositive proof wearing extra words. Rewrite it as a contrapositive: it is shorter and says exactly what was shown.

Prefer the contrapositive when it applies. Use contradiction when the goal is a negative statement, or when the proof needs both $P$ and $\neg Q$ together.

---

## 6. Proof by cases

- **Form:** any goal $Q$, given $C_1 \vee C_2 \vee \cdots \vee C_k$.
- **Why it is valid:** disjunction elimination. If each $C_i$ implies $Q$ and one $C_i$ holds, $Q$ holds.
- **Use it when:** one quantity determines the next step, but only once its sign, parity, residue, or order is known. Absolute values, $\max$ and $\min$, piecewise definitions, and floor functions usually call for cases.
- **Skeleton:**
  1. State the cases and **why they cover everything**: "every integer is even or odd", "$x \ge 0$ or $x < 0$".
  2. Prove $Q$ in each case, labeled.
  3. Conclude $Q$.
- **Example:** $|x| \ge 0$ for real $x$. Either $x \ge 0$ or $x < 0$. If $x \ge 0$, $|x| = x \ge 0$. If $x < 0$, $|x| = -x > 0$.
- **Audit:**
  - **Exhaustive.** The cases cover every possibility, including boundaries ($x = 0$), degenerate objects (the empty set, the zero matrix), and equal parameters ($a = b$).
  - **Every case is done.** "The other case is similar" is acceptable only if the symmetry is stated: which substitution turns one case into the other, and why the hypotheses are preserved by it.
  - **"Without loss of generality".** WLOG $a \le b$ is valid only if the statement is symmetric in $a$ and $b$. Say why it is.
  - **The cases need not be disjoint,** but overlapping cases must agree where they overlap if the proof defines something by cases.

```lean
example (x : ℝ) : 0 ≤ |x| := by
  rcases le_or_gt 0 x with h | h
  · rw [abs_of_nonneg h]; exact h
  · rw [abs_of_neg h]; linarith

example (n : ℤ) : Even (n * (n + 1)) := by
  rcases Int.even_or_odd n with h | h
  · exact h.mul_right _
  · exact (h.add_one).mul_left _
```

`rcases h with h1 | h2` splits a hypothesis `h : A ∨ B`; `by_cases h : p` splits on any proposition `p`.

---

## 7. Proof by exhaustion

- **Form:** $\forall x \in S,\ P(x)$ with $S$ finite, or a claim that reduces to such a set.
- **Why it is valid:** a universal statement over a finite set is the conjunction of its instances.
- **Use it when:** a reduction leaves finitely many cases: residues modulo $n$, small values below a bound, the finitely many configurations of a small structure.
- **Skeleton:**
  1. Prove the reduction: why only these cases matter. This step is usually the real proof.
  2. List every case.
  3. Check each one, with the computation shown or with a mechanical check.
- **Example:** every perfect square is $\equiv 0$ or $1 \pmod 4$. Reduction: $n^2 \bmod 4$ depends only on $n \bmod 4$. Cases: $0^2 \equiv 0$, $1^2 \equiv 1$, $2^2 \equiv 0$, $3^2 \equiv 1$.
- **Audit:**
  - The reduction is proved, not just asserted.
  - The list is complete. Count it: four residues modulo 4, not three.
  - Checking some cases and saying "the pattern continues" is not exhaustion; it proves nothing about the unchecked cases.
  - A computer check counts as proof only if the program is shown or the check is reproducible. In Lean, `decide` makes the kernel do it.

```lean
example (n : ℕ) (h : n < 5) : n ^ 2 % 5 ≠ 2 := by
  interval_cases n <;> decide

example (n : ℤ) : n ^ 2 % 4 = 0 ∨ n ^ 2 % 4 = 1 := by
  have hn : n % 4 = 0 ∨ n % 4 = 1 ∨ n % 4 = 2 ∨ n % 4 = 3 := by omega
  rcases hn with h | h | h | h <;> simp [pow_two, Int.mul_emod, h]
```

---

## 8. Biconditionals and equivalence chains

- **Form:** $P \iff Q$, or "the following are equivalent: $P_1, \dots, P_n$".
- **Why it is valid:** $P \iff Q$ means $(P \Rightarrow Q) \wedge (Q \Rightarrow P)$. For $n$ statements, a cycle of implications $P_1 \Rightarrow P_2 \Rightarrow \cdots \Rightarrow P_n \Rightarrow P_1$ gives every implication by chaining.
- **Use it when:** the claim says "if and only if", "exactly when", "is equivalent to", "is characterized by", or "necessary and sufficient".
- **Skeleton:**
  1. "($\Rightarrow$)" Assume $P$; prove $Q$, by any strategy.
  2. "($\Leftarrow$)" Assume $Q$; prove $P$, by any strategy.

  Or, for a chain $P \iff R_1 \iff R_2 \iff \cdots \iff Q$, justify every link in both directions.
- **Example:** an integer $n$ is even iff $n^2$ is even. ($\Rightarrow$) direct: $n = 2k$ gives $n^2 = 2(2k^2)$. ($\Leftarrow$) contrapositive, as in Section 3.
- **Audit:**
  - Both directions are proved, and they are different. A common error proves one direction twice.
  - In a chain of $\iff$, check each link in the reverse direction too. Squaring, dividing by a quantity that may be zero, and taking a root of a quantity that may be negative are one-way steps.
  - For a cycle of $n$ statements, the cycle is closed: the last implication returns to $P_1$.

```lean
example (n : ℤ) : Even n ↔ Even (n ^ 2) := by
  constructor
  · intro h; exact Int.even_pow.mpr ⟨h, two_ne_zero⟩
  · intro h
    by_contra hn
    rw [Int.not_even_iff_odd] at hn
    exact (Int.not_even_iff_odd.mpr hn.pow) h

example (a b c : Prop) (hab : a → b) (hbc : b → c) (hca : c → a) : [a, b, c].TFAE := by
  tfae_have 1 → 2 := hab
  tfae_have 2 → 3 := hbc
  tfae_have 3 → 1 := hca
  tfae_finish
```

---

## 9. Existence: constructive and nonconstructive

- **Form:** $\exists x \in S,\ P(x)$.
- **Why it is valid:** a single witness establishes an existential statement.
- **Two kinds:**
  - **Constructive:** name $x$, or give a procedure that produces it, and check $P(x)$.
  - **Nonconstructive:** show existence without producing $x$. Typical tools:
    - contradiction: assume $\forall x, \neg P(x)$, derive a falsehood;
    - the intermediate value theorem, the extreme value theorem, compactness;
    - pigeonhole;
    - counting (more objects than bad objects);
    - the probabilistic method;
    - a case split in which a different witness works in each case, without knowing which case holds.
- **Use constructive when** a witness is in sight; it gives more information. **Use nonconstructive when** the witness depends on information you cannot compute, or when only existence is needed.
- **Skeleton (constructive):**
  1. "Let $x = \dots$."
  2. Check $x \in S$: type, domain, integrality, positivity, nonzero denominators.
  3. Check $P(x)$, every clause.
- **Example (nonconstructive):** there are irrational $a, b$ with $a^b$ rational. Either $\sqrt 2^{\sqrt 2}$ is rational, and then take $a = b = \sqrt 2$; or it is irrational, and then take $a = \sqrt 2^{\sqrt 2}$, $b = \sqrt 2$, for which $a^b = \sqrt 2^2 = 2$. The proof does not say which case holds.
- **Audit:**
  - **The witness is checked against every hypothesis,** not only the main property. A witness outside the domain refutes nothing and proves nothing.
  - **The witness does not depend on what it must handle.** In $\forall y\, \exists x$, $x$ may depend on $y$. In $\exists x\, \forall y$, $x$ must be chosen before $y$, so it cannot depend on $y$.
  - **The proof says which kind it is.** A nonconstructive proof gives no way to compute $x$; do not later use it as if $x$ were known.
  - **Choosing an object requires it to exist.** "Let $x$ be the smallest element" needs the set nonempty and a smallest element to exist; "let $x$ be a maximizer" needs the maximum to be attained.

```lean
example : ∃ n : ℤ, n ^ 2 = 25 := ⟨5, by norm_num⟩

example : ∃ x : ℝ, x ^ 2 = 2 ∧ 0 < x := by
  refine ⟨Real.sqrt 2, ?_, ?_⟩
  · exact Real.sq_sqrt (by norm_num)
  · exact Real.sqrt_pos.mpr (by norm_num)

example (f : ℕ → ℕ) (h : ¬ ∀ n, f n = 0) : ∃ n, f n ≠ 0 := by
  by_contra h'
  push Not at h'
  exact h h'
```

`use x` and `refine ⟨x, ?_⟩` supply a witness. In current Mathlib, `push Not` replaces the deprecated `push_neg`.

---

## 10. Uniqueness

- **Form:** $\exists!\, x,\ P(x)$, meaning $\exists x,\ P(x) \wedge \forall y,\ P(y) \Rightarrow y = x$.
- **Why it is valid:** this is the definition of $\exists!$.
- **Skeleton:**
  1. **Existence:** exhibit $x$ with $P(x)$ (Section 9).
  2. **Uniqueness:** let $y$ and $z$ both satisfy $P$; prove $y = z$. Alternatively, let $y$ satisfy $P$ and prove $y = x$.
- **Example:** $2x + 3 = 7$ has exactly one real solution. Existence: $x = 2$ works. Uniqueness: if $2y + 3 = 7$ then $y = 2$.
- **Audit:**
  - **Both halves are present.** Existence alone allows many solutions; uniqueness alone allows none.
  - **The uniqueness half does not assume the formula.** It starts from an arbitrary $y$ with $P(y)$, not from $y = 2$.
  - **"Unique" says in what sense:** unique as an element, up to isomorphism, up to sign, up to a set of measure zero. Name the equivalence.
  - Uniqueness is often proved by contradiction: assume $y \ne z$ both satisfy $P$, and derive a falsehood.

```lean
example : ∃! x : ℚ, 2 * x + 3 = 7 := by
  refine ⟨2, by norm_num, fun y hy => ?_⟩
  linarith
```

---

## 11. Counterexamples and disproof

- **Form:** refuting $\forall x,\ P(x)$ by exhibiting $x$ with $\neg P(x)$. Refuting $P \Rightarrow Q$ by exhibiting a case where $P$ holds and $Q$ fails.
- **Why it is valid:** $\neg \forall x, P(x) \equiv \exists x, \neg P(x)$.
- **Use it when:** small cases fail, the claim drops a hypothesis a known theorem needs, or a proof attempt keeps needing an extra assumption.
- **Skeleton:**
  1. State the precise claim being refuted, quantifiers included.
  2. Give the counterexample explicitly.
  3. Check that it satisfies **every** hypothesis.
  4. Check that the conclusion fails, with the computation shown.
- **Example:** "if $n$ is prime then $2^n - 1$ is prime" is false: $n = 11$ is prime and $2^{11} - 1 = 2047 = 23 \cdot 89$.
- **Audit:**
  - A counterexample that violates a hypothesis refutes nothing.
  - One counterexample suffices to refute a universal claim. No number of examples proves one.
  - Search systematically: small values, boundary values ($0$, $1$, empty, equal parameters), degenerate objects, and the cases a known theorem's hypotheses exclude. The skill's counterexample search is in `SKILL.md` (pre-audit plausibility) and [adversarial-proof-auditing.md](adversarial-proof-auditing.md).

```lean
example : ¬ ∀ n : ℕ, Nat.Prime n → Nat.Prime (2 ^ n - 1) := by
  intro h
  have := h 11 (by norm_num)
  norm_num at this
```

---

## 12. Induction

- **Form:** $\forall n \ge n_0,\ P(n)$ for integers $n$.
- **Why it is valid:** the well-ordering of $\mathbb{N}$, equivalently the induction axiom. If $P(n_0)$ holds and $P(k) \Rightarrow P(k + 1)$ for every $k \ge n_0$, no $n \ge n_0$ can be the first failure.
- **Use it when:** the statement about $n$ is built from the statement about $n - 1$: sums, products, recurrences, adding one element to a set.
- **Skeleton:**
  1. **State $P(n)$** as a sentence, with every other variable either fixed or universally quantified inside $P(n)$.
  2. **Base case:** prove $P(n_0)$ by direct computation.
  3. **Inductive step:** let $k \ge n_0$ be arbitrary and assume $P(k)$ (the inductive hypothesis). Prove $P(k + 1)$, and point to where $P(k)$ is used.
  4. Conclude $P(n)$ for all $n \ge n_0$.
- **Example:** $\sum_{i=1}^{n} i = n(n+1)/2$. Base: $n = 1$ gives $1 = 1$. Step: $\sum_{i=1}^{k+1} i = k(k+1)/2 + (k + 1) = (k+1)(k+2)/2$.
- **Audit:**
  - **The step works for every $k \ge n_0$,** including the first one. The classic false proof that "all horses are the same color" fails only at $k = 1 \to 2$, where the two overlapping groups do not overlap.
  - **The base case matches the starting point.** If the step needs $k \ge 2$, the base must cover $n = 2$ as well.
  - **The inductive hypothesis is used.** A step that never uses $P(k)$ is a direct proof of $P(k+1)$, which is fine, but then induction was unnecessary, and the reader should be told.
  - **The hypothesis is strong enough.** If $P(k + 1)$ needs more than $P(k)$ gives, strengthen $P$ (prove a stronger statement), or quantify the other variables inside $P$ ("generalize the inductive hypothesis").
  - **It does not assume $P(k + 1)$.** Working backward from $P(k + 1)$ is fine for discovery, but the written step must go forward.
  - **Induction on $n$ proves the claim for natural $n$ only,** not for real $n$.

```lean
example (n : ℕ) : 2 * (Finset.range (n + 1)).sum id = n * (n + 1) := by
  induction n with
  | zero => simp
  | succ k ih =>
    rw [Finset.sum_range_succ, mul_add, ih]
    simp only [id]
    ring
```

Structural induction is the same pattern for inductively defined objects (lists, trees, formulas): a base case per constructor without recursive parts, and a step per constructor that assumes the claim for its parts.

---

## 13. Strong induction

- **Form:** $\forall n \ge n_0,\ P(n)$.
- **Why it is valid:** equivalent to ordinary induction applied to $Q(n) := P(n_0) \wedge \cdots \wedge P(n)$.
- **Use it when:** $P(n)$ depends on cases that are smaller than $n$ but not necessarily $n - 1$: factoring $n = ab$, splitting a set or a tree into two parts, recurrences that look back more than one step, the division algorithm.
- **Skeleton:**
  1. State $P(n)$.
  2. Let $n \ge n_0$ and assume $P(m)$ for every $n_0 \le m < n$.
  3. Prove $P(n)$. Where the argument reduces to smaller cases, check that each one is at least $n_0$ and less than $n$.
  4. Values of $n$ for which the reduction does not apply (often the smallest ones) are handled directly. These are the base cases; there may be several.
- **Example:** every integer $n \ge 2$ is a product of primes. If $n$ is prime, done. Otherwise $n = ab$ with $2 \le a, b < n$; by the hypothesis both are products of primes, so $n$ is too.
- **Audit:**
  - **Enough base cases.** A recurrence that uses $n - 1$ and $n - 2$ needs two base cases. Find the smallest $n$ for which the reduction works, and handle every value below it directly.
  - **The smaller cases are in range.** $a, b \ge n_0$ and $a, b < n$ both need justification.

```lean
example (n : ℕ) (hn : 2 ≤ n) : ∃ p, p.Prime ∧ p ∣ n := by
  induction n using Nat.strong_induction_on with
  | _ n ih =>
    by_cases hp : n.Prime
    · exact ⟨n, hp, dvd_rfl⟩
    · obtain ⟨m, hmn, hm2, hmlt⟩ := Nat.exists_dvd_of_not_prime2 hn hp
      obtain ⟨p, hp', hpm⟩ := ih m hmlt hm2
      exact ⟨p, hp', hpm.trans hmn⟩
```

---

## 14. Well-ordering and minimal counterexamples

- **Form:** usually $\forall n \in \mathbb{N},\ P(n)$, or "there is no natural number with property $B$".
- **Why it is valid:** every nonempty set of natural numbers has a least element. This principle is equivalent to induction.
- **Use it when:** a counterexample can be made smaller (infinite descent), or a "smallest" object has a structure you can exploit.
- **Skeleton:**
  1. Suppose the claim fails. Then the set $C$ of counterexamples is nonempty.
  2. Let $m$ be the least element of $C$.
  3. Build from $m$ a smaller counterexample $m' < m$ with $m' \in C$.
  4. This contradicts minimality, so $C$ is empty.
- **Example:** $\sqrt 2$ is irrational, by descent. If $\sqrt 2 = a/b$, take the least positive $b$ for which some $a$ works. Then $\sqrt 2 = (2b - a)/(a - b)$ with $0 < a - b < b$, a smaller denominator.
- **Audit:**
  - The set is a set of natural numbers (or of a well-ordered set). "The smallest positive real counterexample" need not exist.
  - The new counterexample is in the set: it is a natural number, it is positive if the set requires that, and it is a counterexample.
  - It is strictly smaller.

```lean
example (P : ℕ → Prop) [DecidablePred P] (h : ∃ n, P n) :
    P (Nat.find h) ∧ ∀ m < Nat.find h, ¬ P m :=
  ⟨Nat.find_spec h, fun _ hm => Nat.find_min h hm⟩
```

---

## 15. Pigeonhole and double counting

These two are counting arguments that often supply the key step inside one of the strategies above. Patterns and examples are in [proof-techniques-and-heuristics.md](proof-techniques-and-heuristics.md), Sections 5 and 6. Here are only the parts that matter for structure:

- **Pigeonhole** is a nonconstructive existence proof (Section 9): it shows two objects share a box without saying which. State the objects, the boxes, and the map from objects to boxes, and check that the number of objects exceeds the number of boxes.
- **Double counting** proves an equality by counting one set in two ways. State the set being counted, and check that each count counts each element exactly once.

```lean
example (f : Fin 5 → Fin 4) : ∃ i j, i ≠ j ∧ f i = f j := by
  by_contra h
  push Not at h
  have hinj : Function.Injective f := fun i j hij => by
    by_contra hne
    exact h i j hne hij
  have := Fintype.card_le_of_injective f hinj
  simp at this
```

---

## 16. Combining strategies

Real proofs nest these strategies. Name each layer. Common combinations:

- **Induction inside contradiction:** minimal counterexample (Section 14).
- **Cases inside induction:** the inductive step splits on whether $k + 1$ is prime, even, or a boundary value.
- **Contradiction inside a case:** one case is impossible; show that it contradicts a hypothesis.
- **Existence plus contradiction:** nonconstructive existence (Section 9).
- **Equivalence through a hub:** prove $P_1 \iff P_2$ and $P_1 \iff P_3$ instead of a full cycle when $P_1$ is the convenient middle.

In the written proof, state each change of strategy: "We prove this by induction on $n$." "Suppose, for contradiction, that..." "We consider two cases." The reader, and the auditor, then knows what each assumption is for, and when it stops applying.

---

## 17. Errors to check in any proof

These are the structural errors that most often survive into a finished proof, whatever strategy it uses. The audit pass in `SKILL.md` checks for them.

1. **Proving the converse.** The proof shows $Q \Rightarrow P$ for a claim $P \Rightarrow Q$.
2. **Starting from the conclusion.** The proof assumes the claim and derives a true statement. Valid only if every step is a stated $\iff$.
3. **Proof by example.** A universal claim is "proved" by checking cases.
4. **Wrong negation.** Especially of implications and of statements with several quantifiers.
5. **Dependent choices in the wrong order.** In $\forall \varepsilon\, \exists \delta$, $\delta$ may depend on $\varepsilon$; a $\delta$ that also depends on $x$ proves a weaker statement (pointwise instead of uniform).
6. **A contradiction that does not use its assumption.** It shows the hypotheses are inconsistent.
7. **Non-exhaustive cases,** or "similarly" for a case that is not symmetric.
8. **Induction with a gap:** the step fails for the first $k$, or the base cases are too few for a strong-induction step.
9. **Choosing an object that may not exist:** the smallest element of a possibly empty set, the maximizer of a function that may not attain its maximum.
10. **Reused names:** two different objects given the same letter, which silently forces them to be equal.
11. **Existence without uniqueness, or uniqueness without existence,** for a "unique" claim.
12. **One-way steps in an equivalence chain:** squaring, dividing by zero, taking roots of negative quantities.

---

## 18. Sources

The strategies and their standard examples follow these textbooks, each of which covers them in more depth and with exercises. Checked 2026-11-18.

- Richard Hammack, *Book of Proof*, 3rd ed., 2018, free online: <https://richardhammack.github.io/BookOfProof/>. Part II (Chapters 4–6) covers direct proof, cases, contrapositive, and contradiction. Part III covers if-and-only-if, existence, induction, and disproof.
- Daniel J. Velleman, *How to Prove It: A Structured Approach*, 3rd ed., Cambridge University Press, 2019. Chapter 3 organizes proof strategies by the logical form of the goal and of the hypotheses, the approach taken in Section 1 here.
- Eric Lehman, F. Thomson Leighton, and Albert R. Meyer, *Mathematics for Computer Science*, MIT, 2018, free: <https://courses.csail.mit.edu/6.042/spring18/mcs.pdf>. Chapters 1–5 cover proof methods, well-ordering, and induction.
- George Pólya, *How to Solve It*, 2nd ed., Princeton University Press, 1957. Heuristics for finding a proof: working backward, specializing, generalizing, auxiliary problems.
- Ted Sundstrom, *Mathematical Reasoning: Writing and Proof*, version 3, 2020, free: <https://scholarworks.gvsu.edu/books/24/>.
- Oscar Levin, *Discrete Mathematics: An Open Introduction*, 3rd ed., 2019, free: <https://discrete.openmathbooks.org/dmoi3/dmoi.html>.
- Jeremy Avigad and Patrick Massot, *Mathematics in Lean*: <https://leanprover-community.github.io/mathematics_in_lean/>. Chapter 3 (Logic) maps each strategy to Lean tactics.
- Mathlib documentation for `contrapose`, `tfae`, and `Nat.find`: <https://leanprover-community.github.io/mathlib4_docs/>.
