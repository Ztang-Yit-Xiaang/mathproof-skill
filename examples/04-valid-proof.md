# Example 4: A valid proof passes

## Request

Audit the proof:

> Let $n\in\mathbb Z$ be even. Then $n=2k$ for some $k\in\mathbb Z$. Hence $n^2=4k^2=2(2k^2)$. Since $2k^2\in\mathbb Z$, $n^2$ is even.

## Expected audit

**Verdict: `VALID`**

The witness $k$ follows from the definition of evenness. Squaring preserves the equality, the algebraic rearrangement is exact, and $2k^2$ is an integer because the integers are closed under multiplication. Thus the proof constructs the integer witness required to show that $n^2$ is even.

No extra assumption or repair is needed.
