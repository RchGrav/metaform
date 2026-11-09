# Metaform in Rust: server design

**State:** draft, 2026-11-07, by Xander, the design reviewer. The founder has not reviewed it. Section 4 and the progress table reflect the build on Ladybug; section 3's mention of a log and file renames is superseded by `docs/designs/storage.md` 2.3.

This is the design for this project's Metaform server in Rust (`metaform/SPEC.md`, D-15 decided). It specifies how the parts fit. What each command does is already in `metaform/SPEC.md`; this document does not repeat it. Layers wait for the founder's unified layer approach, which replaces section 6 of the specification.

Every item is **Proposed** unless it cites a decided requirement.

## 1. Shape

One Rust workspace in `metaform/rust/` with two crates:

| Crate | Kind | Holds |
|---|---|---|
| `metaform-core` | library | The map model, address rules, command validation, the Ladybug store, and the write manager. No networking. A map is the unit: any element can own a child map, and a map can stand alone, such as an agent's private map (R-4.15). |
| `metaform` | binary | The instance server, the forwarder that each agent starts, and the CLI. |

**Why a library:** Metaform is also used inside the game (R-4.14, world spec W-1.1). The Rust world server links `metaform-core` directly, with no second process beside each world.

The Node server in `metaform/server/` is a test harness, not the design and never a source for it (founder: "this better not become the design we have one already"). The design is the founder's documentation set (`metaform/docs/documentation-set.md`) and `metaform/SPEC.md`.

## 2. Processes

```
agent ──stdio MCP──> metaform mcp <folder>   (forwarder, one per agent)
                          │  Unix socket, MCP frames
                          v
                     metaform serve --home <home>   (one per instance)
                          │  the only writer
                          v
                     <home>/  registry.json, settings.json, projects/...
```

**One server per instance (R-4.4, R-4.14).** An instance is one home: `--home`, or `METAFORM_HOME`, or `~/.metaform`. `metaform serve` takes an exclusive `flock` on `<home>/server.lock` and listens on `<home>/server.sock`. A second `serve` on the same home exits with a message naming the running server. Only the server takes the lock, so no client ever waits on a lock.

**Forwarders (R-4.5).** Each agent's harness starts `metaform mcp <folder>`. The forwarder connects to the instance's socket, sends one handshake line that names the project folder, then relays MCP messages both ways without reading them. It never opens a file under the home. If the socket is absent, it asks the launcher to start the server (`docs/designs/service-launcher.md`, SL-6.1) and retries for a bounded time.

**Who is calling (R-5.3).** The server reads the caller's user and process from the socket (`SO_PEERCRED`) and the project from the handshake. Agent identity replaces the process when the agents module exists (R-8.2).

**The CLI (R-5.14, R-5.17).** **Built 2026-11-07.** `metaform call [--home DIR] [--project DIR | --map NAME] '<json command>'` (or `-` to read the command from stdin) runs one command of the one tool from a single command line. It connects as a forwarder does: the same home default, launcher and handshake. Then it speaks MCP to the server (`tools/list`, then `tools/call`), so the server stays the only way to the data. It prints the tool's result text. Exit 0 on success, 1 on a refusal (the refusal JSON is printed), 2 on a usage or connection error. A CLI command is not an MCP tool (R-5.15). The `topogee metaform` branch will call it.

## 3. The write manager (R-4.7, R-4.13, R-5.8)

Each map has one writer task (R-4.15). It owns that map's state; nothing else changes it. Chained maps each have their own writer, so writing deep in a chain never blocks the map above it.

1. **Queue.** Each connection has its own queue into the project's writer. The writer takes one write from each non-empty queue in turn, so one agent's burst cannot starve another (R-4.7, fair queuing).
2. **Validate.** The command is checked against the tool's input schema, then applied to a copy of the current state. A refusal returns the fixed error code, the rule, and the remediation command (R-5.24). Nothing has changed (R-5.8).
3. **Commit.** The change is written to the map's Ladybug database in one transaction (R-4.1). Rust writes no files itself. Whether a separate effect log is kept beside it is Open (`SPEC.md` D-17).
5. **Publish.** The new state replaces the old one as a whole (`arc-swap`), the revision increments, and the change is announced (R-4.10, section 5).
6. **Acknowledge.** Only now does the caller get its result (R-4.7).

**Reads (R-4.7).** A read takes the current published state and never waits for the writer. It always sees one whole revision.

**Recovery (R-4.13).** On start, the server replays log entries newer than the files' revision.

**Naming (R-4.11, R-4.12).** The writer stores camelCase keys nested by segment. Conversion to and from the agents' snake_case and full addresses happens at the edge, in one module, with the refusals R-4.11 requires.

## 4. Storage (R-4.1)

Maps are partitions of a grouping LadybugDB database: the project's `project.lbug`, or the home's `maps/maps.lbug` (default, 2026-11-07; `docs/designs/storage.md`). Rust works through Ladybug and never writes map files itself. Settings and the project registry may be JSON. The layout under the home and the placement of chained maps are defaults in `docs/designs/storage.md`, sections 2.2 and 2.4. Ladybug allows one read-write process per database; the one server per home (R-4.4) is that process.

## 4a. The stored form and the agent form

This follows the founder's design in the documentation set (`metaform/docs/documentation-set.md`, sections 1.2, 3.1 and module 5), which `metaform/SPEC.md` cites for R-3.4, R-4.1 and R-6.15. It is the design, not a proposal.

**Storage is LadybugDB** (R-4.1; documentation set 1.2):

- The chassis database, `~/.metaform/metaform.lbug`, tracks the registered projects, their source paths and global settings. Settings and the project registry may also be JSON (founder, 2026-11-03).
- Each project's functional graph is in `~/.metaform/projects/<encoded-path-id>/project.lbug`. A project database never stores its own project name; provenance comes from `source.txt` and the chassis database.
- Rust works through Ladybug and never writes map files itself.

**The stored view is nested** (documentation set 5.1; R-4.12). The root `.` holds the registries (`intake`, `system`, `layers`) and root-level skills. Elements nest by address segment, and an element's properties sit at its own node:

```json
{"code": {"pipeline": {"ingest": {"network": {
  "technical_name": "network ingest pipeline", "name": "Packet Intake Engine",
  "role": "Definitive", "uri": "./src/network/pipeline.c",
  "wants": [{"code.buffer.ring.packet": {
      "why": "drain raw frames from the network interface card",
      "how": "holds descriptor pointers across contiguous memory segments",
      "intent": "receive"}}],
  "memory": [{"fact": "isolates receive descriptors from transmit completion queues"}],
  "sources": [{"uri": "./src/network/pipeline.c"}]}}}}}
```

**The agent view is flat** (documentation set 5.2; R-4.12, R-5.2). Agents never see the nested tree. They name elements by full dotted address, a read is a command with no verb, `{".": {}}` returns only the fields named in `intake`, `{".": {"layers": []}}` returns the layer definitions, and `{"orphaned": {}}` returns a bare array of single-key objects. Keys reach agents in snake_case and are stored in camelCase (R-4.11).

**Fields** (R-3.4, Decided): `technical_name`, `name`, `role`, `uri`, `status` and `wants`; a want holds `why`, `how` and `intent`. Roles are Definitive, Supportive, Notable and Divergent (documentation set 3.2). New code uses these names. The earlier names (`name_length`, `goal`, `function`, DE and SE) remain only in the existing Node store and the current contract file until they change.

**Changing:** the founder is replacing the root registries with a unified layer approach: every layer has an address in the `layer` namespace, and `wants`, invisible to intake, lands as `layer.wants` (founder, 2026-11-07). The stored view above changes where that approach reaches it, once the founder describes it in full.

**The database holds section 5.1's state** (the founder pointed to "5.1 Nested Storage View (Internal Database State)", 2026-11-07), **realized as a graph** ("its a graph db thats how its realized"). Every element is a node carrying its fields; nesting is a relationship from each segment to its children; each want is a relationship from receiver to provider carrying `why`, `how` and `intent`. Agents see only the flat view. Layers are added to this graph when the founder's unified layer approach is described. The Node store (`metaform/server/src/store.ts`) does not follow the founder's design: it stores one flat row per address with the earlier field names.

## 5. Announcements and focused delivery (R-4.10, R-5.30, R-5.32, R-5.33)

**Subscriptions.** A client opens `subscriptions/listen`. After each commit the server sends `notifications/resources/updated` for subscribed resources, and `notifications/resources/list_changed` where the client asked for it. Nothing polls.

**`goto`.** The server records the connection's position. The result carries the summary sheet R-5.30 describes, including the `skill://` URIs for that position (pull). If the client is subscribed, the server also announces those skills on its stream (push).

**Skills.** Skills are served as SEP-2640 skills. A skill generated for a ticket and a position is `"resources": "dynamic"`. Skills stay out of the startup listing.

**Tasks.** Intake and layer runs are MCP tasks with status pushed through `notifications/tasks`.

## 6. Conformance tests

Tests live in `metaform/rust/` and test the public interface only (CLAUDE.md). They use the shared fixtures, not copies:

- every request and refusal in `metaform/tool-examples.json`;
- the stored examples validated against `metaform/metaform.schema.json`;

Two tests decide the design: two clients writing to one project at once, both acknowledged, neither starved, the log in one order; and a server killed after the log sync and before the file rename, which recovers to the same state.

## 7. Build order

1. `metaform-core`: the map model, addresses, validation, and the commands `add`, `update`, `delete`, `orphaned` and reads, against the shared fixtures.
2. The write manager, the effect log and recovery.
3. `metaform serve` and `metaform mcp`: the socket, the lock, the forwarder, and MCP through `rmcp`. Verified 2026-11-07 in rmcp 3.9's source and by test: it negotiates MCP 2026-07-28 (`server/discover`), supports `subscriptions/listen` (`accepted_subscription_filter` and `listen`), and keeps `resources/subscribe` for clients older than 2026-07-28 (R-8.1).
4. `goto`, skills as resources, and push.
5. Tasks.
6. Start on demand through the launcher.
7. Map chaining (R-4.15, D-16): child maps, drilling down, and links between projects on the same mechanism.
8. Layers, once section 6 of the specification is rewritten for the unified layer approach.

## Progress

Updated 2026-11-07, late, by Xander. Checked against the code on main.

| Step | State | Where |
|---|---|---|
| 1. `metaform-core`: the map model, addresses, validation, commands, reads | Built | `crates/metaform-core`, 4 tests |
| 2. The write manager and recovery | Built on Ladybug: one fair writer per database, a Ladybug transaction is the commit point, no separate log (`docs/designs/storage.md` 2.3). Acknowledged writes survive SIGKILL. | `crates/metaform-store`, 5 tests |
| 3. `metaform serve` and `metaform mcp` | Built: one server per home, the stdio forwarder starts the server when none is running (D-RS1 default), one tool `project-map` over MCP 2026-07-28, at most 16 open databases; forwarders that start at the same moment share one server (exit status 3 marks the loser); a forwarder whose handshake a closing server drops connects or starts again for up to 5 s; a server restart does not end an agent's session: the forwarder connects again and replays `initialize` and open subscriptions (`src/relay.rs`) | `crates/metaform-server`, 5 tests (server and standalone maps) |
| 4. `goto`, skills as resources, push | `goto` built (R-5.30; its form is Proposed). Announcements built (R-4.10): each connection's map is one resource, `metaform://map/project/<id>/main` or `metaform://map/standalone/<name>`; reading it gives the root read; `subscriptions/listen` (2026-07-28) and `resources/subscribe` (older clients) get `notifications/resources/updated` after each commit, from `Store::watch`, with no thread and no polling. A client that disconnects while listening holds its session up to rmcp's 5 s drain before it closes. Skills as resources and their push (R-5.32) are not built; nothing yet produces skills. | `crates/metaform-server`, 2 tests (announcements) |
| Settings (R-4.8, Decided) | Built 2026-11-08: declared in code with defaults that are never stored; global values in `<home>/settings.json`, a project's in `projects/<id>/settings.json`; one lookup, project before global before default; the CLI's `metaform settings`, `set` and `unset` go through the server (an admin request on the socket, not an agent tool). First setting: `stores.max_open_databases`. | `crates/metaform-store/src/settings.rs`, `crates/metaform-server/src/admin.rs`, 2 tests |
| 5. Tasks (R-5.33, Proposed) | Not built. They come with intake and layer runs on the server. | |
| 6. Start on demand through the launcher | Built (SL-6.1): with the project's launcher installed, the forwarder starts the server as the user call `metaform-<12 hex of the home's path>` (`hold -d --name ... --restart on-failure:3 -- metaform serve --home <home>`); when that call exists it starts it again by name. Without the launcher it starts the server directly (D-RS1). A starting server waits up to 3 s for the home's lock, so a forwarder that arrives while the old server is closing still gets a server. On SIGTERM the server ends its sessions before it closes the store. | `crates/metaform-server/src/start.rs`, 1 test (stub launcher) |
| 7. Map chaining and private maps (R-4.15, Decided) | The store holds maps that belong to no project (`maps/maps.lbug`). An agent opens one with `metaform mcp --map <name>` (built). Chaining waits on the founder: it changes the tool contract (below). | |
| 8. Layers | Waits on the founder's unified layer approach. | |

The project's `.mcp.json` points at the Rust server since 2026-11-07 (`647ef20`, when the founder reloaded to get the MCP and the Node harness no longer connected): `metaform/rust/target/release/metaform mcp --home ${HOME}/.metaform-rust --project .`. The new home leaves `~/.metaform`, the Node harness's data, untouched.

### Proposal for the founder: chaining in the one tool (R-4.15, D-16)

Storage is a default already (`docs/designs/storage.md` 2.2: a `Map` node reached by `CHAINS`). What an agent types is a contract change, so it needs the founder's decision.

- **Create:** `{"chain": "<address>"}` gives that element its own map. It is refused if the element already has one.
- **See:** `goto` on a chained element names the chained map in its summary sheet.
- **Drill down:** an address crosses into a chained map with `/`: `code.renderer/shader.pipeline` is `shader.pipeline` inside the map chained at `code.renderer`. Every command names its target in full, so no command depends on where the agent stood before. The noun-phrase rules apply inside each map.
- **Alternative:** `goto` into a chained element moves the agent into that map, and later commands act there. That is shorter to type, but a write's target then depends on hidden position, and a mistake writes to the wrong map.

Recommended: the explicit `/` form.

## 8. Open

| ID | Question | Recommendation |
|---|---|---|
| D-RS1 | The forwarder's fallback when the launcher is not installed | **Answered 2026-11-07 (Jorge, launcher step 5):** start `metaform serve` directly, detached in its own process group, with its output appended to `<home>/server.log`. The launcher is used whenever it is found (`METAFORM_LAUNCHER`, or this project's `hold` on `PATH`). No record is kept for a direct start; the launcher's record is the only one. |
