# Graph workspace: terms and in-product wording

Owner of this file: Matthew (metaform-38), who owns the prototype's in-product wording. Coordinator: Marcus (metaform-b6). Companion files: `dev/graph_workspace_graph.md` (Jorge, metaform-33), `dev/graph_workspace_seam.md` (Marcus), `dev/user_agent_interfaces-ux.md` (Ida, metaform-54). The prompt is the owner's `dev/user_agent_interfaces.md`.

Every label, hint and message the prototype shows uses the Metaform term in the second column. Rule numbers refer to `metaform/SPEC.md` at `61ef6dc`. Send any new string to Matthew before it ships.

## 1. Term map

| Prompt or UI word | Metaform term the UI shows | Meaning | Do not show |
|---|---|---|---|
| node | **element** (drawn as a node) | One element at one address (R-3.1). The node label is the last address segment; details show the full address. | "item", "entity", "component" |
| node path, breadcrumb | **address** | A dotted path such as `code.engine.game` (R-3.2). Each breadcrumb is one segment. | "path", "route" |
| edge, link | **want** | An arrow from the element that holds the want to the element it names. This is the `map` edge (R-5.11). Edge details show `why`, `how` and `direction`. | "dependency", "relationship", "intent" (renamed `direction`, R-3.6) |
| edge direction | **direction**: `inbound`, `outbound`, `two-way` | Relative to the element that holds the want, never to the project (R-3.6). | arrows that suggest request direction: "The request is never the direction." |
| incoming arrows | **wanted by** | The elements that want this one (`wanted_by` in a `goto` result, R-5.30). | "used by", "dependents" |
| nested graph | **elements beneath `<address>`** | The children of an address segment (R-4.12). Double-click opens them. | "subgraph" in labels (it is fine in code) |
| project | **project** | The root of one map (R-4.2). | "workspace" for a project |
| cross-project link | **`upstream`** / **`downstream`** | `upstream` is what the project relies on and `downstream` is what relies on it. Both are outside the project (R-3.7). The UI marks the project boundary on these. | "external", "linked project" alone |
| layer | **layer** | A named set of records held at elements, such as `specification`, `wants`, `skills`, `memory` (R-6.24, R-5.34). Show the record count, not the records, until the user opens one. | "overlay", "channel" |
| node type | **role**: Definitive, Supportive, Notable, Divergent | Capitalized. A project has exactly one Definitive element (R-3.13). The root scope (`code`, `document`, `media`, `data`, `collection`) may also be shown, as a second, quieter mark. | "core", "main", "critical" |
| status badge | **status** value as stored, such as `un_built` | Show the stored value. Do not map it to a new word. | "todo", "missing", "broken" (the contract refuses these) |
| agent location | **at `<address>`** | An agent is present at the address of its last `goto` (R-5.30). The server keeps presence per connection and does not publish it, so another agent's location is always simulated in this prototype: show "Ida at code.server" with the **Simulated** badge. | "working on node", "editing" (presence is not a write) |
| activity, incoming update | **map changed** | The real feed (`notifications/resources/updated`, see `graph_workspace_seam.md`) says only that a commit happened: no author, no address, no diff. Show "Map changed" and the time. A line such as "Jorge wrote `specification` at code.server" may appear only on a simulated event, with the badge. | "intake", unless the event is an intake run; "sync", "event" |
| live intake | **intake** only for an intake run | Intake is the procedure that builds the map (`metaform/Intake.md`). | "intake" for any other update |
| focal node, pivot | **focus** | A UI-only idea with no Metaform term. Never call it Definitive, and never style it like the Definitive element. | "root", "center", "definitive" |
| orphaned element | **orphaned** | The result of `{"orphaned": {}}` (R-5.23). | "dangling", "unused" |

## 2. Wording rules for strings

1. Use sentence case for labels and buttons, and start with a verb: "Fit to view", "Show all layers", "Isolate layer".
2. Keep a gesture hint to one line under ten words: "Double-click to open. Ctrl-click to go up."
3. Show each gesture hint once, near the gesture, until the user performs it. Do not repeat it on every view. This is the same just-in-time rule the MCP server follows for agents.
4. Give numbers with units: "Zoom 100%", "3 records".
5. Mark simulated data the same way everywhere: a badge with the word **Simulated**. Its tooltip reads "Simulated: not connected to a Metaform server." Do not use "demo", "fake" or "mock" in the interface.
6. Show commands exactly. The CLI at `61ef6dc` has `metaform serve`, `mcp`, `call`, `specification`, `settings`, `set` and `unset`. `metaform register <project_name>` (from the owner's prompt) and `metaform gui` (the owner's reopen command) are not in the CLI yet, so label them "Planned command". Show no command name that the owner has not given.
7. Do not use: "seamless", "powerful", "intuitive", "affordance", "leverage", "utilize". Prefer the TASTE replacements: start, use, adjust, perform, end.

## 3. Decisions and open questions

Decided by the team (the owner may change them):
- **Ctrl-click goes up one address level; Back follows history** (Ida, UI-U2, `user_agent_interfaces-ux.md` section 5). Up and back differ after a pivot or a project switch.
- **Layered top-down layout**, as Mermaid flowcharts draw (Ida, UI-U4).
- **One word per idea:** "focus" is the pivot only. The mode that shows one element with its wants is proposed as **Element** (Graph | Element | Present), so that "Focus" does not name two things. Sent to Ida; not yet accepted.
- **Onboarding shows the step that works today:** `metaform mcp --project <folder>`; the first connection registers the folder (`main.rs:5`, `lib.rs:162` at `61ef6dc`). `metaform register <project_name>` appears beside it, labelled "Planned command".

Decided by the owner (2026-11-09, answers to Matthew's questions):
- **Reopen command:** `metaform gui`. It is not in the CLI yet, so onboarding shows it labelled "Planned command".
- **Host framework:** axum 0.8.9 (`.taste/VOTE.md`). Marcus is checking a reported "veto" with the owner; treat this as final once he confirms.

Open, for the owner:
- **Listing and registering projects.** This is the seam's gap 1 (`graph_workspace_seam.md`). It is one question; this sheet does not ask it again.
