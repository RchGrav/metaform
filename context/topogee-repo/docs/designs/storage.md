# Storage and writers

This note sets the long-term storage design for both products, Metaform and Topogee, and the rule for multiple writers. Jorge, the graph and data specialist, wrote it on 2026-11-07, at the founder's request, with Xander, the design reviewer. It corrects inferences about storage that earlier documents made without the founder deciding them.

The founder's goal for this work, 2026-11-07: "DoD is we undo wrong inference about data storage, we will be using the core architectural storage concepts from anvil, ie • Region-Chunk Grouping: Grouping small chunks (e.g., 16³ or 32³) into larger region files or database partitions to prevent OS filesystem bottlenecks from tens of thousands of tiny files. • Palette Compression: Mapping unique block states per chunk to small bit-packed integer indices rather than storing full block IDs or strings for every voxel. • Empty-Section Culling: Omitting uniform or air-only vertical sections from disk serialization entirely. combined with ladybugdb."

Status words follow `metaform/SPEC.md`. **Decided** means the founder decided it. **Default** means the engineers decided it under `EXPECTATIONS.md`, and it stays open to the founder's correction. Work continues on a default.

## 1. The rule behind every store

Grouping applies to every store, not only to voxels. Many small units, such as chunks, maps or a layer's pieces at each address, are grouped into a few large physical units, such as region files or databases. Each small unit keeps its own identity, its own key and its own write queue. Only its physical placement is shared.

The reason is the same everywhere. Tens of thousands of small files slow the file system. Ladybug has its own version of that limit: each open database reserves address space. One process failed at about 7 databases on default settings. 200 databases worked only with a 64 MB buffer pool and a 16 GB size limit each (`docs/world-ideas.md`, "Tested").

## 2. Specification updates

### 2.1 World voxels (Topogee)

Decided by the founder on 2026-11-07, as above, and recorded by Xander in world spec W-3.2, W-3.3 and W-3.5. Built on main in `topogee/crates/world-store`.

- A section is 16 x 16 x 16 voxels. A chunk is a 16 x 16 column of 24 sections, from y = -64 to 319. A region is 32 x 32 chunks in one file.
- A section stores a palette of its distinct values and a bit-packed palette index for each voxel, using only the bits the palette needs.
- An air section is never written. A uniform section is written as its one value with no indices, which takes about 4 bytes. "Omitting uniform sections entirely" is read this way because omitting a stone section would lose its material.
- A chunk with no sections has no record. A region with no records has no file. A void world with no edits stores zero bytes (W-12.3).
- Voxels never become Ladybug nodes. Entities, ports, links, manifests and code modules are stored in the world's Ladybug database (W-3.5), `<world>/world.lbug`.

### 2.2 Metaform maps

Default, replacing R-4.1's "one database per map":

> **R-4.1** Maps are stored in LadybugDB. A map is the logical unit: it has its own map id, its own write queue (R-4.7) and its own identity. A database is the physical unit that groups maps. A project's main map and its chained maps are partitions of the project's database, `projects/<encoded-path-id>/project.lbug`. Maps that belong to no project are partitions of the home's standalone database, `maps/maps.lbug`. A map moves to its own database when it needs its own writer, its own sharing or its own size; a map run as its own instance (R-4.14) has its own home and therefore its own database. Rust code works through Ladybug and never writes map files itself. The chassis database `metaform.lbug` holds the project registry and global settings; JSON may hold them instead. Nothing is written into a project's own folder, and a project's database never stores the project's name.

**Source:** the founder: "any element in the metaform map can be given its own db"; "db's can represent sub features" (2026-11-07). "Can" grants a capability, and the documentation set 1.2 names one `project.lbug` per project. `DECISIONS.md`: "One database can hold more than one project."

The partition is realized in the graph, not by copying files. Every map has a `Map` node, and every element node carries the id of its map:

```
NODE Map(id STRING PRIMARY KEY, parent STRING, owner STRING)
NODE Element(key STRING PRIMARY KEY,      -- "<map id>|<camelCase address>"
             mapId STRING, technicalName STRING, name STRING, role STRING,
             uri STRING, status STRING)
REL  ROOT(FROM Map TO Element)            -- the map's "." element
REL  CONTAINS(FROM Element TO Element)    -- nesting by address segment (R-4.16)
REL  WANTS(FROM Element TO Element, why STRING, how STRING, intent STRING)
REL  CHAINS(FROM Element TO Map)          -- an element given its own map (R-4.15)
```

- An addressed read is a primary-key lookup on `key`. A walk starts from the map's `ROOT` and follows `CONTAINS`, so it never scans other maps' elements.
- A `WANTS` edge never crosses maps. A dependency on another map goes through `CHAINS` or a link between projects (section 7).
- Native arrays (`memory`, `sources`) and layers attach when the founder's unified layer approach is described (R-4.16).

Default, for R-4.15 and D-16: a chained map is a `Map` node in the same database as its parent, reached by `CHAINS`. Promoting it to its own database moves its partition and leaves a `Map` node whose `id` names the new location. D-16's earlier recommendation, a folder with its own `map.json`, is withdrawn, because JSON map storage was never decided.

Default, for R-6.21 and R-4.3 (layer files): a layer stays a separately indexed unit, and each piece of it stays a separate record, keyed by map, address and layer. Pieces are grouped physically in the database, not kept as loose files. The founder's example "this_address_inbox.json" names a logical file. An inbox file for every address would put tens of thousands of files on disk, which is the problem section 1 avoids. **The founder decided R-6.21, so this default needs his confirmation** (section 4).

### 2.3 The commit point (R-4.13, D-17)

Default: a Ladybug transaction is the commit point. No separate effect log is kept. The spike showed that Ladybug keeps a committed row and drops an uncommitted one when the process is killed with SIGKILL during a transaction (`metaform/verification/ladybug-spike-2026-10-30.json`). The effect log in R-4.13 existed to make JSON file writes atomic, and that need left with JSON. Announcements (R-4.10) come from the writer after each commit. A change journal for history or undo is a layer decision, not a storage requirement.

### 2.4 Layout under a home (D-17)

Default:

```
<home>/                      ~/.metaform, or METAFORM_HOME
  metaform.lbug              project registry, global settings (or settings.json)
  server.lock                held by the one functional map server (R-4.4)
  server.sock                forwarders connect here (R-4.5)
  projects/<encoded-path-id>/
    project.lbug             the project's maps, as partitions
    source.txt               the project folder this id stands for
  maps/maps.lbug             maps that belong to no project
```

The server keeps at most a configured number of databases open, 16 by default (64 until measured, risk 5), and closes the least recently used. Each database opens with a 64 MB buffer pool, a 16 GB size limit and 4 worker threads. Opening a project database on demand took about 5 ms typically and 458 ms at worst across 100 projects (`docs/world-ideas.md`, "Tested").

A world's folder, decided by Xander for Topogee:

```
<world>/
  world.lbug                 entities, ports, links, manifests, modules (W-3.5)
  world.lbug.owner           held by the world server
  region/r.<x>.<z>.region    voxels (W-3.2, W-3.3)
```

Accounts live outside every world, in a SQLite database owned by the edge (world spec L1). SQLite fits tabular data better (`DECISIONS.md`).

### 2.5 Multiple writers

Default, applying to every store in both products:

1. **One owner per store.** Every store has exactly one owning process. The settings system declares the owner by service name: `stores.<name>.owner`. The launcher reads it when it writes a service's recipe (`docs/designs/service-launcher.md`).
2. **The owner proves it.** At open, the owner takes an exclusive lock file beside the store (`server.lock`, `world.lbug.owner`). It releases the lock only after its writer has stopped and the database is closed: a reopen that raced a close reported a corrupt WAL (`metaform/verification/ladybug-probe-2026-11-07.json`). A second process that tries to own the store is refused with the owner's process id. Ladybug's own file lock backs this up: a second read-write process is refused with the holder's process id (spike; confirmed on lbug 0.22.3 from Rust).
3. **Everyone else goes through the owner.** Other processes never open the store, not even read-only. The spike showed a read-only process opened beside the writer and kept the state from its open time: it did not see later commits. Forwarders, the CLI, the viewer and agents reach a Metaform home through `server.sock` (R-4.5). Agents reach a world through the world tool.
4. **The write manager.** One writer thread per database, holding the database's only write connection. Each map, or each world store, has its own queue (R-4.7). The writer serves clients in turn, so one client's burst cannot starve another's. Each command commits in one transaction and is acknowledged after the commit. Ladybug refuses a second write transaction at once and does not queue it, so the queue is ours. A second writing connection is also unsafe, not only refused: on lbug 0.22.3, a write on a connection whose `BEGIN` was refused ended the process with a segmentation fault (`metaform/verification/ladybug-probe-2026-11-07.json`). Ladybug's `enable_multi_writes` setting allows concurrent write transactions in one process, with conflicts caught at commit. It stays off until a load test shows the write manager needs it.
5. **Reads** run on separate read connections against the last committed state, and never wait for the writer.
6. **Several homes.** R-4.14's instances are separate homes, each with its own server, so instances never contend.
7. **Across machines** (D-10): a store stays single-owner. Another machine reaches it through the owner's socket or tool, never through a shared file system.

### 2.5b Rights and creators (W-9.9)

**Status: Built** (2026-11-07), storage half; the checks, chat commands and client are Xander's.

- **Rights** live in the accounts store (`accounts.sqlite3`), table `rights(account, right, granted_by, granted_at)`, one row per account and right. The rights are `place_code` and `link`. The admin is not stored: the server's `--admin` account holds every right at login, so a lost accounts file cannot strand the admin.
- **The rule is kept by the accounts owner**, which sees the rows: the admin grants and revokes anything; a person grants their own agent only a right the person holds, and revokes any right from their own agent; revoking a right from a person revokes it from that person's agents too. A grant or revoke answers every account whose rights changed, so the server can update logged-in sessions at once. A login answers the account's rights and, for an agent, its owner.
- **Creators** live in world.lbug: `Block.creator` and `LINK.creator`, an account id, or null for seeded machines, which count as the admin's. Worlds made before gain the two columns when they open (`ALTER TABLE ... ADD IF NOT EXISTS`); their rows read as null.

### 2.5a Block ids and cell values

**Status: Built** (2026-11-07, world-proof-path item 1, with Xander; the width is the founder's: "I would make the address space for block types very large").

- A cell value is 64 bits: a block type number in the low 32 bits and that block's state in the high 32 bits. Value 0 is air with no state, so the void still stores nothing (W-12.3).
- world.lbug holds the registry: a `BlockType` node per full block id (`namespace:name`) with its number. `world-graph` assigns numbers from 1, in the order given, in one transaction, and never reassigns or reuses one, so stored cells keep their meaning when content changes. Past 4,294,967,295 types it refuses.
- Width costs almost nothing: a section's palette stores each distinct value once, as a varint, and voxels hold only bit-packed palette indices. The varint form is the same at any width, so records written when values were 32-bit read unchanged; no format version or migration was needed.
- At start the server registers the content (the legacy five first, then other materials, then code-block kinds) and shares one snapshot (`blockids::BlockIds`) across the world.

### 2.6 Storing generated terrain (W-10)

**Status: Built** (2026-11-07). The founder asked for it to be built; Xander took these defaults, open to the founder's change: generate on first need; a failure or running out of fuel leaves the chunk ungenerated and it is tried again with a backoff (2 s, doubling to 60 s); a new generator affects only chunks never generated. The generator is bound through the server's configuration for now; binding it to a block in the admin world (W-9.2) comes later.

- **The sandbox** (`topogee/crates/world-gen`, `content/wit/generator.wit`): the `generator` world exports `generate(seed, chunk-x, chunk-z)` and imports one interface, `terrain`, whose `put(x, z, y, height, block)` hands over one vertical run of a block id and whose `fail(reason)` gives up on the chunk. It reaches nothing else. Each chunk runs in a fresh instance with 100,000,000 units of fuel and 32 MiB of memory, so chunks cannot affect one another and the output depends only on the seed and the coordinates. The cells go out through calls with borrowed text rather than a returned list because any allocation in the component links Rust's allocation-failure path, which writes to stderr and so imports WASI, which a generator does not get.
- **Block ids:** the runs name full block ids. An id the registry does not know, or a code block's id, fails the chunk (it stays ungenerated). Content ids are registered at start, so a generator for any loaded content works.
- **Content:** `content/blocks/hills`, seeded rolling hills of `topogee:stone`, `topogee:dirt` and `topogee:grass_block`.
- **A record with no bit** (found by Xander in the browser: the seeded machines' chunks were left as a pit in the hills): in a world that binds a generator, a chunk whose cells were written before generation reached it (seeded block cells, or a world built before a generator was bound) is generated, its stored non-air cells are laid over the result, and then it is stored and its bit set. A chunk with its bit is never generated again.

- **What a region records.** world.lbug gets a `Region` node for each region a generator has touched: its key `x,z`; one record for each generator module that has generated chunks there, holding the module's hash and a bitmap of 1,024 bits, one per chunk, which is 128 bytes; and a relationship to that `Module`. This is W-10.2's "records the generator's module hash with each region it generates". It lives in the graph because the region file's 8 KiB table has no free bytes, and because the graph already records what made the world (W-3.5).
- **Why one mark for each chunk, not one for each region.** W-10.1 generates "when a chunk is first needed", so marks are kept per chunk. Generating a whole region at once would compute 1,024 chunks for one player's first step.
- **Generated air costs nothing.** A generated chunk that is all air has no record in the region file (W-3.3). Its bit is the only trace, and that tells "generated, empty" apart from "not generated yet". A void world with no generator has no `Region` nodes and stores zero bytes (W-12.3, W-2.3).
- **Order of writes.** The chunk's record is written first, through the same batched `save_chunks` as any edit. Its bit is set after that. If the process crashes in between, the record exists and the bit does not. A chunk with a record is always data and is never generated again, so the bit is repaired the next time it is checked. The reverse order could leave a bit with no record, which would read as generated air and lose the chunk.
- **(1) Stage 2 across region borders.** Stage 2 of a chunk reads the stage 1 data of its eight neighbours (W-10.3). Stage 1 depends only on the seed, the coordinates and the module (W-10.2, deterministic), so the neighbours' stage 1 is recomputed, never stored, and never needs the neighbour chunk or its region to be loaded or generated. Each chunk's stage 2 writes only that chunk; a feature that crosses a border is placed in parts by each chunk it touches, from the same neighbour data. Under that assumption, generation needs no write across chunks or regions.
- **(2) A new generator is bound.** Chunks that are already generated keep their data: they are ordinary data (W-10.1), and storage never generates them again on its own. Only chunks without a bit use the new module, and their bits go under the new hash. So the region's record shows which module made which chunk. That is the information needed to find or repair a seam. Whether to regenerate untouched chunks is a question for the founder (section 4).
- **What is not stored:** stage 1 data, the generator's inputs (seed and coordinates are enough), and any per-chunk record of generator failures.
- **Built so far:** nothing. `world-graph` would gain `Region` writes through its one writer, and `world-store` stays unchanged.

## 3. Decision rationale

- **Grouping.** The tested Ladybug limit and the file-system cost both point the same way. One database per map would put the per-process database limit inside every agent's normal work. R-4.15 lets in-world agents create private maps freely. Confidence: high on the direction, because it rests on a test on this machine. Medium on the 64-database cap, which is untested at load.
- **Map id on every element.** Ladybug has primary-key indexes and no secondary indexes that we have verified. A composite key `<map id>|<address>` keeps every addressed read an index lookup. A table for each map would also work, but the schema would grow with every map, and dropping a map is rare. Confidence: medium. A load test with many maps in one database is still to run (section 5).
- **Not Ladybug's partitioned tables.** lbug 0.22.3 has native partitioned node tables (`PARTITION BY HASH|LIST|RANGE`), which looked like the "database partitions" the founder named. The probe ruled them out for maps for now. The primary key was not enforced across partitions: the same key went in twice. Creating a relationship against the partitioned parent table is refused. Both would break the map's integrity rules (R-3.4, R-4.16). Reconsider them if a later Ladybug release enforces keys across partitions.
- **No effect log.** Ladybug's transaction and its recovery after SIGKILL already give atomic, durable commits. Keeping a second log would double every write and add a second recovery path to test. Confidence: medium. One SIGKILL run is not a crash campaign.
- **Region files for voxels, not Ladybug blobs.** A region file is one sequential read for a chunk, and its format is ours to tune. A Ladybug blob per chunk would also group well. It stays possible behind the `RegionStore` trait. Confidence: high.
- **One owner, and no read-only openers.** The stale-snapshot behavior makes a read-only opener give wrong answers without any error. Confidence: high, from the spike.

## 4. Open decisions for the founder

1. **R-6.21, layer files.** The question: may a layer's pieces be grouped records in the database, not separate files on disk? Options:
   - (a) Grouped records (recommended). Each piece keeps its own identity and index.
   - (b) Real files, one per piece, as R-6.21 says now. This costs many files at scale.
   - (c) Real files grouped in region-style containers, a few files per layer.

   Choose (c) if you want each layer to be readable as files by outside tools without going through the server. The work continues on (a).
2. **R-4.1 as rewritten in 2.2.** Confirm that "can be given its own db" means a capability, and that grouping by project is right.
3. **Generated terrain (2.6).** Defaults taken and built (2.6, Status), open to the founder's change:
   - When is a chunk generated: on the first load ticket that reaches it (W-10.1), or ahead of players? Default: on first need.
   - If the generator fails or runs out of fuel (W-6.3), does the chunk stay ungenerated and retry later, or become void? Default: it stays ungenerated, and is tried again after 2 s, doubling to 60 s. Building there is refused until it is generated.
   - When an admin binds a new generator, may chunks nobody has edited be generated again? And how are seams between the old and new generators handled? Default: a new generator affects only chunks never generated, so there is no regeneration and no seam question yet.
   - Still open: is a chunk "edited" once anyone changes a cell? Regenerating could then spare edited chunks only. Storage would need one more bit for each chunk to know that. This matters only if regeneration is ever wanted.

## 5. Risks and verification

1. **A second writing connection crashes the process.** This is safety-relevant: a bug that opens a second write connection takes the whole server down, not only one request. Every store's code must route writes through its one writer thread, and a test must show that a write from another thread waits in the queue.
2. **Torn table entry.** Handled 2026-11-07 (world-store). A torn 8-byte entry can no longer cost more than its own chunk, or return the wrong data. At open, each entry is checked on its own (in range, whole record, CRC); a failing entry makes only its chunk unreadable, and a new save replaces it. Each record now carries its chunk's position (codec version 2), so an entry torn to point at another chunk's record is reported as corrupt rather than returning that chunk: the test found exactly this when two records had the same length and the CRC alone passed. Version 1 records still decode, without the position check. A crash between a record's data and its table entry leaves unreferenced sectors, which later writes reclaim. Tested by editing the file; a real power-loss test is not done. The check's cost, measured 2026-11-08 with `cargo run --release -p world-store --example region_open`: the first read from a full region of terrain-like chunks (a 12 MiB file) took 15 ms, and from a worst-case region of noisy, full chunks (80 MiB) 136 ms; later reads took 60 to 290 µs. It runs once per region open, on the I/O pool, so it never holds up a step.
3. **Crash recovery.** Verified for process kills 2026-11-07. `experiments/metaform-crash/crash.py` killed the server with SIGKILL 25 times in the middle of writes from 6 concurrent agents over 20 rounds. All 972 acknowledged writes survived, and no write was half visible (`metaform/verification/metaform-crash-2026-11-07.json`). The world verified the same way 2026-11-08: `topogee/crates/topogee-acceptance/examples/world_crash.rs` killed `topogee-server` with SIGKILL 25 times on a populated hills world (redstone, linked code blocks, a panel, a granted right). Of 2,444 announced changes, none announced more than 2.5 s before a kill was lost, no untouched terrain cell changed, and no chunk was reported damaged (`topogee/verification/world-crash-2026-11-08.json`). Two redstone gaps were found by these runs and closed: events waiting in the ready queue are now saved with the schedule and re-evaluated at start, and every program cell is re-evaluated when its chunk loads, since the flush writes region files one after another and a kill between them can leave neighbouring chunks from different flushes. 50 kills on 8a7128c: 0 problems (`topogee/verification/world-crash-2026-11-08-redstone.json`). Not verified: power loss, which depends on the disk honouring fsync.
4. **Many maps in one database.** Measured 2026-11-07 with `cargo run --release -p metaform-store --example many_maps`:
   - 5,000 elements in 100 maps: a cold map load (first read after reopen) took 6 to 12 ms.
   - 40,000 elements in 400 maps: a cold load took 18 to 28 ms.
   - Warm reads stayed about 5 µs. Writes ran at 194 to 217 per second, each in its own transaction.
   - The cold load finds a map's elements by `mapId`, a scan that grows with the whole database. A walk from the map's `ROOT` over `CONTAINS` took 5 to 9 ms on the same file, but Ladybug's variable-length paths have a depth bound, so a very deep address could be missed silently. The scan stays: it is correct at any depth, and each map loads once per process until it is closed.
   - One command's cost, measured 2026-11-07 with `examples/bulk_update`: a command writes one receiving element (the tool contract), so only its `wants` grow with it, at about 1 ms each. A receiver with 1 or 10 wants wrote in 18 to 21 ms, with 50 in 57 ms, with 200 in 201 ms. No batching is needed. In world.lbug the same per-row pattern did matter, and was batched: saving 10,000 scheduled events fell from 2.4 s to 0.24 to 0.38 s, and 600 block states from 2.1 s to 17 ms.
   - Measured at 1,000,000 elements, 2026-11-07, by bulk-loading the Element schema into one database: the scan by `mapId` took 45 to 58 ms for a 100-element map, and a primary-key lookup took under 3 ms. At 100,000 elements, the scan took 13 to 21 ms. A map loads once per process until it is closed, so the scan stays; a Map-to-element relationship is not needed yet.
5. **Open-database cap.** Measured 2026-11-07 with `cargo run --release -p metaform-store --example open_dbs -- <dir> 64`, one small project per database:
   - Each open database held about 28 to 33 MB of resident memory, nearly all of it fixed: the bare store took 37 MB, 16 open took 465 to 620 MB, and 64 open took 1.85 to 2.1 GB. The schema's relationship tables account for about two thirds of it; the 64 MB buffer pool is not the cause (16 MB measured the same).
   - Ladybug starts one worker thread per core for each database, 32 on the development machine, so 64 open databases ran about 2,400 threads. At 1,000,000 elements a map scan took 28 to 50 ms with 4 threads, 56 to 93 ms with 32, and 82 to 142 ms with 1. Small maps wrote and loaded as fast or faster with fewer threads (193 writes per second with 4 against 162 with 32).
   - Closing a database returns its memory: with a cap of 8, using 64 projects in turn stayed near 440 MB.
   - Taken as defaults: 4 worker threads per database (Metaform stores and `world.lbug`), and a cap of 16 open databases, which bounds memory near 0.5 GB. A deployment with more memory can raise the cap (`Store::open_with_limit`).
5a. **File growth from deleted rows.** Measured 2026-11-08 on lbug 0.22.3 (`cargo run --release -p world-graph --example schedule_growth`): Ladybug does not reuse the space of deleted node rows, even after a checkpoint. Deleting and re-creating 2,000 rows grew the file about 115 KiB each time, without end; updating the same rows in place, and rewriting string properties in place, did not grow it. The schedule was saved by delete and re-create every second while redstone was busy, which would have grown world.lbug by gigabytes a day; it now updates rows in place and marks rows past the current count unused, and the file stays flat. Emptied inventories and dropped items deleted rows too, about 60 bytes each; now an emptied inventory keeps its row as an empty map, and dropped items live in reusable slot rows (a free slot has id -1). With 200 items dropped and 200 taken away at every save, and an inventory emptied and refilled, 300 saves leave world.lbug flat at 3.3 MB. Rows in world.lbug are now deleted only when a block or a link is removed.
6. **Accounts and worlds on one machine.** Each store has its own owner. A process that owns several stores, such as the world server owning `world.lbug` and the region store, must still keep one writer per store.
7. **World autosave.** Decided by Xander for M4: chunks are authoritative in the ECS while loaded, and dirty chunks flush through `save_chunks` once a second, on unload and on shutdown. A crash can lose up to 1 s of edits. `save_chunks` uses two syncs per region per batch: 256 chunks in one region took 18 ms as one batch against 407 ms one at a time on the development machine.
