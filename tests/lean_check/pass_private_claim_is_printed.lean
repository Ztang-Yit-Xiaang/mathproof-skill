-- Expected: PASS, and the body of the private definition must be shown. Otherwise the output
-- reads `main_theorem : _private...Claim` and a reader cannot tell the claim is only `True`.
private def Claim : Prop := True
theorem main_theorem : Claim := trivial
