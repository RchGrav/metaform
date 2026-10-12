# Design that is not built, as of 2026-09-27

This document lists every design point Rich has given that is not built, or is built differently from what he described. It is written for an agent that will rebuild the specification. Each point says what the design is, why, and its state.

## How to read it

- **State** is one of: not built, partly built, built differently, not checked. "Not checked" means I did not confirm the state against the code.
- **Why** is the reason as I understand it. Where no reason was recorded, the point says so. Do not invent one. Ask Rich.
- **Record** names the specification record that mentions the point, in `specifications/spec/`. A record id means the subject is mentioned there. It does not mean the record states the design correctly. 46 of the 273 records are marked recommended, which means an agent chose them.
- Rich's own text outranks every agent-written record. His own text is the MetaformFoundation in `CLAUDE.md` and the Canonical Intake in `specifications/Canonical_Intake.xml`.

## Sources

| Source | Holds |
|---|---|
| `CLAUDE.md` | The MetaformFoundation, Rich's text |
| `specifications/Canonical_Intake.xml` | The intake procedure, Rich's text |
| `specifications/spec/CAPTURE.md` | 221 design points from 09-11 to 09-27, each with a record id |
| `specifications/spec/OPEN-QUESTIONS.md` | The open D questions |
| `specifications/` top level, `specifications/product/`, `specs/`, `feature-briefs/` | Earlier specifications, restored 2026-09-27 from the `main` and `main-wip-2026-09-24` branches, not yet read against the nine sections |
| `exports/notes-export-2026-09-27.md` | All of Claude's notes, unedited |
| `exports/metaform-intake-20260927T212631Z-full.md` | The last intake of this repository, every field |
| `exports/spec-gap-inventory-2026-09-27.md` | The first, shorter inventory |

---

## 1. What an agent meets first

### 1.1 The top menu shows names only

- **Design:** The first thing a person or an agent meets is the top menu. It shows one name for each thing that can be entered, and none of the commands under it. The top menu is kept as small as possible.
- **Why:** Whatever is at the top is paid for by every session. Metaform exists to save the inference an agent spends orienting itself, and a surface that sends every command at connection spends that saving before work starts. A reader shown every command must weigh each against its task. A rule that adds one entry per command makes the top grow with every module anyone writes, so the clutter returns however often it is cleaned. Rich restarted the design several times over this.
- **State:** Built differently. The MCP server sends 64 tools, 55,139 bytes of schemas, about 13,800 tokens. `metaform help commands` prints every verb of every module.
- **Record:** CLI-037, written 2026-09-27. It corrects MCP-003 and MCP-004.

### 1.2 Commands are written `module:command`

- **Design:** A module's commands are subcommands of its name, written `foo:bar`. The top shows `foo`. `foo --help` lists the `foo:` commands.
- **Why:** The module reads as one command with everything it does beneath it, so fifty commands never sit at the top.
- **State:** Not built. Today the form is `metaform map where` and the tool `map_where`.
- **Open:** How `foo:bar` travels over MCP, whose tool names cannot hold a colon.
- **Record:** CLI-037.

### 1.3 The system is aware of the working folder

- **Design:** What an agent is shown and can run is decided for the folder it works in. A module's menu is reached two ways: the orchestrator forces a menu on a folder, or an agent enters a module by its name. The record of work done in a folder stays with the folder. No agent identity is tracked.
- **Why:** An agent has nothing lasting that identifies it. Subagents of one session share its session id and process id. The folder is a fact the orchestrator sets and the agent does not control. Continuity is the history of the work, and a history kept with the place reaches whoever continues the work. Deciding by folder also keeps an agent from widening what it was given.
- **State:** Partly built. Folder settings and the `folder=<path>` noun exist. Forcing a menu and entering a module do not.
- **Record:** CLI-038.

### 1.4 An alias is one top-level name for several modules

- **Design:** The orchestrator defines a name at the top menu that stands for two or three modules. Entering it gives the commands of all of them.
- **Why:** Without it, the only answer to an agent that needs three modules is to show it everything.
- **State:** Not built. The `modules` folder setting holds a list of modules and is what an alias grew out of.
- **Record:** CLI-039.

### 1.5 `set` and `unset` are for configuration settings only

- **Design:** They store and clear the same settings the settings screen edits. They are not how a module is entered.
- **Why:** A command with one meaning can be read without knowing its history. If `set` both configures and moves an agent between menus, a setting cannot be told from a place.
- **State:** Built differently. `set --modules` narrows a folder's commands, CLI-022.
- **Record:** CLI-040.

### 1.6 Switches are not sent into an agent's context

- **Design:** A command's switches are shown by that command's help, when the agent uses the command.
- **Why:** Switches are reference material. Sending them ahead of need charges every session for them.
- **State:** Built differently. Every tool schema carries each switch its verb reads. `map_knowledge` alone is 5,466 bytes.
- **Record:** CLI-037.

### 1.7 The instructions tell the agent what to do

- **Design:** The instructions an agent receives at connection say what to do next. When the project is not onboarded, they say to onboard it. They are short enough that the host shows all of them.
- **Why:** An agent that connects needs its next action. A description of each module gives it reading and nothing to do. Claude Code cut the instructions off at about 2,000 characters, so text placed last never arrived.
- **State:** Built differently. The instructions are the base text plus each module's `purpose` description, 2,573 bytes. The no-intake notice is placed last.
- **Open:** The wording. It is Rich's to set.
- **Record:** MCP-029. It corrects MCP-007 and MCP-008.

### 1.8 The module field named `purpose`

- **Design:** One vocabulary. A term has one meaning.
- **Why:** `purpose` in the module declaration is a short description of the module. Operative Purpose is a term of the map. Two meanings for one word mislead every reader.
- **State:** Built with the collision.
- **Record:** None.

### 1.9 The MCP server registration

- **State:** Registered for Claude Code on 2026-09-27 with `metaform install claude`. It was not registered before that. One older entry for another project uses the bare launcher path, which MCP-016 rules out.

---

## 2. Intake

### 2.1 Join text is a short statement to orient an agent

- **Design:** The text on a join is enough for an agent to understand the part from where it works, all the way around it. It is not documentation.
- **Why:** An agent reads a node to learn what a part is for, who receives it and what surrounds it. Detail of how it works is in the files, which the path refs name. Detail copied into the map goes out of date with the next code change, and every read pays for it.
- **State:** Built differently. The last intake wrote file names, class names, spec ids, exit codes and test counts into the observation and function fields.
- **Cause found:** The Canonical Intake sets no size or aim for join fields. The words short, concise and orient do not appear for them.
- **Record:** None. MAP-047 covers how an intake is graded.

### 2.2 An intake does not read past notes or memories

- **Design:** The intake reads the material targeted for intake and nothing else.
- **Why:** An intake that reads earlier maps and notes copies them. Measured: about 130,000 tokens on an earlier run, 300,000 to 600,000 tokens and 25 minutes on the last runs.
- **State:** Partly built. The intake footer says it since step 40. It cannot hold while the notes sit inside the folder being mapped, `specifications/spec` is 1.49 MB, and while a subagent inherits `CLAUDE.md` and Claude's memory index from the harness.
- **Record:** BASE-039 for the footer.

### 2.3 Intake by a fresh agent with no stake

- **Design:** A fresh agent with no stake in the project performs the intake. The main agent does it only when it is the only choice.
- **Why:** An agent embroiled in coding work carries the bias of that work into the map. Bias is a fact of all intelligence once it is embroiled, and it creates real blind spots.
- **State:** Partly built. The instruction exists. The last intake ran as a subagent inside the repository and reported that its context held the Foundation and the memory index.
- **Record:** MCP-009, LAYER-014.

### 2.4 The map is the whole intended project

- **Design:** The intake maps the project from its specifications and decisions as well as its code, so the map says what is built, what is not built yet, and where issues are. The intake layer holds functional shape only, never the condition of its objects.
- **Why:** A later agent needs to know what is intended, and the difference between intended and built is where the work is.
- **State:** Partly built. This point conflicts with 2.2 as written. An agent told to read the specifications reads the notes. How the two fit is open.
- **Record:** MAP-046. The Canonical Intake's wording is D99.

### 2.5 The intake does not depend on the size of the agent's context

- **Design:** The intake is recorded one object per call as it is reasoned, and proofed at the end. Each step of the method shows exactly what the agent adds and the call that records it.
- **Why:** A model that works the whole map out in its head before recording depends on how much it can hold. One Opus run read about 290,000 tokens before its first record.
- **State:** Partly built. The per-object tools exist. The Canonical Intake's steps do not show their calls.
- **Record:** MAP-040, BASE-039, D99.

### 2.6 Voice

- **Design:** Fields are written with third-person singular present-tense active verbs ending in -s or -es, so each reads as a sentence when printed after the element's name, and the fields read together. The intake also writes, for each element, one concise statement that continues from its name.
- **Why:** Text that reads as a sentence after the name can be printed on the map and in a prompt with no rewriting.
- **State:** Partly built. The relation and verb fields follow it. The element statement has no place to be recorded.
- **Open:** Which fields, which element's name, where the element statement is kept, D90.
- **Record:** MAP-020.

### 2.7 Workflow intake

- **Design:** An agent performs an intake of an imported workflow to infer its steps, handoffs and the relationships between inputs and outputs.
- **Why:** Reason not recorded in my notes. See `specifications/plugin-system.md` line 287.
- **State:** Not built.
- **Record:** None found.

### 2.8 Points with no record

| Point | Why | State |
|---|---|---|
| The intake is started before the intake agent launches | The page shows the new intake from the first moment, and the layer records the model | Done by hand |
| The intake ships with the release | It is part of the product. Attribution is what is protected | No record |
| `intake finish` reads a file for long text | Long report text on the command line needs heavy quoting | Not built |

---

## 3. Work on the map

The design is that an agent's work runs through the map once Metaform is installed. CAPTURE holds the full text under "Added 09-26 and 09-27". Nearly all of it has a record whose Build line says Open, D92.

### 3.1 Questions are asked and answered at the node

- **Design:** An agent adds a question at the node it concerns and carries on with what does not depend on the answer. The node glows while the question is open, brightly enough to see with the whole map zoomed out. A Messages button appears in the upper left of the 3D view while any question is open. Each click flies to the node of the oldest open question and opens its panel. Rich answers in the web GUI in real time.
- **Why:** Rich is handed lists of questions in documents and has to find and read them. A question shown at the part it concerns carries its own context, and answering on the screen keeps the agents moving.
- **State:** Not built.
- **Record:** MAP-050, VIEW-021.

### 3.2 Node states

- **Design:** Every look is a stored state agents can read. Errors pulse red until resolved, and the resolution is recorded beside the finding. What is specified and not built shows at 70 percent opacity. Work in progress pulses with a floating label that carries the agent's own words. States: blind spot, beneficial, approved spec, in progress, built. For errors: broken, fixing, resolved.
- **Why:** The orchestrator can ask for the errors to be fixed because the errors are data. The red node is the main benefit.
- **State:** Partly built. Work records with conditions exist. The in-progress looks wait on D92.
- **Record:** VIEW-020, VIEW-005, MAP-046, STORE-042.

### 3.3 Tasks on nodes

- **Design:** The orchestrator keeps the task list and writes each task on the nodes the work concerns. One command hands an agent the task with everything the map holds for those nodes. The server asks the agent to review the knowledge layers, tells it other agents' memories are there, and asks it to record its own. The agent keeps a sentence of its progress on each node. The map works as a kanban board.
- **Why:** The agent receives exactly the data its task needs and starts oriented.
- **State:** Not built.
- **Record:** MAP-048.

### 3.4 The task list is a work queue

- **Design:** Agents see the outstanding tasks. An agent that accepts one takes it off the list, so a swarm each takes one. A task whose agent dies stays taken, showing its age, until the orchestrator or Rich puts it back.
- **Why:** Many agents can work at once without two taking the same task.
- **State:** Not built.
- **Record:** MAP-049.

### 3.5 Past work

- **Design:** A completed task leaves the list and the node's label. Its record stays at the node as past work, with its age and the agent's log. An agent is told past work is there and is not made to read it.
- **Why:** A finished task no longer steers anyone, and history an agent does not need should not spend its context.
- **State:** Not built.
- **Record:** MAP-051.

### 3.6 Item flags, and rules that are listed

- **Design:** There are no categories of knowledge layer and no special kinds of item. An item is marked as a task, as read_first, or as always_show. Anything else is a note. What an agent is handed with a task lists the rules and does not carry their full text.
- **Why:** Showing rules in full every time wastes context. Being listed as rules is enough for them to be read.
- **State:** Not built.
- **Open:** Whether listing replaces read_first and always_show, D91.
- **Record:** LAYER-021.

### 3.7 Using Metaform to track Metaform's own work

- **Design:** The sessions that build Metaform record their work and questions in its map.
- **Why:** Rich pointed out on 2026-09-27 that this is not being done and that more would get done if it were.
- **State:** Not done. It depends on 3.1 to 3.4.

---

## 4. Knowledge layers

### 4.1 Another inference layer

- **State:** No knowledge layer has been built on a real map beyond the intake layer. Rich has not seen one.

### 4.2 Layers are built by a for-each prompt

- **Design:** The prompt runs at each node, and the agent writes the layer's content there from what the node says. Linking an element to the node where it belongs marks it a property. A layer for that property runs its for-each over every node the property reaches, toward the leaves and back toward the trunk. Items do not travel.
- **Why:** A property decides where a layer's work is created, so the agent does not have to find those places.
- **State:** Not built.
- **Open:** How a property is recorded, D88. MAP-022 says there is no property join. The Foundation says property joins.
- **Record:** LAYER-020, VIEW-022.

### 4.3 A best-practices layer

- **Design:** A knowledge layer that records best practices needs no property. At each node the agent infers them from what the node says.
- **State:** Not built.
- **Record:** LAYER-016, LAYER-020.

### 4.4 Roots are project information

- **Design:** Reading a project starts at its roots. Properties carry back toward the trunk, so `code` shows Python and C++ when Python is linked to the installer and C++ to the engine. Anything at a root is a rule for the whole project.
- **Why:** Stated in the Foundation. At the trunk the media of the project can be seen.
- **State:** Not checked.
- **Record:** LAYER-022.

### 4.5 Suggesting layers when an intake is offered

- **Design:** When the main agent offers an intake, it suggests a blind spot challenge and a best-practices layer, and asks whether that is all right.
- **State:** Not checked.
- **Record:** MCP-027.

---

## 5. Blind spot analysis

### 5.1 One metaform, two types of analysis

- **Design:** There is one Inference Metaform. A critic that reads only the metaform reasons from outside, on the functional description. A critic that reads the metaform with the code gives precise, actionable findings and is anchored by the code. Each creates its own layer. Both are kept. The terms Native and Latent are dated and are not used.
- **Why:** Bias comes from being embroiled in the code. The first critic sees that a whole approach is wrong. The second seldom does, and is almost always correct about what it does find. It finds gaps in the design, such as missing functions and encounters. It does not watch an agent during a task.
- **State:** Not built. The intake agent reports no critic prompt, no answer prompt and no module that runs a critic. Only the challenge states, answer, approve and plans exist.
- **Record:** LAYER-014, LAYER-015.

### 5.2 The review of blind-spot entries

- **Design:** An entry shows as a red node at 70 percent opacity because it does not exist. Agents review each. Useful turns it green. Not useful, with the reason, turns it yellow. Already handled names what handles it. Rich has the final veto. An approved entry becomes a permanent record of the metaform with provenance.
- **State:** Not built.
- **Open:** How an approved entry enters the metaform, and the form of the veto, D89.
- **Record:** LAYER-015, VIEW-020, STORE-040.

### 5.3 Critics write the task

- **Design:** A critic that sees an issue and knows what it needs writes the task with the finding. A finding is held until agents are assigned or take it. A task can be reviewed before it is released.
- **State:** Partly built. Work records carry held and reviewed.
- **Record:** MAP-046, MAP-049.

### 5.4 The ideation agent

- **Design:** An agent examines the whole project and adds the single most valuable missing feature. It may build its own module to do it.
- **State:** Not built.
- **Open:** Its reason, D103.
- **Record:** LAYER-023.

---

## 6. Changing the metaform

### 6.1 No correction layers

- **Design:** Changing the metaform is updating it. Each change is a new version of the object with provenance. A flag is never a correction. A join can be moved. An element cannot be moved, because it is an address.
- **Why:** An element is its place in the namespace, so moving it makes a different element.
- **State:** Built differently. The correction stack still stands.
- **Open:** Whether correction layers go entirely, D86.
- **Record:** LAYER-011, STORE-017, STORE-034.

### 6.2 The element record

- **Design:** The element is its address and name_length. The project's own name for a functionality goes on the join, which is where the map speaks about the artifact. Removing an element and recording it again at the same address brings back the same element with every record related to it.
- **State:** Partly built. Not checked for the last sentence.
- **Open:** The role on the element when one project holds several AUEs, D87.
- **Record:** MAP-015, MAP-020, STORE-009.

---

## 7. Workflows and prompts

### 7.1 The workflow module

- **Design:** Metaform enables prompt-chained workflows. The orchestrator hands work by name, the workflow's own text reaches the worker exactly as written, and the orchestrator never rewords it.
- **Why:** A prompt chain that is reworded at each handoff is not repeatable. The results should depend on the procedure.
- **State:** Not built. No workflow module, no `--workflow`, no abort, no receipts.
- **Record:** MAP-006, LAYER-017, D44.

### 7.2 Lexicalized prompts

- **Design:** An inference pass tags each step's prompt with the addresses whose memories and knowledge layers that step needs, so a subagent goes straight to them.
- **Why:** This is why names and addresses matter. A prefix prompts on its own.
- **State:** Not built.
- **Record:** LAYER-017, STORE-035. See `specifications/metaprompting_element_segments_example.md`.

### 7.3 The workflow document format

- **Design:** An XML workflow format, with import that keeps the authored text and behavior.
- **State:** Not built. Not placed in the spec.
- **Record:** D44.

### 7.4 The prompt store

- **Design:** Prompts are versioned records. An edit makes a new version for later runs. Provenance names the exact version that produced a layer.
- **State:** Built and not connected. The intake agent reports that nothing outside the tests calls it, no module ships a prompt, and the store stays empty.
- **Record:** STORE-044, VIEW-013.

---

## 8. The web GUI

| Point | Design | State | Record |
|---|---|---|---|
| Prompt editor | Split screen that can go full screen, the graph on the left half and collapsible, a word-processor editor where objects are inserted from a menu and show their text | Partly built, with nothing to open because the prompt store is empty | VIEW-013 |
| Answering questions | See 3.1 | Not built | VIEW-021 |
| Submitting work | A person submits work directly in the GUI | Not built | D92 |
| Property reach | Clicking a property node shows its reach, with particles along the edges and every node it reaches taking its color | Not built | VIEW-022 |
| Variants side by side | Web variants each served on their own port | Not built | PROJ-019 |
| Presentation | No ASCII graphs in the README or docs. Mermaid and GUI screenshots | Not checked | None found |

---

## 9. Chassis, modules and packaging

| Point | Design | Why | State | Record |
|---|---|---|---|---|
| Project place | Modules that load only from the active project | Reason recorded: a project can carry its own modules | Not built. A shared host would leak one project's module into others | BASE-014, D93 |
| Origin as a wheel | Export and import of an origin unit as a wheel | A project can be carried whole | Not built | PROJ-020, PROJ-021 |
| Backup and restore | Separate from import and export | Not recorded | Not specified | STORE-027 |
| CalVer | CalVer during development | Not recorded | pyproject says 0.1.0. The format is open | BASE-020, D94 |
| Install front door | Installing never downgrades without force, with a first-run check for raw pip installs | Not recorded | Not checked | BASE-047, D100 |
| Wheels for forks | CI builds wheels with the module set that has passed, an agent checking each module | A fork can administer itself | Not built | BASE-027 |
| First-run provisioning | Under an unfamiliar harness, Metaform offers help for each feature the harness supports, and never asks again once done | Only the agent knows what its harness supports | Not built | MCP-028, D96 |
| Its own metaform | Metaform ships a metaform of itself to develop itself | Not recorded | Not built | BASE-048, D102 |
| Project clear | Clearing a project's data so intake starts from nothing | Rich asks for it every time | Built, per CLI `clear` | PROJ-025 |
| The git side channel | Worktrees diffed even when never committed, and the ten variations of an iterative workflow stored as a set | Rich does not want this capability lost | Not checked | PROJ-010 to PROJ-024. See `specifications/data_folder.md` |

---

## 10. The Markdown exporter

- **Design:** `metaform map markdown` writes the map, or the part around one address, as a short Markdown document: each element's name, address, role and paths, and for each join its receiver, provider, relation, purpose and non_goal. The function and the observation are left out. It is a command and not a tool.
- **Why:** A concise export of a system's understanding that a person can read and pass on.
- **State:** Not built. The record and four failing tests are written. The code is not.
- **Record:** MAP-052.

---

## 11. Where the specification disagrees with the MetaformFoundation

The Foundation is Rich's text. I have not judged which side is current. Each needs his ruling.

| Subject | Foundation | Specification |
|---|---|---|
| Bases | code, document, media, data, exterior | MAP-014: stakeholder in place of exterior |
| Join roles | hard dependency, property, supportive | Removed on 09-25. Hard dependency is MAP open question 17 |
| Parametric | An array of tunables on a Type, names reserved as illegal entries | No record |
| Signal | The way an Operative Purpose is satisfied | No record in this sense |
| SE | Supportive is a role in the join | MAP-017: Substantial Element |
| C(T) | Each Receiving Entity bound to its Operative Purpose and the Type's single Encounter Function | MAP-001: theory, stored nowhere |
| Property joins | Property joins are transitive | MAP-022: a property has no join |

---

## 12. Rich's description of the system, TRAO-DAG

- **Design:** Rich's own description, given 2026-09-26. It has a binary state on nodes and edges: Func for the designed capability of the Type, Enc for a specific situational activation. Annealing collapses subtypes with the same Func join paths. Prompts expand from a node's Func layer. Blind spots are computed as Func capabilities minus Enc manifestations.
- **State:** Partly built. `ef` on joins and annealing exist. The state on nodes and the computed delta do not.
- **Problem:** The text is not in the repository. It is in a session transcript. Rich should be asked for it.
- **Record:** MAP-020, MAP-030, D101.

---

## 13. Points with no record at all

| Point | Why |
|---|---|
| Code that belongs to Rich's employer never appears in demos, tests or anything public | It is not his to publish |
| Jev: optional, never a requirement. Low confidence goes back to the entering agent, never to a stronger model | Not recorded. See `specs/jev-analysis.md` |
| The DE is nearly the artifact itself | It explains a term of the Canonical Intake |
| No polling and no blocking, system wide | Use the event bus and push. QUAL-015 and QUAL-016 cover part |
| A capability added for a feature updates the template module and gets a helloworld demo | Module authors start from the template, so it must show every capability |

---

## 14. Modules planned for later

Further modules are designed. At Rich's request their details are not recorded until the core is stable. What they need of the core is in section 1. Record: BASE-049.

---

## 15. The state of the specification itself

- **Two places.** Agents made `specifications/spec/` on 2026-09-24 and wrote the nine sections there. Rich never asked for a folder inside `specifications/`. When he says specs he means the specifications.
- **Files left off the branch.** When `chassis` began on 2026-09-24, 38 files of `specifications/`, 11 of `specs/` and 27 of `prompts/` were left behind. They were restored to disk on 2026-09-27 and are not committed.
- **Records without reasons.** Many records hold what Rich said and a date. A later agent cannot act correctly from that. Each record's Why must state the reason in the system's terms.
- **Not done here.** I did not read each of the 273 records against the design. I did not read the restored earlier specifications. Both are needed before the specification can be called complete.
