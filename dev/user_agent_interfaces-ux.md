# Graph workspace: interaction design

Status: Proposed by Ida (now session metaform-14), 2026-11-09. Nothing here is built. The prompt is the owner's `dev/user_agent_interfaces.md`, and this document does not change it. Companion files: `dev/graph_workspace_seam.md` (Marcus: the data the view reads), `dev/graph_workspace_terms.md` (Matthew: every word the view shows), `dev/graph_workspace_graph.md` (Jorge: layout, rendering, the Rust host and `dev/mock/workspace.json`).

This document says what the user sees and what each input does. It uses Matthew's terms: an **element** is drawn as a node, an arrow is a **want**, and a node's label is the last segment of its address.

## 1. View state

One state object drives every view. Every mode, gesture and project switch reads and writes it, so nothing is lost when the view changes.

| Field | Meaning | Kept when |
|---|---|---|
| `project` | The project shown. | Always, until the user opens another project. |
| `container` | The address whose elements fill the graph: `.` for the project's top level, `code.store` inside it. | Mode switches. |
| `selection` | The selected element, or none. | Mode switches, layer changes, incoming activity. |
| `focus` | The element a pivot centred on, or none (item 9). | Mode switches. |
| `viewport` | Zoom and pan for each `project` + `container` pair. | Returning to a container restores its viewport. |
| `expanded` | The addresses whose elements beneath are shown. Every other element with elements beneath starts collapsed, so a first view is not crowded. Kept for each project. | Mode switches, refetches. |
| `layers` | For each layer: visible, hidden or isolated. | Mode switches and project switches, by layer name. |
| `history` | A stack of earlier states (`project`, `container`, `focus`, `selection`). | Back pops one state. |

**Decision: the view derives structure and refetches on change.** A `map-changed` event refetches `map` and the raw dump, because the layer marks come from the dump's record counts, and keeps every field above (seam rule 1). The view's top level is its own marker, `.`; it is never sent in an addressed read, because `{".": {}}` is the raw dump (R-5.34). A `selection`, `focus` or `container` whose address no longer exists falls back to its nearest existing parent address, and a notice says so: "code.store.cache no longer exists. Showing code.store."

## 2. Screen layout (item 1)

```text
+---------------------------------------------------------------------------+
| [=] metaform  >  code  >  store            Graph | Focus | Present   92% |  top bar
+---+-------------------------------------------------------+---------------+
| r |                                                       |  Details      |
| a |                graph canvas (SVG)                     |  (selection)  |
| i |                                                       |               |
| l |                                                       |               |
+---+-------------------------------------------------------+---------------+
| Layers: specification 12 | memory 3 | skills 1      Activity (2 new)  [Simulated] |
+---------------------------------------------------------------------------+
```

- **Top bar:** the project name in the project switcher, then the breadcrumbs of `container`, then the mode switch, then the zoom percentage. The project name is always visible; this makes the active project apparent at once.
- **Rail:** the compact menu (item 10).
- **Details panel:** opens on selection, closes with Esc or its close button. It does not cover the canvas: the canvas narrows instead.
- **Bottom strip:** the layer chips (item 7) on the left, and the activity count and the **Simulated** badge on the right (item 8).
- Dark theme by default, with a light theme. Text contrast is at least 4.5:1 and control contrast at least 3:1 (WCAG 2.2 AA).

## 3. Modes (item 2)

| Mode | Shows | Kept from the state |
|---|---|---|
| **Graph** | The elements in `container` and the wants between them. | All fields. |
| **Element** | The selected element (or `focus`) in the centre, the elements it wants on one side, the elements that want it on the other, and its details at full height. With no selection, Focus uses the Definitive element. | All fields. Returning to Graph restores the Graph viewport. Matthew named it Element so that "focus" means only the pivot. |
| **Present** | The current Graph or Focus view with the chrome hidden: no rail, no panel, larger labels. Arrow keys move the selection along wants, and Esc leaves. | All fields. Present changes nothing in the state. |

Keys `1`, `2` and `3` switch modes (Graph, Element, Present). The switch takes at most 200 ms and never changes `project`, `container`, `selection` or `focus`.

## 4. Pan, zoom and fit (item 3)

- Drag on empty canvas pans. The wheel zooms around the pointer, and a trackpad pinch does the same.
- Zoom range is 10% to 400%. The top bar shows the current value, such as "Zoom 92%".
- `+` and `-` zoom in steps of 20%. `0` fits the view, and `Shift+0` resets to 100%. The rail has the same three buttons.
- Fit to view frames every visible element with a 48 px margin.
- Zoom and pan animate for at most 200 ms with ease-out. With `prefers-reduced-motion`, they jump with no animation.

## 5. Select, open and go up (item 4)

| Input | On an element with elements beneath | On a leaf element | On `upstream.*` / `downstream.*` |
|---|---|---|---|
| Click | Selects it and opens Details. | Same. | Same; Details offers "Open project" when the link names one (seam gap 3). |
| Double-click | Opens it: `container` becomes its address, and the breadcrumbs grow by one segment. | Opens Element mode on it. | Opens the linked project (item 6). |
| Ctrl-click (Cmd-click on macOS) | Goes up: `container` becomes the parent of the current container, and the element that was the container is selected. | Same. | Same. |
| Enter / Shift+Enter | Same as double-click / Ctrl-click, for the keyboard. | | |

**Outside projects (owner, 2026-11-09; SPEC R-4.15).** Something outside the project's repository is one element in our map under `upstream` (or `downstream`), such as `upstream.code.engine.game`, with a `uri` to its repository. That element is a barrier and a reference: nothing from the outside project's map is placed under it or drawn in our graph. Our elements relate to it through ordinary wants. Double-click on it opens its own address subgraph, like any element. Details shows its fields, its `uri` as a link, and "Open its map" when that map is available. "Open its map" opens the outside project's functional map like another project (section 7), with the return chip, and selects the element that corresponds to ours: our `upstream.code.engine.game` is their `code.engine.game`. Reading the outside map is seam gap 4, and its form is not decided yet, so the button stays hidden until the seam can read it.

**Decision on UI-U2, Ctrl-click.** Ctrl-click goes up the address hierarchy by one level. **Back** (`Alt+Left`, `Backspace`, or the back button) returns to the previous state in `history`, which can be a different project or a pivot. The two differ after a pivot or a project switch, so both are needed. The owner may mean something wider, such as the `upstream` and `downstream` view. Then only the Ctrl-click row changes. This is recorded as open in section 12.

Hint: the first time the user selects an element, a one-line hint appears near it: "Double-click to open. Ctrl-click to go up." It disappears after the user performs either gesture (Matthew's rule 3).

## 6. Collapse and expand (item 5)

- An element with elements beneath has a chevron and a count: "4 beneath", with the accessible name "4 elements beneath code.store". A leaf element has neither, so the two never look alike.
- Click the chevron, or press `Space` with the element selected, to collapse or expand it. A collapsed element is drawn as a stack of two offset outlines, with the chevron pointing right. An expanded element has the chevron pointing down.
- A want to or from a hidden element is drawn to its collapsed ancestor, as one arrow with a count: "3 wants". This keeps the layout honest about connections it is not showing.
- "Collapse all" and "Expand all" are in the rail's secondary menu.

## 7. Projects, `upstream` and `downstream` (item 6)

- The project switcher lists every project from `projects()` (seam). Choosing one pushes the current state on `history` and opens that project at `.`, restoring its last viewport if it has one.
- **Project boundary:** `upstream` elements sit in a band on the left edge and `downstream` elements in a band on the right edge. A dashed line separates each band from the project's own elements, labelled "upstream" and "downstream".
- An `upstream` or `downstream` element that names another project shows a small "opens another project" mark. Double-clicking it, or "Open project" in Details, opens that project, with the element it relates to selected where one exists.
- After a cross-project move, the top bar shows a return chip: "Back to metaform · code.server". The chip performs Back and stays until the user returns or opens a third project.
- Which element names which project is seam gap 3 (owner). The mock uses the element's `uri`, which follows Marcus's recommendation.

## 8. Layers (item 7)

- The layer list comes from the `layer.*` addresses (seam rule 3). `wants` is part of intake and is not listed. Wants are always drawn, because they are the skeleton.
- On the graph, an element that holds records of a visible layer shows that layer's mark: a small coloured square with the record count. Each layer has its own colour and its own shape, so the marks work without colour vision.
- Each layer chip has two controls: a visibility switch, and **Isolate**.

| State | Chip | Graph |
|---|---|---|
| Visible | Filled square, normal text. | The layer's marks show. |
| Hidden | Outlined square, muted text, struck-through count. | The layer's marks are gone. |
| Isolated | Highlighted chip with the word "Isolated". Only one layer can be isolated at a time. | Only that layer's marks show. Elements without its records are dimmed to 30% opacity but stay in place, so the layout does not move. |

- "Show all layers" and "Hide all layers" sit at the end of the strip. Isolating a layer remembers the visible set, and leaving isolation restores it.

## 9. Agents and activity (item 8)

- An agent present at an element shows as a circle with its initials at the element's top-right corner. A filled ring means active, and an outlined ring means idle. Its tooltip reads "Ida at code.store.memory · writing specification", with the **Simulated** badge.
- Agents are always simulated in this prototype, because the server does not publish presence (seam gap 2).
- **Activity:** each event adds one line to the activity list at the bottom right, which is collapsed to a count: "Activity (2 new)". Opening it shows the newest first, with time, agent, address and what changed.
- **New activity never moves the viewport and never takes focus.** The element it touched gets an unseen dot. The dot clears when the user selects that element or opens the activity line. An element outside the current container marks its nearest visible ancestor instead.
- Screen readers hear each event through a polite live region, at most one announcement every 5 seconds, so a burst does not flood them.
- A real `map-changed` event has no author or address (seam rule 1), so it shows "Map changed · 14:32" and refetches. Only simulated events name an agent and an address (Matthew's term map).

## 10. Pivot (item 9)

- "Set as focus" sets `focus`. It is in the element's context menu, in Details, and on the key `F`.
- The layout puts the focus element at the top. Below it come the elements it wants, then the elements they want, up to two wants away. Elements further away are dimmed but stay reachable.
- A banner under the top bar explains the change: "Focus: code.store · elements up to 2 wants away", with a separate "Clear focus" button. "Clear focus" and Back both restore the layout from before the pivot.
- The focus element has a thick outline. Matthew's term map says the focus must never look like the Definitive element, which has its own role mark.

## 11. Compact menu (item 10)

- **Rail contents:** essential actions are fit to view, zoom in, zoom out, the mode switch, Back, and the layer list. Secondary actions are collapse all, expand all, the theme, keyboard help (`?`) and the onboarding guide.
- **Hiding:** the rail hides 3 seconds after the pointer leaves it while the user works on the canvas. It never hides while it has keyboard focus.
- **Showing again:** pointer near the left edge (a 12 px zone), `Tab` into it, the key `M`, or the handle. A small handle stays visible at the left edge whenever the rail is hidden; this is the reopen control. This covers prompt lines 12 and 19 with one control (Matthew's UI-04).
- Secondary actions open from a "More" button, on hover or keyboard focus.
- **Narrow screens, under 900 px wide:** the rail becomes a bottom bar with the essential actions, Details becomes a bottom sheet that covers at most 60% of the height, and the layer strip becomes a sheet opened from the bottom bar. Every task in sections 3 to 10 stays possible. Drag pans, and pinch zooms.

## 12. Onboarding (prompt line 6)

First run, when `projects()` is empty, shows one panel in the canvas:

1. "Register a project". The step that works today: connect an agent from the project's folder with `metaform mcp --project <folder>`; the first connection registers the folder. The prompt's `metaform register <project_name>` is shown beside it, labelled "Planned command" (Matthew's rule 6).
2. "Run a simulated intake". The button runs a simulated intake on the sample project and fills the graph over about 3 seconds, with the **Simulated** badge. The text says a real intake is run by an agent with `metaform/Intake.md`. The view fits once, when the first element arrives; later elements never refit it, because an update must not move the viewport (section 9). If an intake ever grows past the view, a quiet "N elements outside the view" hint is the right signal, not a move (not built; decided with Jorge, 2026-11-09).
3. "Open this view again". The product's reopen command is `metaform gui` (owner, UI-U1; built by Jorge in 1a03bf2), shown beside the command that started this prototype. `metaform register` keeps its "Planned command" label, because it does not exist yet.

## 12a. Motion, start-up and the live intake (owner feedback, 2026-11-09)

The owner reviewed the running prototype and said: the live intake needs easing and smoothness; it starts up showing almost nothing and wastes the screen; wants have no direction animation; intake terms are missing from the graph; marks such as "MA" and small circles are unexplained; and the earlier designs should be the starting point. This section answers the motion, framing and intake parts. Matthew answers the legend and intake terms; Jorge draws the motion. Sources reused: the map viewer (`context/topogee-repo/experiments/map-viewer/index.html`: elements glide to new positions, new ones fade in, active wants flow), the earlier intake graph viewer plan (interruptible eased transitions, arrow keys between connected elements, want detail when close, stable positions), and the earlier graph (`context/brain/digital-typology-hhgg-graph-fixed.html`: legend, role pills, receiving element and providing element in details).

**Start-up fills the screen.** On the first visit to a container, the view expands level by level while the visible elements stay within a budget set by the canvas size: one element per 34,000 px² of canvas, at least 12 and at most 60 (about 32 on a 1440 × 760 canvas). A level is expanded whole or not at all, so the picture stays balanced. Then the view fits. A container the user has visited keeps the user's own expansion. Fit leaves room for open panels and caps the zoom at 160%, so a small graph is not blown up.

**Motion has two speeds.** Small feedback (hover, selection, chips, rail) takes at most 200 ms. Layout motion takes 500 ms with the curve `cubic-bezier(.25, .8, .3, 1)`: elements glide from their old position to their new one, new elements fade and grow in, removed ones fade out, and wants fade in after their ends arrive. Every motion can be interrupted: a new layout starts from where the elements are now. Under `prefers-reduced-motion`, everything jumps.

**The live intake is choreographed, not jumped.** Each write during an intake: (1) the new element fades in at its laid-out place, and its neighbours glide; (2) its wants draw in from the holder toward the wanted element over 500 ms; (3) the writing agent's badge glides to the element; (4) one activity line is added. Writes that arrive within 300 ms are laid out together, so a burst does not shake the graph.

**The viewport still never moves by itself (section 9), with two aids.** An indicator at the canvas edge counts new elements outside the view, with the direction they lie in ("3 new ↘"); activating it eases the view to show them. A **Follow** switch beside the activity count, off by default, keeps the newest element in view while an intake runs, with eased moves; the user turns it on, so moving the view is the user's choice. Any pan or zoom turns Follow off.

**Want direction is animated where it helps.** A want's direction shows as a slow flow along the line (holder to wanted for `outbound`, the reverse for `inbound`, both ways for `two-way`). It runs on the selected element's wants, on wants drawn during the intake, and on every want in Present mode; elsewhere the line is still, so the graph does not shimmer. It stops under `prefers-reduced-motion`.

**Detail grows with zoom.** Below 60% zoom, wants are lines only. From 60%, the want's direction mark shows. From 110%, Matthew's intake terms label the want: OP (`why`) and EF (`how`), in short form. Positions never change with zoom.

**Arrow keys move along wants.** In Graph and Element modes, with an element selected, an arrow key selects the connected element that lies most nearly in that direction, and the view eases to keep it in view, because the user asked for the move.

## 13. Decisions and open questions

Decided here, with reasons:

| ID | Decision | Reason |
|---|---|---|
| UI-U2 | Ctrl-click goes up one address level; Back follows history. | Up and back differ after a pivot or a project switch, and the prompt asks for both "return" (line 13) and "broader context". |
| UI-U4 | A layered top-down layout, as Mermaid flowcharts draw ("TD"). | It is the common meaning of "Mermaid-style". Wants point down from the holder, so the Definitive element tends to sit at the top. Jorge chooses the layout engine. |
| UI-05 | Measurable criteria: feedback animation at most 200 ms and layout motion 500 ms (section 12a, after the owner asked for easing); no event moves the viewport or takes focus; contrast at least WCAG 2.2 AA; one accent colour plus four role colours; layer marks distinct by shape as well as colour. | The prompt's adjectives cannot be checked as written. These numbers are Ida's proposals, not the owner's, and the owner may change them. |
| — | Layers dim rather than remove elements on isolate. | Removing elements would re-run the layout and lose the user's place (prompt: "preserve orientation cues"). |

Open, for the owner:

| ID | Question | Recommendation |
|---|---|---|
| UI-U1 | The name of the command that reopens the view, and whether `metaform register` should exist. | Reopen command decided by the owner (2026-11-09, via Matthew): `metaform gui`, built (Jorge, 1a03bf2). `register` stays planned. |
| UI-U2 | Whether "broader graph context" means something wider than one level up. | One level up, as decided above, unless the owner says otherwise. |
| UI-U3 | What "the Rust version as the premium experience" changes in the interface. | No difference in behaviour. The Rust host serves the same interface. Host framework decided by the owner (2026-11-09, via Matthew): axum 0.8.9, after a 4 of 4 team vote over actix-web. |
| Seam 1 | How the GUI lists registered projects. No read or command lists the registry today. | Marcus: an admin request that lists the registry (id, name, folder) beside `settings`, outside the agent tool; a `metaform register <folder>` command only when the owner wants it. |
| Seam 2 | Where agent presence comes from. The server keeps presence per connection and does not publish it. | Marcus: keep presence simulated and labelled, and shape the event so the agents module (SPEC section 11) can send it later. |
| Seam 3 | Which element names a linked project. | Marcus: the element's `uri` names it, as `metaform://map/project/<id>/<map>#<address>` (Proposed). This gives `uri` a new meaning, so it needs the owner. |

## 14. Verification

Each row is checked in the running prototype, or marked unavailable, as the prompt's delivery section requires.

| Check | Pass when |
|---|---|
| Menu hide and reveal | The rail hides after 3 s idle and returns by edge hover, `Tab`, `M` and the handle. |
| Mode switch | Switching keeps project, container, selection, focus and the Graph viewport. |
| Pan, zoom, fit | The zoom percentage matches; fit frames every visible element. |
| Select, open, go up | Click selects; double-click opens and extends the breadcrumbs; Ctrl-click goes up one level; Back restores the previous state. |
| Collapse | Chevron and count show only on elements with elements beneath; hidden wants are drawn to the ancestor with a count. |
| Projects | Switching projects and returning restores the earlier container and viewport; the return chip works. |
| Layers | Show, hide, show all, hide all and isolate change the marks as in section 8, and isolate does not move any element. |
| Activity | A simulated event adds an unseen dot and an activity line, with no viewport change and no focus change. |
| Pivot | The banner explains the focus; Clear focus and Back both restore the earlier layout. |
| Narrow screen | At 375 px wide, every check above can still be done. |
| Keyboard | Every check above can be done without a pointer, with a visible focus ring of at least 2 px. |
