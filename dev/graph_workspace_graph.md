# Graph workspace: layout, rendering, the Rust host and mock data

Status: built and checked in a browser by Jorge (session metaform-33), 2026-11-09, on branch `workspace-mock` (worktree `/home/rich/metaform-ws-mock`), which Ida integrates into `graph-workspace`. The verification record is at the end. Owner decisions on the framework and the open command are still open. This document supports the owner's prompt `dev/user_agent_interfaces.md` and does not change it. The backend seam is Marcus's `dev/graph_workspace_seam.md`, and the screen's terms are Matthew's `dev/graph_workspace_terms.md`. Where this document names a seam type, the seam document governs.

## Specification updates

### 1. Layout: ELK.js, layered algorithm, in a Web Worker

The prototype lays out graphs with `elkjs` (`elk.algorithm: layered`). The direction is top-down (`elk.direction: DOWN`), following Ida's interaction design (UI-U4). The layout runs in a Web Worker, so a layout never blocks input. Mermaid's flowcharts use the same family of algorithm: layered (Sugiyama) layout, with dagre by default and ELK as Mermaid's alternative renderer.

An expanded element is an ELK compound node that holds its children, with `elk.hierarchyHandling: INCLUDE_CHILDREN`, so wants that cross into an expanded element are routed in one pass.

Input order is deterministic: children are sorted by address. The same map therefore gives the same layout (measured below).

Pin the version in `package.json`. The npm registry listed `elkjs` 0.12.1 (modified 2026-10-28). The measurements below used 0.9.3, the copy installed on this machine, so the build must measure 0.12.1 again before relying on these times.

### 2. Rendering: SVG, with one transform for pan and zoom

The graph is drawn as SVG. Pan and zoom adjust one `transform` on a root `<g>`. The zoom percentage shown is that transform's scale. Fit-to-view computes the scale and offset from the layout's bounding box.

SVG fits the measured sizes (at most 167 addresses per project in the mock). SVG also gives keyboard focus, accessible names and CSS states to each element without extra work. Canvas is only worth its cost above several thousand drawn elements. The prototype draws one level at a time, so it does not reach that size.

### 3. How the view builds the drawn graph from the seam

These rules turn `map` (and `dump` for layers) into what is drawn. They are pure functions in `src/graph/`, so views and tests call them without a backend.

- **Graph path.** The view shows the children of one address prefix, the graph path (`""` is the project root, which shows the root scopes). Double-click on an element with children sets the graph path to its address. Ctrl-click sets the graph path to the parent prefix. Breadcrumbs are the prefixes of the graph path.
- **Collapse and expand.** An element with descendants in `map` has hidden descendants until it is expanded. Expanded elements draw their children inside them as a compound node. Collapsed elements show a descendant count. An element with no descendants is a leaf and shows no count.
- **Lifting wants.** Each want edge `[holder, wanted]` is drawn between the nearest drawn ancestor of each end. Duplicate lifted edges merge into one edge with a count. A want whose ends lift to the same element is not drawn; that element shows a count of its internal wants instead.
- **Boundary elements.** If one end of a want lies outside the graph path, the end is drawn as a boundary element at the edge of the view. It is labelled with the address of the outside element at the level where it leaves the graph path. Activating a boundary element sets the graph path to contain it.
- **Element types.** The fill shows the role (Definitive, Supportive, Notable, Divergent, or none yet). A label shows the root scope. The Definitive element from `map.definitive` gets a distinct marker. Elements beneath `upstream`, `downstream` and `layer` are drawn as outside the project. An element whose `uri` is a cross-project link (seam rule 6) is drawn as a link to that project.
- **Layers.** The layer list is the last segment of each address beneath `layer`, plus `wants`. Counts come from `dump`, using goto's rule (seam rule 3). Each layer is visible, hidden or isolated. Visible: elements with records show a badge for that layer. Hidden: no badge. Isolated: elements with no records in that layer and their edges are dimmed, not removed, so the layout does not move. Hiding `wants` hides the edges.
- **Pivot.** Pivoting on an element draws that element and its direct neighbours from `goto` (`wants` and `wanted_by`). The pivot element is placed in the first layer with `elk.layered.layering.layerConstraint: FIRST`. Each pivot is pushed onto a history, so the user can go back to the previous view.
- **Stable viewport on updates.** On `map-changed`, the view refetches, lays out again, and animates elements from their old positions to the new ones. It does not adjust the pan and zoom transform. New or changed elements get an activity mark until the user selects them.

### 4. The Rust host

Built as `metaform-web` (`metaform/rust/crates/metaform-web`). Run `npm run build` in `metaform/workspace`, then `metaform gui` (or `metaform-web [--home DIR] [--assets DIR] [--port N]`). It serves the built React and TypeScript files with its own file handler, and offers the routes in the seam's "Host routes" section:
- `GET /api/projects` lists every project registered in the home, through the server's admin request `projects` (Marcus, ab71e2c). A project registered while the host runs appears without a restart.
- `POST /api/projects/<id>/call` forwards one read command through `metaform_server::call`, the code behind `metaform call`, and returns the result unchanged. A refusal comes back with HTTP 200. Writes are refused with 403, because the workspace only reads; a web page can therefore never change the map through the host.
- `GET /api/projects/<id>/events` is a Server-Sent Events (SSE) stream. `metaform_server::watch` (new) opens `subscriptions/listen` on the connection's map resource, and each `notifications/resources/updated` becomes one `map-changed` event with the data `{}`. The data cannot be empty, because a browser's EventSource drops an event whose data is empty.

The host runs as its own process and is an MCP client of the home socket (Marcus's transport section). Each forwarded read opens a new connection: `metaform_server::call::call` starts a session for every request. The server holds back summary sheet parts that it already delivered unchanged on the same connection, and names them in `unchanged` (R-5.30; `Presence` in `metaform-server/src/tool.rs`). Because every connection is new, the GUI always receives full sheets, so `SummarySheet` has no `unchanged` field and the source keeps no sheet cache. The host must keep one connection per request. If the host ever reuses one connection per project, `SummarySheet` needs `unchanged?: string[]` and the source needs a cache that fills the held-back parts (Marcus, 2026-11-09).

The prototype's browser code still uses the mock source; switching to `MetaformSource` is the seam's verification step, and the prototype must not claim that it is connected.

The host binds to `127.0.0.1` only. It checks the `Host` and `Origin` headers the way `roundtable-web` does (`roundtable/crates/roundtable-web/src/app.rs`, "The Host (and Origin, when sent) must name this server"). Without that check, any web page the user opens could send commands to the map through DNS rebinding.

Placement: a new crate, `metaform/rust/crates/metaform-web`, in the Metaform workspace. The Metaform host must not depend on the Roundtable workspace, and roundtable-web is a different product. It copies roundtable-web's pattern; it does not extend that crate.

Framework: **axum 0.8.9**, the framework roundtable-web already uses. The owner sent the Actix Web link; the evaluation is in the rationale below, and the team voted 4 to 0 for axum (`.taste/VOTE.md`). The owner then said to use whatever works best and to keep axum and elkjs on their merits (relayed by Marcus, 2026-11-09). The host adds no other new crate: `tower-http` was replaced by a 30-line file handler.

### 5. Mock data

`metaform/workspace/src/mock/build_mock.py` writes `workspace.json` beside it, from the project's own maps (branch `workspace-mock`, worktree `/home/rich/metaform-ws-mock`). It reads `metaform/metaform-canonical.json`, `roundtable/metaform.json` and `metaform/intake-example.json`, and writes none of them. Each project is stored as its raw dump (`{".": {}}`, R-5.34). The mock GraphSource derives `map`, `goto` and layer reads from the dump. The mock therefore cannot drift from the read forms. A contract test can check it against the real server later.

| Project | Addresses | Wants | Source |
|---|---|---|---|
| metaform | 119 | 68 | canonical map from the earlier system, plus one outside project |
| roundtable | 167 | 35 | Roundtable's map |
| mashtrac | 13 | 1 | the intake example |

The script makes these adjustments so the dumps match the current specification:
- Role codes become role names (DE is Definitive, SE is Supportive, NE is Notable). CQU is dropped, because it is not a role (R-3.15).
- Roundtable's older want form (a list, with `goal`, `function` and `intent`) becomes the current form (`why`, `how`, `direction`).
- Only intake fields, wants and the sample layers are kept. Older fields such as `references` and `investigations` are dropped (R-6.13). Wants that name a missing address are dropped. The metaform map has four of these.
- `layer.document.specification` is added with the definition the server seeds (R-6.24).
- Specification, memory and skills records are samples, and their text starts with `(mock)`.
- Three cross-project links use seam rule 6: roundtable and mashtrac have `upstream.service.metaform`, and metaform has `downstream.coordinator.roundtable`.
- One outside project (R-4.15, D-16, as corrected in SPEC c7f9eb2): metaform has the single element `upstream.code.engine.workflow` with a `uri` on the reserved `.invalid` domain. The outside project's own map is stored apart (`outside`, keyed by the `uri`) in its own addresses, with `code.engine.workflow` as its Definitive element. The seam reads it through `outsideMap(project, at)` (Marcus, ab4c88a), which returns a `ProjectRef` with id `outside:<uri>`; the ordinary reads answer for that id. For the agent tool, `{"map": "<address>"}` stays the recommended server form, an owner contract decision.
- A first run (`firstRun`): no projects until `simulateIntake()` registers the sample project (`mashtrac`) and fills it one element at a time over about 3 s.
- Three simulated agents (Ida, Marcus, Jorge) and three timed updates are included. Every update and every presence record is simulated, and the file says so (`"simulated": true`).

## Decision rationale

**ELK over dagre and over a Rust or WASM layout.** The view needs compound nodes (expanded elements) with wants that cross their boundary. ELK's layered algorithm routes those edges in one pass when `hierarchyHandling` is `INCLUDE_CHILDREN`. dagre supports compound nodes, but it does not route edges across the hierarchy that way. I found no Rust layered-layout crate with compound nodes. That conclusion comes from my own knowledge, not from a search. If one exists, it would need a WASM build and gives no measured benefit at these sizes.

Measured with elkjs 0.9.3 on Node 26.13.0, on the canonical map (109 addresses and 60 wants that resolve; probe in this session's scratchpad):

| Layout | Time |
|---|---|
| Whole map, every element expanded as compound nodes | 352 ms cold; 125–166 ms warm |
| One level (children of `code`: 36 elements, 49 lifted wants) | 38 ms |
| Determinism | four runs gave the same 2433 × 1862 bounding box |

These times are in Node, not in a browser worker, and on one machine. The one-level case is the common one and is well inside one animation's duration. The confidence that a browser worker shows similar times is moderate. The build should measure it there.

**Dimming, not removing, for an isolated layer.** Removing elements would lay out the graph again and move it under the user's eye. The prompt asks that orientation be kept.

**Actix Web compared with axum 0.8.** The owner sent `https://actix.rs/`. I built two hosts of the same shape: static files from a directory, `POST /api/call` echoing JSON, and `GET /api/events` relaying a tokio broadcast channel as SSE. Both started from `#[tokio::main]`, as `metaform-server/src/main.rs` does. Both were built with release settings on this machine (32 cores, crates already downloaded). The measurements were repeated with actix-files 0.7.4 and tower-http 0.7.1 after Matthew found newer releases. crates.io facts (release dates, download counts) are Matthew's, read 2026-11-09.

| Check | Actix Web 4.19.0 (actix-files 0.7.4) | axum 0.8.9 (tower-http 0.7.1 `fs`) |
|---|---|---|
| Serves when started from `#[tokio::main]` | Yes (verified) | Yes (verified) |
| Static files, index, 404 for a missing file | Yes (verified) | Yes (verified) |
| JSON forwarding route | Yes (verified) | Yes (verified) |
| SSE push from a tokio task | Yes, as a streaming body with `text/event-stream`; core has no SSE type (verified) | Yes, built-in `Sse` type (verified) |
| Release build time | 20.0 s with default features; 12.0 s with `default-features = false` | 10.9 s |
| Distinct normal dependencies (`cargo tree`) | 148 default; 112 lean | 57 |
| Packages in `Cargo.lock` | 165 default; 122 lean | 61 |
| Binary size | 8.2 MB default; 3.7 MB lean | 2.6 MB |
| Runtime model | Its own current-thread runtime per worker thread (actix-rt 2.15.0) | Runs on the caller's tokio runtime |
| Already in this repository | No | Yes, roundtable-web |

Runtime fit (verified for channels, inferred for sockets): an Actix handler received messages from a task on the main tokio runtime through a broadcast channel. Tokio channels work across runtimes. A tokio socket is registered with the runtime that created it. An Actix host would therefore keep each MCP client connection in a task on the main runtime and talk to it through channels. axum needs no such bridge, because the handlers and the rmcp client share one runtime. That runtime is the host process's own; the GUI host does not run inside metaform-server. If the host stays its own process (Marcus's transport section), the Actix runtime never shares a process with metaform-server, and that bridge is the only friction.

Both frameworks meet every requirement the prompt places on the host. Actix's throughput advantage on public benchmarks does not matter for a local, single-user GUI. axum is already this repository's web framework, builds faster, has half the dependencies or fewer, gives a smaller binary and needs no runtime bridge inside the host process. A second framework is a deviation from one pattern without a measured gain.

Confidence: high for every row marked verified. These are single runs on one machine. The build times include only compilation, because the downloads were already cached.

## Open decisions for me (the owner)

1. **Host framework.** Closed: you chose axum 0.8.9 (relayed by Matthew), and the host is built on it.
   - a. axum 0.8. It is the existing pattern, with 57 dependencies, an 11 s release build and one runtime.
   - b. Actix Web 4. It works. It adds a second web framework to the repository, with 112 to 148 dependencies, a 12 to 20 s build and a channel bridge to the tokio runtime. actix-web 4.19.0 was released on 2026-11-09, so pin 4.18.x (Matthew).

   Recommendation: a. Actix is preferable only if you want it for a reason outside these requirements, such as standardizing new web work on Actix. In that case, roundtable-web should move to Actix too, so the repository keeps one pattern. The host is behind one small boundary (files and three routes), so switching later changes one crate.
2. **The command that opens the interface.** Closed: you chose `metaform gui`, and it is built (1a03bf2). `metaform gui [--home DIR]` runs the `metaform-web` host installed beside `metaform`; the host serves a `workspace` folder beside its binary, or the built workspace of the source tree it was compiled from.

The project registry and `metaform register` (seam gap 1) and cross-project links (seam gap 3) are in the seam document and are not repeated here. Chained-map storage is in `dev/chained_map_storage.md`.

### Mermaid text (mermaid-builder)

You shared `connetto-rs/mermaid-builder` (crates.io 0.1.2, updated 2026-01-27, MIT). Marcus read it as a library that writes Mermaid text and does not lay out or render; I have not read its source, so that reading is not verified. It does not replace ELK. It would fit only a "copy as Mermaid" action or an export. Nothing in the prompt asks for one, so nothing is built. If you want one, I recommend our own writer over the crate: a flowchart from `map` is about 60 lines (one `subgraph` per expanded address prefix, one edge per want), and the crate is a single-maintainer 0.x release.

## Risks and verification

Safety first:
- **Local web access to the map.** Handled and checked end to end: the host binds to `127.0.0.1`, refuses a wrong `Host` or `Origin` with 403, refuses every write command with 403, and refuses a path with `..`. Other programs of the same user can still read the map through the host, as they can through the socket.
- **Opening a connection registers a folder.** Handled: the host opens only ids from the server's registry, so it never registers a folder.

### Verification record

Headless Chrome 156 at 1440×900 and 390×844, through Ida's shell on the mock, 2026-11-09 (screenshots in the session scratchpad, `verify/`). Each item is the prompt's DELIVERY AND VERIFICATION list.

| Interaction | Result |
|---|---|
| Menu hide and reveal | Pass: the rail hides 3.8 s after the pointer leaves; the "Show menu" handle, the key M and the left edge bring it back |
| View switching | Pass: Graph, Element and Present keep the project, container and selection |
| Pan, zoom, fit | Pass: drag pans; the wheel zooms (scale 1 to 1.57 at the pointer); the buttons, fit and 1:1 work; the zoom label matches after Ida's 9892b0d |
| Selection and traversal | Pass: click selects and opens Details; double-click opens (after a fix: the redraw after the first click had replaced the node, so the browser sent no dblclick) |
| Ctrl-click to the broader context | Pass (sent as a synthetic Ctrl-click, which reaches the same handler) |
| Collapse and expand | Pass: children draw inside the expanded element and its wants are routed in |
| Layer filtering and isolation | Pass: hide and show (3 marks to 0 to 3); isolate dims 30 elements and moves none (identical transforms) |
| Project navigation | Pass: switching; a cross-project link opens the project at the element its fragment names, selected, with a return chip (after Ida's 9892b0d and 98cdadb) |
| Simulated live intake | Pass: 5 updates in 23 s; viewport, selection and keyboard focus unchanged |
| Graph pivoting | Pass: F sets the focus element at the top with a banner; Clear focus restores |
| Outside project map | Pass: selecting `upstream.code.engine.workflow` offers "Open its map" (seam `outsideMap`, ab4c88a), which opens workflow-engine at `code.engine.workflow` with a return chip back to the element |
| Onboarding (prompt line 6, UX section 12) | Pass: `?first-run` shows Getting started with the working `metaform mcp --project <folder>`, the planned `metaform register <project_name>` labelled as planned, and the command that started the prototype |
| Simulated first intake | Pass: the button registers the sample and fills its map element by element over about 3 s (13 simulated updates). The graph is fitted when the first element arrives, and later elements never move the viewport (after Ida's Canvas fix for a fit of the empty map) |
| Agent names | Pass: activity lines name the agent ("Marcus at code.server.hosting · moved") |
| Narrow screen | Pass: no horizontal scroll at 390 px; bottom bar and Details sheet |
| Served by the host | Pass: the production build loads through `metaform-web`, ELK worker included |

Also checked: layout of every container of every mock project with everything expanded (vitest); mock parity with metaform-core, 630 reads and 0 differences; the host against a real server in a temporary home.

Checks still needed:
- Connect the browser to the host (`MetaformSource`) and repeat the record above on a real project. The seam's verification steps come first.
- Measure layout stability: how far elements move when one element is added. Large movement would disturb the user even with a fixed viewport. Not yet measured.
- Measure elkjs 0.12.1 layout time in the browser worker on the largest container (roundtable `code` took 15 ms in Node).
