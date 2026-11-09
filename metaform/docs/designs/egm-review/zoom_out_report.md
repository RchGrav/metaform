# Zoom-out review: map server design (Stage 5)

**Target:** `docs/designs/metaform-server-design.md`, lines 1–847 (full file)
**Reviewer:** egm-zoom-out, with the zoom-out standard
**Background read:** `docs/designs/metaform-server.md` and `docs/designs/metaform-server-round2.md`. The reviewer also opened `mcp-server/src/*`, `mcp-server/test/metaform.test.ts`, `experiments/map-viewer/server.mjs`, `DECISIONS.md`, `CLAUDE.md`, parts of `TOPOGEE-SPEC.md`, `owner-skills-example.json` and `mcp-tools.proposed.json`.

**Context sufficiency:** passes. The objective, the problem and the owner's positions are clear.

**Verdict:** changes requested. There is 1 Blocker, 9 Majors and 6 Nits.

The design follows the owner's positions closely. Its deferrals are sound YAGNI: no HTTP for agents, no search index, no request ids, the inbox later. Most findings are about one of three things:

- **Layers without a write path:** layer machinery is built, but nothing creates or writes a layer.
- **Wrong placement:** where the case conversion and the WebTransport edge sit.
- **Missing interfaces:** how the viewer gets its starting state, and how the CLI talks to the server.

---

## 🔴 Blocker

### B1. Layer storage and layer reads are built, but nothing writes a layer, and existing element arrays have no stated home

**Lines:** 160–167 (CUJ 3), 264–276, 313–333, 566–567, 684–687, 748–750, 760–764; Open Questions 134–135.

**Problem:**

- The plan builds all of these:
  - a `layers/<layer>/<address>.json` file per layer per address;
  - an R-6.6 walk to find which layers are active at an address;
  - a layer read, plus a read that lists the layer definitions;
  - skill frontmatter in the address read;
  - search over active layers.
- No command registers a layer or writes layer data. Step 1's contract changes only add `layers` to reads and add `search`.
- Yet CUJ 3 and a Step 2 test (line 685) both rely on "a command that registers a layer and writes its first data". That command does not exist in the contract or the plan.
- The contract already accepts arrays on elements. `owner-skills-example.json:3` puts `skills: [...]` on `code`. Line 274 says "every other layer lives under `layers/`", but never says whether `add {"code": {"skills": [...]}}` is stored in `map.json` or in `layers/skills/code.json`.
- The walk depends on R-6.9 (Proposed) and D-13 (Open).
- Skills are listed as an open question at line 134: are they layers, or do they stay in `system`? Lines 318–319 nonetheless assume skills are a layer.

**Why it matters:** Step 2 cannot define the files until it is known where data the contract accepts today is stored. The effect log's main justification (Alternative G: commands that change several files) also depends on that answer.

**Simplest fix:** pick one.

- **(a)** Define the layer write path. That means how array fields route to layer files, and how registration works under R-6.15.
- **(b)** Scope the first version to what can be written today. Everything the contract accepts stays in `map.json`. The address read names the arrays present at the address. A layer read returns the named array. The `layers/` folder, the walk and the layer-definitions read wait until a layer write path is designed.

Option (b) fits R-5.20 ("logic added only to fix an observed issue") and R-5.18 ("too much ceremony").

---

## 🟡 Major

### M1. The effect log has more machinery than the first version needs

**Lines:** 266, 279, 302–306, 657–665.

**Problem:**

- The plan adds log segments, an archive folder, and a sequence number written into every file, including layer files that may hold outside formats such as SEP-2640.
- Every write saves its files right after the log sync. So at most the last entry can be missing from the files after a crash.
- Effects are stored as "sets or removes", which can be applied twice safely. Replaying the tail of the log is therefore safe without a sequence number in each file. One checkpoint per project, or simply replaying the last entry, is enough.
- Segments do not save disk space either, because archived segments are kept, not deleted.

**Why it matters:** this is complexity added before any bottleneck is proven.

**Simplest fix:**

- Keep one log file per project, plus one checkpoint.
- Do not wrap layer files in a sequence-number envelope.
- Add segments only when the log size is measured to be a problem.
- If B1 is resolved as (b), every project command changes only `map.json`. The log is then needed only for announcements and history, which is Alternative G's simpler variant.

### M2. The case conversion is placed at the MCP boundary, so it must recognise addresses inside values and text

**Lines:** 286–299, 311, 349–352, 606–614, 627–631, 715–716.

**Problem:**

- Converting after validation and before the queue means the effect code and the stored state are in camelCase, while the checks run in snake_case. The commands module then works in two forms. Today `commands.ts:26` reads `name_length` directly.
- On the way out, `toAgent` has to find addresses inside remediation payloads, inside `delete.wants`, and inside search result lines such as `Found: "code.bar.foo" in "baz" layer`. That last one is an address inside an English sentence.
- `toAgent` also has to skip `name`, URIs and SEP-2640 entries.

**Why it matters:** this is a local workaround where a structural fix is available.

**Simplest fix:**

- Put the conversion where the store reads and writes its files: `map.json`, layer files and file names.
- The store knows exactly which strings are keys and address segments, so it needs no list of exceptions.
- Everything above the store then works in the agent's form: commands, reads, search, remediations, the log and announcements.
- This is still "the layer between the agents and the data" that position 16 names.

### M3. WebTransport sits inside the process that is the only writer

**Lines:** 60–61, 335–341, 495–498, 733, 772–786.

**Problem:**

- `announce.ts` puts these in the map server: an HTTP/3 and TLS stack, a self-signed certificate that must be renewed at least every 14 days, and a library still to be chosen.
- Node has no built-in WebTransport server. The likely libraries bring a native QUIC build. Problem 5 rejects Ladybug for needing exactly that: a native binary for each platform.

**Why it matters:**

- A certificate or library fault in the process every agent depends on is a large risk for one local subscriber.
- The future chassis hook would need HTTP/3 just to hear about changes.

**Simplest fix:**

- The map server offers announcements as a subscription on its existing Unix socket.
- The viewer process, which already serves the page and passes it the certificate hash, terminates WebTransport for the browser.
- This keeps `DECISIONS.md:15` (WebTransport, no WebSocket fallback) and keeps the writer simple.

### M4. The viewer has no way to get its starting state

**Lines:** 171–174, 726–727, 782–793.

**Problem:**

- The viewer applies changes as they arrive and fetches entries it missed.
- The root read returns only the index (position 13).
- `--database --export` is removed.
- Nothing says how a newly opened viewer gets the full map before the first announcement. Round 2's M7 raised this ("needs a separate full view").

**Simplest fix:** state one of these.

- On subscribe, the server sends a full snapshot in the agent's form, tagged with its sequence number.
- Or the viewer calls `--export` through the server.

### M5. How the CLI talks to the server is a second, unstated interface

**Lines:** 236–238, 370–371, 700–701, 719–727.

**Problem:**

- The handshake binds one project to a connection, and the connection then speaks MCP with one tool.
- These CLI commands are neither project-scoped nor in the tool: `register`, `--projects`, `--settings`, `--set`, `--import`, `--export`, `server status|stop|restart`. Line 701 says "Handles `status` and `stop` requests from the CLI" without saying how.
- R-5.14 (proposed by the owner, not yet confirmed) asks that every tool command be usable from the CLI. The plan's CLI has no path to `project-map` itself.

**Simplest fix:**

- Name a small set of admin requests on the socket, chosen by the handshake.
- Make the CLI a one-shot forwarder for tool commands, with one `tools/call` per run. This reuses the MCP path instead of adding a separate command set.

### M6. Removing a "stale" socket can remove a live one, which breaks the one-writer guarantee

**Lines:** 228–235, 694–696.

**Problem:**

- Line 232 says binding the socket decides which server runs.
- Step 4 lets a starting server delete the socket if the process id in the lock file no longer exists.
- Suppose two starters both read a stale lock. One deletes the socket and binds. The second then deletes that live socket and binds its own. Two servers now write the same files.

**Simplest fix:**

- Decide staleness by trying to connect to the socket. A refused connection means it is stale.
- The process id then becomes information only, and the lock file adds nothing to the guard.

### M7. The version check's remedy does not resolve the usual mismatch

**Lines:** 250–251, 698–700, 709–710.

**Problem:**

- On `VERSION_MISMATCH` the forwarder exits "so the harness starts the current one". The harness restarts the same forwarder from the same checkout, with the same version.
- The usual case is an old server running after a pull of newer code. The fix for that is to restart the server.
- Separately, `createServer` calls `loadContract()`, which reads `mcp-tools.proposed.json` from disk (`server.ts:8`, `contract.ts:14-24`). The plan creates a server for each connection (line 699). A long-running server would therefore pick up an edited contract while running old code: the very skew the handshake is meant to catch.

**Simplest fix:**

- On a mismatch, give `server restart` as the remediation. Or, when the forwarder is newer, have it ask the old server to stop and then auto-start the current one.
- Load the contract once, when the server starts.

### M8. The socket, the lock and the files must follow `METAFORM_HOME`

**Lines:** 11–12, 203, 211, 228–229, 694, 843.

**Problem:**

- The design names `~/.metaform/server.sock` and `server.lock` throughout.
- The tests set `METAFORM_HOME` (`test/metaform.test.ts:23`).
- The "server and routing" tests kill the server and start new ones.
- If the endpoint does not follow `homePath()`, test runs and other worktrees will kill or write to the owner's live server. Round 2's B1 raised this.

**Simplest fix:** state that every path the server uses comes from `homePath()`.

### M9. Step 6 and several spec citations describe work that is already done

**Lines:** 50–53, 428–430, 799–820.

**Problem:**

- Commit `1f9c262` already did Step 6:
  - `DECISIONS.md:12` and `AGENTS.md:7-8` no longer say "LadybugDB is selected";
  - `TOPOGEE-SPEC.md` already has section 4.2 (R-4.4 to R-4.13), the new R-5.1, R-5.10 and R-5.11, and the three Proposed refusal codes.
- Items 24 and 25 would edit text the owner has already approved, and line 817 quotes text that no longer exists.
- Problem 3 (line 51) and Alternative E (line 430) cite R-5.10 and R-5.11 as today's behaviour, but those lines now state the new behaviour.

**Simplest fix:** mark Step 6 done, or reduce it to a check, and cite the replaced wording as history.

---

## 🟢 Nit

### N1. Open Questions that the plan has already answered

**Lines:** 132–135, against 318–319 and 333.

The search scope question is answered at 333. The question of whether skills are layers is assumed answered at 318–319. Either move these out of Open Questions or mark the plan's answer as provisional.

### N2. Build-order dependencies

**Lines:** 637, 677–682.

- Step 2's `tree.ts` change (import and export "through the server") needs the server from Step 3.
- Step 1's tests run through the stdio entry in `main.ts`, which Step 3 replaces.

State the test harness used in Steps 1 and 2.

### N3. Name the code being reused

**Lines:** 653–655, 755.

- `tree.ts` `flatten` and `nest` already convert between the nested document and elements. They are the natural reader and writer for the nested `map.json` (R-4.12).
- `store.ts` `prefixes()` already lists the trunk-to-leaf prefixes of an address, which search and the R-6.6 walk need.

### N4. Nearest-parent routing is an agent's choice with no observed issue behind it

**Lines:** 243–245.

R-5.20 asks for an observed issue first. It also has a cost: a forwarder in an unregistered nested repository (`/work/game/vendor/lib`) would quietly route to `/work/game`. Exact-path matching (`home.ts:94-97`) plus the `PROJECT_NOT_REGISTERED` remediation is simpler.

### N5. Pinned line numbers will go stale

**Lines:** 589, 597, 602, 826.

Edits in Step 1 will shift these targets. Name the test or the block instead.

### N6. The detached server's output has no stated destination

**Lines:** 230–231, 707.

Round 2's M4 raised this. A short line naming a log file under the home is enough.
