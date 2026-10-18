---
name: throwaway-probe-leaves-no-test-files
description: Use when writing a throwaway probe or probe test file.
category: development
---

# Throwaway probes leave no test files behind

Pytest collects any `test_*.py` in the tree, so an untracked probe file reruns the whole browser suite on every run and pollutes shared logs.

- Put probes outside the `tests/` folders, or make them copies that delete themselves on exit.
- Delete the probe and any log it wrote when the ticket ends, and confirm with `ls` on the test folder before reporting done.
- Run a probe with `-n 0` and a `-k` filter for the one case under test.
