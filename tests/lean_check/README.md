# Checker regression tests

```bash
python3 tests/lean_check/run_tests.py    # needs the built lean/ project
python3 tests/lean_check/test_pins.py    # no Lean needed
```

Each top-level `*.lean` file is a fixture. `pass_*` must pass and `fail_*` must fail. A failing fixture must fail for the reason listed in `REASONS` in `run_tests.py`, so an unresolved import cannot count as an attack caught. `helpers/` holds files that fixtures refer to; the runner does not treat them as fixtures.

To test the tests, run the suite against another checker. A known-bad one should fail it:

```bash
git show bef93cf:skill/scripts/lean_check.py > /tmp/old_check.py
python3 tests/lean_check/run_tests.py --checker /tmp/old_check.py
```

These fixtures contain attacks on the checker, and compiling them runs their code. They only add declarations and do not touch files or the network. Keep any new fixture that way.
