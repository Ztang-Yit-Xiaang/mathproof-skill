# Proof Techniques and Problem-Solving Heuristics

This reference gives tactical patterns for advanced mathematical problem solving across competition mathematics (IMO, Putnam), pure mathematics (Real/Complex Analysis, Abstract Algebra, Topology), and combinatorics.

## Contents

1. Basic proof strategies
2. Induction
3. Invariants and monovariants
4. Extremal principle
5. Pigeonhole principle
6. Double counting
7. Analysis bounds
8. Algebra and diagram chasing
9. Matrix and spectral arguments
10. Probability and concentration
11. Convexity and optimization
12. Approximation and asymptotics

---

## 1. Basic Proof Strategies

The strategies chosen by the logical form of the goal (direct proof, contrapositive, contradiction, cases, exhaustion, equivalence, existence, uniqueness, counterexample, induction, well-ordering) are in [basic-proof-strategies.md](basic-proof-strategies.md). For each one it gives the logical law that makes it valid, a skeleton the written proof must follow, what to audit, and the Lean tactics. Fix the outer structure there first; the sections below fill in the steps.

---

## 2. Mathematical Induction & Structural Variants

### Weak vs. Strong vs. Structural Induction

- **Weak Induction:** Prove $P(1)$, then prove $P(k) \implies P(k+1)$. Use when the state at step $k+1$ depends directly on step $k$.
- **Strong Induction:** Prove $P(1)$, then prove $(\forall j \le k, P(j)) \implies P(k+1)$. Use when step $k+1$ decomposes into smaller subproblems of variable sizes (e.g., prime factorization, tree structures, polynomial division).
- **Structural Induction:** Used for inductively defined sets (e.g., expressions, trees, graphs). Base cases prove property for atomic objects; inductive steps prove property is preserved under constructors.
- **Cauchy / Reverse Induction:** Prove $P(1)$, prove $P(k) \implies P(2k)$, and prove $P(k+1) \implies P(k)$. Useful for proving classic inequalities like AM-GM.

---

## 3. Invariants & Monovariants

### Invariants (State Preservation)

An **invariant** is a property or quantity $I(S)$ associated with a state $S$ that remains unchanged under all allowed state transition operations:
$$I(S_{t+1}) = I(S_t)$$

- **Parity Invariants:** Check mod 2 behavior of sums, products, grid colorings, or permutation inversions.
- **Modular Invariants:** Check invariants modulo $n$ (e.g., sum of digits mod 9, polynomial evaluation mod $p$).
- **Coloring Arguments:** Assign colors to elements (e.g., chessboard 2-coloring, 3-coloring of grid tiles) to show certain configurations or tilings are impossible.

### Monovariants (Strict Monotonicity & Termination)

A **monovariant** (or Lyapunov function) is a quantity $M(S)$ that strictly increases (or decreases) with each valid operation:
$$M(S_{t+1}) > M(S_t) \quad \text{or} \quad M(S_{t+1}) < M(S_t)$$

- **Termination Proofs:** If $M(S)$ takes values in a bounded discrete set (e.g., $\mathbb{N}$), a strictly decreasing monovariant guarantees the process terminates in finite steps.
- **Convergence Proofs:** If $M(S)$ is bounded above in $\mathbb{R}$ and monotonically increasing, it must converge.

---

## 4. The Extremal Principle

When proving a property about a finite or bounded set of mathematical objects, **focus on an extreme element**:
- The element with the **minimum** or **maximum** value of a chosen metric (e.g., smallest distance, largest angle, degree of highest vertex, minimal counterexample).

### Common Applications
1. **Geometric Extremal Arguments:** Consider the pair of points at minimum distance or the polygon vertex with minimum interior angle.
2. **Infinite Descent (Fermat):** Assume a non-trivial integer solution exists. Choose the solution with the smallest positive parameter. Show that a strictly smaller solution can be constructed, yielding a contradiction.
3. **Graph Theory:** Consider the longest path in a graph or the vertex of maximum degree.

---

## 5. The Pigeonhole Principle (Dirichlet)

### Standard & Generalized Forms

- **Basic Form:** If $N$ items are put into $k$ containers and $N > k$, at least one container receives at least 2 items.
- **Generalized Form:** If $N$ items are put into $k$ containers, at least one container receives $\lceil N/k \rceil$ items.
- **Continuous / Measure-Theoretic Form:** If $N$ sets in a measure space with total measure $M$ are contained within a space of measure $< M / k$, some point is covered by at least $k+1$ sets.

### Proof Patterns
- **Subsequence Extraction (Erdős-Szekeres):** Any sequence of $n^2+1$ distinct real numbers contains a monotonic subsequence of length $n+1$.
- **Modular Congruence Pairs:** Among any $n+1$ integers, there exist two whose difference is divisible by $n$.

---

## 6. Double Counting & Fubini Swap

Double counting proves an equality by evaluating the size of a set $S$ or the sum of an array in two distinct ways:

$$\sum_{x \in A} \sum_{y \in B} I(x,y) = \sum_{y \in B} \sum_{x \in A} I(x,y)$$

### Applications
- **Handshaking Lemma:** $\sum_{v \in V} \deg(v) = 2|E|$.
- **Incidence Matrices:** Counting edges between two bipartite sets $A$ and $B$.
- **Combinatorial Identities:** Proving algebraic identities like $\sum_{k=0}^n \binom{n}{k}^2 = \binom{2n}{n}$ via committee selection arguments.

---

## 7. Analysis Bounding Tactics ($\varepsilon$-$\delta$ & Real Analysis)

### Standard Analysis Toolkit
1. **Triangle Inequality Bounding:** Split error $|f(x) - L|$ into $|f(x) - g(x)| + |g(x) - L|$ using an intermediate approximant $g(x)$.
2. **$\frac{\varepsilon}{2}$ Technique:** Allocate $\frac{\varepsilon}{2}$ budget to each component of a composite error term.
3. **Cauchy-Schwarz Inequality:**
   $$\left(\sum_{i=1}^n a_i b_i\right)^2 \le \left(\sum_{i=1}^n a_i^2\right) \left(\sum_{i=1}^n b_i^2\right)$$
4. **AM-GM Inequality:**
   $$\frac{x_1 + x_2 + \cdots + x_n}{n} \ge \sqrt[n]{x_1 x_2 \cdots x_n}$$
5. **Jensen's Inequality:** For a convex function $f$, $f\left(\sum w_i x_i\right) \le \sum w_i f(x_i)$.

---

## 8. Abstract Algebra Diagram Chasing & Exact Sequences

### Diagram Chasing Steps
1. **Define Homomorphisms Explicitly:** State kernel and image inclusions ($\ker \varphi$, $\text{im } \varphi$).
2. **Element Tracking:** Start with an arbitrary element $x \in A$. Trace its image under maps $\alpha(x), \beta(\alpha(x))$.
3. **Injectivity & Surjectivity Verification:**
   - To show $\varphi$ is injective, prove $\ker \varphi = \{0\}$.
   - To show $\varphi$ is surjective, for any $y \in B$, construct an explicit pre-image $x \in A$ such that $\varphi(x) = y$.

---

## 9. Matrix and Spectral Arguments

- **Spectral decomposition:** For a real symmetric or complex Hermitian matrix, move to an orthonormal eigenbasis and reduce a quadratic-form claim to scalar eigenvalue claims.
- **PSD ordering:** To prove $A \preceq B$, show $x^*(B-A)x\ge 0$ for every compatible $x$.
- **Rank/null-space decomposition:** Separate identifiable and null directions before claiming invertibility or uniqueness.
- **Perturbation:** State the norm, spectral gap, and parameter regime before applying eigenvalue, invariant-subspace, or inverse perturbation bounds.

## 10. Probability and Concentration

- **Conditioning:** Use the tower property to isolate dependence or expose a simpler conditional distribution.
- **Symmetrization:** Compare an empirical process with an independent ghost sample when the hypotheses permit it.
- **Concentration:** Match boundedness, variance, independence, martingale, or tail assumptions to the exact inequality being used.
- **Nonlinear expectation:** Check Jensen's direction and equality conditions before exchanging expectation with a nonlinear map.

## 11. Convexity and Optimization

- **First-order convexity:** For differentiable convex $f$, use $f(y)\ge f(x)+\nabla f(x)^\top(y-x)$.
- **Strong convexity/smoothness:** Track constants and inequality directions; do not infer one property from the other.
- **Optimality conditions:** Separate necessary conditions from sufficient conditions and verify constraint qualifications.
- **Coercivity/compactness:** Establish existence before selecting a minimizer.

## 12. Approximation and Asymptotics

- Record whether a statement is exact, additive-error, relative-error, high-probability, or asymptotic.
- Track all quantified parameters and whether constants depend on dimension, confidence, or regularity.
- Verify remainder bounds rather than replacing a function by a truncated expansion as an equality.
- Distinguish pointwise, uniform, and operator-norm control.
