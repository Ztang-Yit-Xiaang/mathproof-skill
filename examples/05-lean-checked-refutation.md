# Example 5: A refutation machine-checked in Lean

## Request

Audit this argument, and verify your verdict in Lean:

> Let \(f:\mathbb{R}\to\mathbb{R}\) be differentiable with \(f'(x_0)=0\). Then \(x_0\) is a critical point, so \(f\) attains its global minimum at \(x_0\).

## Expected audit

**Verdict: `INVALID`** · **Lean status: `LEAN-CHECKED`**

**First unsupported step.** "\(x_0\) is a critical point, so \(f\) attains its global minimum at \(x_0\)."

**Why it fails.** Stationarity is a necessary condition for an interior minimum of a differentiable function, not a sufficient one.

**Counterexample.** \(f(x)=-x^2\) is differentiable and \(f'(0)=0\), but \(f(1)=-1<0=f(0)\).

**Lean verification.**

File: `lean/MathProofSkill/Evals/Optimization001.lean`

```lean
def Claim : Prop :=
  ∀ f : ℝ → ℝ, Differentiable ℝ f → ∀ x, deriv f x = 0 → IsMinOn f univ x

theorem claim_false : ¬ Claim := by
  intro h
  have hd : Differentiable ℝ (fun x : ℝ => -x ^ 2) := by fun_prop
  have hstat : deriv (fun x : ℝ => -x ^ 2) 0 = 0 := by simp
  have := h _ hd 0 hstat (mem_univ 1)
  norm_num at this
```

Checker output (`python3 skill/scripts/lean_check.py lean/MathProofSkill/Evals/Optimization001.lean --require claim_false`):

```text
PASS: lean/MathProofSkill/Evals/Optimization001.lean
  MathProofSkill.Evals.Optimization001.claim_false : ¬MathProofSkill.Evals.Optimization001.Claim
    axioms: propext, Classical.choice, Quot.sound
```

| Informal | Lean | Match |
| --- | --- | --- |
| \(f:\mathbb{R}\to\mathbb{R}\) differentiable | `f : ℝ → ℝ`, `Differentiable ℝ f` | faithful |
| \(f'(x_0)=0\) | `deriv f x = 0` | faithful (differentiability is assumed, so `deriv` is not a junk value) |
| global minimum at \(x_0\) | `IsMinOn f univ x` | faithful |

**Repair.** Add convexity: for a differentiable convex \(f\), \(f'(x_0)=0\) does imply a global minimum. The one-variable version is machine-checked as `isMinOn_of_deriv_eq_zero` in `lean/MathProofSkill/Evals/Optimization002.lean`.
