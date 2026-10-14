E       ValueError: max() iterable argument is empty

src/metaform/modules/dispatch/tests/test_dispatch.py:454: ValueError
=========================== short test summary info ============================
FAILED src/metaform/modules/dispatch/tests/test_dispatch.py::test_a_second_writer_on_the_session_never_ends_the_runner_and_lines_keep_one_order

Memory observation written at close: "Gotcha: tx.rows(by=('session_id','seq'), after=...) needs a cursor of [seq, name], because the key column name is appended to the index's rest. A one-value cursor raises an SQL error." and "Runner.table(fatal=False) logs a failed line write to stderr and returns None instead of calling self.fail. That also hides bugs in the line path, so test line writes through the thread itself."