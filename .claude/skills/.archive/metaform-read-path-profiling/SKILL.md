---
name: metaform-read-path-profiling
description: Use when a Metaform node read or map_where is slow.
category: development
---

# Measure a Metaform read in a fresh request scope before changing it

Time the slow read inside `request_scope(fresh=True)`, split the time by call, and fix the call that repeats work. Do not fix from reading the source alone.

- A read timed outside a fresh scope hits warm caches and shows the wrong cost. The first call in a fresh scope pays a cold module discover; report it separately from the steady cost.
- A cost that grows with candidates times file size is quadratic: a per-position search that re-splits a whole cited file costs a full split per candidate. Split each file once per read, keep the lines beside the text, and compare windows over that list. Prove the answers unchanged against the previous code on a large file, and time both.
- A live page read is only evidence if the serving process started after the last edit to the code it runs. Compare its start time with the file's mtime (see restart-processes-after-code-fix). A server started mid-edit runs an intermediate version, so time again after the restart.
- Record the before and after medians on the same home, with the target stated in the ticket.
- Profile a copy of the live home with its running rows stamped as this home's, so the runners are really asked for status. A copy whose running rows belong to another home skips them and hides the cost: 15 ms there, 33 ms with four live runners.
- Count SQL statements per read beside its time, and guard the count with a test that holds it flat as ended sessions grow (41 statements before, 2 after, on 40 ended sessions).
- Ask runners concurrently, not one after another: each ask cost about 3 ms, and they add up in turn.
- Under shared load, run each case in interleaved rounds on its own copy, and report every round, not the best one.

Numbers and the 2026-10-16 case: `references/node-read-profile.md`.
