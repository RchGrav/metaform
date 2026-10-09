# Metaform: where things are

As of October 1, 2026. Branch `chassis` at commit `f1c2929`, pushed to https://github.com/RchGrav/metaform/tree/chassis.

## What Metaform is

Metaform keeps a functional map of a project. Each part of the project is an element at a namespace address, and each join records who receives what a part provides: the receiver's Operative Purpose, the why, served by the provider's Encounter Function, the how. An intake builds the map once, and agents read it before they work, so they start from the project's recorded understanding and do not rebuild it. Agents use it through an MCP server or the `metaform` command line, and a person watches it in a web viewer with a 3D map and a 2D map.

The design lives in `specifications/spec/`, indexed in `00-index.md`, with open questions in `OPEN-QUESTIONS.md`.

## What landed on October 1

**The store is kept, never refused.** Records LAYER-025, STORE-029.
- Refining the map writes new versions into the intake layer itself. There are no correction layers, and every earlier version is kept.
- A store written by an earlier layout is updated when it is opened, after a backup copy is made. It is never refused. The rule: the layout version changes only for a change that requires an update. The store is now at layout 10.

**Work is tracked on the map like a kanban.** Records D92, STORE-042, VIEW-032, VIEW-036, VIEW-037.
- A ticket sits on the node it is assigned to and links other nodes for reference. Its kind is missing, broken, flawed or enhancement, and it keeps that kind while it is worked. It records who took it and each step filed.
- The viewer has a Board: Backlog, To do, Doing and Done, with drag and drop, search and a filter by kind.
- A node's right-click menu opens its work history.
- Agents are told, in short imperatives, to use Metaform for all task assignment. A `tasks` setting turns this off for a project that keeps its own board.

**The map shows work happening.** Records VIEW-035, VIEW-038.
- A ticket's node flashes in its kind's light: red for broken, yellow for flawed, green for enhancement. The flashing gets faster with each step filed. A missing part is drawn in changing characters until it is built.
- An agent working a ticket is an animated figure. It appears on the defining element, walks the map's edges to the ticket's node, circles it while the work goes on, and walks back when the ticket closes.
- Labels wrap, stay readable, and keep their draw order. Hovering shows what a part does, taken from its joins.

**The intake asks for more, and names things plainly.** Records MAP-020, STORE-009.
- Every join records IFD, Information Flow Direction, the primary flow of information: sends, receives or both.
- Every element records its canonical name, the name the project uses, beside its namespace address.
- New namespace rules forbid coined type words. A name must be the established term people in that field use, or the plain common noun for what the thing does.

**Testing runs on every core.** The full suite of 744 tests runs in about 3.5 minutes instead of about 30.

## How it was checked

- 740 of 744 tests pass. The 4 that fail under full load are browser timing tests. Each passes when run alone, and they failed the same way before these changes.
- The work was tried end to end on real data. Metaform was installed, an intake of Metaform itself ran in a clean, separate session, and in the live viewer a ticket was taken, its figure walked out and circled the node, a step made the flashing faster, and closing the ticket sent the figure back.

## What is open

- **Collapsing into a single layer, LAYER-026.** When the map is right, write its current state as one clean layer that becomes the data going forward. Designed, not built. Its questions are in D111.
- **A fresh intake of Metaform.** It will run on the current rules, so the map that ships with Metaform has element names and IFD from the start. A clean copy is prepared.
- **The process advisory agent.** Defined in `.claude/agents/process-advisory.md`. It examines Metaform's processes against the specifications and suggests what each still needs. It has not run yet.
- **Decisions waiting on the owner:** whether the `extra` field goes entirely; a step of the Canonical Intake that cites a definition no longer there; whether tickets that wait should glow quietly, so that only work in progress flashes.
- **Known bugs, from the intake of Metaform.** The installer's check does not test each AI client itself. Adding an element in the viewer can leave an empty layer when the write is refused. `config --json` opens the settings screen in a terminal instead of printing JSON. The memory tool does not keep an entity's type. Four more findings are not yet checked. Two found bugs were fixed: refining dropped a join's perspective and verb, and export left out tickets' steps and messages.
