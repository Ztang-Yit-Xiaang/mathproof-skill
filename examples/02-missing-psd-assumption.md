# Example 2: Missing PSD assumption

## Request

Audit this proof:

> Let \(A\) be a real symmetric matrix. Since \(A\) has real eigenvalues, \(x^\top A x\ge 0\) for every \(x\). Therefore, \(f(x)=\frac12x^\top A x\) is convex.

## Expected audit

**Verdict: `CONDITIONALLY VALID`**

**First unsupported step.** “\(A\) has real eigenvalues” is used to conclude that all eigenvalues are nonnegative.

**Why it fails.** Symmetry guarantees an orthonormal eigenbasis and real eigenvalues; it does not determine their signs.

**Counterexample.** Take \(A=[-1]\). It is real and symmetric, but with \(x=1\),

\[
x^\top A x=-1<0.
\]

The resulting function \(f(x)=-\frac12x^2\) is concave, not convex.

**Weak natural repair.** Add \(A\succeq 0\). For a quadratic function, this condition is exactly what makes the Hessian PSD and the function convex.
