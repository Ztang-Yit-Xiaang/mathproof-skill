# INVESTIGATE mode

Use this when the user wants a durable record of one claim: what was tried, what was checked, and what its status honestly is. For ordinary proofs and audits, use the other modes, which need none of this.

The rule is simple: **record what happened, and let the tool derive the status.** Do anything else you find useful along the way. You never write a status, and a status you write has no effect.

## What the status can say

Status is computed from the ledger. At this stage nothing can reach `VALID` or `INVALID` through this tool. The strongest result is `kernel-passed-local`, with the verdict `UNVERIFIED`, because a local check cannot stand in for a clean-machine check and a person's signature. Report that plainly. Do not upgrade it in your own words.

Your ordinary verdict in `AUDIT` or `PROVE` is a separate thing. If you give one alongside a record, say which is which.

## Commands

`<dir>` is the investigation's directory, and claim ids look like `<investigation>/<claim>`, in lowercase. Run these from anywhere, using this skill's `scripts/mathproof.py`:

```bash
python3 scripts/mathproof.py init <dir>
python3 scripts/mathproof.py claim add --dir <dir> --id inv/c1 --text "The informal claim." --kind theorem
python3 scripts/mathproof.py check --dir <dir> --claim inv/c1 --decl Full.Name.of_theorem --polarity claim --project <lean-project> File.lean
python3 scripts/mathproof.py status --dir <dir> --claim inv/c1
python3 scripts/mathproof.py report --dir <dir> --claim inv/c1
python3 scripts/mathproof.py verify <dir>
```

`check` exits 0 on a pass, 1 on a failure, and 2 if it could not run. Exit 2 records nothing. A failure is worth keeping: it stays in the ledger as a record of what was tried.

## Choosing the polarity

Say what the checked theorem is, relative to the claim:

- `claim`: exactly the claim.
- `negation`: exactly the negation of the claim. Use this to refute it.
- `step`: anything else, such as one step of an argument or facts about one example. A step never counts as proving or refuting the claim.

`--decl` needs the exact full name, including namespaces, and it must be a theorem.

## Other records

Add these with `event add --dir <dir> --claim <id> --kind <kind> --data '<json>'`. Store a file first with `artifact add --dir <dir> <file>`, which prints the hash these records need:

| Kind | Data |
|---|---|
| `fidelity` | `statement_hash` (the Lean file's hash), `rows` (the fidelity table), `class` (`faithful`, `instance`, `partial`, `unfaithful`), `direction`, `judge`, `scope_note` |
| `informal_proof` | `artifact`, `author_context` |
| `informal_audit` | `proof_hash`, `result` (`no-flaw` or `flaw`), `auditor` |
| `assumption` | `text`, `standing`, `origin`, `change` |
| `budget_stop` | `reason`, `open_items` (a list) |
| `abandon` | `reason` |
| `note`, or any kind you invent | anything except a `status` field. Shown in the report as unverified notes |

For `fidelity`, `direction` is `F=>I` when a proof of the formal statement gives the claim, and `I=>F` when the claim implies the formal statement, which is what refuting it requires. Use `self-declared` as the judge for your own judgment. Without a verified signature, it stays a label and cannot change the verdict.

You cannot add `check` by hand, and a claim's statement cannot be changed. For a revised statement, add a new claim and record the link in a note.

## Finishing

Run `verify` before you report. It re-runs every check, so it can take minutes per file with Mathlib. Exit 0 means the ledger is consistent and the checks reproduce, and it does not mean the claim is proved. Give the user the `report` output, the `verify` result, and the Lean status as written.
