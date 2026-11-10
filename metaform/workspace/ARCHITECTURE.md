# Architecture of the Metaform GUI

**Status:** Written by an agent, 2026-11-09, and built as described by 2026-11-10, to carry out the owner's GUI specification, `dev/gui_specification.md`. That document governs. This one says how the page is built and which parts are real and which are simulated.

## 1. One canonical specification

The page holds one typed model of the project's functional specification, `Spec` (`src/spec/model.ts`). The graph, the specification outline, the entity panel and the Markdown are views of it. No view keeps its own copy.

```text
server map  ──read──▶  saved: Spec  ──┐
                                      ├──▶  current: Spec  ──▶  graph, outline, entity panel, Markdown
accepted edits (pending the write) ───┘
proposals (not accepted)  ── shown beside `current`, never inside it, unless the user includes them in a marked section
```

- `saved` is built from the server's raw dump of the project (`{".": {}}`): every element with its address, name, technical name, role, status, source reference, wants (why, how, direction) and layer records.
- An edit the user makes, or a proposal the user accepts, is sent to the server as a `project-map` command. The server checks it and stores it, or refuses it with a reason and a remediation, which the page shows. When the server announces the change, `saved` is read again. Between the accept and the announcement the edit is in `current` and marked as pending.
- Transient state is kept apart from the specification: the view (selection, camera, open panels), the activity stream, and proposals that are not accepted.

## 2. Evidence status

Every claim the page shows carries one status, shown with a word and a mark, not colour alone.

| Status | Where it comes from |
|---|---|
| source-backed | The element has a source reference (`uri`) or records in the `sources` layer. The page shows the path. |
| inferred | A relationship (why, how, direction) or a field that intake recorded with no source reference of its own. |
| unverified | An element with no source reference. |
| user-authored | Written or changed in the page by the user. |
| agent-proposed | A proposal that has not been reviewed. |
| accepted, rejected | A reviewed proposal. An accepted one becomes part of the specification. |

The map does not record a status field today. The first three are derived from what the map holds, and the page says so. The page never states that an analysis took place.

## 3. Real and simulated

| Part | Real or simulated |
|---|---|
| Reading a project's map, and following changes as agents write | Real: the Rust host and server, `/api/projects`, `/call`, `/events` |
| Writing an edit or an accepted proposal | Real: a write route on the host that forwards one `project-map` command. It accepts a request only when its Origin is the page's own address, as the earlier Metaform page did. |
| The Markdown | Real: generated in the browser from `current`, with the user's choices of what to include. The preview, the copy and the download come from one function. |
| Agent proposals | Simulated. No agent service is reachable from the host. The page offers proposals from a local generator behind the `AgentService` interface and labels each one "Simulated". A real service implements the same interface. |
| The activity stream | Map changes are real: each item is made by comparing the specification before and after a change the server announced. Test results, build results, dependency changes and runtime issues have no source yet; they appear only with sample data and are labelled "Simulated". |
| Sample data (`?mock`, `npm run dev`) | Simulated, and labelled. |

## 4. Parts of the page

| Folder | Holds |
|---|---|
| `src/spec/` | The `Spec` model, how it is built from a raw dump, edits and proposals, evidence status, and the Markdown generator. Pure functions, with tests. |
| `src/graph/` | The graph: layout by purpose (ELK), the SVG renderer, the camera, the flow on the lines. |
| `src/panels/` | The panel system: zones (left, right, bottom), floating panels, resizing, the saved layout and text size. No dependency. |
| `src/views/` | The panels themselves: entity, evidence, outline, findings, activity, review, Markdown preview; the top bar and the graph controls. |
| `src/review/` | The store that takes edits and proposals, sends each accepted change to the server, and records it in the `review` layer. |
| `src/activity/` | Findings read from the specification, and the activity items. |
| `src/source/` | The seam to the server: reads, events, writes, and the `AgentService` interface. |
| `src/mock/` | Sample data and the simulated services. |

## 5. The graph

- It draws elements and wants only. There are no address boxes. A want is a line of straight runs with right-angle turns and rounded corners, as in the Topogee map viewer (owner, 2026-11-10: the curved lines could not be read). Layout is by purpose: who the project serves comes first and what it relies on comes last. The renderer chooses the direction for the shape of the pane: downward in a tall pane, across in a wide and short one. A layer that is too long for the pane wraps.
- Depth follows the earlier Metaform map: levels are counted along the wants from the elements nothing relies on. A map of up to 200 elements is shown whole. A closed element shows how many hidden elements it holds. Controls: collapse all, expand all, one level more or less, open or close one element, and undo.
- Categories are the first segment of an address (downstream, code, document, data, media, upstream). Each can be shown, hidden or isolated. Isolation makes the other categories recede and moves nothing.
- Fit graph, fit selection, fit branch and fit visible scope keep the graph clear of the controls that lie over the pane.
- The camera eases to a new fit when the user changes what is shown. A selection does not move it, and a change from an agent never does.
- The flow on the lines runs for the selected element.

## 6. Limits

- Each element hangs from the one element that reached it first. Closing that element hides it even when another visible element relies on it.
- A want to a hidden element is not drawn.
- A pending edit shows in the panels at once. The graph shows it after the server confirms it.
- Proposals that wait, and the list of rejected proposals, last until the page is loaded again. An accepted proposal and a user's edit are recorded in the map's `review` layer.
- The light theme and maps above 200 elements were not checked in a browser.
