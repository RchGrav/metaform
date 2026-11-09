# Metaform Functional Map Server

> **Storage superseded (2026-11-07).** This document designs JSON file storage (`map.json`, layer files, a log). The founder never decided JSON for the map. Maps live in LadybugDB: `metaform.lbug` for the chassis and one `project.lbug` per project (`metaform/SPEC.md` R-4.1; the founder's documentation set, section 1.2). Read its storage sections as history; its other positions stand only where the specification still holds them.


*   **Author:** Rich
*   **Status:** Draft
*   **Date:** 2026-11-03

--------------------------------------------------------------------------------

## Overview

The functional map server is the foundation of the Metaform. It is one
long-running process on the Metaform home, `~/.metaform`. It tracks every
project, holds each project's map and layers as JSON files, and is the only
process that writes them. Each agent still starts its own MCP instance, but that
instance is a thin forwarder. It names its project folder and passes every call
to the server. The server applies writes one at a time for each project,
commits each one before it answers, and announces each change as it commits.

Agents reach the map through one tool, `project-map`. Reading an address gives
that element's own fields. `goto` places the agent at an address and gives it
what is directly linked there: its wants, what relies on it, its attached
layers, its skills and its memory count. Reading the root gives a connected
index of the whole project. A search says where
something is. Layers are kinds of knowledge kept in their own files and indexed
by the map, and parts outside the server can add them through the server. The
`layer` command adds a layer. Every other command works the same way as
before, and writes a layer's data like any other field. Memory is a module with
its own tool, `project-memory`. Its commands are the canonical memory server's,
and it shows the memory graph of the address where the agent is.

Source: the founder's positions 1–23 in
[`metaform/docs/designs/metaform-server.md`](metaform-server.md).

## The Problem

An agent that works on part of a project first has to orient itself. It has to
find where a functionality sits, what that functionality needs, what needs it,
and which knowledge applies there. The aim is to give the agent exactly what
its work needs, nothing more and nothing less (position 8). The current build
cannot do this for more than one agent, and it does not give that context in
the right shape.

1.  **Only one agent can write a project.** Each agent's harness starts its own
    server process over stdio (`metaform/server/src/main.ts:80`). Each process opens
    the project's Ladybug database itself (`metaform/server/src/store.ts:80`).
    Ladybug allows one read-write process per file, so a second agent on the
    same project is refused by the file lock
    (`metaform/verification/ladybug-spike-2026-10-30.json:10`).
2.  **Nothing announces a change.** After a commit the server tells no one
    (`metaform/server/src/server.ts:11`). The map viewer shows changes during intake
    only by polling. Every 1.5 seconds it copies the database files, starts a
    new Node process to export the whole map, and compares the result
    (`experiments/map-viewer/server.mjs:7-13`). This runs whether or not
    anything changed, and the founder's decisions exclude recurring polling
    (`DECISIONS.md:15`).
3.  **Reads do not give localized context.** A read returns the address and
    everything beneath it (R-5.10). A read of the root returns every intake
    field for the whole project (R-5.11). There is no read that returns exactly
    what is linked to one address, and no way to find where something is.
4.  **Refusals do not say why.** A schema failure returns the failing path and
    the validator's wording, for example `must match pattern "^[^.$\[\]\s]+..."`,
    with no code, rule or fix (`metaform/server/src/contract.ts:27-36`). R-5.24
    requires all four.
5.  **The store works against the design.** The map is the project's intent,
    but in a database file it cannot be read, compared or kept in version
    control. The database needs a native binary for each platform. Its
    strengths, graph queries over large data and many concurrent writers, are
    not needed by a map of this size with one writer. The earlier system's
    whole map is 40 KB (`metaform/metaform-canonical.json`).

## Goals

*   **One server, one writer.** One server process runs on the home. A second
    attempt to start one connects to the running server instead. No agent
    instance, CLI command or outside part writes files under the home; only the
    server does.
*   **Many agents at once.** Any number of agents on any number of projects work
    at the same time through their forwarders. Each call reaches the project of
    the folder its forwarder named.
*   **Committed before answered.** A write is acknowledged only after it is on
    disk. A failed command changes nothing (R-5.8). After a crash and restart,
    no acknowledged change is lost.
*   **Changes announced as they commit.** Every committed change reaches
    subscribers when it commits, with no polling. The map viewer shows intake
    as it happens without its copy-and-export loop.
*   **Reads shaped by position.** (Field names follow the store as it is; the
    R-3.4 renames are separate work.)
    *   The address read returns the element's own fields only. Its wants come
        back when the read names them. It does not return what relies on the
        address, the attached layers, skills or memories (the founder: "I was
        completely wrong when I said viewing an address shows its edges").
    *   `goto` places the agent at an address. It returns the element, its
        wants, the full breakdown of who or what relies on the address, the
        names of the attached layers, the frontmatter of its skills, and its
        memory count. Memories at that address are then reached through the
        memory tool.
    *   The root read returns a connected index: addresses and the relations
        between them as edges, with only the one Definitive functionality
        marked, and no other detail (position 13).
    *   A read that names a layer returns that layer's content at the address
        (R-5.21).
    *   Search reads all content, layers included, and answers where a match
        is, in the form `Found: "code.bar.foo" in "baz" layer` (position 17).
*   **One command adds a layer.** `layer` registers a layer in the project's
    `layers` dictionary (R-6.15). Its definition has a schema (`fields`, as in
    the wants definition, R-6.17), a description, a sentence (`template`) and
    an instruction. Every other
    command works the same way, and
    writes a layer's data at an address like any other field (the founder: "make
    a command called layer to add a layer. every other command works the same
    way").
*   **Memory is a module.** It exposes its own tool, `project-memory`, whose
    commands are identical to the modelcontextprotocol.io memory server's. It
    shows a different memory graph depending on where the agent is, so the
    only way to read and write the memories of an address is to be there.
*   **Agents see one naming style.** Agents send and receive snake_case. The
    store keeps camelCase. A name that would not convert back exactly is
    refused (position 16).
*   **Every refusal says why.** Each refusal returns a fixed code, the rule it
    broke, the reason in plain words, and a remediation command (R-5.24,
    position 23).
*   **Plain files.** Maps, layers, settings and the project registry are JSON
    files under `~/.metaform`. The server has no Ladybug dependency.
*   **A name agents can reason from.** The tool is called `project-map`
    (position 15).

## Non-Goals

*   **The world system's MCP server.** This server is for developing Topogee.
    The world needs its own MCP server, built custom and inspired by metaform,
    so agents can blueprint their features (`world-system-spec.md` W-1.1,
    W-1.4).
*   **The inbox and messaging.** They come later (position 21), in the agents
    module, which the founder will specify after the functional map server is built
    (`metaform/SPEC.md` section 11). This design keeps `goto` as the point where
    an address inbox will be read.
*   **The chassis, its modules and the hook between the chassis and the
    server.** The chassis is a separate part of a larger vision (position 10).
    This design keeps the hook possible, because outside parts add layers
    through the server, but it does not build the hook.
*   **Orchestration, the ACP harness, agent identity (D-8) and role
    assignment.** Orchestration reads the map and does not change it
    (position 6).
*   **Changes to the method.** Roles, the want record and its grammar, the
    address rules and the intake procedure stay as the founder defined them.
*   **A search index.** Search runs over the in-memory map and the layer files.
    An index is added only after a search is measured to be too slow (R-5.20).
*   **More than one server on one home, or servers across machines (D-10).**
*   **The R-3.4 field renames** (`name_length` to `technical_name`, `goal` and
    `function` to `why` and `how`, the new intent values). They change the
    protected `metaform/metaform.schema.json` and are separate work.

## Open Questions

*   **Server language**: The brief treats the server as Node, built from
    `mcp-server/`, because that is the code being worked on. The author has
    not stated it.
*   **Announcement channel**: WebTransport (`DECISIONS.md:15`) now lives in the
    viewer server. Node has no built-in WebTransport server, so its library
    still has to be chosen and tested in Step 5.
*   **Search scope**: Confirm the agent's choices: the layer files at each address, a
    substring match ignoring case, and a cap of 50.
*   **Layer files after a delete**: What happens to an address's layer files
    when the address is deleted or replaced?
*   **Shape of `wants` (D-4)**: Stored as an object keyed by the other
    element's address, as `DECISIONS.md` describes. The protected schema still
    allows the array; aligning it is separate work.

## Critical User Journeys (CUJs)

### CUJ 1: An agent orients at an address

*   **Given**: The server runs on `~/.metaform`. The project at
    `/work/game` is registered. An agent's harness starts its `project-map`
    forwarder in `/work/game`.
*   **When**: The agent sends `{"goto": "code.engine.game"}`.
*   **Then**: It is now at that address. It receives the element, its wants,
    who or what relies on it, the names of its attached layers, the frontmatter
    of its skills, and its memory count. It holds no layer content and nothing
    from other addresses' layers. `project-memory` now shows this address's
    memory graph.

### CUJ 2: Two agents write the same project

*   **Given**: Two agents work in `/work/game` through their own forwarders.
*   **When**: Both send an `update` at the same moment.
*   **Then**: The server applies one, then the other. Each agent receives "ok"
    only after its change is on disk. Neither is refused for a lock.

### CUJ 3: The server crashes during a write

*   **Given**: An agent has added the layer `features` with `layer`. It has then
    received "ok" for an `add` that wrote an element and that element's
    `features` data, which touches `map.json` and a layer file.
*   **When**: The server process is killed. The agent's forwarder exits, and
    the next forwarder started starts the server again.
*   **Then**: The layer and its data are both present. A command that had not
    been acknowledged is either fully present or fully absent.

### CUJ 4: The founder watches intake

*   **Given**: The map viewer is open and subscribed to the server.
*   **When**: The intake agent adds elements.
*   **Then**: Each element appears when its command commits. The viewer does
    not copy files or poll.

### CUJ 5: An agent finds the project's own name for a thing

*   **Given**: A ticket says "fix pktring". `pktring` is the project's `name`
    for the element at `code.buffer.ring.packet`, whose `technical_name` is
    "packet ring buffer".
*   **When**: The agent searches for `pktring`.
*   **Then**: It receives `Found: "code.buffer.ring.packet"` for the element
    whose `name` matches, and `Found: "code.buffer.ring.packet" in "features"
    layer` where a layer at that address mentions it. It then goes to that
    address for detail.

## Technical Plan (Architecture)

Choices marked **(agent's choice)** were made by the agent at the author's
request. The author can overrule any of them. Everything else comes from the
founder's positions or a Decided requirement.

### Processes

```text
 agent harness A        agent harness B        map viewer (browser)
      | stdio                | stdio                  ^ WebTransport
      v                      v                        |
 forwarder (folder A)   forwarder (folder B)    viewer server (server.mjs)
      | Unix socket          | Unix socket            | Unix socket, subscribed
      +----------+-----------+------------------------+
                 v
   +---------------------------------------------------------+
   | functional map server   (~/.metaform/server.sock)                  |
   |  handshake -> route to project -> MCP (both tools)      |
   |  shape checks -> project queue -> map checks -> effect  |
   |  commit to log.db -> memory -> JSON files -> answer     |
   |  each committed entry -> subscribers on the socket      |
   +---------------------------------------------------------+
                 |
                 v
   ~/.metaform  (JSON files and log.db; only the server writes here)
```

*   **The functional map server** is one long-running Node process. It owns everything
    under the home, and nothing else writes there (position 22). It opens no
    network port.
*   **A forwarder** is the program an agent's harness starts as its MCP server
    over stdio. It holds no tool contract and no map code. It connects to the
    server's socket, sends a one-line handshake, then copies bytes in both
    directions. The agent and the server negotiate MCP directly through it.
    When the socket closes, the forwarder exits; it never reconnects, because a
    byte pipe cannot resume an MCP session. **(agent's choice)** A byte pipe
    keeps the contract in one place, so a forwarder cannot drift from the
    server after an upgrade.
*   **The viewer server** (`experiments/map-viewer/server.mjs`) subscribes on
    the same socket and relays changes to the browser over WebTransport
    (`DECISIONS.md:15`). TLS, the certificate and the WebTransport library live
    there, not in the process that writes the data. **(agent's choice)**
*   **The CLI** connects on the same socket for one request and exits.
*   **Direct HTTP access for agents** is left out of the first version
    **(agent's choice)**. Forwarders cover every harness that starts a local
    stdio MCP server, and an HTTP endpoint with no agent identity would let any
    local process write any project.
*   **Platforms**: Linux, including WSL2, and macOS. Windows is not supported
    in the first version. **(agent's choice)**

### Storage choices

The rule is to choose the best tool for the job, weighing the pros and cons and
how it may be used in the future (`DECISIONS.md`, R-4.1).

*   **The map, layers, settings and registry are JSON** (position 14). They are
    the project's intent, and JSON can be read and compared as text.
*   **The change log is SQLite**, in `~/.metaform/log.db`, through Node's
    built-in `node:sqlite`, so it needs no native add-on. The log is a table of
    rows that is appended to and read by sequence number, which is what SQLite
    does well. It gives crash-safe appends and "every entry after N" without a
    log format written by hand, and the same file is the lock that keeps one
    server running. **(agent's choice)**
*   **Ladybug is not used.** The map is about 40 KB, and with one writer its
    graph queries add nothing. It stays a candidate for a search index rebuilt
    from the files (Future Improvements).

### Start-up and the single server

Every path comes from the home folder: `~/.metaform`, or `METAFORM_HOME` when it
is set (`home.ts` `homePath()`), so tests and worktrees never reach the founder's
server.

1.  A starting server opens `log.db` and takes SQLite's exclusive lock
    (`PRAGMA locking_mode = EXCLUSIVE`, then a write). If another server holds
    it, the new one exits. The operating system releases the lock when the
    holder dies, so a crash never leaves a stale lock. **(agent's choice)**
2.  Only the lock holder removes a leftover `server.sock` and binds a new one
    (mode `0600`). It then writes `server.json` with its process id, version,
    start time and checkout path, so a second start can say which process
    holds the lock instead of only failing, and `server status` can show it.
    `server.json` is information only; the lock is what decides.
3.  The home must be on a native Linux or macOS file system. On WSL, a folder
    under `/mnt/c` is reached through 9p, where SQLite's locks are not
    reliable and the single-writer rule could fail without any error. Before step 1,
    the server checks the home's file system type with `fs.statfs` and refuses
    to start on 9p, naming the reason. **(agent's choice)**
4.  It loads `groups.json` and the tool contracts once, then loads each
    registered project, layer files included. A project that fails to load is
    marked failed.
5.  A forwarder or CLI call that finds no server starts `daemon.ts` as a
    detached process, from the checkout it runs from, and retries the socket
    for up to five seconds. The server writes its output to
    `~/.metaform/server.log`.
6.  The CLI has `server status`, `server stop` and `server restart`. Status
    shows loaded projects, failed projects, open connections, subscribers and
    each project's last sequence number. `restart` is `stop`, then a start as
    in step 5.

These choices follow the earlier system's experience, reported by the session
reviewing `metaform-tasks`: there every process opened the shared SQLite files
directly, and its logs show a damaged database, lock waits, and server restarts
caused by one slow read blocking every request. One server holding an
exclusive lock is the opposite of that arrangement.

### Connections and the handshake

Each connection starts with one JSON line, which the server reads before it
hands the socket to anything else. **(agent's choice)** for the forms.

*   **Agent:** `{"folder": "<real path>", "version": "<v>"}`. The server
    resolves the folder to the registered project whose path is the folder or
    its nearest parent, so a forwarder started in `/work/game/src` reaches
    `/work/game`. It then serves MCP on the connection, with both tools.
*   **CLI:** `{"admin": true, "version": "<v>"}`, followed by one request line
    and one answer line:
    `{"register": {"folder", "name"}}`, `{"projects": {}}`,
    `{"settings": {"folder"?}}`, `{"set": {"key", "value", "folder"?}}`,
    `{"import": {"folder", "map"}}`, `{"export": {"folder"}}`,
    `{"status": {}}` and `{"stop": {}}`. An import is one command through the
    project's queue, with every check a write gets.
*   **Subscriber:** `{"subscribe": "<real path>", "version": "<v>"}`. The
    server sends a snapshot of the project in the agent's form with its
    sequence number, then one line per committed entry. A subscriber that
    reconnects subscribes again and gets a new snapshot.
*   **Refusals reach the agent.** A folder with no registered project, or a
    forwarder whose version differs from the server's, still gets an MCP
    session. Every tool call on it is refused with `PROJECT_NOT_REGISTERED`
    (remediation: the `register` command) or `VERSION_MISMATCH` (remediation:
    `server restart`). A call never registers a project as a side effect;
    today `home.ts:100-109` does, and that is removed.
*   **The version** is `version` in `metaform/server/package.json`. A server
    accepts only its own version.
*   The project and the agent's present address are bound to the connection
    for its lifetime. Session state belongs in the agents module, against the
    agent's identity; until it exists, the connection stands for the agent
    (R-8.2).

### Files under the home

```text
~/.metaform/
  server.sock, server.log
  server.json                    the running server's pid, version, start time, checkout
  log.db                         every project's change log, and the server lock
  registry.json                  {"projects": [{"path", "name", "folder"}]}
  settings.json                  global values only; defaults stay in code (R-4.8)
  projects/<folder>/             <folder> is the project name made safe, plus a number
    source.txt                   the project's real path
    map.json                     the elements and the project's `layers` dictionary
    settings.json                this project's overrides (R-4.8)
    layers/<layer>/<address>.json   one file per layer per address
```

`map.json` holds two keys, so an element can never be confused with the
dictionary of layers:

```json
{
  "elements": {
    "code": {"engine": {"game": {
      "name": "game loop", "nameLength": 1, "role": "DE",
      "wants": {"code.render.frame": {"goal": "draw each tick", "function": "renders a frame", "intent": "outbound"}}
    }}}
  },
  "layers": {"features": {"description": "...", "template": "...", "fields": {}, "instruction": "..."}}
}
```

*   Elements nest by address segment, as R-4.2 describes. Agents never see the
    nested form: every read, search result and refusal names elements by their
    full address.
*   `wants` is an object keyed by the other element's address, whose value is
    the want record (`DECISIONS.md`: "Provider address is the key"). This
    settles the shape of D-4 for storage. **(agent's choice)**
*   Every stored key and address segment is camelCase (position 16). Layer file
    names use the agent's snake_case address, so two addresses can never
    collide on a case-insensitive file system. The root address `.` uses the
    file name `_root.json`. **(agent's choice)**
*   A layer file holds the layer's data at that address: a dictionary for a
    named layer, a list otherwise, and for memory the memory server's
    `{"entities": [...], "relations": [...]}`.
*   Files are written with mode `0600` and folders with `0700`.
*   The `intake` and `system` groups are global data in
    `metaform/server/groups.json`, not in any project's folder (R-6.15).

### Adding a layer

The founder's rule: `layer` adds a layer, and every other command works the same
way.

*   `layer` registers a layer in the root `layers` dictionary of `map.json`
    (R-6.15). The form matches the other commands: the command, then a key, then
    a value.
*   The definition must have a schema, a description, a sentence and an
    instruction (the founder: "layer command must name its fields and sentence
    and instruction just like wants"; "layer needs a schema, description a
    template, and an instruction"). The schema is `fields`, in the form the
    wants definition uses (R-6.17):

    ```json
    {"layer": {"features": {
      "description": "The feature or features each element belongs to.",
      "template": "{this.address} ({this.name}) belongs to the {feature} feature.",
      "fields": {
        "feature": {"part_of_speech": "Noun phrase", "rule": "Name one feature of the project in lowercase words.", "example": "search"}
      },
      "instruction": "Tag every element with the feature or features it belongs to."
    }}}
    ```

    *   `template` is the sentence. A dump renders each record of the layer as
        one sentence (R-6.20). `{this.address}` and `{this.name}` are the
        element that holds the record, as in the wants sentence.
    *   `fields` is the schema. It names every field of a record, and each
        field gives its `part_of_speech`, `rule` and `example`.
    *   `description` says what the layer holds.
    *   `instruction` says what to put in the layer.
    *   A `layer` command without all four, or with a field that is missing
        any of `part_of_speech`, `rule` or `example`, is refused and changes
        nothing, as a want missing a field is (R-5.6). The definition may also
        hold the other parts of R-6.16, such as `ref`.
*   A layer name follows the same rule as an address segment. A second `layer`
    for a name that is already registered replaces its definition, since each
    `layer` carries a whole one. **(agent's choice)**
*   Data goes into a layer through `add` and `update` at an address, with the
    layer name as the field. Its shape at the element depends on whether the
    layer's records are named (the founder: "if the layer is named, then its a
    dictionary, otherwise they are a list with a incrementing key or
    something"). The definition says which, with `"named": true`; a layer
    without it is a list. **(agent's choice)** for the key `named`.
    *   **Named:** the data is a dictionary keyed by each record's name:
        `{"add": {"code.engine.game": {"skills": {"rust_build": {...}}}}}`.
        `add` writes the records given and keeps the others. `update` with
        `{"skills": {"rust_build": null}}` removes one record by name. A
        record's name is stored as sent and is not converted, like `name`.
    *   **Not named:** the data is a list, and a record's position is its
        key: `{"add": {"code.engine.game": {"features": [{"feature": "search"}]}}}`.
        `add` appends and `update` replaces the list (R-5.5).
    *   `update` with the layer field set to `null`, such as
        `{"features": null}`, removes that address's layer file.
*   A field whose name is a registered layer or a system layer is stored in
    `layers/<layer>/<address>.json`. An intake field stays in `map.json`. A
    field in none of the three groups is refused with `LAYER_NOT_REGISTERED`,
    as R-6.15 requires. `intake` in `groups.json` lists the field names the
    store uses today, so no current write is refused.
*   `intake` and `system` are reserved groups (R-6.15). Their definitions are
    global data, shared by every project, and are never kept in a project's
    files (the founder: "intake and system should be in the projects global data
    not in the projects own db").
    *   `intake` holds the base map's fields. Wants is a layer in it (R-6.22).
        Its data stays in `map.json`. It is kept out of the `layers`
        dictionary, and the layer itself cannot be deleted (the founder: "wants
        is a layer but its in a reserved group called intake which keeps it
        from appearing under layers or being accessible to delete").
    *   `system` holds the system layers: `skills`, `memory` and `sources`
        (the founder: "there is also system layers like skills and memory system
        layers can only be manually created by editing the code"). A system
        layer's data at an element is a layer file, like any other layer's.
    *   `memory` is a system layer, but it is read and written only through
        the memory module's own tool, not through `project-map`. See "The
        memory module".
    *   Agents write data to these layers at an address with `add`, `update`
        and `delete`, as they do for any layer. They have no control over
        whether the layers exist (the founder: "agents can assign data to these
        layers at the address they just have no control over the existence of
        these layers"). A new intake field or system layer is added only by
        editing `metaform/server/groups.json` (item 13).
    *   `{"layer": {}}` lists neither group. `{"layer": "wants"}` and
        `{"layer": "skills"}` are refused with `LAYER_NOT_REGISTERED`.
    *   A `layer` command that names a field in `intake` or a layer in `system`
        is refused, so no project layer can replace or shadow it.
    *   Setting one of these layers to `null` at an element removes that
        element's data, not the layer. `{"skills": null}` removes the
        element's skills file. `{"wants": null}` removes all of that element's
        wants, as `null` does for any field (R-5.5). Today it removes nothing,
        because wants are not stored as a field (`commands.ts:78`), so this is
        fixed. A single want is still removed with
        `{"delete": {"<address>": {"wants": ["<other address>"]}}}`.
*   `layer` is one command, one log entry and one announcement, like the
    others.
*   The same command lists layers (the founder: "to list layers just use the
    layer command and send nothing, but it only lists the layers in the layers
    key, and the names only not its contents to list its contents send layer
    plus the layer name"):
    *   `{"layer": {}}` returns the names in the `layers` dictionary as a
        dictionary with empty values, for example
        `{"features": {}, "porting": {}}` (the founder: "layers are a dictionary
        with curley braces"). It returns no definitions, and nothing from
        `intake` or `system`.
    *   `{"layer": "features"}` returns that layer's entry in the `layers`
        dictionary: `{"features": {<its definition>}}`. A name that is not
        registered is refused with `LAYER_NOT_REGISTERED`. **(agent's
        choice)** for the string form and the result shapes.
    *   Both are reads. They do not wait for the queue, write nothing to the
        log, and are not announced.
    *   "Its contents" is read as the layer's entry in the `layers` dictionary,
        not its data across the map. A layer's data is read at an address
        (R-5.21), because detail comes only from reading an actual address.

### The memory module

Memory is a module with its own tool (the founder: "you can make a dedicated
memory tool"; "make memories a module"). Tools are organized by module, and a
module exposes a tool (R-5.26), so memory does not add commands to
`project-map`. The tool exists for context management: it keeps durable facts
about the project at the addresses they come from, so an agent finds them where
it works.

*   **Commands identical to the canonical server.** The tool's commands are the
    modelcontextprotocol.io memory server's, unchanged: `create_entities`,
    `create_relations`, `add_observations`, `delete_entities`,
    `delete_observations`, `delete_relations`, `read_graph`, `search_nodes`
    and `open_nodes`. A memory is an entity with a `name`, an `entityType` and
    `observations`. A relation has `from`, `to` and a `relationType` in active
    voice. No command says where a memory goes (the founder: "you dont specify
    where you want to assign memories the memory command is identical to the
    canonical memory command").
*   **The graph depends on where the agent is.** Each address has its own
    memory graph. The tool shows and changes the graph of the address where the
    agent is, which `goto` sets. The only way to read or write an address's
    memories is to be at that address (the founder: "it shows a differeent memory
    graph depending where ytou are.. that means the only way to read and write
    those memories is via presence at that address"). That address is each
    memory's origination address. `read_graph` returns this address's graph
    only. A call made before any `goto` is refused, with `goto` as the
    remediation.
*   **Links.** The graph grows by naming existing memories, and a relation can
    link to any memory or address (the founder: "they can name any address or
    memory to link to"), so a memory can bridge two addresses. `to` is first
    looked up among the memories here; if none has that name, it is read as an
    address. A link to neither is refused. **(agent's choice)** for reading an
    address from `to`, which keeps the commands identical to the canonical
    ones.
*   **Presence.** `goto` binds the agent's present address to its connection,
    as the project is bound (see "Routing a call to its project"). Both tools
    share the connection, so `project-memory` uses the address `project-map`
    went to. Session state belongs in the agents module, held against the
    agent's identity (the founder: "thats where the session state has to live").
    That module comes after this design, so until it exists the connection
    stands for the agent (R-8.2).
*   **Storage.** The module owns no files. It sends every write through the
    functional map server's project queue and log, because the functional map server is the only
    writer (R-4.4). An address's graph is stored in
    `layers/memory/<address>.json`, as the memory server's entities and
    relations. A memory's name is unique within its address's graph.
*   **Removal.** Removing a memory removes the relations that name it, as the
    memory server does. Deleting an element removes the relations, at any
    address, that link to it, in one command and one log entry.
*   **How it plugs in.** The chassis is not part of this design, so the map
    server brokers the module (R-5.13). On each connection it lists both
    tools and routes each `tools/call` by tool name. A `project-map` command
    that writes the `memory` field is refused, and its remediation is the
    matching `project-memory` command. `goto` shows the memory count of the
    address. When the chassis exists, it can host the module instead.
*   **Agent's choices:** the tool name `project-memory`, reading an address
    from `to`, presence held per connection, names unique within an address,
    and removing links when a memory or an element is removed.

### Modules and the data controller

The founder: a module passes control of only the parts that need the chassis,
decided by presence at start-up, and keeps the rest itself (R-2.11, "K.I.S.S.").

*   **The boundary.** Every write is already an effect of final values, so the
    party that commits an effect is the one that controls the data, whoever
    built it. The boundary between a module and its data controller is three
    calls: `submit(project, effect, handshake)` returns a sequence number,
    `subscribe(project)` gives committed entries, and a read of committed
    state. The functional map server's store implements it. **(agent's choice)**
*   **Standalone.** With no chassis, the functional map server is its own controller,
    with `log.db` and the JSON files, and any harness can use it as an
    ordinary MCP server.
*   **With a chassis.** At start-up the functional map server checks whether a chassis
    holds the controller role. If one does, the functional map server submits the parts
    that matter for deep integration through it and keeps the rest itself.
    The file and log formats do not change, so nothing migrates. Control never
    moves while running. Which parts move, and how presence is detected, are
    decided when the chassis is specified; this design builds only the
    boundary.
*   **The first user is memory.** The memory module already keeps no files of
    its own and submits its effects through the functional map server's controller. It is
    built against the boundary, not against the store's inside.
*   **Module synergy.** Every module keys its data by functional address, so
    modules meet at addresses without calling each other. Each module
    declares: its tool; its layers; its part of the `goto` summary sheet; the
    commands it unlocks in other tools (R-5.26); and the committed changes it
    listens to. The functional map server, or the chassis when present, composes the
    declarations, so a new module adds to `goto`, search and the event stream
    without changes to other modules. In this design, memory declares the
    `project-memory` tool, the `memory` system layer, the memory record count
    in `goto`, and that it listens for element deletes to drop links to them.
    **(agent's choice)** for the declaration's parts.

### The write path

Each project has one write queue (position 20). The registry and settings
share another.

1.  A `tools/call` arrives on an agent's connection.
2.  The server checks the command's shape in the agent's snake_case form:
    the contract, the name rule and the field grammar. These checks need no
    map. A failure is refused with code, rule, reason and remediation
    (position 23), and nothing changes.
3.  The command waits in its project's queue.
4.  The server runs every check that reads the map, against the committed
    state: an element that something still wants, a want or link that names
    nothing, an unregistered layer, a second Definitive element. A failure is
    refused, and nothing changes. Running these inside the queue keeps two
    agents from both passing a check that only one can satisfy. This is how
    the current code works (`commands.ts:153-165`).
5.  The server computes the command's **effect** on a copy of the state. An
    effect holds final values, never changes: each touched element's whole
    record or `null`, each touched layer file's whole content or `null`, and
    each touched layer definition or `null`. Applying an effect twice gives
    the same result.
6.  The server converts the effect's keys and address segments to camelCase,
    inserts it into `log.db` with the next sequence number, the time and the
    connection's handshake, and commits (`synchronous = FULL`). **This is the
    commit point.**
7.  The server applies the effect in memory, then writes each touched file:
    to a temporary file, synced, renamed into place, then the folder synced.
    It then records the entry as applied in `log.db`.
8.  The server answers the agent, in snake_case.
9.  The server sends the entry to the project's subscribers.

**Recovery.** A failure before step 6 changes nothing. At start-up the server
loads each project's files and applies every entry after the last one recorded
as applied. Effects hold final values, so applying one that already reached
the files is harmless. If anything fails after step 6, the server reloads that
project from its files and the log; if the reload fails, the project is marked
failed and refuses calls with the reason. The log keeps every entry as the
history of changes (`DECISIONS.md:21`).

**Registry and settings** are single files. Each change rewrites its file in
the same temporary-file and rename way, which is atomic on its own.

### Reads

Reads do not wait for the queue. They read the last committed in-memory state
and convert it to snake_case on the way out.

*   **Address read** `{"code.engine.game": {}}` returns the element's own
    fields, without its wants. `{"code.engine.game": {"layers": ["wants"]}}`
    returns its wants, as any named layer comes back (R-5.21). The read never
    returns what relies on the address, attached layers, skills or memories;
    that takes `goto` (the founder: "you can view the wants and specify to view
    the wants like address wants, what you wont do is get the full breakdown of
    who or what relies on the address, or the wants and the attached layers
    that requires using goto"). **(agent's choice)** for naming wants through
    `layers`. The result keys the element by its address:
    `{"code.engine.game": {"name": "game loop", "name_length": 1, "role": "DE"}}`,
    with `"wants": {...}` added when it is named. Field names stay as the store
    has them until the R-3.4 renames.
*   **Goto** `{"goto": "code.engine.game"}` places the agent at the address and
    returns what CUJ 1 lists: the element and its wants; the full breakdown of
    who or what relies on the address, which is each element whose wants name
    it, with that want's `why`, `how` and `intent`; the names of the attached
    layers, meaning the layers with a file at that address (the R-6.6 walk
    waits for D-7 and D-13), not their content; the frontmatter of its skills; and its memory count (the founder:
    "when you use goto, thats what triggers showing the frontmatter for the
    skills, showing the memory count and all of that stuff"). `goto` changes no
    data, so it does not wait for the queue and is not logged or announced.
    **(agent's choice)** for including each dependent's want in the breakdown.
    **The arrival is a summary sheet.** A layer can carry any data, but the
    system prescribes the minimal dump that arrives when an agent reaches a
    functionality. Knowledge arrives as record counts, not records, in one
    JSON document shaped to describe the node and show where its data lives
    (the founder: "the knowledge gets dumped as a summary sheet, that means
    record counts not records it can arrive as a single json document that is
    shaped to describe the node and present the structure where the data
    lives"). The first `goto` to an address returns:

    ```json
    {"at": "code.engine.game",
     "element": {"name": "game loop", "name_length": 1, "role": "DE"},
     "wants": {"code.render.frame": {"goal": "...", "function": "...", "intent": "outbound"}},
     "relied_on_by": {"code.input.poll": {"goal": "...", "function": "...", "intent": "inbound"}},
     "layers": {"features": {"records": 2}, "porting": {"records": 1}},
     "skills": {"rust_build": {"name": "rust_build", "description": "..."}},
     "memory": {"records": 3}}
    ```

    *   `layers` names each layer with data here and its record count. The
        records themselves come from a layer read at this address.
    *   `skills` holds the frontmatter of the skills attached here. This is how
        an agent learns a skill exists, at the moment it is relevant.
    *   `memory` is the record count of this address's memory graph, read
        through `project-memory`.
    *   **(agent's choice)** for the key names and the `records` form.

*   **Skills live in the functional map server and are never gated.** Skill entries are
    the `skills` system layer, stored at the addresses they apply to. Any
    agent can trigger any skill at any time; nothing checks where it stands.
    What it does not get is the context to know a skill exists until it is
    relevant, which `goto` supplies (the founder: "our skills will be in the mcp
    server...nothing stops you from triggering a skill, nothing gates
    triggering a skill, but agents dont get the context to know the skill
    exists until its relevent"). A skill's body is read by name with the MCP
    resource template `skill://{name}`. `resources/list` does not list skills,
    so an agent learns their names only from `goto`. A skill's name is unique
    across the project. **(agent's choice)** for the resource template; the
    other choice is a `project-map` command such as `{"skill": "<name>"}`.

*   **Goto delivers once per context.** The first arrival at an address
    delivers its information. Moving away and back in the same context does
    not deliver it again; only information that has changed since it was
    delivered comes back (the founder: "goto only dumps new info IF the info
    changes its once per context! so first arrival, from there if you move
    between nodes you will not get that dump a second time in the same
    context"). This is the single delivery of context blocks in `TOPOGEE.md`.
    *   The server remembers, for each address, the content of each part it
    delivered: the element, its wants, what relies on it, the attached layers,
    the skill frontmatter and the memory count. On a later `goto` to the same
    address it returns only the parts whose content differs, and the agent's
    presence still moves. With nothing changed, it returns
    `{"at": "<address>"}`. **(agent's choice)** for tracking by part and for
    that reply.
    *   Until the agents module gives agents an identity, born out of their
    first context, one connection is one context, so a new connection starts
    with nothing delivered. That module will hold this record against the
    agent, and its handoff resets delivered parts to unread, as `TOPOGEE.md`
    describes.
    *   **The record can be wrong, so being wrong is cheap.** A harness can
    compact an agent's context while its connection stays open, and a plain
    MCP client sends no signal when it does. The server then believes the
    agent still holds parts it has lost. Two rules keep this cheap. Each part
    stays small, so sending it again costs little. And a `goto` to the
    address the agent is already at returns every part in full, so an agent
    that has lost its bearings recovers by going to where it is, with no
    extra argument to remember. Where ACP reports a compaction (through the
    agents module), the record resets on that signal instead. There is one
    record of what was delivered, and no markers or checks that test what an
    agent remembers. **(agent's choice)**, from the earlier system's
    experience: its two delivery ledgers disagreed, a `compacted=true` flag
    depended on agents noticing their own compaction, and the machinery grew
    by thousands of lines without proving what a model still held
    (`metaform-tasks` `src/metaform/modules/agents/context.py`,
    `src/metaform/shown.py`; reported by the session reviewing that code).
    *   Arriving at an address is also how an agent will read the address
    inbox (R-6.23; the founder: "that is also how you get to read the inbox is by
    arriving at the address"). The inbox comes later, so this design builds
    only the delivery rule it will use.
*   **Layer read** `{"code.engine.game": {"layers": ["skills"]}}` returns the
    named layers' content at that address (R-5.21), as
    `{"code.engine.game": {"skills": {...}}}`. This is also how an agent
    gets a skill's body. The contract's read value changes from an empty object
    to an object that may hold `layers`.
*   **Root read** `{".": {}}` returns
    `{"addresses": [...], "edges": [["holder", "other"], ...], "definitive": "<address>"}`.
    An edge runs from the element that holds the want to the element it names.
    It carries no `why`, `how` or `intent` (position 13). `addresses` lists
    every stored element, including the trunk elements a write created.
    The Definitive element is the one whose `role` is `DE`, the value the
    intake writes today (`metaform/Intake.md`); `definitive` is `null` when there is
    none. A write that would make a second `DE` is refused with
    `ROLE_TAXONOMY_FAILURE` (R-5.24). **(agent's choice)**
*   **Listing layers** uses the `layer` command, as given under "Adding a
    layer". It replaces the root read `{".": {"layers": []}}` of R-5.22.
*   **Search** `{"search": "pktring"}` matches the text against every value and
    every address path, ignoring case, in the map and in the layer files at
    each address. It returns a bare array of lines:
    `Found: "code.bar.foo"` for a match in the element, and
    `Found: "code.bar.foo" in "baz" layer` for a match in a layer. Results stop
    at 50, followed by one line giving the number not shown.
    *   A match is a substring match, ignoring case, against the agent's
        snake_case form, so `dead_letter` finds a stored `deadLetter`.
    *   One line per address for the element, and one per address and layer.
        A match on a trunk segment reports the trunk element's address.
    *   Lines are ordered by address, element lines first.
    *   When more than 50 match, the last line is `"<n> more not shown"`.
    *   **(agent's choice)** for the layers searched, the match rule, the order
        and the cap.

### Announcements

Each committed entry is sent to the project's subscribers on the socket: the
project, the sequence number, the addresses it touched, and the effect in
snake_case. A new subscriber first gets a snapshot (see "Connections and the
handshake"), so it never needs a separate full read or a catch-up request. The
first subscriber is the viewer server, which relays to the browser over
WebTransport. The viewer's 1.5-second copy-and-export loop is removed.

### Names, validation and refusals

*   A name segment is valid only if it is lowercase words joined by single
    underscores, each word starting with a letter. Anything else would not
    convert back to the same snake_case, and is refused with
    `NAME_ROUND_TRIP_FAILURE`. The reason names the rule broken, for example
    "an underscore before a digit does not survive storage", and the
    remediation is the corrected address: digits joined to the word before
    them, capitals lowercased, repeated underscores made single.
*   This rule is checked in code, not in the contract's patterns. Those
    patterns are shared with the protected `metaform/metaform.schema.json`, and the
    contract checks fail unless both match (`metaform/tests/check_contract.py:165-167`,
    `tools/verify_bootstrap.py:58-61`). The schema is left as it is.
    **(agent's choice)**
*   The conversion between snake_case and camelCase happens in one place: the
    store, when it reads and writes files and log entries. Everything above the
    store, the checks, effects, reads, search, refusals and announcements,
    works in the agent's form, so nothing has to find addresses inside values
    or sentences. Values are never converted: free text, URIs, `name`, record
    names in a named layer, and content in an outside format such as SEP-2640
    skill entries. **(agent's choice)**
*   Every refusal is `{"code", "rule", "reason", "remediation"}`. The codes are
    those of R-5.24, plus these, marked Proposed in R-5.24 until the founder
    confirms them: `NAME_ROUND_TRIP_FAILURE`, `PROJECT_NOT_REGISTERED`,
    `VERSION_MISMATCH`, and, for checks R-5.24 has no code for, `NOT_FOUND`
    (an address that does not exist), `ELEMENTS_BENEATH` (a delete with
    elements under it), `WANT_INCOMPLETE` (a want or layer definition missing
    a field), `PROJECT_FAILED` (a project that failed to load), `NOT_PRESENT`
    (a memory call before any `goto`) and `INTERNAL_ERROR`.
    **(agent's choice)** for the added names.
*   A schema failure is mapped to `GRAMMAR_CONSTRAINT_VIOLATION`, with the
    failing path and a reason in plain words. The validator's own message is
    never the answer an agent receives.

### What changes in the existing code

*   `store.ts` loses Ladybug. The `Store` class keeps its role: one project's
    committed state in memory, the conversion at its edge, and the file writes.
    The commands keep reading through it (`get`, `all`, `receivers`,
    `hasChildren`), and they write by building an effect. The store implements
    the data-controller boundary (`submit`, `subscribe`, committed reads).
*   `log.ts` is new: the SQLite log and the lock.
*   `home.ts` keeps the registry and settings logic, on JSON files, and stops
    registering projects on lookup.
*   `commands.ts` keeps the command grammar, refusals and remediations, and
    gains `layer` and the map checks inside the queue. `reads.ts` and
    `search.ts` hold the reads, `goto` and search.
*   `main.ts` becomes the CLI. `daemon.ts` is the server, and `forwarder.ts`
    is what a harness starts.
*   `@ladybugdb/core` leaves `package.json`. No data is migrated: existing maps
    are cleared, and new test intakes build them again (the founder: "no data
    needs to move because we need to clear and do test intakes anyway").
*   The tool is renamed `project-map` in the contract and its tests
    (position 15).

## Alternatives Considered

### Alternative A: Keep the map in Ladybug, owned by a long-running chassis

This was the specification as written: R-4.1, R-4.4 and R-4.5.

*   **Pros**: Graph queries in Cypher; transactions with rollback; recovery
    after a crash built in; indexes for large data; `store.ts` and its tests
    already work on it.
*   **Cons**: One read-write process per file, so the viewer copies the database
    to read it. No change feed. A native binary for each platform. (The missing musl build
    is not a concern: the founder notes that no harness runs on musl.) A map that cannot be read, compared or kept in
    version control. Its strengths go unused for a 40 KB map with one writer.
*   **Reason for Rejection**: Rejected by author. The map, layers, settings and
    registry are JSON, provided that a live server tracks all projects and is
    the sink for every agent's MCP server (position 14). Ladybug may return
    later as an index rebuilt from the files, never as the original copy (see
    Future Improvements).

### Alternative B: A plain map file with no running process

This was the first hypothesis of the brainstorm.

*   **Pros**: No process to start, stop or recover.
*   **Cons**: Nothing announces a change, so a live view has to poll. Nothing
    puts writes from several agents in order.
*   **Reason for Rejection**: Rejected by author. The map has a running back
    end that applies commands and announces each change (position 9), and the
    viewer must not poll ("you know this kinda sucks there cant be a running
    process it talks to?").

### Alternative C: The chassis is the process that owns the map

*   **Pros**: One process for the map, settings, modules and events.
*   **Cons**: Ties the map to a part with a much larger scope, and to a chassis
    language (D-9) that is not decided.
*   **Reason for Rejection**: Rejected by author. The functional map server "is a process,
    not the chassis". The chassis is a separate part of a larger vision, and it
    hooks the functional map server when both are present (position 10).

### Alternative D: Each agent's server process opens the store directly

This is how `mcp-server/` works today.

*   **Pros**: No shared process. Each agent starts what it needs.
*   **Cons**: A second writer on the same project is refused by the lock. No
    process can announce a change to anyone other than its own agent.
*   **Reason for Rejection**: Rejected by author. Each agent's instance becomes
    a forwarder to the one server, and only one server can start (position 22).

### Alternative E: Reads that return detail for the whole map or a subtree

This is R-5.10 and R-5.11 as written.

*   **Pros**: One call returns everything beneath an address.
*   **Cons**: Detail about addresses the agent does not work on fills its
    context. That breaks the aim of exactly what is needed (position 8).
*   **Reason for Rejection**: Rejected by author. "You can ONLY get detail by
    reading an actual address." The root read is a connected index with only the
    Definitive functionality marked (position 13).

### Alternative F: Other names for the tool

The names considered were `metaform_apply` (the current name), `topomap` and
`project_map`.

*   **Pros**: `metaform_apply` needs no change. `project_map` has no character
    that any client could reject.
*   **Cons**: `metaform_apply` describes one action and a name agents cannot
    reason from. `topomap` is a coined word that reads as "topographic map".
*   **Reason for Rejection**: Rejected by author. The tool is `project-map`
    ("dash if its allowed"). A dash is allowed by MCP, Claude and OpenAI. A
    harness that turns tools into code functions has to rename a dashed name,
    which is the remaining risk.

### Alternative G: The command log as history only, or no log

*   **Pros**: Fewer parts. No replay and no sequence numbers.
*   **Cons**: A crash between two file renames in one command leaves a partial
    change, against R-5.8. Without a log there is also no history of changes
    (`DECISIONS.md:21`) and no sequence for subscribers to catch up from.
*   **Reason for Rejection**: Rejected by the agent at the author's request
    ("please make recommendation"). The log is the commit point (step 6 of the
    write path).

### Alternative K: A log written by hand in JSON lines

This was the first version of this design: segment files, a sequence number in
every JSON file, and archiving.

*   **Pros**: No second storage format. The log can be read with any text tool.
*   **Cons**: Its own rules for a half-written last line, rotation, archiving
    and folder syncs. A sequence number inside every file, including layer
    files in an outside format. A separate lock file and a process-id check,
    which can let two servers run after a crash.
*   **Reason for Rejection**: Rejected by the agent under the founder's rule to
    choose the best tool for the job. SQLite does crash-safe appends and reads
    by sequence number, and its exclusive lock keeps one server running and is
    released when the holder dies. It is built into Node, so it needs no native
    add-on.

### Alternative H: A forwarder that holds the tool contract

In this alternative the forwarder is a full MCP server that validates calls and
passes on only the tool calls.

*   **Pros**: Bad calls are refused before they reach the server.
*   **Cons**: Every forwarder carries a copy of the contract and the conversion
    rules, and an old forwarder differs from an upgraded server.
*   **Reason for Rejection**: Rejected by the agent at the author's request. The
    forwarder is a byte pipe, and the contract lives only in the server.

### Alternative I: Direct HTTP access for agents in the first version

*   **Pros**: A harness that supports HTTP needs no forwarder.
*   **Cons**: Without agent identity (D-8), any local process could write any
    project. It also needs a new dependency, `@modelcontextprotocol/node`.
*   **Reason for Rejection**: Deferred by the agent at the author's request.
    Forwarders cover every harness. HTTP can be added once identity exists.

### Alternative J: Chassis modules add commands to the one tool

*   **Pros**: Agents see one tool.
*   **Cons**: Puts commands for unrelated functionality, such as messaging, in
    the map's tool.
*   **Reason for Rejection**: Rejected by author. Tools are organized by module:
    a module exposes a tool, and tools that act on the same functionality
    collapse into one (position 11). The founder later added that a new module
    can unlock commands and features under other tools that do not come from
    that module directly (R-5.26). A module's own functionality, such as
    messaging, still goes in its own tool. What the agents module may unlock
    under `project-map`, such as reading the address inbox on arrival, is
    specified with that module.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security**: The socket and every file under the home are readable and
    writable by the user account that runs the server (mode `0600`, folders
    `0700`). The functional map server opens no network port. Until agent identity
    exists (D-8), the trust boundary is the user account: any process running
    as that user can connect to the socket. The viewer server's WebTransport
    listener binds to `127.0.0.1` only and carries no write commands.
*   **Performance**: A write costs one SQLite commit plus one synced
    temporary-file write and rename for each touched file. This has not been
    measured; the design is built for maps of tens of kilobytes and a handful
    of agents. Reads do not wait for writes. Search scans memory and the layer
    files; an index is added only after a measured search is too slow
    (R-5.20). Projects, layer files included, are loaded into memory when the
    server starts, so no request reads from disk: reads, `goto`, search and
    snapshots all work from memory, and one slow request cannot hold up the
    others behind a disk read.
*   **Rollout and rollback**: The old entry point `node src/main.ts <folder>`
    stops serving MCP once the server exists, and says to use the forwarder.
    Rolling back means checking out the previous commit. No data needs
    restoring while maps are rebuilt by test intakes.
*   **Isolation**: An unexpected error before the commit point fails only the
    request that caused it, with `INTERNAL_ERROR`. After the commit point it
    reloads that project. A project whose files fail to load is marked
    failed, refuses calls with `PROJECT_FAILED`, and leaves other projects
    working.

## Risks

| Risk | Handling |
|---|---|
| The server dies while agents are connected | Forwarders exit. The next forwarder a harness starts restarts the server. A harness that does not restart its MCP server loses the tool until its next session. Accepted for version 1. |
| A crash during a write | The SQLite commit is the commit point, and effects replay safely (see "The write path"). |
| A compaction leaves `goto` believing the agent still holds parts it lost | Parts are small, and a `goto` to the address the agent is already at returns every part in full. An ACP compaction signal resets the record once the agents module exists. |
| A retried `add` appends twice | Accepted for version 1. Request ids are a future improvement. |
| A harness rejects the dashed tool name | Accepted. A dash is allowed by MCP, Claude and OpenAI. |
| A full disk | The write fails before or after the commit point and is handled as above. Accepted. |
| Windows | Not supported in version 1. |
| The home is on a WSL `/mnt` drive, where SQLite locks are unreliable | The server refuses to start there and names the reason. |
| The log grows | Every entry is kept as history. Accepted until its size is measured to matter (R-5.20). |
| WebTransport cannot be made to work in the viewer | Stop and report to the founder. `DECISIONS.md:15` rules out a WebSocket fallback. |

### Additional Resources

*   [`metaform/docs/designs/metaform-server.md`](metaform-server.md):
    the brief, with the founder's positions 1–23.
*   [`metaform/docs/designs/metaform-server-round2.md`](metaform-server-round2.md):
    round 2 review findings.
*   `TOPOGEE.md`, `metaform/SPEC.md`, `DECISIONS.md`, `AGENTS.md`,
    `docs/pushback.md`.
*   `metaform/verification/ladybug-spike-2026-10-30.json`: the lock behaviour.

### Future Improvements

*   **A search index**: Ladybug, or another engine, as an index rebuilt from the
    JSON files, if a measured search is too slow. It never holds the original
    copy.
*   **Direct HTTP access for agents**: Once agent identity (D-8) exists.
*   **The chassis hook**: How the chassis registers outside layers, receives
    announcements, and offers its modules' tools.
*   **Request ids for retries**: A caller-supplied id so that a retried `add`
    does not append twice.
*   **Windows**: Named pipes in place of the Unix socket.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Build in this order. Each step leaves the code building and every test passing,
and ends with a feature commit and push under `AGENTS.md`. Each step changes
the contract only for the commands it builds, and updates the contract's copy
in `metaform/SPECIFICATION.md` in the same step, because `tools/verify_bootstrap.py`
fails unless the two match. All paths are relative to the repository root.

1.  Names and refusals, on the current store.
2.  The JSON store, the SQLite log, and layers. MCP is still served over stdio
    by `main.ts`.
3.  The server, the forwarder, the CLI and routing.
4.  Reads, `goto` and search, then the memory module (Step 4b).
5.  Announcements and the viewer.

The specification and founder-boundary edits that an earlier draft listed as a
sixth step are already made (commit `1f9c262` and later).

No data is migrated. Existing maps are cleared and rebuilt by test intakes.

**Tests.** At most five tests per feature, through the public interface
(`CLAUDE.md`). Each step edits the tests it breaks in that step. New tests are
appended to `metaform/server/test/metaform.test.ts`; when that file would pass 500
lines, the tests of one feature move to a file named for it, and the `test`
script runs every file in `test/`. Python contract cases go in
`metaform/tests/check_tool_input.py`, which has the command helpers.

### Target Files to Create/Modify

#### Step 1: Names and refusals

##### 1. `metaform/mcp-tools.proposed.json` (Modify)

*   **Type / Scope**: Tool contract (protected; the name change is authorized
    by position 15 and R-5.1).
*   **Proposed Changes**: The tool `name` becomes `project-map`. The address
    patterns do not change (see "Names, validation and refusals").

##### 2. `metaform/SPECIFICATION.md`, `metaform/SKILL.proposed.md` (Modify)

*   **Type / Scope**: Draft specification with the contract appendix; proposed
    agent skill (protected prompt material).
*   **Proposed Changes**: Copy the new contract into the appendix. Replace
    `metaform_apply` with `project-map` in `metaform/SKILL.proposed.md`, in the
    appendix's copy of it, and at `metaform/SPECIFICATION.md:337` and `:908`. In
    `metaform/SKILL.proposed.md:10`, drop the word "provisional", because R-5.1 has
    decided the name. No other wording changes.

##### 3. `metaform/tests/check_contract.py`, `metaform/tests/check_tool_input.py` (Modify)

*   **Type / Scope**: Python contract checks.
*   **Proposed Changes**: Expect the name `project-map`
    (`check_contract.py:159`, `check_tool_input.py:14`).

##### 4. `metaform/tool-examples.json` (Modify)

*   **Type / Scope**: Example commands and results.
*   **Proposed Changes**: `referenced_delete_error` (lines 52–67) takes the
    new refusal shape, `{"code": "DEPENDENCY_LOCK", "rule", "reason",
    "remediation"}`, because `metaform.test.ts:71` compares it exactly.

##### 5. `metaform/server/src/convert.ts` (Create)

*   **Type / Scope**: TypeScript module.
*   **Proposed Changes**: `roundTrips(segment)` returns whether a segment
    survives the conversion, and the rule it breaks if not. `corrected(address)`
    returns the address with each segment fixed as "Names, validation and
    refusals" describes. The conversion itself is added in Step 2.

##### 6. `metaform/server/src/contract.ts` (Modify)

*   **Type / Scope**: TypeScript module.
*   **Proposed Changes**: `explain()` maps a schema failure to
    `GRAMMAR_CONSTRAINT_VIOLATION` with its path and a plain reason. A refusal
    is built as `{code, rule, reason, remediation}`. The check that the
    contract declares one tool stays.

##### 7. `metaform/server/src/commands.ts` (Modify)

*   **Type / Scope**: TypeScript module.
*   **Proposed Changes**: Each existing check becomes a named function that
    refuses with its code, rule, reason and remediation:
    *   `NOT_FOUND`: the address does not exist (line 21).
    *   `TECHNICAL_NAME_ALIGNMENT_FAILURE`: `name_length` exceeds the segments
        (line 28).
    *   `GRAMMAR_CONSTRAINT_VIOLATION`: the schema fails (lines 31, 155).
    *   `WANT_INCOMPLETE`: a want is missing a field (line 40).
    *   `ELEMENTS_BENEATH`: a delete with elements under it (line 108).
    *   `DEPENDENCY_LOCK`: a delete of an element something wants, with the
        remediation it has today.
    *   `NAME_ROUND_TRIP_FAILURE`: checked on every address in the command
        before anything else, with the corrected address as remediation.

    A refusal keeps `"status": "error"` and the echoed command, as today. The
    R-3.4 field renames and their checks are not part of this design.

##### 8. `metaform/server/src/server.ts` (Modify)

*   **Type / Scope**: TypeScript module.
*   **Proposed Changes**: An unknown tool is refused with
    `GRAMMAR_CONSTRAINT_VIOLATION` in the same shape (line 18).

**Feature "names and refusals", tests (4)**: a segment such as `version_2` is
refused with `NAME_ROUND_TRIP_FAILURE` and the remediation `version2`. A valid
snake_case write reads back exactly as sent. A schema failure returns
`GRAMMAR_CONSTRAINT_VIOLATION` and a reason with no regular expression in it.
A delete of a wanted element returns `DEPENDENCY_LOCK` and its remediation,
and changes nothing. The existing test "a refused command changes nothing"
(`metaform.test.ts:90`) is rewritten into the last of these, not added.

#### Step 2: The JSON store, the SQLite log, and layers

##### 9. `metaform/server/src/log.ts` (Create)

*   **Type / Scope**: TypeScript module.
*   **Proposed Changes**: Opens `log.db` under the home with `node:sqlite`,
    sets `locking_mode = EXCLUSIVE` and `synchronous = FULL`, and takes the
    lock with a write; if it cannot, it throws `ServerRunning`. Tables:
    `entries(project, seq, time, handshake, effect)` and
    `applied(project, seq)`. `append(project, handshake, effect)` commits and
    returns the sequence number. `markApplied(project, seq)` and
    `after(project, seq)` support recovery and snapshots.

##### 10. `metaform/server/src/convert.ts` (Modify)

*   **Type / Scope**: TypeScript module.
*   **Proposed Changes**: Adds `toStored(value)` and `toAgent(value)`, which
    convert keys and address segments between snake_case and camelCase. They
    know which keys are addresses (`elements` paths, `wants` keys, layer file
    names) and leave every value untouched.

##### 11. `metaform/server/src/store.ts` (Modify)

*   **Type / Scope**: TypeScript module.
*   **Proposed Changes**: Removes Ladybug. `Store.open(folder, log)` loads
    `map.json` and the layer files, applies log entries after the last applied
    one, and keeps the state in memory in the agent's form. `get`, `all`,
    `receivers`, `hasChildren` and `layerData(address, layer)` read it.
    `commit(effect, handshake)` appends to the log, applies the effect in
    memory, writes each touched file (temporary file, sync, rename, folder
    sync), and marks it applied. Any error after the append reloads the store.
    `tree.ts` `flatten` and `nest` turn the nested `elements` into addresses
    and back. The existing queue (`store.ts:95-96`) stays the project's write
    queue. For tests only, `METAFORM_FAULT=after-commit` makes the process exit
    right after the append.

##### 12. `metaform/server/src/commands.ts` (Modify)

*   **Type / Scope**: TypeScript module.
*   **Proposed Changes**: Each command builds an effect of final values on a
    copy of the state, inside the queue, and the checks that read the map run
    there. Adds the `layer` command as "Adding a layer" describes. Routes a
    field to `map.json` or a layer file by `groups.json` and the `layers`
    dictionary, and refuses a field in no group with `LAYER_NOT_REGISTERED`.
    `{"wants": null}` removes the element's wants. A second element with role
    `DE` is refused with `ROLE_TAXONOMY_FAILURE`.

##### 13. `metaform/server/groups.json` (Create)

*   **Type / Scope**: Global data, shared by every project; edited by hand.
*   **Proposed Changes**: Holds the two reserved groups of R-6.15. `intake`
    lists the field names the store uses today (`name`, `name_length`, `role`,
    `uri`, `status`, `goal`, `function`, `intent`, `wants`), with the wants
    definition of R-6.17. `system` holds `skills`, `memory` and `sources`, each
    with `named: true`. The server loads it once, when it starts.
    **(agent's choice)** to keep this global data with the server's code,
    because system layers are created only by editing the code.

##### 14. `metaform/server/src/home.ts`, `tree.ts`, `main.ts` (Modify)

*   **Type / Scope**: TypeScript modules.
*   **Proposed Changes**: `home.ts` keeps the registry in `registry.json` and
    settings in `settings.json` files, and removes the two Ladybug settings;
    it still registers a folder on lookup until Step 3. `tree.ts` imports and
    exports on the JSON store, and exports in the agent's form. `main.ts`
    drops `DEFAULT_SIZE`, `DatabaseSize`, the size options and
    `--database <file> --export`, and still serves MCP over stdio for one
    folder.

##### 15. `metaform/mcp-tools.proposed.json`, `metaform/SPECIFICATION.md`, `metaform/tests/check_tool_input.py` (Modify)

*   **Type / Scope**: Contract, its copy, Python cases.
*   **Proposed Changes**: A new `layer` branch takes an empty object, one
    string, or an object keyed by layer name whose definitions require
    `description`, `template`, `fields` and `instruction`, may hold `named`,
    and whose fields require `part_of_speech`, `rule` and `example`. The read
    branch's key pattern excludes `layer`. Copy to the appendix. Add cases: a
    full `layer` command is accepted and not read as an address; one without
    `instruction` is rejected.

##### 16. `metaform/server/package.json`, `package-lock.json` (Modify)

*   **Type / Scope**: Package manifest.
*   **Proposed Changes**: Remove `@ladybugdb/core`.

**The viewer** depends on `--database --export` (`server.mjs:11`), so it does
not work from this step until Step 5. It is an experiment; this is accepted.

**Existing tests** in this step: the tests at `metaform.test.ts:137-165` are
rewritten for JSON files, keeping what they check: each project has its own
folder holding `source.txt`, nothing is written into the project's own folder,
two paths with the same folder name stay two projects, and the project name is
not stored in its map. The settings test (line 167) is removed with the Ladybug
settings; settings are tested again when the first real setting exists.

**Feature "store and log", tests (4)**: an acknowledged write survives a
restart. With `METAFORM_FAULT=after-commit`, an `add` that writes an element
and its data in a registered layer is whole after restart. A corrupt
`map.json` makes that project refuse with `PROJECT_FAILED` while another
project still opens. Concurrent writes are all applied (rewrites the test at
line 106).

**Feature "layers", tests (5)**: `layer` registers a layer, and an `add` of
that field writes `layers/<layer>/<address>.json`, not `map.json`. A `layer`
without its schema, description, sentence or instruction is refused and
changes nothing. A `layer` naming `wants` or `skills` is refused, and an `add`
of a field in no group is refused with `LAYER_NOT_REGISTERED`. A named layer's
data is a dictionary keyed by record name, and an unnamed layer's data is a
list. Setting the field to `null` removes that address's layer file.

#### Step 3: The server, the forwarder, the CLI and routing

##### 17. `metaform/server/src/daemon.ts` (Create)

*   **Type / Scope**: TypeScript module; the long-running server.
*   **Proposed Changes**: Start-up as "Start-up and the single server"
    describes. For each connection, reads the handshake line, then serves MCP
    with `serveStdio(factory, {transport: new StdioServerTransport(socket,
    socket)})` from the MCP SDK (`metaform/SPEC.md` R-8.1), answers the CLI's
    admin requests, or (in Step 5) adds a subscriber. Catches unexpected
    errors per request.

##### 18. `metaform/server/src/forwarder.ts` (Create)

*   **Type / Scope**: TypeScript module; the program a harness starts.
*   **Proposed Changes**: Takes the project folder as its argument, or its
    working folder when none is given. Connects to the socket, starting
    `daemon.ts` detached if nothing answers, and retries for up to five
    seconds. Sends the handshake line, then pipes stdin to the socket and the
    socket to stdout. Exits when the socket closes, writing the reason to
    stderr.

##### 19. `metaform/server/src/server.ts` (Modify)

*   **Type / Scope**: TypeScript module; the MCP surface.
*   **Proposed Changes**: `createServer(project, connection)` takes the
    project's `Store`, or the refusal the connection carries
    (`PROJECT_NOT_REGISTERED`, `VERSION_MISMATCH`, `PROJECT_FAILED`). The
    contract is loaded once by the daemon, not for each connection.

##### 20. `metaform/server/src/main.ts`, `home.ts`, `tree.ts` (Modify)

*   **Type / Scope**: TypeScript modules.
*   **Proposed Changes**: `main.ts` becomes the CLI, sending one admin request
    per run: `register <folder> [--name <name>]`, `--projects`,
    `--settings [<folder>]`, `--set <key> <value> [<folder>]`,
    `--import <file> <folder>`, `--export <folder>`, and
    `server status|stop|restart`. `register` and `server` are read as commands
    before the `<folder>` argument. With only a folder, it prints that MCP is
    now served through the forwarder. `home.ts` stops registering on lookup
    and gains `register(folder, name)`. `tree.ts` import and export run as
    admin requests.

##### 21. `metaform/server/package.json` (Modify)

*   **Type / Scope**: Package manifest.
*   **Proposed Changes**: Add the script `"forwarder": "node src/forwarder.ts"`.
    The `test` script runs every file in `test/`.

**Test setup** in this step: `connect()` (`metaform.test.ts:41-49`) starts the
forwarder with `METAFORM_HOME` set to the test's temporary home. `database()`
(lines 33–37) registers and imports through the CLI. An `after()` hook runs
`server stop` against each temporary home.

**Feature "server and routing", tests (5)**: two forwarders started at once
leave one server running. A forwarder in a subfolder reaches its project. A
forwarder in an unregistered folder gets `PROJECT_NOT_REGISTERED` and the
register command on its first call. After the server is killed, a new
forwarder starts a new one with no acknowledged change lost. `tools/list`
returns exactly the map tool (rewrites the test at line 56).

#### Step 4: Reads, goto and search

##### 22. `metaform/mcp-tools.proposed.json`, `metaform/SPECIFICATION.md`, `metaform/tests/check_tool_input.py` (Modify)

*   **Type / Scope**: Contract, its copy, Python cases.
*   **Proposed Changes**: The read value may hold `layers`, an array of names.
    New branches: `goto` takes one address string, and `search` takes one
    string. The read branch's key pattern also excludes `goto` and `search`.
    The description names the reads, `goto` and search in plain words. Copy
    to the appendix. Add cases: a read with `layers`, a `goto` and a `search`
    are each accepted and not read as an address.

##### 23. `metaform/server/src/reads.ts`, `search.ts` (Create)

*   **Type / Scope**: TypeScript modules, kept apart from `commands.ts` so each
    file stays under 500 lines.
*   **Proposed Changes**: The address read, layer read, root read, the two
    `layer` reads, `goto` with its once-per-context record on the connection,
    and search, as the Technical Plan describes. Until D-7 and D-13 are
    decided, the attached layers at an address are the layers with a file
    there; the R-6.6 walk is added when they are.

##### 24. `metaform/tool-examples.json` (Modify)

*   **Type / Scope**: Example commands and results.
*   **Proposed Changes**: `read_after_role_removal` (lines 84–90) takes the new
    address read shape, because `metaform.test.ts:76` compares it exactly. Add
    one `goto`, one root read and one search example.

**Existing tests** in this step: the test at line 114 ("a read returns
everything beneath it") is rewritten for the new address read.

**Feature "reads", tests (4)**: an address read returns the element's own
fields only, and naming `wants` adds them. A layer read returns that layer's
content. The root read returns addresses, edges and the Definitive address,
with no other fields. `{"layer": {}}` returns only the names, and
`{"layer": "<name>"}` only that layer's entry.

**Feature "goto", tests (4)**: the first `goto` returns the element, its
wants, what relies on it with each want, each attached layer with its record
count, skill frontmatter and the memory record count, and no layer records. After moving away and
back on the same connection, with nothing changed, a `goto` returns only
`{"at": ...}`. After the element's wants change, a `goto` back returns only
the new wants. A `goto` to the address the agent is already at returns every
part in full.

**Feature "search", tests (3)**: a match in an element's `name` returns
`Found: "<address>"`. A match in a layer returns
`Found: "<address>" in "<layer>" layer`. A common word returns 50 lines and
the count line.

#### Step 4b: The memory module

##### 25. `metaform/server/src/modules/memory/tool.json` (Create)

*   **Type / Scope**: The memory module's tool contract.
*   **Proposed Changes**: Declares `project-memory` with the canonical memory
    server's commands and input shapes. Its description says the tool keeps
    durable facts at the addresses they come from, for context management
    (`DECISIONS.md`, "Tool surface is capped").

##### 26. `metaform/server/src/modules/memory/memory.ts` (Create)

*   **Type / Scope**: TypeScript module.
*   **Proposed Changes**: Built against the data-controller boundary, with a
    module declaration as "Modules and the data controller" describes. Takes
    the present address from the connection and
    refuses a call before any `goto` with `NOT_PRESENT`. Turns each command
    into an effect on that address's `memory` layer file, through the
    project's queue. Checks that a name is new to the address's graph and that
    each relation's `to` names a memory here or an existing address. Removes
    relations that name a removed memory. Answers `read_graph`,
    `search_nodes` and `open_nodes` from the present address's graph.

##### 27. `metaform/server/src/contract.ts`, `server.ts`, `commands.ts` (Modify)

*   **Type / Scope**: TypeScript modules.
*   **Proposed Changes**: `contract.ts` loads one contract per module.
    `server.ts` lists both tools and routes each call by tool name.
    `commands.ts` refuses a write to the `memory` field, with the matching
    `project-memory` command as the remediation; deleting an element removes
    memory relations that link to its address.

**Feature "memory", tests (5)**: after `goto` to one address, a memory created
there reads back with `read_graph`, and after `goto` to another it does not.
A call before any `goto` is refused with `NOT_PRESENT` and `goto` as the
remediation. A relation whose `to` names an address links the two, and
deleting that element removes the relation. A relation to neither a memory
here nor an address is refused and changes nothing. A `project-map` write to
`memory` is refused with the `project-memory` remediation. The "server and
routing" test of `tools/list` now expects both tools.

#### Step 5: Announcements and the viewer

##### 28. `metaform/server/src/announce.ts` (Create)

*   **Type / Scope**: TypeScript module.
*   **Proposed Changes**: Keeps each project's subscribers. On subscribe, sends
    the snapshot and its sequence number; after each commit, sends the entry.
    `daemon.ts` hands subscriber connections to it.

##### 29. `experiments/map-viewer/server.mjs`, `index.html` (Modify)

*   **Type / Scope**: Viewer server and page.
*   **Proposed Changes**: The step starts by proving that a browser (Chrome)
    opens a WebTransport session to a Node server with a self-signed
    certificate passed by its hash. The library is chosen in that proof and
    recorded in `DECISIONS.md`. If no library works, the step stops and the
    founder is told. Then `server.mjs` removes the copy-and-export loop and the
    `snap/` folder, subscribes to the functional map server, creates and renews its
    certificate (at most 14 days), serves the page with the hash, and relays
    the snapshot and each entry. `index.html` builds the picture from the
    snapshot and applies each entry. The viewer keeps today's field names
    until the R-3.4 renames.

**Feature "announcements", tests (2)**: a new subscriber receives a snapshot
at the current sequence number. A committed write then reaches it as one
entry with the next sequence number. The browser side is checked by hand, as
the Verification Plan says.

### Verification Plan

*   **Type check**: `cd mcp-server && npm run typecheck`
*   **Node tests**: `cd mcp-server && npm test`, run for the affected feature
    while building and in full at the end.
*   **Contract checks**:
    *   `.venv/bin/python metaform/tests/check_contract.py`
    *   `.venv/bin/python metaform/tests/check_tool_input.py`
    *   `.venv/bin/python tools/verify_bootstrap.py`
    *   `.venv/bin/python metaform/validate_metaform.py metaform/owner-skills-example.json`
    *   `.venv/bin/python metaform/validate_metaform.py metaform/provider-reference-example.json`
*   **File size**: every source file stays under 500 lines (`CLAUDE.md`).
*   **Test intakes**: run `server stop`, clear `~/.metaform`, then run test
    intakes through a forwarder with the newest procedure, `metaform/Intake.md` (Digital Typology Intake,
    version 3.1). It is byte-identical to the founder's `~/brain/intake-new.md`.
    Do not use `metaform/Intake.xml`, which is the older prompt. Keep the viewer open and
    confirm each element appears as its command commits, with no polling.
