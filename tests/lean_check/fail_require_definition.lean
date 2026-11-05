-- Expected: FAIL. `main_theorem` exists, but it only defines the proposition. Nothing is proved.
def main_theorem : Prop := (1 : Nat) = 2
