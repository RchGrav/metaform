# Draft: CTX-066 How it shows and Acceptance, refs stay where linked

For the owner's approval. Ticket code.graph.knowledge#17, 2026-10-15. The working tree already carries the owner's correction of CTX-004 and CTX-066's "What this means" (a ref is not a property). These sentences of CTX-066 still describe the moving link and are now false of the code (`src/metaform/data/refs.py` `link`):

- How it shows: "Recording the same ref at `code.dispatcher.runner` leaves one ref, linked at `code.dispatcher`."
- Acceptance 1: "Recording `x` at `code.a`, then the same `x` at `code.b`, leaves one ref, linked at `code`."
- Acceptance 2: "After that, a read of `x@code` finds it, and a read of `x@code.a` or `x@code.b` answers that it is now at `code`. No sequence of records moves the link sideways or toward the leaves."
- Acceptance 5: "Giving `x` to a different thing writes nothing and returns a notice naming `x@code`, with `is_error` false."

Proposed bullet, appended after CTX-066's Status line:

- Amendment, 2026-10-15, ticket code.graph.knowledge#17: a ref never moves. Linking a file at `code.dispatcher.runner` that is already linked at `code.dispatcher.agent` makes a second ref at `code.dispatcher.runner`, with a name of its own (the ref_id stays unique in the project, so a derived name takes `_<extension>` or `_2`); the first stays at `code.dispatcher.agent`. Acceptance 1 and 2 read: recording `x` at `code.a`, then the same file at `code.b`, leaves two refs, `x@code.a` and another at `code.b`; a read of `x@code.b` answers that `x` is linked at `code.a`. Acceptance 5 names `x@code.a`. Layout 22's migration made one key and value at several places one ref at their nearest common node; the migration now keeps one ref at each place, and the live stores were restored (artifacts/refs-restore-2026-10-15/README.md). Built: `src/metaform/data/refs.py` `link`, `place`, `migrate`; test `test_a_ref_stays_where_it_was_linked_and_a_file_linked_at_two_places_is_two_refs` in `tests/test_store_map.py`.

CTX-065's Build still says the record is open and that a ref is a row of `refs`; that is #c's, not changed here. CTX-009 stays for properties.
