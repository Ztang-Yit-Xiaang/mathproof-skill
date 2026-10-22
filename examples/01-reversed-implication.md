# Example 1: Reversed implication

## Request

Audit the following proof:

> If an integer is divisible by 4, then it is even. The integer 6 is even. Therefore, 6 is divisible by 4.

## Expected audit

**Verdict: `INVALID`**

**Claim and assumptions.** The argument uses

$$
4\mid n \Longrightarrow 2\mid n
$$

and the fact that $2\mid 6$.

**First unsupported step.** From $2\mid 6$, it concludes $4\mid 6$.

**Why it fails.** This reverses the direction of the known implication. Divisibility by 4 is sufficient for evenness, but evenness is not sufficient for divisibility by 4.

**Counterexample.** The chosen integer is already a counterexample: $6=2\cdot 3$, but no integer $k$ satisfies $6=4k$.

**Repair.** No repair is needed to the theorem $4\mid n\Rightarrow 2\mid n$; the attempted converse should be removed.
