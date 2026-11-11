# INVESTIGATE mode

Use this when the user wants a durable record of one claim: what was tried, what was checked, and what its status honestly is. For ordinary proofs and audits, use the other modes, which need none of this.

The rule is simple: **record what happened, and let the tool derive the status.** Do anything else you find useful along the way. You never write a status, and a status you write has no effect.

## What the status can say

Status is computed from the ledger. At this stage nothing can reach `VALID` or `INVALID` through this tool. The strongest result is `kernel-passed-local`, with the verdict `UNVERIFIED`, because a local check cannot stand in for a clean-machine check and a person's signature. Report that plainly. Do not upgrade it in your own words.

Your ordinary verdict in `AUDIT` or `PROVE` is a separate thing. If you give one alongside a record, say which is which.

## Commands

`<dir>` is the investigation's directory, and claim ids look like `<investigation>/<claim>`, in lowercase. `--kind` on `claim add` is your own word for it, such as `theorem` or `lemma`. Run these using the full path to this skill's `scripts/mathproof.py`; they work from any directory, and files can be given by any path:

```bash
python3 scripts/mathproof.py init <dir>
python3 scripts/mathproof.py claim add --dir <dir> --id inv/c1 --text "The informal claim." --kind theorem
python3 scripts/mathproof.py check --dir <dir> --claim inv/c1 --decl Full.Name.of_theorem --polarity claim --project <lean-project> File.lean
python3 scripts/mathproof.py status --dir <dir> --claim inv/c1
python3 scripts/mathproof.py report --dir <dir> --claim inv/c1
python3 scripts/mathproof.py verify <dir>
```

`check` exits 0 on a pass, 1 on a failure, and 2 if it could not run, for example when a file or Mathlib is missing or a time limit ran out. Exit 2 records nothing. A failure is worth keeping: it stays in the ledger as a record of what was tried.

The status line reads like `KERNEL-PASSED (local; negation, fidelity: faithful, self-declared)`. `KERNEL-PASSED` is not one of the `Lean status` values in the main protocol: it means the local checker passed and the verdict stays `UNVERIFIED`. A proof and a refutation share the headline `kernel-passed-local`, so read the polarity in this line.

## Choosing the polarity

Say what the checked theorem is, relative to the claim:

- `claim`: exactly the claim.
- `negation`: exactly the negation of the claim. Use this to refute it.
- `step`: anything else, such as one step of an argument or facts about one example. A step never counts as proving or refuting the claim.

`--decl` needs the exact full name, including namespaces, and it must be a theorem.

## Experiments

A numerical experiment is evidence, never a proof or a refutation: it can't raise a claim's status, and a violation it reports shows up only as a candidate to examine. Write the experiment as one Python or R file that reads `MP_SEED` (an integer), `MP_PARAMS` (a JSON object) and writes one JSON object to the path in `MP_OUT`, with any counterexample candidates as a list under `"violations"`:

```bash
python3 scripts/mathproof.py experiment run --dir <dir> --claim inv/c1 --code check.R --lang r --seed 1 --params '{"n": 100}' --timeout 600
python3 scripts/mathproof.py experiment rerun --dir <dir> --seq <event seq>
```

`run` records the code, seed, parameters, an environment fingerprint, and a hash of the results, whatever the outcome (`completed`, `timeout`, or `error`). Nothing is made up when the program fails or R is missing. `rerun` runs the stored code again and exits 0 only when the outcome and results match. Experiments aren't sandboxed, and the memory limit can't be enforced on macOS; each record says so. Put an `renv.lock` next to an R file to pin its packages.

## Other records

Add these with `event add --dir <dir> --claim <id> --kind <kind> --data '<json>'`. Store a file first with `artifact add --dir <dir> <file>`, which prints the hash these records need:

| Kind | Data |
|---|---|
| `fidelity` | `statement_hash` (the Lean file's hash), `rows` (a list of objects with `informal`, `formal`, and `match`, which is the fidelity table), `class` (`faithful`, `instance`, `partial`, `unfaithful`), `direction`, `judge`, `scope_note` |
| `informal_proof` | `artifact`, `author_context` |
| `informal_audit` | `proof_hash`, `result` (`no-flaw` or `flaw`), `auditor` |
| `assumption` | `text`, `standing`, `origin`, `change` |
| `budget_stop` | `reason`, `open_items` (a list) |
| `abandon` | `reason` |
| `note`, or any kind you invent | anything except a `status` field. A `text` field is shown in the report as an unverified note |

For `fidelity`, `direction` is `F=>I` when a proof of the formal statement gives the claim, and `I=>F` when the claim implies the formal statement, which is what refuting it requires. Use `self-declared` as the judge for your own judgment. Without a verified signature, it stays a label and cannot change the verdict.

You cannot add `check` by hand, and a claim's statement cannot be changed. For a revised statement, add a new claim and record the link in a note.

## Finishing

Run `verify` before you report. It re-runs every check, loading Mathlib four times per file, so expect minutes per file and much longer on a busy machine. Exit 0 means the ledger is consistent and the checks reproduce, and it does not mean the claim is proved. Give the user the `report` output, the `verify` result, and the Lean status as written.
