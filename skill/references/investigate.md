# INVESTIGATE mode

Use this when the user wants a durable record of one claim: what was tried, what was checked, and what its status honestly is. For ordinary proofs and audits, use the other modes, which need none of this.

The rule is simple: **record what happened, and let the tool derive the status.** Do anything else you find useful along the way. You never write a status, and a status you write has no effect.

## What the status can say

Status is computed from the ledger. At this stage nothing can reach `VALID` or `INVALID` through this tool, because no signature can be verified yet. A local check gives at most `kernel-passed-local`. An authoritative judge report, described below, gives at most `judged-unreviewed`, and `judge-rejected` if the judge failed a check that passed locally. The verdict stays `UNVERIFIED` either way. Report that plainly. Do not upgrade it in your own words.

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

## Authoritative judgment

A local check runs on a machine an agent can change. The authoritative judge runs `lake comparator`, in its sandbox, in a GitHub Actions workflow on a clean checkout of `main`. It compares each checked file against a Challenge: the statement alone, proved by `sorry`.

Freeze the claim's formal statement once, and the Challenge is generated from it:

```bash
python3 scripts/mathproof.py statement --dir <dir> --claim inv/c1 --name main_theorem \
  --prop-file prop.lean --preamble-file defs.lean --project <lean-project>
```

`prop.lean` holds the proposition alone, with every variable bound (`∀ n : ℕ, …`); it cannot contain `:=`. `defs.lean` is optional. Each of its commands starts at column 0 with `def`, `theorem`, `lemma`, `abbrev`, `structure`, `inductive`, `class`, `instance` (each may follow `noncomputable`, `private`, or `protected`), a doc comment, or `open` followed by plain names; continuation lines are indented. Neither file may `import`, or use anything that changes how Lean reads what follows or runs code while it compiles (`notation`, `macro`, `simproc`, `set_option`, `variable`, `namespace`, attributes, `run_cmd`, `#` commands, `native_decide`, `IO`, the `Lean` metaprogramming API, and similar). Tactic blocks (`by`) are refused too, because a tactic can elaborate differently on each compile and the judge prints the statement from one compile while the comparator checks another: write local definitions and lemmas as terms; the command names what it refused. The Challenge is the preamble, then `main_theorem : (PROP)` for a proof and `main_theorem_negation : ¬ (PROP)` for a refutation. A fixed Lean program then loads the compiled Challenge at run time and checks that both theorems are declared at the root, by the Challenge, on the lines the generator wrote, and that the second is exactly `Not` of the first. Because it loads the Challenge rather than containing its text, nothing in the statement can change how it runs. The checker's audit then prints the claim's type as Lean elaborated it, without the statement's own notation, once as usual and once with every instance and numeric type shown, and every definition the type reaches that the statement itself defines, with its body. Read the explicit form: `1 = 2` reads as false, but in `Fin 1` it holds. The command prints both and records them with the statement; read them, because a local definition can look like a Mathlib one in the text. The authoritative judge runs the same steps again, in a sandbox with no network that can write only its build directory, and puts what was printed in the report; only the judge's run counts, and a pass on a claim with a statement counts only if the report shows it. A proof must then be checked with `--decl main_theorem` and polarity `claim`, and a refutation with `--decl main_theorem_negation` and polarity `negation`; the judge skips any other target, and authoritative verify ignores a pass for one, or a pass from a report older than the statement. The comparator compares every constant the theorem's type reaches, values included, so a proof that weakens the statement or redefines a local definition under the same name is rejected.

A statement never changes. To change it, add a new claim and freeze its statement with `--revises inv/c1`; the old claim keeps its checks and judgments, and its status names the claim that revised it.

A claim with no frozen statement can still use a hand-written Challenge, one per claim and polarity:

```bash
python3 scripts/mathproof.py challenge-file --dir <dir> --claim inv/c1 --polarity claim Statement.lean
```

The ledger must be committed to `main`. A person then runs the `Authoritative judge` workflow with the ledger's path in the repository, and runs:

```bash
python3 scripts/mathproof.py verify <dir> --authoritative latest --repo OWNER/NAME --ledger-path <path-in-repo>
```

`latest` fetches the report of every successful run of the workflow on `main`. `verify` uses a report only if `gh attestation verify` shows that this repository's `.github/workflows/authoritative.yml` produced it, on `refs/heads/main`, on a GitHub-hosted runner. Each such report for this ledger's path in the repository is an **anchor**: it records the ledger head the judge saw. A report for another path that shares this ledger's first event, such as a copy or the same ledger before a rename, must also be extended; its results count too, but it does not count as an anchor. The local ledger must extend every anchor. If one anchor's head is not in it, events that anchor covered were changed or deleted, and `verify` prints `ANCHOR VIOLATED` and fails. If no attested report anchors the ledger, `verify` prints `NO ANCHOR` and fails, rather than quietly showing local statuses. Results come from every anchor, and each must name a recorded check. A pass also needs the Challenge registered now; a rejection stands even if the Challenges were changed since, so editing `challenges.json` cannot hide one. Only a newer attested result under a different Challenge withdraws an older one; a newer `error` withdraws nothing. Events after the newest anchor are not covered until the next run. You can pass one downloaded `judge-report.json` instead of `latest`, but then older anchors are not checked. Give the ledger's path in the repository yourself with `--ledger-path`, exactly as you gave it to the workflow. `verify` never works it out from the checkout, because symlinks and git settings there can be changed to point at another ledger. Each note says why a report or result was ignored. Never run `judge` yourself: it needs Linux `bwrap` and refuses to run without it.

Run `verify` from a checkout and a `gh` that agents cannot write to: an agent that can change the code, or put its own `gh` first on `PATH`, can forge any result.

What this rests on: GitHub's attestations, and branch protection on `main`, which keeps the workflow file and the committed ledger reviewed. An anchor lasts as long as its run's report artifact, at most 90 days on a public repository, and deleting a run removes it. Statements and Challenges are unsigned for now, so a judged result shows `missing: statement signature, fidelity signature`, plus `vacuity witness` for a proof.

## Signing judgments

A person signs what Lean cannot judge: that the frozen statement says what the claim means, a fidelity judgment, an informal audit, a waiver, or a retraction. Sign with an SSH key that has a passphrase and that agent sessions cannot reach (DEC-008). `sign` never signs through an `ssh-agent`, but an agent session could call `ssh-keygen` itself with any key loaded into one, so don't load this key into an agent they share (on macOS, check that `AddKeysToAgent` and `UseKeychain` don't load it). A hardware key that needs a touch (`ssh-keygen -t ed25519-sk -O verify-required`) closes this:

```bash
python3 scripts/mathproof.py sign --dir <dir> --event <seq> --key ~/.ssh/mathproof_review --identity you@example.com
```

The command refuses a ledger whose chain does not verify, then shows what you are signing: for a statement, the name, preamble, proposition, and the type the `statement` command recorded (an agent can write that field; the judge's report prints it independently); for a fidelity judgment or an informal audit, the Lean file or the proof text itself; for a retraction, the event it removes. It then asks you to type the claim id. That prompt guards against signing the wrong thing by mistake; it is not a security control, and only the key's passphrase is. The signature covers your identity, the claim id, the hash of its informal text, the hash of its frozen statement, the signed event (for a retraction, also the kind and seq of what it removes), and the ledger head, so it cannot be moved to another claim or event.

A signature counts only when an authoritative verify checks it against an allowed-signers file (the `ssh-keygen` format, namespace `mathproof-review`) that is kept outside the ledger, for example in a protected branch or your home directory:

```bash
python3 scripts/mathproof.py verify <dir> --authoritative latest --repo OWNER/NAME --ledger-path <path-in-repo> --signers ~/.config/mathproof/allowed_signers
```

A verified statement signature marks the statement signed; a verified fidelity signature makes that judgment `signed-human`, and signed judgments then decide over unsigned ones; a signed informal audit gives the label "informal proof, human-audited, not machine-confirmed"; a signed retraction removes the event it names only when that can't make the claim look stronger: a passing check that the judge did not reject and that no passing check of the other polarity contradicts, a `faithful` judgment, a no-flaw audit, an informal proof with no flaw found, or an experiment with no violations. Anything else stays. A signature counts only for the exact event it signed, and none counts in a ledger whose chain is broken. An unsigned retraction changes nothing. `established` and `refuted-certified` also need gates later tasks add (the assumption audit, and a vacuity witness for a proof), so a fully signed claim still reads `judged-unreviewed` with `missing: assumption audit`.

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
