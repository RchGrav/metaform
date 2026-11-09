# Round 2 review

> **Storage superseded (2026-11-07).** This document designs JSON file storage (`map.json`, layer files, a log). The founder never decided JSON for the map. Maps live in LadybugDB: `metaform.lbug` for the chassis and one `project.lbug` per project (`metaform/SPEC.md` R-4.1; the founder's documentation set, section 1.2). Read its storage sections as history; its other positions stand only where the specification still holds them.


**Note on references.** `concepts_brief.md` in this report is the brief as it stood during the review. It is now [`metaform-server.md`](metaform-server.md). Its line numbers have changed since, and positions 18–23 were added after this review.

**Subject:** the revised concept. A live server per machine keeps every project's map, the settings and the project registry as JSON with a command log. It is the sink for every agent's MCP server. It announces changes, serves the `project-map` tool (address read, root read, deep search), indexes layer files that can be added from outside, and converts between the agents' snake_case and the store's camelCase. The chassis hooks it when present.

**Ground rules.** The method and the founder's positions 1 to 17 (`concepts_brief.md:286-303`) are not under review (`docs/pushback.md:201-209`). Every finding asks whether this build plan can carry them. A finding marked "reopens round 1" names the round-1 item and says what is new.

**How to read the findings.**
- **Observed:** what a reviewer saw at the cited line. The synthesizer spot-checked `home.ts:94-109`, `metaform/SPEC.md:197-223`, `AGENTS.md:9` and `DECISIONS.md:15`. The other references are as the reviewers reported them.
- **Inferred:** the reviewers' reading.
- **Severity:** where lenses disagreed, the higher one is used and the difference is noted.

## Reviewer status

| Reviewer | Persona | Status |
| --- | --- | --- |
| `egm-design` | `agents/design_critic.md` | completed |
| `egm-codebase-details` | `agents/codebase_details.md` | completed |
| `egm-zoom-out` | `agents/zoom_out.md` | completed |
| `egm-comprehension` | `agents/comprehension.md` | completed |
| `egm-implementation-readiness` | `agents/implementation_readiness.md` | completed |
| `egm-structural` | `agents/structural.md` | completed |

Severity breakdown: 6 Blockers, 21 Majors, 5 Nits.

## Analysis

### 🔴 B1. Nothing says how the server starts, how only one copy runs, or how a forwarder finds it
*Lenses: design, zoom-out, implementation-readiness, codebase-details, structural, comprehension*
- **Observed:**
  - Today each harness starts its own process for one folder (`metaform/server/src/main.ts:78-81`).
  - The only guard against a second writer today is Ladybug's file lock (`store.ts:7-8`, `home.ts:17-18`). Moving the registry and settings to JSON (`concepts_brief.md:313`) removes that guard.
  - The CLI has no start, stop or status command (`main.ts:1-10`).
  - `homePath()` honours `METAFORM_HOME` (`home.ts:58-60`; R-4.1, `metaform/SPEC.md:172`).
  - Each test run sets its own temporary home (`test/metaform.test.ts:22-23`) and starts its own stdio server (`:43`).
  - Worktrees are a kept rule (`DECISIONS.md:109`), so one machine holds several checkouts.
  - None of the files the reviewers read names who starts the server, its endpoint, a single-instance guard, or what a forwarder does while the server is down.
- **Inferred:**
  - Two forwarders starting together could each start a server. Both would then write the same JSON files, and no error would show. Position 5 does not cover this: it is about agents, and this is about server processes. One harness reconnecting is enough to cause it (design).
  - "Per machine" conflicts with the per-user home and with the tests. If there is one server per machine, test runs and other worktrees reach the founder's live server and data. If there is one server per home, R-4.1 and the tests keep working (zoom-out, structural, readiness).
  - A forwarder must not queue writes while the server is down. R-4.7 (Proposed) acknowledges a write only after it commits (`metaform/SPEC.md:203`).
  - With one process doing all registration, the round-1 M6 start-up race on `metaform.lbug` goes away, and so does the folder-numbering race in `newFolder` (`home.ts:111-116`).
- **Blocks:** everything that runs on the server, the test harness, and the first step of any build order.

### 🔴 B2. With one server for all projects, a call has no route to its project
*Lenses: design, zoom-out, implementation-readiness, codebase-details, structural, comprehension*
- **Observed:**
  - R-5.2 and R-5.3 are Decided: no command selects a project. Until identity exists, "the server starts for one project folder. That folder is not part of the form" (`metaform/SPEC.md:219-223`).
  - D-8, identity, is Open (`:454`).
  - R-8.2 (Proposed): the server keeps no session state (`:420-422`).
  - Today the folder comes from the command line (`main.ts:78-79`, `:88`, `:96`).
  - `Home.project` creates a project for any folder it is given (`home.ts:100-109`).
  - `find` matches only the exact real path (`home.ts:94-97`), so an agent started in `repo/src` does not match a project registered at `repo`.
  - In the installed SDK (2.4.0), `serveStdio` gives its factory no request information, while `createMcpHandler` passes `requestInfo` for HTTP (`node_modules/@modelcontextprotocol/server/dist/createMcpHandler-DzlXH0KL.d.mts:220-223`).
- **Inferred:**
  - A server for all projects cannot "start for one project folder". R-5.3's interim rule loses its meaning, and no position replaces it.
  - A stdio forwarder knows its folder and can send it outside the form. An agent on HTTP has no folder argument and no identity, so the project has to come from the URL, a header or a `_meta` field.
  - Binding the project to a connection may count as session state under R-8.2.
  - Because of `home.ts:100-109`, any caller that supplies a path would register a project there, including a subfolder or the home directory. Creating a project needs its own rule.
- **Blocks:** every tool call. Positions 12, 13 and 17 are all scoped to one project. Also blocks R-4.9 and the HTTP transport.

### 🔴 B3. No stated rule makes the server the only writer under the home, and search freshness depends on that rule
*Lenses: design, zoom-out, implementation-readiness, codebase-details, structural, comprehension*
- **Observed:**
  - R-4.5 (Decided) carries today's one-writer rule: "No other process opens a database. The MCP server, the CLI, the web interface and every module reach the data through the chassis" (`metaform/SPEC.md:199`).
  - Positions 9, 10 and 14 move the store to a server that "is not the chassis" (`concepts_brief.md:295-300`).
  - Position 10: layers "must be able to be added externally" (`:296`).
  - Position 17: search reads all content (`:303`).
  - R-6.15 (Decided): a layer is registered "before data is written to it" (`metaform/SPEC.md:371`). R-5.24 has `LAYER_NOT_REGISTERED` (`:267`). R-6.11 says only Systems change layers (`:349`).
  - `--import`, `--set` and `--export` open the stores directly (`main.ts:60-76`, `:83-86`). R-5.14 (Proposed by the founder) makes every tool usable through the CLI (`metaform/SPEC.md:279`).
  - `DECISIONS.md:15` and `AGENTS.md:22` exclude recurring polling.
  - No code watches files. The only change detection in the repository is the viewer's 1.5-second copy-and-export loop (`experiments/map-viewer/server.mjs:7-13`).
- **Inferred:**
  - When R-4.4 and R-4.5 are replaced, the one-writer rule goes with them unless it is restated for the server (structural).
  - "Added externally" can be read two ways:
    - **(a) Outside parts write layer files directly.**
      - Those writes skip input validation, including position 16's round-trip check, layer registration, the command log and the announcement.
      - The server's search and path enumeration go stale unless it watches files. Watching is unreliable on some file systems; the reviewer notes that WSL2's `/mnt/*` drives do not deliver Linux file notifications. Scanning instead comes close to the excluded polling.
    - **(b) Outside parts ask the server to register and write.**
      - The server stays the only writer.
      - Search can read at call time or update an index on commit.
      - Recovery covers layer files.
  - A CLI `--set` or `--import` while the server runs would write behind the server's in-memory copy, and the server's next write would overwrite it. A migration run while the server runs is a second writer in the same way.
- **Blocks:** keeping search current (position 17), R-6.15 and R-5.24 for outside layers, crash recovery, the content of the hook (still-open), and R-5.14.

### 🔴 B4. Where want records live, and so what an address read returns, can be built two ways
*Lenses: implementation-readiness, comprehension, codebase-details, structural, design*
- **Observed:**
  - Position 13 says "no layers not even the wants layer" (`concepts_brief.md:299`). Position 7 says a layer is a separate file (`:293`). Position 12 returns layers "by existence only" (`:298`).
  - R-6.15 lists `wants` under `intake`, not `layers` (`metaform/SPEC.md:369`, `:375`). R-6.7: "The intake layer is the metaform itself. It is not selectable" (`:329`). `DECISIONS.md:9` calls `wants[]` "the functional knowledge layer".
  - Today want records are a relation table (`store.ts:35`).
  - Every other field that is not a column, arrays included, is stored whole as one JSON string in a `layers` column (`store.ts:28-35`, `:176-186`). That is where `skills[]`, `memories[]`, `tasks[]` and `inbox[]` (`DECISIONS.md:45`) live today.
  - The protected schema keeps array layers inside the element (`metaform/metaform.schema.json:222-226`). `merged` grows arrays in place (`commands.ts:47-54`).
- **Inferred:** two readings fit the text.
  - **Reading A:** want records stay in the map file. The address read returns this element's own `why`, `how` and `intent`.
  - **Reading B:** want records are a layer file. The address read returns only the fact that a wants layer exists, plus the connected addresses. An agent at an address then cannot see why its own wants exist without a command nobody has stated.
  - The same question applies to the existing in-element arrays: stay in the element, or move to layer files?
  - This is separate from D-4. D-4 is the shape of `wants`; this is where they are stored.
- **Blocks:** the map file format, the address read and its tests, where search reports a match in `why` (`in "wants" layer` or not), and migration of the relation table and the `layers` column.

### 🔴 B5. After position 12, no stated command returns a layer's content
*Lenses: comprehension, zoom-out, structural*
- **Observed:**
  - Position 12 returns layer names only (`concepts_brief.md:298`). Position 13 returns no layers (`:299`). Position 17 returns locations, "not the matched content" (`:303`).
  - These lines are still Decided:
    - R-5.21: other layers come back "only when the read names them" (`metaform/SPEC.md:257`).
    - R-5.22: `{".": {"layers": []}}` returns the layer definitions (`:259`).
    - R-6.14: the registries limit what a dump returns (`:363`).
    - R-6.20: a dump renders a template report (`:398`).
  - The contract allows only an empty object as a read's value (`metaform/mcp-tools.proposed.json:97-99`), so R-5.22's read option is refused today.
  - Open question 9 asks only about a skill's body (`concepts_brief.md:321`).
- **Inferred:**
  - If R-5.21 and R-5.22 hold, a read that names a layer returns its content, and position 12 describes only the default read.
  - If they do not hold, nothing reads inbox messages, `sources`, tickets, `features` (R-6.19) or outside layers.
  - The gap is wider than open question 9.
- **Blocks:** every use of layer content by an agent, inbox delivery (position 7), and R-6.20.

### 🔴 B6. More Decided lines and founder boundaries conflict with the positions than the brief lists, and the spec has no place for the server
*Lenses: zoom-out, structural, comprehension, design*

Reopens round-1 B1. Position 14 settles the direction, so B1 is now a drafting gap, not an open choice. What is new is the list below, which round-1 B1 and open question 13 do not cover.
- **Observed:**
  - **Store and process:**
    - R-4.4 and R-4.5 (Decided, `metaform/SPEC.md:197-201`): the chassis "holds the only connections", and "A query across projects runs in the chassis". Position 14's server, which is not the chassis, tracks all projects.
    - R-4.7 (Proposed, `:203`) puts the write queue in the chassis.
    - R-2.6 (Proposed, `:65-69`) puts the store, events and settings in the chassis.
    - R-4.6 still names `mcp-server/` a prototype, decided "by R-1.1 and R-4.4" (`:207-209`).
  - **Settings:** R-4.8 (Decided, `:181-183`) puts project overrides in the project database. Open question 5 moves settings to JSON (`concepts_brief.md:313`) but does not say where an override lives.
  - **Reads:**
    - R-5.21, R-5.22, R-6.14 and R-6.20 (see B5).
    - R-5.23 (Decided, `:263`): `orphaned` maps each address "to its values". Position 13 allows detail only from reading an actual address.
    - R-5.1 (Decided, `:215`) lists the commands without `search`, and fixes "one MCP tool".
    - `TOPOGEE.md:35` puts the content of `sources` and the ticket into the localized context. Position 12 gives names only.
  - **Transport:**
    - R-8.1 (`:418`) says the server uses `serveStdio`. Its status line (`:422`) follows R-8.2 and may not cover R-8.1.
    - The concept adds MCP's HTTP transport. Section 8 has no requirement for it.
  - **Chassis and modules:**
    - R-2.3 (Decided, `:55`): "The system has a chassis and modules".
    - R-2.6 makes "The MCP server and the form" a base module of the chassis (`:68`).
    - R-2.7 (Decided, `:73-81`) defines the module contract against the chassis only.
    - `DECISIONS.md:107`: "New features land as modules that use services exposed by the chassis".
    - Section 11 lists "Chassis, modules, settings" as outside the document (`:472`), yet sections 2 and 4 hold requirements on them.
  - **Founder boundaries:** `AGENTS.md:7` and `DECISIONS.md:12` still say "LadybugDB is selected". `AGENTS.md:8` says a standalone MCP deployment "uses the same authoritative database". The zoom-out lens reads `AGENTS.md:8` as possibly already fitting position 14.
  - **Rule:** the spec forbids building a Proposed or Open item as Decided (`metaform/SPEC.md:13`, `:18`).
- **Inferred:**
  - An implementer of the server breaks R-4.4 and R-4.5 on the first commit, and R-5.21 and R-5.22 on the first read.
  - With no chassis present, nothing says which modules exist or what contract they follow on the server side.
  - The spec has no section for the server's start-up, registry, log, announcements, routing, forwarders or version. It has no home for the conversion, layer files, search or the HTTP transport either.
- **Blocks:** the store, the reads, the announcements, and building from the spec under R-1.1.

### 🟡 M1. The command log has no stated role, so neither R-5.8 nor crash recovery has a mechanism
*Lenses: design, zoom-out, implementation-readiness, codebase-details, structural, comprehension*

Reopens round-1 M1 and M13. Round-1 M1 assumed a single map file. Under position 7, one command can now change several files.
- **Observed:**
  - R-5.8, "A failed command changes nothing" (`metaform/SPEC.md:237`), rests on Ladybug `BEGIN/COMMIT/ROLLBACK` (`store.ts:123-139`, `commands.ts:159`).
  - `apply` logs nothing (`commands.ts:153-165`).
  - Restart durability is tested only on Ladybug (`test/metaform.test.ts:90-104`).
  - R-6.15 needs the root `layers` dictionary written before layer data (`metaform/SPEC.md:371`). Under position 7, that data is in another file.
  - `add` appends to arrays (`commands.ts:46-54`), so applying a command twice doubles them.
  - The only definition of the log is an agent's proposal (`concepts_brief.md:216`, `:282`).
  - Position 7 writes one "message that it was read and by whom" per read (`concepts_brief.md:84`).
- **Inferred:**
  - Several operations change more than one file: registering a layer and writing its first data, or deleting an address that has an inbox file. Renaming a temporary file is atomic for one file only, so a crash between two renames leaves a partial change.
  - The plan has to state:
    - whether the log is the record of truth, written first and replayed at start-up, or a history written after the commit;
    - the order of writes and fsyncs;
    - a sequence number on each entry, and in each snapshot the last sequence it contains, so replay does not apply an entry twice;
    - whether failed commands are logged;
    - whether the log holds the command or its effect. An effect replays the same way under a later contract; a command may stop validating after a rename such as R-3.4 (codebase-details);
    - which form the log holds: the agent's snake_case or the stored camelCase;
    - one log per project or one per machine, and how it is compacted;
    - whether the inbox read record is a log entry or layer data;
    - what start-up does with a file that fails to parse or validate.
  - Only the write-first variant can repair a crash between file writes. The history-only variant has fewer parts, and a crash there loses at most one log entry, not data (zoom-out, readiness).
- **Blocks:** R-5.8 on files, crash recovery, attribution under `DECISIONS.md:21`, and the inbox read record.

### 🟡 M2. A retried `add` doubles data once calls pass through forwarders
*Lens: design*
- **Observed:** `add` appends to arrays (`commands.ts:47-53`; R-5.5, `metaform/SPEC.md:229`).
- **Inferred:** with forwarders and a server that can restart, a call can commit and then lose its reply. If the forwarder or the agent retries, the array entries are written twice. This is separate from replay in M1. It needs a request id that the caller supplies, and a repeated id should return the first result.
- **Blocks:** safe reconnection through forwarders and HTTP.

### 🟡 M3. One failure in one project stops every project
*Lenses: design, codebase-details*
- **Observed:**
  - `apply` rethrows any error that is not a `CommandError` (`commands.ts:161`). `tools/call` does not catch it (`server.ts:16-22`).
  - There is one Store with one queue per process (`store.ts:95-96`).
  - Opening a store creates its tables (`store.ts:105-110`).
- **Inferred:**
  - Today a thrown error ends one agent's process. In a shared server it ends service for every project and agent.
  - A map or layer file that fails to parse at load does the same.
  - The server needs error isolation for each request and each project, a write queue per project, and a "failed to load" state for a project.
- **Blocks:** operating the server described in position 14.

### 🟡 M4. Running the server day to day is not specified
*Lenses: implementation-readiness, codebase-details, structural*
- **Observed:**
  - The CLI has only `--projects` and `--settings` for inspection (`main.ts:89-90`). It has no stop, restart or status command (`main.ts:1-10`).
  - `fail()` is the only error output (`main.ts:35-38`).
  - `AGENTS.md:22` asks that the operator can see each agent's context usage and tool surface.
  - The SDK exports `TRACEPARENT_META_KEY` and `CLIENT_INFO_META_KEY` (`index.d.mts:810`).
- **Inferred:**
  - **Not defined:**
    - where the server's output goes once it is detached from a terminal;
    - how to stop, restart or check it;
    - what a forwarder does when the server restarts in the middle of a call;
    - whether all projects load at start or on first call.
  - **To trace a bad change, each log entry needs:**
    - project, sequence number and time;
    - connection, plus the forwarder's process id and folder, self-reported until D-8;
    - client info and trace parent;
    - the command;
    - status and R-5.24 code;
    - touched addresses;
    - duration.
  - **A status command needs to show:**
    - loaded projects and failed loads;
    - open connections;
    - the last sequence number for each project.
- **Blocks:** debugging and operating the shared server.

### 🟡 M5. Version skew between forwarders, the server and the files is not handled
*Lenses: design, zoom-out, implementation-readiness, codebase-details, structural, comprehension*
- **Observed:**
  - The contract is read once at start from the repository root, relative to the source file (`contract.ts:5-6`, `:14-24`), and served from that copy (`server.ts:14`).
  - The server reports `version: '0.0.0'` (`server.ts:10`, `package.json:3`). It lists two protocol versions (`server.ts:11`).
  - Tests read the tool name and schema from disk (`test/metaform.test.ts:16`, `:45`, `:60-61`).
  - `serveStdio` pins one server instance per connection (`stdio.d.mts:47-50`).
- **Inferred:**
  - A long-running server keeps the contract of the checkout it started from. Agents and tests in other worktrees see that contract, not their own. The test at `:61` would fail against a server that started before a contract change.
  - If a forwarder keeps any part of the tool schema or the conversion rules, it drifts from the server after an upgrade.
  - The JSON files, layer files and log entries carry no format version. A newer server cannot tell old data from new, and neither can an outside layer writer under reading (a) of B3.
  - The forwarder-to-server link needs its own version check and a stated action on a mismatch.
- **Blocks:** upgrades, the rename to `project-map`, and development beside a live server.

### 🟡 M6. Transports: what the installed SDK supports, and what an HTTP endpoint without identity exposes
*Lenses: codebase-details, design, zoom-out, implementation-readiness, structural*
- **Observed:**
  - `@modelcontextprotocol/server` 2.4.0 (`package.json:13`) has these pieces:
    - `serveStdio` takes a `transport` option, and its documentation names a `StdioServerTransport` over a Unix socket or TCP stream (`stdio.d.mts:22-30`, `:90`).
    - `createMcpHandler` (HTTP, a factory per request, an event bus with `toolsChanged`) is exported (`createMcpHandler-DzlXH0KL.d.mts:144-189`, `:254-359`).
    - Localhost Host and Origin checks are exported (`index.d.mts:810`).
  - Mounting on `node:http` needs `@modelcontextprotocol/node` (`createMcpHandler-DzlXH0KL.d.mts:333-334`). That package is not in `package.json:10-15`.
  - The code uses `connect(new StdioServerTransport())` (`main.ts:80`), but R-8.1 says `serveStdio` (`metaform/SPEC.md:418`).
  - D-8 is Open, and R-6.11 "cannot be enforced until agent identity exists" (`metaform/SPEC.md:349-351`).
  - `DECISIONS.md:21` requires multi-user access. The viewer binds `127.0.0.1` (`server.mjs:16`).
- **Inferred:**
  - A forwarder can be a byte pipe from stdin and stdout to a socket. It then holds no MCP code, and the agent and the server negotiate the protocol directly.
  - HTTP needs a new dependency or a small adapter. Either one goes to the founder (`AGENTS.md:18`).
  - **Exposure:** an HTTP endpoint that writes any project with no identity can be reached by any local process. A browser page can reach it through DNS rebinding. On TCP, every user on the machine can reach it. The minimum is:
    - loopback or a Unix socket with owner-only permissions;
    - an Origin check;
    - a token kept in the home.
  - **Is HTTP needed at first?**
    - The zoom-out lens: the server needs only one inbound transport. Stdio forwarders are needed at first because of the tests and stdio-only harnesses.
    - If the forwarder is a stdio-to-HTTP bridge, direct HTTP clients come at no extra cost.
- **Blocks:** the transport choice, R-8.1, and the chassis hook.

### 🟡 M7. Change announcements have no channel, payload or audience, and a recorded boundary applies
*Lenses: design, zoom-out, implementation-readiness, codebase-details, structural, comprehension*
- **Observed:**
  - Position 9: a viewer receives changes as they commit (`concepts_brief.md:295`).
  - **The current viewer:**
    - copies the `.lbug` files every 1.5 s, runs `--export`, and pushes the whole document over server-sent events (`server.mjs:7-14`);
    - takes a database path, not a project (`server.mjs:3`);
    - renders element detail by old snake_case names, such as `name_length`, `id` and `project` (`index.html:33`, `:181`, `:194`, `:240`).
  - **Recorded rules:**
    - `DECISIONS.md:15` and `AGENTS.md:22`: "WebTransport control channel", "No WebSocket fallback", and no tested transport selected yet.
    - `DECISIONS.md:14` excludes "diagnostic floods into agent context".
  - R-8.2 (Proposed): no session state (`metaform/SPEC.md:420`).
- **Inferred:** nothing states:
  - whether announcements are the control channel, and so WebTransport, or are separate from it;
  - what an announcement carries: the command, the changed addresses, or a new view;
  - who receives announcements: the viewer, the chassis, agents;
  - whether a change to a layer made from outside is announced;
  - a sequence number, ideally the log position, so a subscriber that reconnects can detect a gap and catch up;
  - whether position 13's limit on whole-map reads also applies to the human viewer. The viewer cannot run on the agent's root read, so it needs a separate full view;
  - whether keeping a list of subscribers counts as session state under R-8.2.
- **Blocks:** position 9, retiring the viewer's polling loop, and the announcement half of the hook.

### 🟡 M8. Position 16's conversion, placed before validation, would silently switch off field checks; the files that must change are protected
*Lenses: codebase-details, structural, implementation-readiness*
- **Observed:**
  - `check()` validates `view(element)` against `metaform/metaform.schema.json` (`commands.ts:25-33`, `contract.ts:22`). The schema's field names are snake_case, for example `name_length` (`metaform/metaform.schema.json:88`).
  - A key the schema does not name falls to `NamespaceValue` (`metaform/metaform.schema.json:214-216`), which accepts scalars (`:7-23`).
  - `check()` reads `element.fields.name_length` directly (`commands.ts:26`).
  - `AGENTS.md:9`: intake schemas are protected, "Do not evade the rule through a derived schema copy."
  - Every address and segment pattern is `[^.$\[\]\s]+` (`metaform/mcp-tools.proposed.json:19`, `:39`, `:59`, `:95`, `:314`, `:332`, `:437`; `metaform/metaform.schema.json:218`, `:236`). It allows uppercase, hyphens, leading or doubled underscores, an underscore before a digit, and non-ASCII letters.
  - R-5.24's fixed code list has no code for a name that does not round-trip (`metaform/SPEC.md:267`).
- **Inferred:**
  - If elements are converted to camelCase before validation, `nameLength: 9` passes as an unknown scalar, and neither the schema nor the length check sees it. The conversion has to run after validation on the way in and before output on the way out.
  - A camelCase copy of the schema would be the derived copy `AGENTS.md:9` forbids.
  - Refusing names that do not round-trip needs new patterns in the tool schema and a new R-5.24 code.
  - Positions 15, 16 and 17 all need edits to protected contract files. Whether the positions count as the founder's direct instruction under `AGENTS.md:9` is not recorded.
- **Blocks:** building positions 15, 16 and 17 without breaking R-5.6 to R-5.8.

### 🟡 M9. The scope of the conversion is not stated
*Lenses: comprehension, structural, zoom-out, implementation-readiness, codebase-details, design*
- **Observed:**
  - Position 16 converts "names" on `$.projectName.namespaceAddress` (`concepts_brief.md:302`). R-4.2 writes the path as `$.projectname.namespace.address.of.element` (`metaform/SPEC.md:189`).
  - Underscores carry meaning in address segments: `code.queue.dead_letter` (R-3.18 rule 4, `:106`). R-3.11 reads underscores as spaces (`:115`). Existing data has `command_line` (`metaform/metaform-canonical.json:206`).
  - Values with underscores or hyphens:
    - `not_built` (`TOPOGEE.md:41`, `test/metaform.test.ts:120`);
    - `two-way` (R-3.6, `metaform/SPEC.md:154`);
    - definition keys such as `part_of_speech`, and template placeholders (R-6.16, R-6.17, `:381-394`).
  - Setting keys are `database.buffer_pool_mb` (`home.ts:36`).
  - Project names keep capitals and hyphens (`home.ts:104`).
  - Skill entries follow SEP-2640, an outside format (`metaform/SPEC.md:370`). Native layers "retain their native formats" (`metaform/metaform.schema.json:224`).
  - Addresses also appear as values:
    - `delete.wants` (`metaform/mcp-tools.proposed.json:589`);
    - remediation payloads (`commands.ts:104-106`);
    - orphan and search results.
  - The export test compares against a snake_case document (`test/metaform.test.ts:84`).
- **Inferred:** an implementer cannot tell:
  - **What converts:** keys only, or also address segments, addresses that appear as values, values, free text, setting keys, project names, layer names and file names.
  - **The order:** whether lowercasing runs first. If it does, `deadLetter` becomes `deadletter` and is accepted when it should be refused.
  - **Outside formats:** whether skill frontmatter and outside layer content pass through untouched.
  - **Output form:** which case `--export`, `--import`, the log, announcements and search use.
  - **Search matching:** whether a query for `dead_letter` matches the stored `deadLetter`, while text inside `why` must not be converted.
  - **Project names:** how a project such as `MyApp` or `my-app` maps into `$.projectName`.
- **Blocks:** the store format, input validation, search matching, export and migration.

### 🟡 M10. Layer file names taken from the camelCase form can collide on case-insensitive file systems
*Lenses: structural (Major, conditional), codebase-details (Nit), design (Nit)*
- **Observed:**
  - Position 7 names files from the address, as in `this_address_inbox.json` (`concepts_brief.md:293`). Whether the stored form or the agent form is used is not stated.
  - Position 16 lowercases and then converts.
- **Inferred:**
  - `queue.dead_letter` becomes `deadLetter`, and `queue.deadletter` stays `deadletter`. Those two names differ only in case, so they collide on macOS and on Windows drives.
  - Deep addresses can also exceed file-name length limits.
  - This is Major only if files are named from the stored form.
- **Blocks:** the layer file naming scheme.

### 🟡 M11. The address read (position 12) has several readings
*Lenses: comprehension, implementation-readiness, codebase-details, structural*
- **Observed:**
  - Position 12 returns "layers attached there", "the frontmatter of the skills for that address", and "the names of the directly connected functionalities, both those this address depends on and those that depend on it" (`concepts_brief.md:298`).
  - R-6.3, R-6.4 and R-6.6: layers carry down to the leaf through a walk from the root (`metaform/SPEC.md:311-325`).
  - The founder's example attaches a skill at `code`, a trunk (`metaform/SPECIFICATION.md:103-110`).
  - The example skill entry holds `uri`, `frontmatter` (`name`, `description`) and `resources` with a `digest` (`metaform/SPECIFICATION.md:104-118`).
  - R-3.12 makes `name` a field (`metaform/SPEC.md:119`). R-3.7 uses `upstream` and `downstream` as root scopes outside the project (`:158`). `TOPOGEE.md:35` uses them for neighbours.
  - **What can be reused:**
    - providers through `Store.get().wants`, and receivers through `Store.receivers()` (`store.ts:145-154`, `:212-218`);
    - addresses and edges through `Store.all()` (`store.ts:156-166`);
    - trunk-to-leaf paths through `prefixes()` and `nest()` (`store.ts:44-48`, `tree.ts:56-69`).
- **Inferred:**
  - **"Attached"** can mean stored at this address, active after the R-6.6 walk, or chosen for the task. An agent at `code.engine.game` gets nothing from `code`, gets the `code` skill, or gets a subset that needs task input the read does not take. A negated layer, or one that is active but empty, behaves differently under each reading.
  - **"Frontmatter"** can mean the `frontmatter` object or the whole entry. If `uri` comes back with it, part of open question 9 may already be answered.
  - **"Names"** can mean addresses or `name` values.
  - **"Both directions"** can mean wants held and wants received, or parent and children.
- **Blocks:** the address read's output shape and its tests, skill delivery, and the round-1 test "an agent receives only the skills resolved for its address" (`concepts_brief.md:206`).

### 🟡 M12. The root read: what an edge carries, and how "only one Definitive" is enforced
*Lenses: zoom-out, implementation-readiness, codebase-details, comprehension, structural*
- **Observed:**
  - Position 13 returns "the relations as edges", with no wants content, and one Definitive label: "There is only one" (`concepts_brief.md:299`).
  - `TOPOGEE.md:34` describes the global view as "the directional flow of functional substance". R-3.6 makes `intent` the flow, relative to the holder (`metaform/SPEC.md:154`).
  - R-3.13 gives every element a role (`:123-128`).
  - `role` is any string in both schemas, and the contract still says DE (`metaform/mcp-tools.proposed.json:144-148`; `metaform/metaform.schema.json:48-51`).
  - No check counts Definitive elements (`commands.ts:25-33`). R-5.24 has no code for a second one (`metaform/SPEC.md:267`).
  - Each sample file has exactly one DE (comprehension lens).
- **Inferred:**
  - **Edges:**
    - In want direction (holder to the other element), an edge needs no want content.
    - In substance flow, an edge needs `intent`, and `two-way` becomes two edges. Part of the wants content is then in the root read, which position 13 excludes.
  - **"Only one":** it can be a refusal on data, which needs a new code; a display choice, which needs a rule for picking among several; or a separate label ("that we can give"), which needs a setter and a command.
  - The output for zero Definitive elements is undefined.
- **Blocks:** the root read, validation, the viewer, and what the intake prompt tells the agent.

### 🟡 M13. The search command has no contract
*Lenses: codebase-details, implementation-readiness, comprehension, design, zoom-out, structural*
- **Observed:**
  - The read key excludes only `add|update|delete|orphaned` (`metaform/mcp-tools.proposed.json:95`), inside a `oneOf` (`:10`). R-5.1 lists no `search` (`metaform/SPEC.md:215`).
  - Today every result is JSON (`server.ts:21`). R-5.23 gives query results as bare arrays (`metaform/SPEC.md:263`).
  - Position 17's example is an English line, `Found: "code.bar.foo" in "baz" layer` (`concepts_brief.md:303`).
  - In project documents, "trunk to leaf" means the prefixes of one address in order (`docs/address-only-example.md:15`; R-3.18 rule 3, `metaform/SPEC.md:105`).
  - R-3.16 (Decided): ephemeral knowledge goes in a ticket "and never in the map" (`:140`). `TOPOGEE.md:25-26` lists tickets and the address inbox as CEL Components.
  - Position 8: "nothing more and nothing less than exactly what is needed" (`concepts_brief.md:294`).
- **Inferred:**
  - `{"search": …}` matches both the read branch and a new search branch, and `oneOf` then rejects it. Without a contract change it is read as an address named `search`.
  - **Not stated:**
    - the result shape (text lines or an array of objects);
    - the result line for a match in the element itself;
    - whether the search term is echoed;
    - the match rule (substring or pattern, case, whole word);
    - whether field names match as well as values;
    - whether a match on a branch segment reports the branch or every leaf beneath it;
    - which form the query is compared in (M9);
    - whether there is a cap on results. A common word across every layer can return thousands of lines into an agent's context.
  - **Reopens round-1 N1.** If tickets and the inbox are layers, they are "in the map" for search and "never in the map" for R-3.16. The word now decides which results come back.
- **Blocks:** position 17 and its tests, and R-5.1's command list.

### 🟡 M14. The tool list: "the single tool" versus tools by module, a list that changes while agents are connected, and R-2.7's route
*Lenses: design, comprehension, implementation-readiness, structural*
- **Observed:**
  - The server declares `capabilities: { tools: {} }`, with no `listChanged` (`server.ts:11`).
  - `contract.ts:16` throws unless there is exactly one tool. The test asserts one tool (`test/metaform.test.ts:56-63`).
  - Position 11: a module exposes a tool. Position 12: "Without ACP, agents are told to orient through it" (`concepts_brief.md:297-298`).
  - R-5.1 and `DECISIONS.md:13` fix one tool. Every new tool needs a founder decision (`DECISIONS.md:108`).
  - R-5.13: the MCP server brokers to modules (`metaform/SPEC.md:277`).
  - R-2.7 (Decided): "A module reaches the chassis only through what the chassis exposes" (`:73-81`).
- **Inferred:**
  - "Single" can mean the map module's only tool, or the only tool on the server.
  - If module tools reach agents through the server, the tool list changes when the chassis connects or leaves. Then:
    - the server must send `notifications/tools/list_changed`;
    - forwarders must pass notifications that the server sends first;
    - a call to a module that is gone needs a defined error;
    - a tool list that differs per agent needs D-8 or a setting per forwarder.
  - R-2.7 decides whether messaging sends inbox commands through the chassis or straight to the server. That route is beyond the still-open "what the hook carries".
  - Which tools an agent sees without ACP is not stated.
- **Blocks:** position 10, position 11, `tools/list` and its test.

### 🟡 M15. The inbox file can have two writers, against position 2
*Lenses: implementation-readiness, comprehension, design*
- **Observed:**
  - Position 7: inbox files are named by address, and "the system clears it not an agent" (`concepts_brief.md:84`, `:293`).
  - Position 10: messaging "could be a module that is part of the chassis and thats where commands related to the inbox come from" (`:296`).
  - Position 2: each writer gets its own file (`:288`).
- **Inferred:** if the messaging module writes messages and the server clears delivered ones, one file has two writers. One process has to be the only writer of inbox files, or the files split further. The record of who read a message also waits on D-8.
- **Blocks:** the inbox layer and the hook.

### 🟡 M16. Migration has steps round 1 did not list, and no cut-over or way back
*Lenses: design, implementation-readiness, codebase-details, structural, zoom-out, comprehension*

Reopens round-1 M11 with new detail. The still-open mapping questions are not repeated here.
- **Observed:**
  - **Data shape:**
    - Arrays live in the `layers` column (`store.ts:28-35`, `:177-183`).
    - The tests write `layers: ['investigations','couplings']` at the root (`test/metaform.test.ts:121`). R-6.13 says these are not layers (`metaform/SPEC.md:357`).
  - **Role spellings in existing data:**
    - `DE`/`SE` (`metaform/intake-example.json:11`, `:21`);
    - `defining`, the misspelled `subtantial`, and `notable` (`metaform/metaform-canonical.json:69`, `:134`, `:773`).
  - **Root fields:** the canonical root holds `id`, `name` and `project` (`metaform/metaform-canonical.json:3-5`). R-3.10 forbids `project`.
  - **Import:** `importProject` checks only that providers exist, not the schema (`tree.ts:80-98`).
  - **Field mapping:**
    - `ice` sits on a want (`store.ts:19`). The role it maps to sits on an element (`metaform/SPEC.md:132`).
    - R-3.12 forbids `name` equal to `technical_name` (`:119`).
  - **Settings and registry:** the only declared settings, `database.buffer_pool_mb` and `database.max_size_gb`, size Ladybug (`home.ts:33-41`). The registry and settings are Ladybug nodes, with values stored as strings (`home.ts:51-54`, `:134`).
  - **Export paths:** `--export` (`main.ts:70-76`), `--database --export` (`main.ts:50-54`) and `Home.projects()` (`home.ts:88-91`). They need `@ladybugdb/core` 0.22.0 (`package.json:11`).
  - **Existing data:** the codebase-details reviewer reports that `~/.metaform` does not exist on this machine, and that the only `.lbug` file it found is the viewer snapshot `experiments/map-viewer/snap/s.lbug`.
- **Inferred:**
  - Under position 7, each array becomes layer files. R-6.15 needs each layer registered first, or a direct import is refused with `LAYER_NOT_REGISTERED`.
  - **Mappings that are not mechanical:**
    - `ice` to Supportive: one provider can carry `ice` from one receiver and not from another, but a role belongs to the whole element.
    - `name_length` to `technical_name` can be computed, but R-3.12 refuses it where the result equals the existing `name`.
  - **Conversion and validation:** the converter has to map every role spelling found, drop or move `id` and `project`, and run full validation itself, because import does not.
  - **Cut-over:** an old stdio entry in a harness configuration can keep writing `project.lbug` while the server writes JSON. Nothing stops the old entry point once a project is migrated.
  - **No way back:** `importProject` expects the old field names, so rollback loses every change made after migration unless a reverse converter is written.
  - **Settings:** the two Ladybug settings have no meaning on JSON and need a rule.
  - **Where migration runs:** a migration built into the server keeps the native dependency in the product. One run while the server runs is a second writer (B3).
  - Which `METAFORM_HOME` folders hold real data should be listed before the migration is sized.
- **Blocks:** moving existing projects, and rollback.

### 🟡 M17. The server's language and base are not recorded
*Lenses: implementation-readiness, structural*

Reopens round-1 M9 and open question 6. Position 14 now makes the server "the foundation".
- **Observed:**
  - R-4.6: "`mcp-server/` is a prototype ... The foundation is not built on it" (`metaform/SPEC.md:207-209`). R-1.1 forbids a temporary foundation (`:34`).
  - `DECISIONS.md:107` names the Python chassis. `DECISIONS.md:25` lists the runtime language as a choice still to make. The brief says "Node MCP server" (`concepts_brief.md:9`).
- **Inferred:** an implementer cannot tell whether the server is written in Node from `mcp-server/` or in another language. The forwarders depend on the same choice.
- **Blocks:** starting any code.

### 🟡 M18. Section 9 and the decision table cannot express the new foundation
*Lenses: structural, implementation-readiness, zoom-out*

Reopens round-1 M10.
- **Observed:**
  - **Section 9:**
    - Step 1 is "Chassis: decide D-9" (`metaform/SPEC.md:428`).
    - Step 2 is "Store and layers in the chassis" (`:429`).
    - Step 3 already asks for "a transport that serves many agents at once" (`:430`).
    - The acceptance lines rely on the replaced reads and on export equality (`:437`, `:441`).
  - **Decision table:**
    - D-9 blocks "All of section 9" (`:455`).
    - D-10 is framed around Ladybug files and several chassis (`:460`).
  - **The brief's staging** is conditional on "a file" and has no step for the server (`concepts_brief.md:331-337`).
- **Inferred:**
  - D-9 no longer blocks the server steps. It splits into the chassis language and what the hook carries.
  - D-10 becomes a question about several servers or homes.
  - New decision entries are needed for:
    - the server's language;
    - the role of the log;
    - the scope of the conversion;
    - the announcement channel.
- **Blocks:** any valid build order.

### 🟡 M19. The test plan does not fit the budget, and some tests cannot work as written
*Lenses: implementation-readiness, zoom-out, codebase-details*

Reopens round-1 M12.
- **Observed:**
  - The budget is at most five tests per feature, through the public interface, with cross-language boundaries stubbed (`CLAUDE.md`, Testing).
  - `test/metaform.test.ts` holds 10 tests (`:56` to `:167`).
  - Some tests assert Ladybug details (`:137-142`, `:156-166`, `:167-175`).
  - The read tests assert the whole-map detail that position 13 replaces (`:114-127`), and so does `metaform/tool-examples.json:84-90`.
  - Each test starts its own stdio server (`:43`).
- **Inferred:**
  - **Features to name, each with up to five tests:**
    - store and log;
    - server and forwarder;
    - reads;
    - search;
    - layer files and announcements;
    - migration.
  - **Crash test:** through the public interface, it means killing the server between commands and reading through a new forwarder. That needs the endpoint to follow `METAFORM_HOME` (B1).
  - **Hook tests** must stub the other runtime.
- **Blocks:** verifying every new feature.

### 🟡 M20. Parts of the concept are not recorded as founder positions
*Lens: structural*
- **Observed:**
  - These parts of the concept appear in none of positions 1 to 17 (`concepts_brief.md:287-303`):
    - one server per machine;
    - thin stdio forwarders;
    - agents on MCP's HTTP transport;
    - a command log.
  - The brief records the log only as "Proposed by an agent" (`:282`).
  - The spec forbids building a Proposed item as Decided (`metaform/SPEC.md:13`, `:18`).
- **Inferred:** a plan that treats these as the confirmed foundation builds Proposed items as Decided. Each needs a founder position or a Proposed status in the spec.
- **Blocks:** the status of the start-up, transport and log requirements.

### 🟡 M21. Terms with more than one reading, and no single place that says which text governs
*Lenses: comprehension, structural*
- **Observed:**
  - **"Layer"** has at least four uses:
    - the conversion step (position 16, `concepts_brief.md:302`);
    - a separate file of one kind of knowledge (position 7, `:293`);
    - an array on an element (`metaform/mcp-tools.proposed.json:105`, `:320`; `DECISIONS.md:8`, `:45`);
    - every field that is not a column, in the store (`store.ts:28`).
  - **"Server" and "the MCP server"** have no fixed process. R-2.6, R-4.5, R-5.3, R-5.13, R-8.1 and R-8.2 (`metaform/SPEC.md:68`, `:199`, `:221`, `:277`, `:418`, `:420`) each say "the server" or "the MCP server". The concept names a per-machine server, every agent's MCP server and thin stdio programs. Position 9's "running back end" and position 14's "live running server" are not stated to be one process.
  - **"Sink"** reads as one-way, but the server also replies, announces and brokers (position 10).
  - **Precedence:**
    - Reading-order pointers disagree: `AGENTS.md:3` says read TOPOGEE.md first, `AGENTS.md:25` says start with README.md, metaform/SPECIFICATION.md and DECISIONS.md, and `metaform/SPEC.md:5` says it does not depend on metaform/SPECIFICATION.md.
    - `metaform/SPEC.md:3` says the founder has not reviewed it, yet lines carry Decided.
    - The rule that current founder decisions win over the spec is in `DECISIONS.md:36`, not in the spec's "How to read" (`metaform/SPEC.md:7-20`).
    - The positions are in `concepts_brief.md`, which git shows as untracked.
- **Inferred:**
  - Migration has to pick between the element-array meaning and the separate-file meaning of "layer". Using the word for the conversion adds a third meaning that is not knowledge.
  - Each of R-5.3, R-5.13, R-8.1 and R-8.2 has to be assigned to the forwarder or the server:
    - R-8.1 fits the forwarder.
    - R-5.3 splits between them: only the forwarder sees the harness, and the server sees only forwarders.
    - R-8.2 conflicts with a server that keeps announcement subscribers.
  - Someone reading TOPOGEE.md, the spec and the positions together has to rebuild the precedence rule by hand, and will build some replaced lines.
- **Blocks:** assigning requirements to processes, migration of array fields, and building from the spec.

### 🟢 N1. The `project-map` rename reaches beyond the contract
*Lenses: implementation-readiness, codebase-details*
- **Observed:** `metaform_apply` appears at `metaform/mcp-tools.proposed.json:4`, `metaform/tests/check_contract.py:159`, `metaform/tests/check_tool_input.py:14`, `metaform/SKILL.proposed.md:10` and `metaform/SPECIFICATION.md`. `test/metaform.test.ts` reads the name from the contract and needs no change.
- **Inferred:** `metaform/SKILL.proposed.md` may be protected prompt material under `AGENTS.md:9`. Check that before editing it.

### 🟢 N2. Ladybug-only settings
*Lenses: comprehension, codebase-details*
- **Observed:** `database.buffer_pool_mb` and `database.max_size_gb` (`home.ts:33-41`) are asserted by `test/metaform.test.ts:167-175`.
- **Inferred:** they do nothing on JSON. The pattern of settings declared in code, with defaults that are never stored (`home.ts:118-140`), can be kept.

### 🟢 N3. "Functionality", "address", "element", "entity" and "node" are used for the same thing
*Lens: comprehension*
- **Observed:** position 3 says "a home, which is a functionality" (`concepts_brief.md:289`). R-3.1 says element, R-3.8 says node, and R-3.18 rule 2 says "all entities are elements". `TOPOGEE.md:20` says entities are addresses.
- **Inferred:** a reader cannot tell whether one functionality can span more than one address. That matters for a ticket's home.

### 🟢 N4. `concepts_brief.md` is internally inconsistent
*Lenses: structural, comprehension*
- **Observed:**
  - **Formatting:**
    - The open questions run 1-9, 13, 10-12 (`:306-329`).
    - No blank line separates position 17 (`:303`) from the open-questions heading (`:304`), so the heading renders inside item 17.
    - Answered questions are marked three ways (`:306`, `:309`, `:312`, `:313`, `:325`).
  - **Stale text:**
    - Q5 is answered but still blocks "the scope of 'no chassis'" (`:314`).
    - The title, the Overview, the Goals and the Alternatives rows still describe storage and the chassis as undecided (`:1`, `:9`, `:13`, `:255`, `:272-276`).
    - B1 still says "while the store is undecided" (`:29`).

### 🟢 N5. Requirement and decision numbering is out of order in the spec
*Lens: structural*
- **Observed:**
  - R-3.18 comes before R-3.10 (`metaform/SPEC.md:101`, `:111`).
  - R-4.8 and R-4.9 come before R-4.2, and R-4.6 comes after R-4.7 (`:181-207`).
  - R-5.21 to R-5.25 come before R-5.13 (`:257-277`).
  - R-6.20 comes before R-6.19 (`:398-402`).
  - D-10 comes after D-14 (`:460`).
  - The closed D-1 to D-3 remain under "Open decisions" (`:447-449`).
- **Inferred:** the replacements B6 and M18 call for need a stated rule for new IDs and for marking replaced lines.

## New open questions

Each item is new, or adds something new to an item on the still-open list. The finding it comes from is given in brackets.

1. **One server per machine, or one per `METAFORM_HOME`? Who starts it, where is its endpoint, what keeps it to one copy, and what does a forwarder do while it is down?** Blocks: B1, M19 and every forwarder.
2. **How does a call name its project, through a stdio forwarder and over HTTP? What happens for a subfolder or an unregistered folder? Does binding the project to a connection count as session state under R-8.2?** Blocks: B2 and R-5.3.
3. **Is the server the only process that writes files under the home, including layer, inbox, registry, settings and log files? Does "added externally" (position 10) mean through a command, or by writing files directly?** Blocks: B3, search freshness and M1. *Adds to "what the hook carries".*
4. **Which one process writes inbox files, and which clears them?** Blocks: M15.
5. **Are want records stored in the map file or in a wants layer file? Does the address read return this element's own `why`, `how` and `intent`? Do the existing in-element arrays move to layer files?** Blocks: B4 and migration. *Adds the storage location to the D-4 shape question.*
6. **Do R-5.21 and R-5.22 still hold, so that a read naming a layer returns its content?** Blocks: B5 and R-6.20. *Wider than the still-open "how an agent gets a skill's body".*
7. **Is the command log written first and replayed at start-up, or written afterwards as history? Does it hold commands or effects, in which form, one per project or one per machine? Are failed commands logged? Is the inbox read record a log entry?** Blocks: M1 and crash recovery.
8. **Are the per-machine server, the stdio forwarders, the HTTP transport and the command log founder positions, or Proposed?** Blocks: M20.
9. **Do positions 15 to 17 count as the founder's direct instruction to change the protected contract files under `AGENTS.md:9`?** Blocks: M8, N1 and the search command.
10. **Which strings does the conversion touch, and in which order? Which case do export, import, the log, announcements, search and file names use? Which R-5.24 code refuses a name that does not round-trip? How does a hyphenated or capitalised project name map into `$.projectName`?** Blocks: M8, M9 and M10.
11. **In the address read: does "attached" mean stored here or active after the walk? Is the skill entry returned whole, `uri` included, or only `frontmatter`? Are neighbours given as addresses or as `name` values, and are parent and children included?** Blocks: M11. *Related to D-7 (`metaform/SPEC.md:453`).*
12. **Do edges in the root read carry direction only, or `intent` as well?** Blocks: M12.
13. **Is "only one Definitive" a refusal on data, a display choice, or a separate label? Who sets it, and what does the root read show for zero?** Blocks: M12.
14. **What are the search command's key, match rule, result shape, line for a match in the element itself, and result cap? Are tickets and the inbox inside search scope, given R-3.16?** Blocks: M13. *Adds to the still-open question about layers switched off at an address.*
15. **Are announcements the WebTransport control channel of `DECISIONS.md:15`? What do they carry, and to whom? Does position 13's limit apply to the human viewer?** Blocks: M7.
16. **Does a chassis module reach the server through the chassis (R-2.7) or directly? Which side opens the connection, and how does each learn the other is present? Does the tool list differ per agent on one endpoint, and what does an agent see without ACP?** Blocks: M14. *Adds the route and the discovery to "what the hook carries".*
17. **What is the server's language, and is `mcp-server/` its base?** Blocks: M17 and all code. *Reopens round-1 open question 6.*
18. **Is R-8.1 (`serveStdio`) Decided or Proposed?** Its status line follows R-8.2 (`metaform/SPEC.md:422`). Blocks: the transport choice (M6).
19. **Until positions 1 to 17 are merged into the spec, where does the spec say they govern?** Blocks: building from the spec (M21, B6).

## Alternatives raised

Every item below is proposed by an agent. None is decided. The proposing lenses are in brackets.

**Start-up, routing and transport**
- **Single instance per home (proposed by an agent).**
  - A lock file at `$METAFORM_HOME/server.lock` holds the process id and the build version, and a Unix socket at `$METAFORM_HOME/server.sock` is the endpoint. On Windows, a named pipe.
  - A forwarder that cannot connect takes the lock, starts the server detached, and retries for a fixed time. Otherwise it returns a tool error that names the log file.
  - Because the endpoint follows `METAFORM_HOME`, tests and worktrees stay apart.
  - [design, zoom-out, implementation-readiness, structural]
- **Forwarder as a byte pipe with a first-line handshake (proposed by an agent).**
  - The first line is `{folder realpath, pid, forwarderVersion}`.
  - The server runs `serveStdio(factory, {transport: new StdioServerTransport(socket, socket)})` for each connection.
  - The forwarder holds no contract. `tools/list` and validation come from the server. On a version mismatch the forwarder exits so the harness restarts it.
  - [codebase-details, implementation-readiness, structural]
- **One inbound transport (proposed by an agent).** The server listens only on MCP HTTP, with the project in the URL path. The forwarder is a stdio-to-HTTP bridge started with the folder argument, as `main.ts` is today. [zoom-out]
- **HTTP with one URL per project (proposed by an agent).**
  - `/projects/<folder-id>/mcp` through `createMcpHandler`, reading `ctx.requestInfo`.
  - Bound to loopback, behind the SDK's Host and Origin checks, plus a token kept in the home.
  - Creating a project becomes a separate CLI act.
  - [design, codebase-details, implementation-readiness, structural]

**Writes, durability and recovery**
- **Server as the only writer (proposed by an agent).**
  - The CLI, migration, the viewer and the chassis are clients of the server.
  - Outside layers are registered and written through a server command, or the hook once it exists.
  - A start-up scan by modification time or hash, plus a `--reindex` command, covers files the founder edits by hand.
  - [design, zoom-out, implementation-readiness, codebase-details, structural]
- **Log as the commit point (proposed by an agent).**
  - Append the normalised command or its effect, with a sequence number and a request id, and fsync it.
  - Apply it in memory, then write the snapshots by temporary file and rename. Each snapshot records the last sequence it applied.
  - Replay later entries on start-up.
  - The log position is also the announcement sequence number.
  - [design, structural, codebase-details, implementation-readiness variant a]
- **JSON file as the truth, log as history (proposed by an agent).** Each commit is a temporary write and a rename. The log is appended afterwards, for attribution, and never replayed. This has fewer parts, but it does not cover a command that changes several files. [zoom-out, implementation-readiness variant b]
- **Request id for idempotent retries (proposed by an agent).** A repeated id returns the first result. [design]
- **Per-project isolation (proposed by an agent).** A write queue and a load state for each project. An unexpected error fails one request, not the process. [design, codebase-details]
- **Status command (proposed by an agent).** It shows loaded and failed projects, open connections, and the last sequence number and log size per project. [codebase-details]

**Conversion and names**
- **One boundary function for the conversion (proposed by an agent).**
  - It converts field keys and address segments only, with one segment grammar: lowercase words joined by single underscores, each word starting with a letter.
  - It runs after validation against the protected schema on the way in, and before responses, search results and announcements on the way out.
  - No store schema is needed.
  - [codebase-details, implementation-readiness, structural]
- **Snake_case layer file names (proposed by an agent).** Name layer files from the snake_case address to avoid case collisions. [structural, codebase-details]
- **A conversion table (proposed by an agent).** State what the conversion touches as a table (keys, segments, values, setting keys, project names, file names), with one example each and the refusal code. The code name is the founder's to choose. [comprehension]
- **A separate name for the conversion step (proposed by an agent).** Call it "the boundary between the form and the store", in R-2.1's terms, and keep "layer" for knowledge layers. [comprehension]
- **Fixed process names (proposed by an agent).** Give each process one name in the spec, for example "per-machine server" and "stdio forwarder". Add a line to each of R-5.3, R-5.13, R-8.1 and R-8.2 saying which process it applies to. [comprehension]

**Reads, search and announcements**
- **No search index in the first slice (proposed by an agent).** Compute search and the trunk-to-leaf paths at call time from the in-memory map and the layer files. Add an index only after a measured search proves too slow (R-5.20). [zoom-out]
- **Search result as a bare array (proposed by an agent).** For example `[{"address": "code.bar.foo", "layers": ["baz"]}]`, with the term echoed, consistent with R-5.23. Render the `Found: ...` sentence through an R-6.20 template. [comprehension]
- **One announcement per log entry (proposed by an agent).** Each carries `{project, seq, status, touched addresses, command in agent form}`. Subscribers detect gaps and fetch again. The viewer gets a separate full view in agent form, and the 1.5-second loop in `server.mjs:7-13` is removed. [codebase-details, design, zoom-out]
- **Skill bodies through the SDK's skills extension (proposed by an agent).** `skills/get` (`node_modules/@modelcontextprotocol/core/dist/ext/skills/index.d.mts:295-299`) matches the SEP-2640 entries already in `metaform/metaform-canonical.json:6-21`. Needs the founder (`DECISIONS.md:108`). [codebase-details]
- **R-2.7's conditions for the hook (proposed by an agent).** When the hook is built, apply R-2.7's three conditions (defined, available in the template module, documented) to what the server exposes. Not before. [zoom-out]

**Migration**
- **A separate one-time migration tool (proposed by an agent).**
  - It runs with the server stopped, so `@ladybugdb/core` stays out of the server.
  - It runs the existing `--projects`, `--settings` and `--export` for each registry entry, then applies a founder-approved mapping table.
  - It registers each array as a layer before writing it.
  - It validates with the contract and `metaform/validate_metaform.py`, then writes the JSON.
  - It writes a cut-over marker that the old entry point refuses to run past, renames `project.lbug` to `project.lbug.migrated`, and keeps the `.lbug` files until the founder accepts the converted maps.
  - [design, zoom-out, implementation-readiness, codebase-details, structural]

**Build order and spec layout**
- **Smallest first slice (proposed by an agent).**
  - **Contents:**
    - one server per home holding the registry, settings and maps in memory;
    - one write queue, with each command applied, validated, written by temporary file and rename, logged and announced;
    - the existing grammar, plus the address read, the root read and search at call time;
    - one MCP HTTP listener, a stdio forwarder, and an announcement stream with the viewer as its only consumer.
  - **Waits until the chassis exists:**
    - the hook;
    - tools by module through ACP;
    - messaging and the inbox;
    - file watching;
    - other event consumers.
  - [zoom-out]
- **Build order A (proposed by an agent).**
  1. Founder answers to new questions 1 to 3, 5, 7, 9, 10 and 17.
  2. A store library with no network: JSON, log, atomic commit, recovery.
  3. Server, forwarder, routing and version handshake.
  4. Address read, root read and conversion.
  5. Layer files, search and announcements.
  6. Migration and cut-over.
  7. The chassis hook.

  [implementation-readiness]
- **Spec layout and build order B (proposed by an agent).**
  - **Placement:**
    - a new section for the server between sections 4 and 5;
    - the conversion in section 2;
    - layer files in a new 6.5 that absorbs R-4.3;
    - search in 5.3;
    - transports in section 8.
  - **Section 9 order:**
    1. server, registry, settings and log;
    2. map file, conversion and validation;
    3. reads and search;
    4. layer files;
    5. migration;
    6. viewer;
    7. hook;
    8. CLI.
  - **Decision table:**
    - split D-9 into the chassis language and the hook's contents;
    - recast D-10 for several servers or homes;
    - add entries for the server's language, the log's role, the conversion's scope and the announcement channel.
  - [structural]
- **Precedence in the spec (proposed by an agent).** Give each spec line a position replaces a "Replaced by position N" status. In "How to read", name `concepts_brief.md` positions 1 to 17 as governing until they are merged. [comprehension]
