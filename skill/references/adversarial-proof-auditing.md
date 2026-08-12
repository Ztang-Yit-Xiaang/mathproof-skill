# Adversarial Proof Auditing & Fallacy Detection Protocol

This protocol provides systematic guidelines for auditing mathematical proofs, catching subtle logical fallacies, testing edge cases, and conducting counterexample searches before finalizing any proof.

## Contents

1. Adversarial auditing mindset
2. Boundary and edge-case battery
3. Common fallacies
4. Minimal counterexample template
5. Research-math attack battery

---

## 1. The Adversarial Auditing Mindset

Adversarial proof auditing treats every material step as requiring independent support. The auditor actively attacks assertions and unstated assumptions while remaining willing to return `VALID` when the argument survives the checks.

```
                  ┌───────────────────────────────┐
                  │   PROPOSED CLAIM / PROOF      │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                 ┌────────────────────────────────┐
                 │  Boundary & Edge-Case Battery  │
                 └──────────────┬─────────────────┘
                                 │
                                 ▼
                 ┌────────────────────────────────┐
                 │ Fallacy & Logical Leap Scanner │
                 └──────────────┬─────────────────┘
                                 │
                 ┌──────────────┴─────────────────┐
                 ▼                                ▼
       [ Counterexample Found ]         [ Proof Audited & Passed ]
       -> Refute claim immediately      -> Proceed to formal polish
```

---

## 2. The Boundary & Edge-Case Battery

Run every variable and domain through the following stress-test checklist:

### A. Numerical & Algebraic Edge Cases
- **Zero & Unity:** $n=0$, $n=1$, $x=0$, $x=1$.
- **Negative & Imaginary:** Negative integers, complex numbers ($i$), negative square roots.
- **Divisibility:** Division by zero, division by expressions that *could* equal zero under specific variable assignments.
- **Limits & Infinities:** $n \to \infty$, $x \to 0^+$, empty sets, infinite dimensional spaces.

### B. Analytical & Function Edge Cases
- **Continuity & Differentiability:** Functions with jump discontinuities, Weierstrass non-differentiable function, Dirichlet function.
- **Compactness & Openness:** Open vs closed intervals ($(0,1)$ vs $[0,1]$), bounded vs unbounded sets.
- **Convergence:** Pointwise vs uniform convergence; conditionally convergent vs absolutely convergent series.

### C. Algebraic & Geometric Edge Cases
- **Matrix Singularity:** Matrices with $\det(A) = 0$, non-square matrices, zero transformations.
- **Degenerate Geometries:** Collinear points, triangles with area zero, parallel lines, empty intersections.
- **Group/Ring Structures:** Non-commutative groups (matrix multiplication), rings with zero divisors.

---

## 3. Top 10 Common Mathematical Fallacies & Flaws

| Fallacy Type | Description | Classic Trap Example | How to Detect |
| :--- | :--- | :--- | :--- |
| **1. Division by Zero** | Concealed division by $(a-b)$ when $a=b$ | $a=b \implies a^2=ab \implies a^2-b^2=ab-b^2 \dots \implies 2=1$ | Check every algebraic step where an expression is cancelled or divided |
| **2. Affirming the Consequent** | Assuming $Q \implies P$ is true because $P \implies Q$ is true | "If $x > 5$, then $x^2 > 25$. Since $x^2 > 25$, $x$ must be $> 5$." (False for $x=-6$) | Verify directional arrow of every implication |
| **3. Untyped / Free Variable Shift** | Reusing $k$ for two independent quantities | "Since $a$ is even, $a=2k$. Since $b$ is even, $b=2k$." | Ensure independent variables use distinct symbols ($2k$ vs $2m$) |
| **4. Unstated Uniformity** | Exchanging limit operations without verifying uniform convergence | $\lim_{n \to \infty} \int f_n = \int \lim_{n \to \infty} f_n$ | Audit Dominated Convergence Theorem / uniform convergence conditions |
| **5. Assuming Existence / Non-Emptiness** | Defining "the smallest element" of a set without proving the set is non-empty | "Let $m$ be the minimum element of set $S \subset \mathbb{R}$." (Fails if $S=(0,1)$) | Verify Well-Ordering Principle or compactness before taking min/max |
| **6. Circular Reasoning (Begging the Question)** | Using the conclusion $Q$ inside the proof of $Q$ | "Assume $x^2$ is even. By equation (1), $x^2=2k$, which shows $x^2$ is even." | Construct dependency DAG of proof assertions |
| **7. Proof by Example** | Showing $P(x)$ for $x=2, 3, 5$ and asserting $\forall x, P(x)$ | "$2^2-1=3$, $3^2-1=8$, so $n^2-1$ is always composite." (Fails for $n=2$) | Check if universal quantifier $\forall$ is proven generally |
| **8. Ill-Defined Functions** | Defining $f([x]) = g(x)$ for equivalence classes without checking independence of representative | $f(a/b) = a+b$ on $\mathbb{Q}$ (Fails since $1/2 = 2/4$ but $1+2 \ne 2+4$) | Verify $x \sim y \implies f(x) = f(y)$ for quotient spaces |
| **9. Overgeneralizing Finite Results to Infinite** | Applying finite distributive/associative laws to infinite series | $\sum_{i=1}^\infty (a_i + b_i) = \sum a_i + \sum b_i$ when series diverge | Audit conditionally vs absolutely convergent series rules |
| **10. Misinterpreting Biconditionals** | Proving only one direction of an "if and only if" claim | Proving $P \implies Q$ and declaring $P \iff Q$ complete | Ensure both $(\implies)$ and $(\impliedby)$ are explicitly labeled and proven |

---

## 4. Minimal Counterexample Generation Template

If a proposed claim is false, present the refutation using this structure:

```markdown
### Refutation & Counterexample

**Claim:** [State the original claim being refuted]

**Counterexample:**
Let [Define explicit values/functions/objects].

**Verification:**
1. [Show counterexample satisfies all hypotheses of the claim]
2. [Show counterexample explicitly fails the claimed conclusion]

**Diagnosis:**
The claim fails because it implicitly assumed [Identify missing condition, e.g., uniform continuity, non-zero determinant].
```

## 5. Research-Math Attack Battery

### Matrix analysis

- Distinguish symmetric/Hermitian, PSD, positive definite, and invertible.
- Check whether a norm inequality is being upgraded to a Loewner-order inequality.
- Verify rank, null-space, spectral-gap, and conditioning assumptions.
- When using an eigendecomposition, verify the matrix class that licenses it.

### Probability

- Check measurability and integrability before manipulating expectations.
- Verify independence before factorizing expectations or probabilities.
- Distinguish almost-sure, in-probability, distributional, and mean-square convergence.
- Check the precise hypotheses of concentration inequalities.

### Optimization

- Distinguish stationarity, local optimality, and global optimality.
- Verify convexity, constraint qualifications, and differentiability before invoking KKT or first-order sufficiency.
- Check whether strong convexity or smoothness constants are positive and used in the correct direction.

### Approximation and asymptotics

- Preserve the difference between equality, approximation, bounds, and asymptotic equivalence.
- Track constants, regimes, probability levels, and dependence on dimensions or parameters.
- Test whether an error term is uniform over the domain where the conclusion is claimed.
