# Metaform in Rust

Two crates. The founder has not yet confirmed the stored form (`metaform/docs/designs/metaform-rust.md`, section 4a). Both follow the founder's documentation set and the storage defaults in `docs/designs/storage.md`.

- `crates/metaform-core`: the map model in memory, the address and naming rules, command validation against the contract, the commands and the refusals. It has no storage. The JSON file store it once had was never decided, and it has been removed (R-4.1).
- `crates/metaform-store`: the store behind the one Metaform tool.
  - Maps are realized as a graph in LadybugDB (R-4.16): `Element` nodes, `CONTAINS` for nesting, and `WANTS` carrying `why`, `how` and `direction`.
  - Maps are partitions of a grouping database: `projects/<id>/project.lbug`, or `maps/maps.lbug` (R-4.1 default).
  - One owner per home (`server.lock`, R-4.4).
  - One writer thread per database serves clients in turn (R-4.7).
  - Reads use the last committed snapshot. Each commit is announced (R-4.10).

- `crates/metaform-server`: the `metaform` binary.
  - `metaform serve` is the one functional map server for a home (R-4.4). It listens on `<home>/server.sock`.
  - `metaform mcp` is the stdio forwarder each agent harness starts (R-4.5). `metaform mcp --map <name>` opens a map that belongs to no project instead (R-4.15). The map lives in `maps/maps.lbug` and is created on first write. Until agent identity exists (R-8.2), anyone who can reach the home's socket can open it. It starts the server if none is running, names its project folder in one handshake line, and relays MCP. It never writes files.
  - The server offers exactly one tool, `project-map`, defined by the contract, over MCP 2026-07-28 and earlier versions through rmcp 3.9 (R-8.1).
  - A home that holds data this store did not write, such as the Node harness's `~/.metaform`, is refused and left untouched.

  - `metaform call` runs one tool command from the command line (R-5.14, R-5.17), through the same server: `metaform call --project . '{".": {}}'`, or `-` to read the command from stdin. Exit 0 on success, 1 on a refusal (printed), 2 on a usage or connection error.

Run it: `cargo build --release -p metaform-server`. This repository's `.mcp.json` runs `target/release/metaform mcp --home ${HOME}/.metaform-rust --project .`, so rebuild the release binary after a change. The same home works from a shell: `target/release/metaform call --home ~/.metaform-rust --project . '{".": {}}'`.

- `goto` (R-5.30) places the agent at an address and returns the summary sheet once per connection, then only the parts that changed.

Not built yet: announcements on MCP subscriptions (R-4.10, R-5.32), layers, and starting the server through the service launcher.

Field names follow R-3.4: `technical_name`, the four roles, and `why`, `how` and `direction` in want records.
