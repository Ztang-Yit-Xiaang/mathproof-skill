# Example 3: Approximation treated as equality

## Request

Audit this argument:

> Since $\sin x\sim x$ as $x\to0$, we have $\sin x=x$ for sufficiently small $x$. Therefore, $\int_0^{0.1}\sin x\,dx=0.005$.

## Expected audit

**Verdict: `INVALID`**

**First unsupported step.** The argument replaces asymptotic equivalence with exact local equality.

**Why it fails.** The statement $\sin x\sim x$ means

$$
\lim_{x\to0}\frac{\sin x}{x}=1,
$$

not that the two functions agree on a punctured neighborhood of zero.

**Countercheck.** The exact integral is

$$
\int_0^{0.1}\sin x\,dx=1-\cos(0.1),
$$

which is close to, but not equal to, $0.005$.

**Repair.** Use a Taylor expansion with a remainder bound if an approximation is intended, and label the conclusion as a bound or approximation.
