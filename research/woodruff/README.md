# Woodruff survey: research ledger

The research ledger for proving results from David Woodruff, *Sketching as a Tool for Numerical
Linear Algebra* (arXiv 1411.4357), a published survey. Thirteen claims, each with a Lean proof
that passed the local checker on Lean v4.35.0 and `lake comparator` in CI.

- `ledger/`: the hash-chained event log and its content-addressed artifacts.
- `ledger/challenges.json`: the registered Challenge for each claim, by artifact hash.
- `challenges/`: the same Challenge files, readable. Each is the claim's statement proved by
  `sorry`, exactly as judged by `lake comparator` in the earlier CI runs. Four of them
  (theorems 13 and 14, lemmas 44 and 45) are single-theorem cuts of a two-theorem Statements
  file; the statement text is unchanged.

## Provenance

This ledger is a copy of the working ledger kept outside the repository, with one change: each
check event's `project` field, an absolute local path, is replaced by the repo-relative `lean`.
Every event's `prev` and `hash` were then recomputed, so the chain verifies, but its hashes differ
from the working copy's. Head of the working copy: `262d1bd9…e404`; head here, event 49:
`55f9e36cf23872e2f7ff89980e845ee9dd12871839c1e5e75c27606090c3c8f0`. No other field changed.

To judge it, dispatch the *Authoritative judge* workflow on `main` with `ledger` set to
`research/woodruff/ledger`, then run `mathproof verify --authoritative`.
