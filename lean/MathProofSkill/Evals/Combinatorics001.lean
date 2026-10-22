import Mathlib

/-!
# combinatorics-001 — Handshake lemma

Informal claim: the sum of degrees in a finite undirected graph equals twice the number of
edges. Expected verdict: `VALID`.

Formalization scope: **simple graphs** (no loops, no multi-edges), which is Mathlib's
`SimpleGraph`. Multigraphs are not covered by this file.
-/

namespace MathProofSkill.Evals.Combinatorics001

theorem handshake {V : Type*} [Fintype V] [DecidableEq V] (G : SimpleGraph V)
    [DecidableRel G.Adj] : ∑ v, G.degree v = 2 * G.edgeFinset.card :=
  G.sum_degrees_eq_twice_card_edges

end MathProofSkill.Evals.Combinatorics001
