# Review packet: claim inv/c1

**Headline:** `argued`

**Verdict:** INCOMPLETE

## Intended statement

> If n is even then n^2 is even.

## What you are asked

No proof of this claim has passed Lean's kernel, so you are the check. Read each step and its justification, and find the first step that does not follow.

Approving this packet records a human audit of an informal proof. It does not make the claim VALID: the status stays UNVERIFIED until Lean checks the proof.

## Proof 1

Written by: prover-1

**First unverified step:** 1.

1. Let n be even, so n = 2k for some integer k. **(first unverified step)**

    Because: Definition of even.

    Machine-checked: no.

2. Then n^2 = 4k^2 = 2(2k^2).

    Because: Squaring and factoring.

    Machine-checked: Lean proved sq\_step, local run. Its statement:

        ∀ k : ℤ, (2 * k) ^ 2 = 2 * (2 * k ^ 2)

3. So n^2 is even.

    Because: It is twice the integer 2k^2.

    Machine-checked: no.

Proof file hash: `32ba1f671908e7987de3afefc26bd7fe71ae2f3c303e472e03153f928f73da58`

No audit is recorded yet. To approve or reject, record an `informal_audit` event naming the proof file hash above, then sign it: `sign --event SEQ`.
