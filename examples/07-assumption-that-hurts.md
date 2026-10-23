# Example 7: A repair that hurts

## Request

Audit this proof, and repair it if you can:

> Let $A$ be a real $n\times n$ matrix with $A^2=0$. Multiplying on the left by $A^{-1}$ gives $A=A^{-1}A^2=0$. So $A=0$.

## Expected audit

**Verdict: `INVALID`** · **Lean status: `LEAN-CHECKED`**

**First unsupported step.** "Multiply on the left by $A^{-1}$." Nothing says $A$ is invertible.

**Counterexample.**

$$
A=\begin{pmatrix}0&1\\0&0\end{pmatrix},\qquad A^2=0,\qquad A\neq 0.
$$

**Repair, and what it costs.** The step that fails suggests the repair "assume $A$ invertible". The cost audit rejects it:

- *Consistency fails.* If $A$ is invertible, so is $A^2$, and an invertible matrix is not $0$ when $n\ge 1$. No matrix satisfies both hypotheses, so "invertible and $A^2=0$ implies $A=0$" is true only vacuously. Reporting it as `CONDITIONALLY VALID` would hide that.

A repair that keeps a real class of matrices is symmetry. It is consistent ($A=0$ qualifies), it does not imply the target, and a user can check it directly. If $A^\top=A$, then $A^\top A=A^2=0$, so $\operatorname{tr}(A^\top A)=\sum_{i,j}a_{ij}^2=0$ and $A=0$. The same argument works for normal matrices, the weakest natural condition here.

**Lean verification.**

File: `lean/MathProofSkill/Evals/Linear004.lean`

```lean
theorem claim_false : ¬ ∀ A : Matrix (Fin 2) (Fin 2) ℝ, A * A = 0 → A = 0

theorem invertible_repair_vacuous {n : Type*} [Fintype n] [DecidableEq n] [Nonempty n]
    (A : Matrix n n ℝ) (hA : IsUnit A) : A * A ≠ 0 :=
  (hA.mul hA).ne_zero

theorem symmetric_repair {n : Type*} [Fintype n] [DecidableEq n]
    (A : Matrix n n ℝ) (hsym : Aᵀ = A) (h : A * A = 0) : A = 0
```

Checker output (`python3 skill/scripts/lean_check.py lean/MathProofSkill/Evals/Linear004.lean --require claim_false --require invertible_repair_vacuous --require symmetric_repair`):

```text
PASS: lean/MathProofSkill/Evals/Linear004.lean
  MathProofSkill.Evals.Linear004.claim_false : ¬∀ (A : Matrix (Fin 2) (Fin 2) ℝ), A * A = 0 → A = 0
    axioms: propext, Classical.choice, Quot.sound
  MathProofSkill.Evals.Linear004.invertible_repair_vacuous : ∀ {n : Type u_1} [inst : Fintype n] [inst_1 : DecidableEq n] [Nonempty n] (A : Matrix n n ℝ), IsUnit A → A * A ≠ 0
    axioms: propext, Classical.choice, Quot.sound
  MathProofSkill.Evals.Linear004.symmetric_repair : ∀ {n : Type u_1} [inst : Fintype n] [DecidableEq n] (A : Matrix n n ℝ), A.transpose = A → A * A = 0 → A = 0
    axioms: propext, Classical.choice, Quot.sound
```

| Informal | Lean | Match |
| --- | --- | --- |
| real $n\times n$ matrix, $A^2=0$, $A=0$ | `Matrix (Fin 2) (Fin 2) ℝ`, `A * A = 0`, `A = 0` | instance (one size suffices to refute) |
| $A$ invertible, $n\ge1$ | `IsUnit A`, `[Nonempty n]` | faithful |
| $A$ symmetric | `Aᵀ = A` | faithful |

The `Nonempty n` hypothesis is not decoration. Over an empty index type, `Matrix n n ℝ` is the zero ring, where every matrix is both $0$ and invertible. That is the vacuity trap from the Lean protocol, met in the formal setting itself.
