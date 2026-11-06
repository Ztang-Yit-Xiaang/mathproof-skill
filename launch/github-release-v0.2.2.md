# MathProof Skill v0.2.2 — Lean checker fix

**Please update.** Earlier versions of `lean_check.py` could report `PASS` for a proof of `1 = 2` or `False`. The README, site, and protocol said such files were rejected, and that was wrong.

None of the 22 eval files uses these constructs, and all 22 pass the hardened checker. If you rely on a result checked with an earlier version, re-run the new checker on that file.

## What was wrong

- **Forged audit.** The audit was appended to the checked file, and the checker read the file's own output. A file could print a fake audit line and stop with `#exit`.
- **Kernel check switched off.** An option name built from strings got past the source scan, and nothing replayed the declarations afterward.
- **Hidden axiom.** An axiom with an internal-looking name went unaudited.
- **Misleading statements.** A file's own notation applied when statements were printed, so a theorem of `True` could print as `False`.

## What changed

A file now has to pass five stages:

1. **Source scan:** Lean's own parser reports the header, and only the real Lean and Mathlib libraries may be imported.
2. **Packages:** each package must come from its official repository and match its manifest, with no edited files.
3. **Compile:** the untouched file compiles in its own temporary directory.
4. **Audit:** separate processes check axioms with Lean's `collectAxioms`, check where imported modules load from, and print statements without the file's own notation.
5. **Replay:** `leanchecker` re-checks the compiled file with the kernel.

Each declaration also prints an `explicit:` line, and every definition from the file that a statement depends on is listed.

## What may break

- A file importing your project's own lemmas now fails, so keep each formalization in one file.
- A Mathlib fork, or a package with edited files, now fails.
- `--require` needs at least one required declaration to be a theorem.
- `autoImplicit` is off during checks.
- Checks are slower, because Mathlib loads four times, and output is longer. The README records the long output as a known issue.

## What this does not fix

This is a local check and is not proof against a deliberately hostile file: compiling Lean runs the file's code as you. It cannot tell whether a compiled `.olean` in `.lake/packages` matches its sources, and a misleading instance still passes if nobody reads the printed output. See [the trust boundary](https://github.com/Ztang-Yit-Xiaang/mathproof-skill/blob/main/skill/references/lean-verification.md#7-trust-boundary).

**Evidence:** CI on Linux passes all 22 evals, 28 fixtures, and 11 behavior tests. An independent reviewer attacked the code before the final fixes; those fixes have not had a second review.

Full details are in the [changelog](https://github.com/Ztang-Yit-Xiaang/mathproof-skill/blob/main/CHANGELOG.md).
