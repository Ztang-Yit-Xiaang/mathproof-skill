# Formal Logic Bridge & LaTeX Standards

This reference guide establishes the bridge between informal human mathematical exposition, Lean 4 tactic formalization, and publication-grade LaTeX typesetting standards.

---

## 1. Informal Prose to Lean 4 Tactic Mapping

Proof assistants like Lean 4 require structured, line-by-line logical transformations. Mapping informal prose steps to formal tactics improves logical precision and autoformalization readiness.

```
INFORMAL PROSE                  LEAN 4 TACTIC
"Assume x is an integer..." ──> `intro x`
"Split into cases..."       ──> `rcases` / `by_cases`
"By definition..."          ──> `unfold` / `dsimp`
"Intermediate claim C..."   ──> `have hC : C := by ...`
"By contradiction..."       ──> `by_contra h`
"By induction on n..."      ──> `induction n with k hk`
"Chain of equalities..."    ──> `calc` block
```

### Direct Proof Mapping Example

#### Informal Prose Step:
> "Let $n \in \mathbb{Z}$ be an even integer. By definition of even, $n = 2k$ for some $k \in \mathbb{Z}$. Then $n^2 = (2k)^2 = 4k^2 = 2(2k^2)$. Since $2k^2 \in \mathbb{Z}$, $n^2$ is even."

#### Illustrative Lean 4 Mapping

This snippet is machine-checked as `lean/MathProofSkill/Evals/Number001.lean` in the repository. Never treat formal code as evidence until `scripts/lean_check.py` passes on it; see [lean-verification.md](lean-verification.md).
```lean
theorem even_sq (n : ℤ) (h : Even n) : Even (n ^ 2) := by
  obtain ⟨k, rfl⟩ := h
  exact ⟨2 * k ^ 2, by ring⟩
```

---

## 2. LaTeX Typesetting & Formatting Standards

To ensure publication-quality presentation, follow these LaTeX standards in all output:

### A. Number Sets & Font Conventions
- Use `\mathbb{R}` for real numbers ($\mathbb{R}$).
- Use `\mathbb{Z}` for integers ($\mathbb{Z}$).
- Use `\mathbb{N}` for natural numbers ($\mathbb{N}$).
- Use `\mathbb{Q}` for rational numbers ($\mathbb{Q}$).
- Use `\mathbb{C}` for complex numbers ($\mathbb{C}$).
- Use `\mathcal{P}` for power sets or calligraphic families ($\mathcal{P}$).

### B. Display Math & Alignment
- For single-line equations, use `$$ ... $$` or `\[ ... \]`.
- For multi-step derivations, use `\begin{align*} ... \end{align*}` with `&` aligned at equality or inequality symbols:

```latex
\begin{align*}
|f(x) - L| &= |(f(x) - g(x)) + (g(x) - L)| \\
           &\le |f(x) - g(x)| + |g(x) - L| \\
           &< \frac{\varepsilon}{2} + \frac{\varepsilon}{2} = \varepsilon.
\end{align*}
```

### C. Piecewise & Case Functions
Use `\begin{cases} ... \end{cases}` for piecewise functions:

```latex
f(x) = \begin{cases}
x^2 & \text{if } x \ge 0, \\
-x & \text{if } x < 0.
\end{cases}
```

### D. Operators & Symbols
- Use `\implies` ($\implies$) for implication in display math, but write out "implies" or "it follows that" in prose text.
- Use `\iff` ($\iff$) for biconditionals in display math, but write out "if and only if" in prose text.
- Use `\le` ($\le$) and `\ge` ($\ge$) instead of `< =` or `> =`.
- Use `\cdot` ($\cdot$) for multiplication scalar dots, never raw asterisks `*`.
- Use `\setminus` ($\setminus$) for set differences ($A \setminus B$).

---

## 3. Autoformalization Readiness Checklist

When preparing an informal proof for potential translation into Lean 4 / Coq:

1. **Explicit Quantifiers:** Ensure every variable has an explicit scope and domain type ($\forall x \in \mathbb{R}$, $\exists n \in \mathbb{N}$).
2. **No Hand-Waving:** Replace phrases like "similarly," "it is obvious," or "by symmetry" with explicit sub-lemmas or exact symmetry transformations.
3. **Algebraic Identity Verification:** Keep intermediate algebraic steps small enough that decision procedures (`ring`, `linarith`, `simp`, `nlinarith`) can solve each equality step automatically.
4. **Explicit Domain Assumptions:** Include non-emptiness, continuity, or boundary conditions explicitly in the hypothesis block.
