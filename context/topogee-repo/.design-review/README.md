# Design review notes

## Where we are

Updated 2026-11-07.

**Founder's goal of 2026-11-07** (Metaform done right and a working Topogee void world, with Jorge).
- Topogee void world: met. Checked on main at 558753b: 35 workspace tests pass, clippy clean, and the web client verified in Chrome 156 (`topogee/docs/screenshots/`).
- Metaform in Rust: not finished. Built: store, fair writer, forwarder, one tool, `goto`, private maps (`metaform mcp --map`), change announcements to subscribed agents (R-4.10), and the server started on demand through the launcher (launcher step 5; checked live against the real launcher: created once, rerun by name after a stop, no duplicate). Waiting on the founder: chaining's form in the tool, layers, the switch of `.mcp.json`. Not built: skills push, tasks. The table is in `metaform/docs/designs/metaform-rust.md`, "Progress".

**Done recently**
- Proof path items 4 and 5: people and agents place code blocks and link them under rights the admin grants (`--admin`, `/grant`, `/revoke`; W-9.9), and blocks show players panels and take their presses. Blocks and programs get an empty WASI, so block code is ordinary Rust (W-7.1a). Remaining on the path: item 6 (code-driven bodies and creatures) waits on the physics engine choice (D-W1).
- Jorge: batched writes where world.lbug ran one transaction per item (schedules about ten times faster, block states 2.1 s to 17 ms for 600), a per-step limit on cell changes and on queued cell events, and a write of a cell's own value changes nothing.
- Redstone emulated in the game, not the server: block types run WASM programs on cell events (placed, broken, used, neighbour changed, scheduled), with state in the cell. Wire, power, lever, light, torch (inverter) and repeater (delay, one way) are content on one shared power rule. An agent built a torch clock through its world tool and it blinks in Chrome. Players and agents use cells (levers) within reach, at 10 a second.
- Terrain generation in a sandbox (Jorge): a WASM generator fills each chunk on first need, recorded per chunk; hills seen in Chrome (`topogee/docs/screenshots/hills-generated.png`), drawn with client chunk meshing (about 128,000 cells in 49 meshes).
- Block ids as content (Jorge): namespaced ids (`topogee:` apart from `minecraft:`), a lasting registry, 64-bit cells (32-bit type, 32-bit state). Scheduled events last across a restart.
- Texture packs: `topogee-pack` imports a community pack's block textures by namespaced id; the client draws them from the atlas. No third-party art committed until D-W11.
- Blocks read and write cells (`topogee:host` voxels interface), within 16 m and 4,096 sets an event.
- Bus security (W-9.8): creating is a right, interacting is open; rules in `docs/designs/world-proof-path.md`.
- The world spec is in Metaform: the intake agent ran the founder's procedure (Intake.md 3.1) on `docs/designs/world-system-spec.md` into the project map in `~/.metaform-rust`, through `metaform call` (Jorge's CLI). 61 elements, 114 wants, Definitive `code.server.world`, orphans only the three downstream users. Questions for the founder are below. The Metaform spec comes next, once he has seen this one.
- M4, building: people and agents place and break cells, stored through world-store and sent to everyone nearby; seen in Chrome (`topogee/docs/screenshots/m4-building.png`) and checked live with an agent through the `world` tool. In progress (Jorge): loaded chunks authoritative in the ECS with a 1 s batched flush (`save_chunks`), damaged chunks refused, block cells reconciled at start.
- Jorge, storage: torn region entries fail one chunk at a time, with the chunk position in each record; Metaform survives SIGKILL under load (25 kills, 0 acknowledged writes lost); the cold-load scan measured at 1,000,000 elements.
- The bus carries data (W-6.5): a message is a kind and its bytes, `topogee:host` 0.2.0, with a 64 KiB cap per message. No block imports WASI.
- Launcher steps 3 and 4: records under `topogee/services`; each service runs as its declared user with exactly its declared capabilities and no new privileges, kept across restarts. Review found and fixed a HoldOn hole: `sudo hold <name>` reran a user-editable record as root.
- Entity ids (Jorge, finding 2 of his review): the counter is raised above every stored block id at startup, so a replaced accounts file never hands out a block's id. The acceptance check proves it; it failed before the fix ("new account id 1 must be above every block id (highest 6)").
- The web client seen in a real browser (Chrome 156, headless, over the DevTools protocol): registration, chat, walking, the machines with labels, a click on the switch lights lamp A, the clock blinks lamp B, no console errors.
- Authentication hardened: hashing on a worker pool with fair turns, failed-login backoff that fails closed, an 8-character minimum, a 4 m range on use, prompt disconnects. Jorge reviewed the accounts store. Jorge's acceptance check (`topogee-acceptance`) proves the definition of done against the real server.
- Topogee M3 merged and live-tested through an agent: the switch lights lamp A, the clock blinks lamp B on its own, the sign greets the agent by name; block state survives a restart. The zstd link clash is fixed at its source (Jorge), and agents link only `topogee-client`.
- Metaform in Rust (Jorge): `metaform serve` (one server per home), `metaform mcp` (stdio forwarder that starts the server), exactly one tool `project-map`, maps as a Ladybug graph in partitions of `project.lbug`, one fair writer per database, two agents on one project at once tested. Verified by Xander: 12 tests pass, clippy clean.
- Topogee M1 merged and live-tested: login, chat, snapshots keyed by id, walking, agent token login. M2 merged and live-tested: an agent through stdio MCP with one tool, `world` (look, move, say, chat). In progress: M3, code blocks on the bus in the server.
- Topogee: workspace and protocol note; `world-store` (Jorge: Anvil-style sections, palette, culling, region files); `topogee-blocks` (WASM runtime, fuel limits, host interface only) with six proof-of-concept blocks; `topogee-agent` (the one world tool); the web client with the founder's agent figures.
- Metaform in Rust, step 1 merged: `metaform-core`, 4 tests passing, clippy clean.

- Service launcher steps 1 and 2 merged: `launcher/` builds; carried tests 91 passed, 1 failed (a HoldOn race), 13 skipped (root).

**Next**
1. Switch this project to the Rust Metaform once the founder says yes (below), then rebuild maps by intake.
2. Launcher step 3: the `topogee service` branch and the store paths outside `~/.metaform`.
3. Launcher steps 4 and 5: the permission steps, then the Metaform server's recipe with on-demand start.
4. Review Metaform's design (`metaform/SPEC.md`), which has not been reviewed yet, with the preprint's claims and R-1.3 measurement in view.

**Waiting on the founder**
- Which physics engine (D-W1: Avian, Rapier or Box3D). It is all that holds back item 6 of the proof path: creatures, dropped items and minecarts driven by code.
- Which community texture pack the simulacrum uses (D-W11): one whose license allows use and redistribution in a private install, with no Mojang assets.
- How specs go into Metaform (from the first intake): map a specification as the system it specifies (done for the world spec) or as a document (`document.*`)? Are builder, AI agent and server administrator the right downstream users? The address names chosen (such as `code.environment.staging` for the admin world, `code.link.data.voxel` for busstone). Answered 2026-11-07: the -ing rule is for technical writing, not for the game (world spec W-11.10); W-3.9's triangle check is superseded by the block-damage approach. Whether Metaform should enforce the rule on technical maps is still open.
- Chaining in the one tool (R-4.15): `{"chain": "<address>"}` to create, and `/` to address inside a chained map (`metaform/docs/designs/metaform-rust.md`, proposal). Recommended: the explicit `/` form.
- Done 2026-11-07: `.mcp.json` "metaform" runs the Rust server with its own home, `${HOME}/.metaform-rust`. `~/.metaform` (the Node harness's data) is untouched and nothing was renamed. The Node server had stopped connecting in this repo ("Connection closed").
- Storage (Jorge's note, `docs/designs/storage.md`, section 4): (1) may a layer's pieces be grouped records in the database rather than one file each (R-6.21)? Recommended: grouped records, each piece keeping its identity. (2) Confirm that "can be given its own db" is a capability, with maps grouped by project and promotable to their own database (R-4.1).
- Whether to update the protected `metaform/metaform.schema.json` and tool contract to section 5.1's names. The build follows 5.1 either way.
- `intent` values: the documentation set (a base verb, such as `receive`), R-6.17 (inbound, outbound or two-way) and `TOPOGEE.md` (send, receive or send_receive) disagree. Intake semantics; the founder's call.
- The unified layer approach in full: how it replaces the root registries.
- The founder's unified layer approach: so far, layer types live in the `layer` namespace and `wants` lands as `layer.wants`. The spec waits for the full description.
- The 117 `[cite: 1]` markers in `metaform/Intake.md` (protected): remove or keep.
- How the project earns income: no plan yet; Metaform leans open source and preprint, so income would come from Topogee. Options are tracked in `register.md`, "Income".
- Metaform's license. Recommended: Apache-2.0.
- The preprint: a DOI through Zenodo, the author line, and a v2 with R-1.3 measurements (see `register.md`).
- D-SL2, taken as a default: AgentSight starts at boot through `/etc/wsl.conf`; the founder can overrule.
- The test-budget exception for carried HoldOn tests (taken as a default; the founder can overrule).
- `TOPOGEE.md` and "Product: Topogee Navigator" still use the old naming.
- World spec D-W11 to D-W15: the texture pack, and the fluids and breakage choices.


Notes kept by Xander, the design reviewer (`.claude/skills/topogee-dev/SKILL.md`). They are memory aids, not authority. The founder's statements, `DECISIONS.md`, `metaform/SPEC.md` and `docs/designs/world-system-spec.md` govern. Check a claim here against those before you rely on it.

| File | What it holds |
|---|---|
| `register.md` | Settled points, open items and conflicts found in review, with sources |
| `log.md` | One entry per review session: what was read, changed and left open |

## The two products

- **Topogee** is the shared world: `docs/designs/world-system-spec.md` (draft, not reviewed by the founder), `docs/world-ideas.md` (brainstorm), `docs/designs/world-agent-prior-work.md`, roundtables 1, 4 to 7 and 20 in `docs/roundtables/`.
- **Metaform** is the context tool for development agents: `metaform/SPEC.md`, `DECISIONS.md`, `docs/designs/metaform-server*.md`, `metaform/Intake.md`.

Older documents call Metaform "Topogee". See `DECISIONS.md`, "Naming: Topogee and Metaform".
