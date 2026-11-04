-- Expected: FAIL before compiling. A sibling import could hide a bypass in a module that is
-- never replayed, so only imports on the allow-list are accepted.
import HiddenBypass
theorem main_theorem : (1 : Nat) = 2 := hidden_proof
