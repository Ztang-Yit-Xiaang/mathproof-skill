# Example 6: The $O(1/k)$ rate of gradient descent (PROVE, graduate level)

## Request

> Prove the classical convergence rate of gradient descent: if $f$ is convex and $L$-smooth with minimizer $x^\star$, then gradient descent with step $1/L$ satisfies $f(x_k)-f(x^\star)\le \dfrac{L\|x_0-x^\star\|^2}{2k}$. Machine-check it in Lean.

This is Theorem 2.1.14 in Nesterov, *Lectures on Convex Optimization* (2nd ed., 2018), and one of the most widely used results in first-order optimization.

## Expected output

**Verdict: `VALID`** · **Lean status: `LEAN-CHECKED`** (faithful, in fact slightly stronger; see the post-audit)

### Assumption ledger

| Object | Assumption |
| --- | --- |
| $E$ | real Hilbert space (complete real inner-product space) |
| $f : E\to\mathbb{R}$ | differentiable everywhere |
| $\nabla f$ | $L$-Lipschitz: $\|\nabla f(x)-\nabla f(y)\|\le L\|x-y\|$, with $L>0$ |
| $f$ | convex on $E$ |
| $x^\star$ | a minimizer of $f$ (turns out to be unnecessary) |
| iterates | $x_{k+1}=x_k-\tfrac1L\nabla f(x_k)$ |

The target is an upper bound for every $k\ge1$, not a limit statement.

### Strategy

Two classical inequalities, one controlling $f$ from above (smoothness) and one from below (convexity), combine into a one-step bound in which $\|x_k-x^\star\|^2$ telescopes. A Lyapunov function then packages the telescoping sum and the monotonicity of $f(x_k)$ into a single induction.

### Lemma 1 (descent lemma)

For all $x,y\in E$,

$$
f(y)\le f(x)+\langle\nabla f(x),y-x\rangle+\frac L2\|y-x\|^2 .
$$

*Proof.* Let $d=y-x$ and $\varphi(t)=f(x+td)-t\langle\nabla f(x),d\rangle-\frac L2t^2\|d\|^2$. By the chain rule,

$$
\varphi'(t)=\langle\nabla f(x+td)-\nabla f(x),d\rangle-Lt\|d\|^2
\le \|\nabla f(x+td)-\nabla f(x)\|\,\|d\|-Lt\|d\|^2\le 0
$$

for $t\in(0,1)$, by Cauchy–Schwarz and then the Lipschitz bound $\|\nabla f(x+td)-\nabla f(x)\|\le Lt\|d\|$. So $\varphi$ is nonincreasing on $[0,1]$, and $\varphi(1)\le\varphi(0)$ is the claim. $\square$

### Lemma 2 (first-order convexity)

For all $x,y\in E$, $f(x)+\langle\nabla f(x),y-x\rangle\le f(y)$.

*Proof.* $\psi(t)=f(x+t(y-x))$ is convex on $\mathbb{R}$ as the composition of $f$ with an affine map, and $\psi'(0)=\langle\nabla f(x),y-x\rangle$. For a convex function of one variable, the derivative at $0$ is at most the slope from $0$ to $1$: $\psi'(0)\le\psi(1)-\psi(0)=f(y)-f(x)$. $\square$

### Lemma 3 (sufficient decrease)

$f(x_{k+1})\le f(x_k)-\frac1{2L}\|\nabla f(x_k)\|^2$.

*Proof.* Lemma 1 with $x=x_k$ and $y=x_{k+1}=x_k-\frac1L g$, where $g=\nabla f(x_k)$:
$f(x_{k+1})\le f(x_k)-\frac1L\|g\|^2+\frac L2\cdot\frac1{L^2}\|g\|^2=f(x_k)-\frac1{2L}\|g\|^2$. $\square$

In particular $f(x_k)$ is nonincreasing.

### Lemma 4 (one-step progress)

$f(x_{k+1})-f(x^\star)\le\frac L2\left(\|x_k-x^\star\|^2-\|x_{k+1}-x^\star\|^2\right)$.

*Proof.* Lemma 2 with $x=x_k$, $y=x^\star$ gives $f(x_k)-f(x^\star)\le\langle g,x_k-x^\star\rangle$. Adding Lemma 3,

$$
f(x_{k+1})-f(x^\star)\le\langle g,x_k-x^\star\rangle-\frac1{2L}\|g\|^2 .
$$

Expanding $\|x_{k+1}-x^\star\|^2=\|(x_k-x^\star)-\frac1Lg\|^2=\|x_k-x^\star\|^2-\frac2L\langle x_k-x^\star,g\rangle+\frac1{L^2}\|g\|^2$ shows the right-hand side equals $\frac L2(\|x_k-x^\star\|^2-\|x_{k+1}-x^\star\|^2)$. $\square$

### Theorem

For every $k\ge0$,

$$
k\,\bigl(f(x_k)-f(x^\star)\bigr)\le\frac L2\|x_0-x^\star\|^2,
\qquad\text{hence}\qquad
f(x_k)-f(x^\star)\le\frac{L\|x_0-x^\star\|^2}{2k}\quad(k\ge1).
$$

*Proof.* Let $\Phi_k=k\,(f(x_k)-f(x^\star))+\frac L2\|x_k-x^\star\|^2$. Then

$$
\Phi_{k+1}=k\,(f(x_{k+1})-f^\star)+(f(x_{k+1})-f^\star)+\tfrac L2\|x_{k+1}-x^\star\|^2
\le k\,(f(x_k)-f^\star)+\tfrac L2\|x_k-x^\star\|^2=\Phi_k ,
$$

using $f(x_{k+1})\le f(x_k)$ (Lemma 3, with $k\ge0$) on the first term and Lemma 4 on the rest. So $\Phi_k\le\Phi_0=\frac L2\|x_0-x^\star\|^2$; dropping the nonnegative term $\frac L2\|x_k-x^\star\|^2$ gives the first bound, and dividing by $2k>0$ the second. $\square$

### Post-audit

- **Where each hypothesis is used.** Differentiability: the chain rule in Lemmas 1 and 2. Lipschitz gradient: only Lemma 1. Convexity: only Lemma 2. $L>0$: the step $1/L$ and the final division. Completeness of $E$: only so that $\nabla f$ is defined via the Riesz representation.
- **Redundant hypothesis.** Minimality of $x^\star$ is never used. Lemma 2 holds for any $y$, so the bound holds for **every** reference point $x^\star\in E$. Minimality only matters for interpreting $f(x_k)-f(x^\star)$ as the optimality gap (it is then $\ge0$). Lean flagged this: its linter reported the hypothesis as unused, and the formal theorem omits it.
- **Monotonicity is not optional.** Without $f(x_{k+1})\le f(x_k)$ the telescoping only bounds the *average* $\frac1k\sum_{i\le k}(f(x_i)-f^\star)$, not the last iterate.
- **Step size.** The proof uses exactly $1/L$; for a step $\eta\in(0,1/L]$ the same argument gives $\frac{\|x_0-x^\star\|^2}{2\eta k}$, but for $\eta>2/L$ gradient descent can diverge (take $f(x)=\frac L2x^2$).
- **Division by $k$.** The rate is stated for $k\ge1$. In Lean, $a/0=0$, so a naive formal statement for all $k$ would be false at $k=0$ for the wrong reason; the division-free form is the primary theorem.

### Lean verification

File: [`lean/MathProofSkill/Evals/Optimization003.lean`](../lean/MathProofSkill/Evals/Optimization003.lean), about 150 lines. Each lemma above is a Lean theorem of the same name: `descent_lemma`, `convex_first_order`, `sufficient_decrease`, `one_step`, `lyapunov`, `gd_rate`, `gd_rate'`.

```lean
variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [CompleteSpace E]

theorem gd_rate' {f : E → ℝ} {L : ℝ≥0} (hL0 : 0 < L) (hf : Differentiable ℝ f)
    (hL : LipschitzWith L (∇ f)) (x : ℕ → E)
    (hx : ∀ k, x (k + 1) = x k - (1 / (L : ℝ)) • ∇ f (x k))
    (hconv : ConvexOn ℝ univ f) {xstar : E} (k : ℕ) (hk : 0 < k) :
    f (x k) - f xstar ≤ L * ‖x 0 - xstar‖ ^ 2 / (2 * k)
```

| Informal | Lean | Match |
| --- | --- | --- |
| real Hilbert space $E$ | `InnerProductSpace ℝ E`, `CompleteSpace E` | faithful |
| $f$ differentiable | `Differentiable ℝ f` | faithful |
| $\nabla f$ is $L$-Lipschitz, $L>0$ | `LipschitzWith L (∇ f)`, `0 < L` | faithful (`∇` is Mathlib's `gradient`) |
| $f$ convex | `ConvexOn ℝ univ f` | faithful |
| $x^\star$ a minimizer | *(omitted)* | stronger: holds for every `xstar` |
| $x_{k+1}=x_k-\frac1L\nabla f(x_k)$ | `hx` | faithful |
| bound for $k\ge1$ | `gd_rate'` with `0 < k`; `gd_rate` division-free for all `k` | faithful |

Checker output: see the README or run

```bash
python3 skill/scripts/lean_check.py lean/MathProofSkill/Evals/Optimization003.lean \
  --require gd_rate --require gd_rate\' --require descent_lemma --require convex_first_order
```
