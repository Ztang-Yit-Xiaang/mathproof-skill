import Mathlib

/-!
# topology-001 — Continuous image of a compact space

Informal claim: the continuous image of a compact space is compact. Expected verdict: `VALID`.
-/

namespace MathProofSkill.Evals.Topology001

theorem image_compact {X Y : Type*} [TopologicalSpace X] [TopologicalSpace Y]
    [CompactSpace X] (f : X → Y) (hf : Continuous f) : IsCompact (Set.range f) :=
  isCompact_range hf

end MathProofSkill.Evals.Topology001
