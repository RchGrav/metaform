# Graph workspace: the backend seam

Status: Proposed by Marcus (session metaform-b6), 2026-11-09. Nothing here is built. This document supports the owner's prompt `dev/user_agent_interfaces.md`. It does not change that prompt.

The prompt asks that the prototype's graph model and event sources be replaceable, so that a real backend can be connected later. This document defines that seam. The mock data and the later Metaform adapter implement the same interfaces, `GraphSource` and `WorkspaceEvents`. The code is `metaform/workspace/src/source/` on branch `workspace-source`. The interface shapes follow what the Metaform server returns today, so the adapter maps calls instead of reshaping data.

Related work:
- Jorge (metaform-33): layout, rendering, the Rust host and the mock data, in `dev/graph_workspace_graph.md`.
- Matthew (metaform-38): the terms sheet and every string the prototype shows, in `dev/graph_workspace_terms.md`.
- Ida (metaform-54): interaction and UX design, and the sorted list of gaps for the owner, in `dev/user_agent_interfaces-ux.md`.

## Facts this seam rests on

Each fact was read from the code on branch `specification-layer` (commit `cef7de5`) or from `metaform/SPEC.md` on that branch. None was checked against a running server for this document.

| Read | Request | Result | Source |
|---|---|---|---|
| Shallow graph | `{"map": {}}` | `{"addresses": [...], "edges": [[holder, wanted], ...], "definitive": "<address>" or null}`. The root is left out. No fields, no layers. | `reads.rs` `shallow`; R-5.11 |
| Summary sheet | `{"goto": "<address>"}` | `at`, `element` (base fields), `wants`, `wanted_by`, `layers` (name to `{"records": n}`), `memory` (`{"records": n}`), and `instructions` when a layer is defined there | `reads.rs` `goto`; R-5.30, R-6.27 |
| Layer records | `{"<address>": {"<layer>": {}}}` | `{"<address>": {"<layer>": [records]}}` | R-6.27 |
| Raw dump | `{".": {}}` or `{".<address>": {}}` | The stored nested JSON at that path, every layer included | `reads.rs` `raw`; R-5.34 |
| Layer list | addresses that start with `layer.` in the shallow graph | The layer's field name is the last segment, for example `specification` | R-6.24 |
| Change feed | subscribe to `metaform://map/project/<id>/<map>` | `notifications/resources/updated` with no diff | `announce.rs` `map_uri`, `changes` |

Other facts:
- An element's address is its position. Nesting comes only from address segments: `code.server.relay` is beneath `code.server`. There is no separate parent field.
- A want is held by the element that wants: the edge `[holder, wanted]` means "holder wants wanted". Each want carries `why`, `how` and `direction` (R-3.6).
- Root scopes: `code`, `document`, `media`, `data`, `collection`, `upstream`, `downstream`, `layer` (R-3.3). `upstream`, `downstream` and `layer` are root prefixes: what follows them can be another root scope.
- Roles: Definitive, Supportive, Notable, Divergent. At most one element is Definitive.
- One server process serves every project in one home. The project comes from the connection's handshake, `{"project": <folder>}`. That connection registers the folder in the home's project registry if it is new (`lib.rs` `open_project`).
- `element` in the summary sheet holds the element's scalar fields only (`model.rs` `base_fields`). Wants and array layers come back only when named.
- CLI commands at `cef7de5`: `serve`, `mcp`, `call`, `specification`, `settings`, `set`, `unset`. There is no `register` command.

## The interface

TypeScript, because the prompt asks for React and TypeScript. Names follow Metaform's terms. Matthew's terms sheet governs what the screen calls them.

```ts
type Address = string;                 // "code.server.relay"; "" is never used for the root
type Role = "Definitive" | "Supportive" | "Notable" | "Divergent";

interface ProjectRef {
  id: string;                          // opaque; never parse it
  name: string;
  folder: string;
}

interface ShallowGraph {               // the result of {"map": {}}, unchanged
  addresses: Address[];
  edges: [holder: Address, wanted: Address][];
  definitive: Address | null;
}

interface Want { why?: string; how?: string; direction?: string; [field: string]: unknown }

interface SummarySheet {               // the result of {"goto": address}, unchanged
  at: Address;
  element: { technical_name?: string; name?: string; role?: Role; uri?: string; status?: string; [field: string]: unknown };
  wants: Record<Address, Want>;
  wanted_by: Record<Address, Want>;
  layers: Record<string, { records: number }>;
  memory: { records: number };
  instructions?: Record<string, string>;
}

type RawDump = { [path: string]: unknown };   // the result of {".": {}}, unchanged: {".": <nested tree>}

interface GraphSource {
  projects(): Promise<ProjectRef[]>;
  map(project: string): Promise<ShallowGraph>;
  dump(project: string): Promise<RawDump>;
  goto(project: string, at: Address): Promise<SummarySheet>;
  layerRecords(project: string, at: Address, layer: string): Promise<unknown[]>;
}

type WorkspaceEvent =
  | { kind: "map-changed"; project: string; simulated: boolean }
  | { kind: "agent-presence"; project: string; agent: string; at: Address | null; activity: string; simulated: true };

interface WorkspaceEvents {          // not EventSource: that would shadow the browser's EventSource
  subscribe(project: string, listener: (event: WorkspaceEvent) => void): () => void;   // returns unsubscribe
}
```

Rules for both implementations:
1. `map-changed` carries no diff. The view refetches `map` and keeps its viewport, selection and focal element. This matches the real server, which sends `notifications/resources/updated` with no content.
2. The view computes nesting, collapse, the nested graph of an element, and the layer filter from `ShallowGraph`, `RawDump` and `SummarySheet`. The source does not compute them. The real server has no read for them.
3. The layer filter needs record counts for every element at once, so it reads one raw dump, not one `goto` per element (118 calls for the Metaform mock). The layers are the definitions beneath `layer` in the dump: an element there with an `instruction` defines the layer named by its last segment (R-6.24). At each element, an array-valued field whose name is a defined layer holds that layer's records, and its length is the count. A child element is any object-valued key other than `wants`. On `map-changed` the view refetches the dump too. (Added at Jorge's request; narrowed 2026-11-09 to defined layers, as Ida built it in `src/state/structure.ts`. `goto` counts every array field except `memory` and `skills`, so it also lists the native array `sources` (R-4.16 status) as a layer. The defined-layer rule is the correct one. The difference is latent: no write path creates `sources` today, because neither the contract nor the schema has the field. Marcus records it as D-08, to fix when `sources` becomes writable.)
4. Every event has `simulated`. The prototype shows a "simulated" label whenever it is `true`, as the prompt requires.
5. `agent-presence` is always `simulated: true` in this version. Metaform has no source for it (see gap 2).
6. A cross-project link is an element's `uri` of the form `metaform://map/project/<id>/<map>#<address>`. The part before `#` is the server's `map_uri`; the fragment names the element to land on, as a URI fragment names a part of a resource (RFC 3986, section 3.5). Without a fragment, the link lands on the other project's map with no focal element. This form is Proposed (gap 3). In the mock, `<id>` is the project name; real ids are opaque.

## Transport

Proposed by Marcus; Jorge owns the host and decides the framework.

- The host is its own process and a client of the home's socket, like `metaform call`. It does not run inside `metaform-server`. Reasons: one process owns each store and every other process goes through it (D-10); a host crash cannot end agents' MCP connections; and the server keeps one runtime (tokio with rmcp), so the web framework's runtime model does not touch it.
- The host serves the built assets and one route that forwards a command to the socket. It sends the result back unchanged, a refusal included.
- Push: the host subscribes to the map resource through the socket and relays each `notifications/resources/updated` to the browser as a server-sent event (SSE). Updates go one way only, so SSE is enough. WebSocket would add a second direction that nothing uses, and the browser's `EventSource` reconnects on its own. Nothing polls (R-4.10).
- Read in the code at `61ef6dc`, not run: after the handshake line `{"project": "<folder>"}`, a socket connection is a full MCP session (`lib.rs` `session`, `tool.rs` `MapTool`). It accepts `subscriptions/listen` (protocol `2026-07-28`) and the older `resources/subscribe`. So the host is an MCP client over the socket, with one connection per open project, because each handshake names one project. Opening a connection registers a new folder (`open_project`), so the host must open only projects that are already registered.

## Host routes

Proposed by Marcus; Jorge may change them, and `src/source/metaform.ts` follows. Not built.

| Route | Answer |
|---|---|
| `GET /api/projects` | `ProjectRef[]`, from the registry listing of gap 1. Until that exists, the host's own configured list. |
| `POST /api/projects/<id>/call` | Body: one command of the Metaform tool. Answer: the server's result unchanged. A refusal comes back as the refusal JSON (`status: "error"`, `code`, `message`, `remediation`) with HTTP 200, so it is never confused with a host failure. |
| `GET /api/projects/<id>/events` | Server-sent events. Each `notifications/resources/updated` for the project's map becomes one event named `map-changed`, with no data. |

The adapter throws `RefusalError` for a refusal and `TransportError` when the host fails or answers in an unknown form. The view shows the two differently: a refusal is the server's answer; a transport error means no answer.

## Mapping the prompt's features to the seam

| Prompt feature | Seam source | Real backend today |
|---|---|---|
| Graph view, layered layout | `map` | Yes |
| Selection and details | `goto` | Yes |
| Nested graph (double-click), breadcrumbs | address prefixes in `map` | Yes, computed in the view |
| Broader context (Ctrl-click) | the parent address prefix | Yes, computed in the view |
| Collapse and expand | address prefixes in `map` | Yes, computed in the view |
| Layers: show, hide, isolate | `layer.` addresses, `goto` layer counts, `layerRecords` | Yes |
| Pivoting (new focal element) | `goto` on the new element; `wants` and `wanted_by` give the neighbours | Yes |
| Multiple projects | `projects()` | Yes on branch `project-listing`: the admin request `projects` (gap 1) |
| Cross-project links | `upstream.*` and `downstream.*` elements | Partly: the elements exist; the link to another project does not (gap 3) |
| Agent presence and activity | `agent-presence` events | No (gap 2) |
| Live updates | `map-changed` | Yes, through the map resource subscription |
| Onboarding: register a project, first intake | none | No `register` command; intake is run by an agent with `metaform/Intake.md` |

## Gaps

Decided here, with the reason:

- **Refetch, not diffs.** The server sends no diff, and a shallow map is small. Computing diffs on the client would duplicate state the server owns. Revisit when a measured map makes refetching slow.
- **The view derives structure.** Nesting, collapse and the parent context are pure functions of the addresses. Adding reads for them would add server forms the owner has not asked for (one pattern, fewer forms).
- **Opaque project ids.** The id in `map_uri` is the server's. The interface never parses it, so the server can change how it keys projects (Ida's Q-011) without breaking the GUI.

Open, for the owner (gap 1 is now decided):

1. **Listing projects.** Decided by the owner, 2026-11-09: one GUI covers many projects, with one web server per host over the one serving process that manages every project's databases. Built by Marcus on branch `project-listing` (`ab71e2c`): `{"admin": {"projects": {}}}` and `metaform projects` answer each registered project's `id`, `name` and `folder`, and register nothing. `GET /api/projects` calls it through the socket. A `metaform register` command is not built; a project is registered when an agent first connects from its folder.
2. **Agent presence.** The server holds `goto` presence per connection only. SPEC section 11 moves presence to the agents module, which is not specified. Recommendation: keep presence simulated and labelled, and shape the event so the agents module can emit it later. No server change now.
3. **Cross-project links.** `upstream.*` and `downstream.*` are what lies outside the project (R-3.7). Nothing says that such an element can point to another project on the same home. Options:
   - a. The element's `uri` names the other project's map and, after `#`, the element: `metaform://map/project/<id>/<map>#<address>` (rule 6). Then navigation follows the `uri`.
   - b. No link: the GUI shows `upstream` and `downstream` as boundary elements only.

   Recommendation: a, because `uri` already exists as a base field and `map_uri` already names maps across connections. It needs the owner, because it gives `uri` a new meaning.

## Verification

Before the prototype is called connected:
- A contract test reads `map`, `goto` and one layer from a seeded project through `metaform call` and checks that each result parses as the TypeScript types above.
- The mock data passes the same check.
- A change written with `add` produces exactly one `map-changed` event, and the view keeps its viewport.

None of these has been run. The prototype runs on the mock until they pass.

## Outside projects and their maps (owner, 2026-11-09)

Something outside the project's repository is one element in the project's map, under `upstream` or `downstream`, such as `upstream.code.engine.game`. Its `uri` names that repository. That element is a barrier and a reference: the outside project's map is linked inside it, and it can hold details about the outside project, but neither is part of the project, so `map` never carries the outside project's detail (SPEC R-4.15). The outside project can have its own functional map: a separate map for a different project, with the regular root scopes and its own `upstream`. `upstream.code.engine.game` here corresponds to `code.engine.game` there. Project elements relate to the outside element through ordinary wants.

In the GUI, double-clicking an element opens its own address subgraph, as for any element. Double-clicking an outside element whose map is available opens that map like another project (section 7 of the UX design, with the return chip), focused on the corresponding element. Reading that map is gap 4. In the seam, `GraphSource.outsideMap(project, at)` returns the outside map as a `ProjectRef` (opaque `id`, `name`, and the repository `uri` instead of a `folder`), or null; the view then uses the five ordinary reads on it, so opening it is the same as opening another project (`05707d0` and the next commit on `workspace-source`). The server request is not decided; the recommended agent form is `{"map": "<address>"}`, answering the outside map's shallow graph in its own addresses, and a host can build `outsideMap` on it. This replaces gap 3's open question for the common case: the link to another map is the outside element and its `uri`.
