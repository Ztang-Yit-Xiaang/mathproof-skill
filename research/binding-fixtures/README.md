# Binding fixtures (S2.2.T1)

A ledger whose only purpose is to show, under the authoritative judge, that a Challenge generated
from a frozen statement binds a proof to that statement. The mathematics is trivial on purpose.

Each claim's statement was frozen with `mathproof statement`, and each proof was checked locally
with `mathproof check`, so every check below passes locally. What the judge must decide:

| Claim | Proof file | Polarity | What it does | Expected judge result |
|---|---|---|---|---|
| `bind/weak` | `src/weak_honest.lean` | claim | Proves the statement | pass |
| `bind/weak` | `src/weak_weakened.lean` | claim | Proves a weaker statement (`1 < n` for `0 < n`) under the same name | fail |
| `bind/localdef` | `src/localdef_redefined.lean` | claim | Redefines the statement's local `f` so the false statement holds | fail |
| `bind/localdef` | `src/localdef_negation.lean` | negation | Refutes the statement with the real `f` | pass |

`bind/weak` has a pass and a fail on the same claim, so its status is `judge-rejected`: a rejection of
any checked proof of a claim stands. That is the intended reading here, not a defect.

A third statement, in `src/shadow.*`, defines its own `Nat.Prime` inside a namespace and opens it.
It is not recorded: `mathproof statement` refuses `namespace` and `end` in a preamble. Before that
rule existed it was compiled on 2026-11-16 with Lean v4.35.0, and `Nat.Prime 4` resolved to
Mathlib's `Nat.Prime`, so nothing was shadowed. When a statement does reach its own definition, the
binding output lists it: for `bind/localdef`, `defined_in_statement` is `f`.

Attacks tried on 2026-11-16 (an independent review, then rerun against the final check with the word
list bypassed, so only the Lean check stood in the way):

| Attack | Result |
|---|---|
| Preamble leaves a namespace open and declares the root `NAME` and `NAME_negation` with `run_cmd` | Rejected: `flt_small is declared on line 8, not 14` |
| Preamble adds a false hypothesis with `variable` and `include`, and `macro_rules` rewrites any `run_meta` | Rejected: the negation is not exactly `Not` of the claim |
| Preamble redefines `¬` with `local notation` | Rejected: the Challenge does not compile |
| Proposition `True) := by sorry … example : (…` | Passes the Lean check with type `True`, which the person reads; `build` refuses `:=` in a proposition, so it cannot be recorded |
| Preamble `def n : ℕ := by first \| (fail_if_success … plausible …); exact 1 \| exact 2` (a value chosen at random on each compile, so the printed statement and the comparator's could differ) | Found in a third review; `build` now refuses `by` in a statement |
