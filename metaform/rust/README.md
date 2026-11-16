# Metaform in Rust

The Rust form is the reference form of Metaform. The Node and Python forms repeat its answers exactly (`metaform/conformance`). It is a Cargo workspace of four crates.

| Crate | What it holds |
|---|---|
| `crates/metaform-core` | The map in memory and everything decided about a command: the shape check (`shape.rs`), the address and naming rules, the commands, the reads, the refusals, the layers and the specification layer, and the Markdown export and import. It has no storage and no network. |
| `crates/metaform-store` | The store behind the tool, on LadybugDB. A map is a graph: `Element` nodes, `CONTAINS` for nesting, `WANTS` with `why`, `how` and `direction`, and one `Record` node for each layer record (R-4.16). Maps are partitions of a database: `projects/<id>/project.lbug` for a project, `maps/maps.lbug` for maps that belong to no project (R-4.1). One writer thread for each database serves clients in turn (R-4.7). |
| `crates/metaform-server` | The `metaform` binary: the server, the stdio forwarder and the command line. |
| `crates/metaform-web` | The host of the graph workspace: it serves the built page from `metaform/workspace/dist` and forwards reads to the home's server. It refuses writes. |

## The commands

```text
metaform mcp   [--home DIR] [--project DIR]   stdio MCP for an agent harness; DIR defaults to .
metaform mcp   [--home DIR] --map NAME        stdio MCP on a map that belongs to no project
metaform call  [--home DIR] [--project DIR | --map NAME] '<json command>' | -
metaform projects [--home DIR]                every registered project: id, name, folder
metaform gui   [--home DIR] [--port N]        the graph workspace; prints its address
metaform specification export [--check] | import FILE
metaform settings | set KEY VALUE | unset KEY
metaform serve [--home DIR]                   the server for a home; `mcp` starts it when needed
```

- One server process owns a home (R-4.4). It listens on `<home>/server.sock`, and `server.lock` holds the home. `metaform mcp` starts the server if none is running, names its project folder in one handshake line, and relays MCP. It never writes files (R-4.5).
- The server offers one tool, `project-map`, defined by `metaform/mcp-tools.proposed.json`, over MCP 2026-07-28 and earlier versions through rmcp 3.9 (R-8.1).
- `metaform call` exits 0 on success, 1 on a refusal (which it prints) and 2 on a usage or connection error.
- `metaform gui` serves on `http://127.0.0.1:4170/`, or on a free port when 4170 is in use.
- The home is `--home`, or `METAFORM_HOME`, or `~/.metaform`. A home that holds data this store did not write is refused and left untouched. The path of `<home>/server.sock` must be at most 107 bytes.

## Build and use

```sh
cargo build --release -p metaform-server -p metaform-web
METAFORM_LAUNCHER= cargo test
target/release/metaform call --home ~/.metaform-rust --project . '{"map": {}}'
```

This repository's `.mcp.json` starts `target/release/metaform mcp --home ${HOME}/.metaform-rust --project .`. After a rebuild, a server that is already running for a home still runs the old build. End it, and the next agent that connects starts the new one.

## What an agent receives

- A successful write answers `{"status": "ok"}` (R-5.35). A refusal repeats the command, then gives `status`, `code`, `message` and `remediation` (R-5.24).
- `goto` places the agent at an address and returns the whole summary sheet every time. The server remembers nothing for a connection. The sheet names where a layer's rules are; the rules themselves are at the layer's definition element.
- Each commit is announced to clients that subscribed to the map's resource (R-4.10). Nothing polls.

## Not built

- The list of enabled layers, links and blocks (`SPEC.md`, "Where a layer is active").
- Chaining (R-4.15): the store keeps an element's `child_map`, and no command sets it.
- `search` (R-5.27), tasks (R-5.33), the memory module (R-5.29), tickets (R-5.31), and skills as MCP resources with their push (R-5.32).
- Agent identity (D-8). Until it exists, any process that can reach a home's socket can open any map in that home, and a connection stands for an agent.

The owner has not yet confirmed the grouping of maps into databases (`SPEC.md` D-17).
