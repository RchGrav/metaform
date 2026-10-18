# Example: effect/sink walk over module verbs

Context (2026-10-14): a walk in the mcp module's tests checks that every verb reaching the network or writing declares it. Before the walk learned about data operations, `x.tables()`, loopback, subprocess and file reaches, a mutation check that flipped map add-base, activate, collapse, work and memory delete_entities to `effect='read'` printed `caught: []`. The walk had seen 110 of 155 write verbs as having no write at all, so the green test proved little.

Fix sequence that worked:
1. Run the mutation check; expect the flipped verbs. Empty output means blind.
2. Teach the walk the missing sink kinds one at a time, re-running the flip after each.
3. Assert in the test that flipped verbs are exactly the reported set.
4. Assert that write or remove verbs with no sink equal a named allow-list (9 of 146 at the time), each with a reason. Report allow-listed declarations that look wrong; do not change them inside the guard change.

Bookkeeping exceptions (table creation on first use, caches, shown-once records, the first base made on first use) are named constants with reasons, not inline ignores.
