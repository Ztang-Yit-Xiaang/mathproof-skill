-- Expected: FAIL. `prelude` drops core Lean, so the file can define its own `False` and an
-- axiom named `propext`. An allow-list that compares only names would accept this.
prelude
inductive False : Prop
axiom propext : False
theorem main_theorem : False := propext
