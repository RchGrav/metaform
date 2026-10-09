# Change order, 2026-10-08

The decisions of 2026-10-08, in the order they can be built, grouped into four lanes that can run side by side, each with what it changes, why, and what it waits on. Nothing here replaces a record; each item becomes or amends one when it is built. The design notes behind it are in `artifacts/design-notes-2026-10-08.md`.

Status of each item: **done** (committed on `main`), **decided** (agreed, not built), **open** (needs the owner's answer first).

## 0. Done on 2026-10-08, for the record

- Agents no longer reach the person: consensus, Help me answer, chat on a question, `map tell` and the agents' `ask` are removed; a worker that is stopped writes in its ticket's note. MAP-050, VIEW-042, VIEW-043 withdrawn, BASE-052.
- Nothing restarts by itself: a stopped session stays idle and reachable, its ticket stays taken; autostart takes only untried tickets with a task. Change order 2026-10-07 item 5, in part.
- A part's state is a stage (`unbuilt`, `under-construction`, `built`) or the fault `broken`, set by the intake and the person. MAP-046.
- The sentinel, a workflow skill sent whole over ACP; Raise an issue on a node's menu and panel. VIEW-045.
- Upstream and downstream as toggles beside the layers. VIEW-046.
- Exclude replaced by `.metaform/ignore.txt`. BASE-058.
- The `logic` root, with workflows under `logic.workflow`. MAP-055, BASE-051, LAYER-028.
- The digital typology intake in Axiom is the served intake, with the core-node schema; Axiom scripts use `.axiom`. BASE-039, MCP-031.
- BASE-059, skills are universal, recorded.
- `main` consolidated; `chassis` retired.

## Lane 1: the intake

### 1.1 Close the intake tool gaps (decided)

The served intake names these as bindings B1 to B6. Close the ones that lose what the agent records:
- **Notes without a condition are kept** (B4), on the element or join itself, as a versioned field, so exclude notes and other notes survive. Today they are discarded with a notice that pushes agents to invent a condition.
- **Missing is not a condition** (B5): ruled out, 2026-10-08; what is absent is unbuilt.
- **The join takes refs** (B3), since the intake records refs on a join where required.
- **ifd accepts the schema's words** (B1): `send`, `receive`, `both` as well as the tool's `sends`, `receives`.
- The run id (B2) needs no change: the intake carries it in the finish report.

Why: a test of the new intake measures what the tools keep, so the tools must keep what it records.

### 1.2 Run the new intake into a new base (decided, after 1.1)

One full intake of this project with `intake.axiom`, into a new base, compared with the 2.1 base `intake-20261008T030107Z`: element addresses not prefixed by the AUE, the core node connected, CQU roots, notes kept.

### 1.3 The core node and collections on the system side (decided; waits on the owner's review of 1.2)

- The core node is an element of the map with a name and no namespace address, holding the AUEs, collections and CQUs (schema `metaform.axiom`). The store identifies an element by its address today, MAP-015, so it needs an element that has a name and no address; the intake tools need a way to record it, since `intake element` requires an address. The page draws it at the center instead of starting from one DE, and the reads that look for the map's entry return what it holds.
- `collection` joins the roots: MAP-014 and `roots.json`. A project can hold several CQU roots, one per collection.
- The stored `namespace-rules` section gets a new version naming `logic` and `collection`.

Open: the collection element's role, AUE or a grouping element with no AUE role.

## Lane 2: what the map shows

### 2.1 Stage and kind as separate fields (done, 2026-10-08; MAP-046 amended)

The part's **stage** and the ticket's **kind** (broken, flawed, enhancement, plain task) share one field today, so setting one wipes the other. Split them: the board shows and filters by kind; the map draws stage; taking a build ticket sets under construction by itself; built is said only by the person or the intake.

### 2.2 Critic findings light nodes (decided)

Restore critics writing findings, now as held tickets with a kind, which light their nodes in the critic's color. Only three sources ever light a node: the intake, a critic pass the person runs, and the person. A worker never does. Each light is one ticket and goes out when that ticket is done.

### 2.3 The sentinel's turn and the person's Accept (decided)

The sentinel marks its proposals ready, which makes the node flash in its color. The person accepts a proposal from the right-click menu or the chat, which writes its tickets held and stops the flashing.

### 2.4 The attention rule, drawn (decided, after 2.1 to 2.3)

| What you see | Meaning |
|---|---|
| Flashing | waiting on the person; nothing else flashes |
| Solid color | waiting on the agent of that color: critic, sentinel, worker |
| Fading in and out, faster as steps are filed | an agent is working |
| Drawn as text, the shader climbing | unbuilt and being built |
| Normal | nothing to do |

Broken stops flashing red; a finding flashes in the critic's color.

Open: whether an intake's broken mark flashes like a critic's finding; whether flawed and enhancement light the map or show on the board only.

## Lane 3: logic and skills

### 3.1 Move to the logic root (decided)

The workflow module reads `logic.workflow.` where it reads `workflow.`; LAYER-028's reserved layer name becomes `logic`; any element at the old root in a base moves by a correction.

### 3.2 Skills as folders, BASE-059 (decided, after 3.1)

- The eight skills leave `prompts.xml` for `skills/<name>/` folders: `SKILL.md` with frontmatter and the `ing.metaform.` keys, the procedure in `references/<name>.axiom`, kebab-case names.
- Mark each discoverable or internal. The sentinel and the evaluator are internal.
- A `skills` tool on the MCP server: list, load and read by name or by `logic.skill.<name>`, libs loaded fresh.
- The deploy script copies discoverable skills with their libs into harnesses that inject discovery, and records it; the server injects the index at connect for any other harness, with a setting to force it.
- Dispatch loads the sentinel through the `skills` tool by address.
- The `talk` and `system` prompts in dispatch become skills the same way.

## Lane 4: safe concurrent work

### 4.1 Work claims, LAYER-029 (decided, with open points)

- Each sentinel proposal names its reach, the nodes and joins it touches; a larger proposal blocks more, and the person sees that cost when choosing.
- One claim per proposal, starting when its first ticket is taken and ending when its last ticket has landed (merged, with worktrees).
- The claim is a layer: checked, it highlights the area; unchecked, it hides it as unavailable.
- No ticket inside an active claim starts; no worker can release or step around a claim.
- A claim checker role reviews a claim and reports when it is drawn too wide.

Open: whether the checker also looks for claims drawn too narrow; whether it narrows a claim itself or brings the person a finding (leaning: a finding); when it runs (leaning: after a ticket waits on a claim, and on the person's request).

### 4.2 Merges one at a time (decided)

Each branch rebased onto the latest `main` and tested again before it merges, so later work is tested against earlier work.

### 4.3 The rest of change order 2026-10-07 item 5 (decided there; after 4.1 and 4.2)

Worktrees on by default, runner checkpoints, pinned adapters, agent stderr in the transcript, model and effort per ticket.

## Later, waiting on a decision

### 5.1 The code layer (open)

Decided in principle: the base stays functional; a code layer holds code elements attached to the joins they carry out, with call and import edges; functional, code and hybrid views; built by a parser for structure and an agent for attachment. Waits on how a code element is addressed: LAYER-028's dot form, the `scope@thing` form read with `@` as "for", or the code's qualified name `@` namespace `:` join. See `artifacts/namespace-and-logic-root-2026-10-08.md`, section 4.

### 5.2 Published ids under `ing.metaform` (open)

Module, prompt and published layer ids under the domain root, so authors cannot collide. Waits on the scope of the domain root.

## Small, any time

- **Cypher for agents.** Done 2026-10-08: `map cypher`, over the layers in view or the ones named, STORE-046.
- **The board drag test,** which fails under the browser driver; confirm whether it predates 2026-10-08 and fix it.
- **The ten baseline test failures** (build, provision, TUI, first working test, memory count, module data source).
- **Regenerate the MCP server dump** after lanes 1 to 3.

## Order and overlap

The four lanes can run at once, but they share files, which is the problem lane 4 solves:
- Lanes 1 and 2 both touch the intake module's condition handling (1.1 and 2.1). Build 1.1 first, or in the same lane.
- Lanes 2 and 3 both touch dispatch (2.3, 3.2) and the page (2.4). Keep 2.4 and 3.2's page work apart in time.
- Lane 4 touches dispatch's scheduling, which 2.3 also touches.

So: lane 1 (1.1) and lane 3 (3.1) start first, being the most separate; lane 2 starts with 2.1 once 1.1 has landed; lane 4 follows 2.3.
