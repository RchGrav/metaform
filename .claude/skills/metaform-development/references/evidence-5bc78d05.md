The tree is being edited concurrently (server.py gained `same_origin` from someone else mid-run). Checking whether the remaining pyright error is mine.

  /home/rich/metaform/src/metaform/cli.py:571:36 - error: Argument of type "str | None" cannot be assigned to parameter "next_step" of type "str" in function "__init__"

Another agent added `GATE_SECRET` to the same import line, which now runs past 120 characters. Wrapping it so ruff stays clean, without changing their names.