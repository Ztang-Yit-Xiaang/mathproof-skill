-- Expected: PASS, and the definition must be shown. Its name looks like a generated eliminator,
-- but no inductive type `Foo` exists, so it is the user's own definition.
def Foo.casesOn : Prop := True
theorem main_theorem : Foo.casesOn := trivial
