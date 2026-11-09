# Chained maps: one database each, or partitions of the project database

Status: assessment by Jorge (session metaform-33), 2026-11-09, for the owner through Marcus. Nothing in storage is changed. It answers: are separate database files per chained map feasible now that the store has the `stores.max_open_databases` cap, and where is the chained map's `uri` stored?

## Answer

Separate database files per chained map are feasible under the cap. The cost is about 32 MB of resident memory and 5 threads for each chained map while it is open. The cap of 16 keeps the total near 580 MB however many chained maps exist. R-4.15 says `map` stops at a chained map's Definitive element, so ordinary reads never open a chained database. Only an agent or a view that asks for the chained map opens it.

I recommend one database per chained map, kept by the home and keyed by the upstream repository's `uri`. The owner's own words ask for a separate database. A chained map is also the reference map of another project, so several projects can share one copy. The open decision below states what this changes and when the current default is better.

## Evidence

Measured at commit 1e16b78 (branch `workspace-mock`) with `cargo run --release -p metaform-store --example open_dbs -- <dir> 40 16`: 40 projects used in turn, at most 16 open.

| Used | Open | Resident memory | Virtual size | Threads |
|---|---|---|---|---|
| 0 (store only) | 0 | 45 MB | 17 GB | |
| 1 | 1 | 80 MB | 35 GB | 11 |
| 16 | 16 | 565 MB | 296 GB | 86 |
| 40 | 16 | 582 MB | 296 GB | 86 |

- Each open database adds about 32 MB resident, 5 threads (4 Ladybug workers and the writer) and about 17 GB of reserved virtual address space. The reserve is the likely cause of the earlier failure at about 7 open databases with default settings (`lib.rs` `DEFAULT_MAX_OPEN` comment). It is reserved, not used, but a system with a low address-space limit (`ulimit -v`) or tight overcommit can refuse it.
- Closing a database returns its memory: 40 used under a cap of 16 stayed at 582 MB.
- Not measured today: the time to reopen a closed small database. The storage note measured "a cold load of a few milliseconds" on 2026-11-07 (`storage.md` risk 5).

## The two options

| | A. Partition of `project.lbug` (current default, `storage.md` 2.2) | B. One database per chained map (recommended) |
|---|---|---|
| Matches the owner's words | Partly: "can be given its own db" read as a capability | Yes: "any element ... can be given its own db" |
| Memory while used | None extra | About 32 MB and 5 threads per open chained map, bounded by the cap |
| Ordinary reads (`map`, `goto` on the parent) | Never touch the chained map | Never open its database (R-4.15) |
| Writers (R-4.7, "each map has its own write queue") | One writer per project; a busy chained map delays the main map | One writer per chained map, so maps do not delay each other |
| Sharing an upstream map between projects | One copy per project that chains it | One file per upstream repository, shared |
| Updating an upstream map (a new intake of the upstream repository) | Once per copy | Once |
| A write that touches the parent and the chained map | One transaction | Two databases, so no single transaction. Creating a chain is the only such write: create the chained database first, then commit the link in the parent. A crash in between leaves an unlinked file, which the store can remove at open. |
| Search across a map and its chains (R-5.27) | One database | Opens each chained database in turn, a cold load each when it is closed |
| Files | One database per project | One more database per upstream repository |

## Where the `uri` is stored

- **Option B:** the `uri` is the chained database's key and is stored in it, on its `Map` node. The home keeps the database at a path derived from the `uri`, so every project that chains the same repository reaches the same file. The parent database holds the link: a `CHAINS` relationship from the holding element to a `Map` stub that records the `uri`. Reads show it as the `uri` of the chained Definitive element at `upstream.<element>`, which is what the mock does.
- **Option A:** the `uri` is a property of the chained map's `Map` node in `project.lbug`.

In both, the `uri` is a property of the map and not an intake field of the upstream Definitive element. The Definitive element's own `uri` keeps its intake meaning: where that element is found. Showing the map's `uri` in that slot is a read convention, and it needs the owner's word if the two can differ.

## Open decisions for the owner

1. **Storage of chained maps.** Options A and B above. I recommend B, because it is what the owner described, it gives each map its own writer, and one upstream map serves every project that relies on it. A is preferable if the home must run with little memory (under about 1 GB), or if a write that changes the parent map and a chained map must commit together.
2. **Versions of a shared upstream map.** Under B, two projects can rely on different versions of the same upstream repository. The question is whether the key is the `uri` alone or the `uri` with a version or commit. I recommend the `uri` with the commit the intake read, so a project's chained map does not change under it. That is the owner's call, because it decides whether upstream maps update for everyone at once.

## Not yet decided by anyone

- The read that returns a chained map's own elements. R-4.15 says `map` stops at the chained Definitive element and that an agent reads the chained map "only when it asks for it", but no read form is named. I proposed one to Marcus in the same pattern as `goto`: `{"map": "upstream.code.engine.game"}` returns that chained map's shallow graph, with its addresses under that prefix.

## Risks and verification

- Address space: each open database reserves about 17 GB. Before B is the default, test opening 16 chained maps under the strictest address-space limit we intend to support.
- A cold reopen of a small database was last measured on 2026-11-07. Measure it again at the current commit before relying on "a few milliseconds".
- Removing an unlinked chained database at open must be tested with a kill between the two steps of creating a chain, as the crash test does for writes (V-005).
