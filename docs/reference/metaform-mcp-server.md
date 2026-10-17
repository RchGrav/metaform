# Metaform MCP server

What Metaform's MCP server sends to an agent, where each piece comes from, and how to change it. The tool tables below were generated from the running server, `metaform mcp serve` in this repository with the shipped modules that ship enabled, on 2026-10-11: 123 tools, whose `tools/list` entries are 114,095 bytes of JSON.

## The four things the server offers

An MCP server can offer four things. Metaform's server offers all four.

| What | When the agent gets it | Where it comes from in Metaform |
|---|---|---|
| Instructions | Once, when the agent connects | `<instructions>` in `src/metaform/modules/mcp/resources/prompts.xml`, with the notices the folder's state calls for |
| Tools | Listed at connect; called when the agent needs them | One tool for each command of each enabled module, and Metaform's own commands (tables below) |
| Resources | Only when the agent reads one by address | The addresses under [Resources](#resources) |
| Prompts | When the person types the slash command | The `<commands>` tag of each module's `prompts.xml` |

## Instructions

What the server sends when an agent connects is the mcp module's `<instructions>` element in `src/metaform/modules/mcp/resources/prompts.xml`, followed by the short notices a module adds for the folder's state, such as intake's first-run notice.

- **To change it:** edit that tag. The next agent that connects gets the new text. No restart and no reinstall are needed.
- **To send nothing:** leave the tag empty.
- **To read the guide to this folder's modules and state:** call `metaform_instructions`, with `module` for one module's full instructions, or read the resource `metaform://instructions`.
- **Length:** the MCP standard sets no limit. Claude Code keeps the first 2,048 characters of a server's instructions and drops the rest; its log says `Server instructions truncated from N to 2048 chars`. Other clients may keep more.

## How an agent calls a tool

Each command is its own tool. A module's command is `<module>_<command>`, such as `map_where` or `intake_start`; Metaform's own commands are `metaform_<command>`, such as `metaform_set` or `metaform_feedback`. A tool takes its command's arguments directly, as its input schema lists them, each with its type and description; every module's tool also takes `project` and `layers` for that one call. A tool's description is its command's summary, followed by its caution when it has one; a caution tool runs only with `confirm` true.

Each tool's annotations say what it does, from the effect its verb declares: `readOnlyHint` and `idempotentHint` for a read, `destructiveHint` for a removal and for a tool that is the person's decision (marked *person's decision* below), `openWorldHint` for a command that starts or steers agents or reaches the network. The Effect column below shows them. A result that is a JSON object comes as text and also as `structuredContent`.

A tool that is the person's decision (clearing the project, switching, collapsing or removing a base, deleting memories) takes no `confirm` from the agent: it runs only when the person says yes in the form their AI tool shows them. Without that answer, for a dispatched agent always, it is refused with its caution, which names what it would take, and the command the person runs, CLI-011 and MCP-006 (UX review round 1, 2026-10-17).

An error ends with one `Next:` line naming the tool to call or the resource to read.

## Turning tools off

`metaform disable <module>` turns a module's tools off everywhere and `metaform enable <module>` turns them back on. `metaform set --modules map,memory` shows only the named modules' tools in this folder, without disabling the others. A running session is told its tool list changed. The list is sorted by name and the same on every connection to the folder.

## Over HTTP

`metaform mcp serve --http` serves the same tools over Streamable HTTP at `http://127.0.0.1:7434/mcp`; `--port` or the setting `mcp_port` chooses the port. It serves the folder it is started in to every client that connects, and refuses a request whose Host or Origin is not 127.0.0.1 or localhost. For Claude Code:

```
claude mcp add --transport http --scope user metaform http://127.0.0.1:7434/mcp
```

`metaform set --mcp-transport http` makes `metaform install` register that address with each AI tool instead of the stdio command.

## From cloud AI tools

ChatGPT, Claude on the web and other remote hosts reach a Metaform on a person's own machine through the cloud broker at `https://metaform.ing/mcp` (or `/mcp/<instance>` for a machine with its own name). On that machine: `metaform cloud login`, then `metaform cloud connect`; in the AI tool, a custom connector at that URL. The same tools are served, with each tool call held to the scopes the AI tool was granted and the machine allows (`cloud_capability`). See the cloud module and docs/guides/metaform-node.md.

Over HTTP and the cloud tunnel the server also offers the two tools ChatGPT calls by name (setting `mcp_search_fetch`):

| Tool | What it does | Effect |
|---|---|---|
| `search` | Search this Metaform: the map's layer items, the memories and the project's terms. Returns ids to read with fetch. | read |
| `fetch` | Read one result of search by its id: a node's brief, an item, or a glossary. | read |

## Resources

| Address | What it holds |
|---|---|
| `metaform://metaform` | Metaform's glossary, the terms every agent works by, the mcp module's glossary prompt as written and nothing more. It replaced `metaform://glossary`; no alias is kept |
| `metaform://{project}` | The folder's project's own glossary: the peer register standard, then the project's terms from its map, generated by the map module |
| `metaform://tools` | Every tool in one line, grouped under its module's prefix, then the enabled modules' rules; for an AI tool that lists tools by name only |
| `metaform://instructions` | The guide to this folder's modules and state, as `metaform_instructions` gives it |
| `metaform://instructions/{module}` | One module's full instructions, as `metaform_instructions` gives them with `module` |
| `metaform://prompts/{name}` | A stored prompt's newest text and version, by name |
| `metaform://reports/{name}` | One report, feedback or shape file exactly, by the name `metaform_list_reports` gives |
| `metaform://intake/procedure`, `metaform://intake/schema` | The intake procedure and its forms, declared by the intake module |
| `metaform://{address}` | One node's brief, such as `metaform://code.manager.route`: the map's `where` read of it as a session's first read gives it |
| `metaform://{address}/items/{n}` | The one memory, ticket, question or message numbered n at the address, n in hex as shown, such as `metaform://code.manager.route/items/1f` (the fragment form `metaform://code.manager.route#1f` is read too): its title, why, body and links. A missing address or item is refused with `-32602` and a next step |

`metaform://tools` ends with the rules block: each enabled module's `<rules>`, one line each, `[<module>] <rule> Why: <why>`. `completion/complete` fills an Address in the address templates, one segment at a time, and the numbers at an address. A client that lists `metaform://{address}` in a `subscriptions/listen` stream's `resourceSubscriptions` is sent `notifications/resources/updated` for it when an item is numbered there.

## Extensions

Each is served only to a client that declares it on the request, and every tool still answers in full text without it.

| Extension | What Metaform does with it |
|---|---|
| MCP Apps, `io.modelcontextprotocol/ui` | `map_where` and `map_roots` open `ui://metaform/map`, the web GUI's 2D and 3D map focused on the address; `map_item` and `map_node` open `ui://metaform/node`, the node with what relies on it, what it relies on and its numbered items; `dispatch_sessions` and `dispatch_start` open `ui://metaform/trace`, the ticket's agent threads followed while the agent works; `metaform_instructions` and `map_glossary` open `ui://metaform/glossary`. The views use the official MCP Apps SDK, `@modelcontextprotocol/ext-apps` 2.0.3, declare an empty content policy, the clipboard and their border in `_meta.ui`, follow the host's theme, size and display modes, and read through `metaform_view`, an app-only tool the model never sees. Selecting a node tells the agent which Address the person is looking at; an Address the agent names in a later call turns the open views to it, and a host that calls a view's own tools can turn it with `metaform_view_show`. The map view is built by `scripts/build_map_view.mjs`, which the wheel build runs; a map view older than the page is not served. Settings `mcp_apps` and `mcp_apps_offer`. |
| Tasks, `io.modelcontextprotocol/tasks` | A verb declared `task=True`, such as `hello_wait`, is answered with a task while it runs on in the server, kept in the project for a day so it outlives that server; a verb declared `task='run'` is answered with the workflow run the server advances by itself as the task (none ships yet: `workflow_assign`, whose run id the calling agent acts on, answers as any tool). `tasks/get`, `tasks/update` (the person's answer to a paused run) and `tasks/cancel` work on both; a cancel ends a task cancelled once its verb stops, or completed with its result when the verb finished first. Setting `mcp_tasks`. |
| Elicitation (core) | A tool with a caution, and a person-only setting an agent asks to change, are put to the person as a form: `input_required` on the 2026-07-28 wire, `elicitation/create` on the 2025 handshake. Never for a dispatched agent. Setting `mcp_consent`, person only. |

## Tools

### agents

The roles of the agents Metaform starts, the prompts each is sent, and what each session was sent.

| Tool | What it does | Effect |
|---|---|---|
| `agents_drop` | Go back to a prompt's shipped text, so its edit is no longer sent. Caution: Every agent of the roles that name this prompt is sent the shipped text from its next turn. | write |
| `agents_override` | Save an edit of a role's prompt, sent in place of the shipped text from the next turn. Caution: Every agent of the roles that name this prompt is sent the edit from its next turn. | write |
| `agents_role` | Read one role: what it is for, each prompt it is sent with its text and version, its tools and authority, and the agents running as it. | read |
| `agents_roles` | List the roles of the agents Metaform starts, with the prompts each is sent. | read |
| `agents_sent` | Read which role a session ran as and which prompt versions each of its turns carried. | read |

### dispatch

Start an agent on a ticket through ACP, follow it, message it and stop it.

| Tool | What it does | Effect |
|---|---|---|
| `dispatch_agents` | List the agents dispatch can start, the default among them, and how many more may be summoned now. Each comes with its name, its start command, and whether that command is found on this system. | read |
| `dispatch_autostart` | Start agents on the waiting tickets in board order, while the person has Autostart agents checked. Held tickets are left out, and at most dispatch_agents run at once. | write, open world |
| `dispatch_broadcast` | Send a person's message to every agent running on the project at once, and keep it with whom it reached. | write, open world |
| `dispatch_broadcasts` | List the broadcasts kept on the project, newest first, each with whom it reached. | read |
| `dispatch_claim` | Reserve the part of the map a chosen proposal touches, so no other ticket there starts until its tickets land. | write |
| `dispatch_claims` | List the work claims reserving parts of the map, with their state, and the proposals sentinels made. | read |
| `dispatch_cancel` | Cancel a ticket, the person's own: its agent's turn is cancelled with session/cancel, its session ends, and the ticket is closed with the outcome cancelled, never completed. Refused to an agent while agents_may_set_control is off. | remove, open world |
| `dispatch_fork` | Fork a running agent's session into a side conversation that keeps everything it knows, where its agent offers session/fork; its thread is a child of the session's. | write, open world |
| `dispatch_handoff` | Read a ticket handed to you by its id: the ticket, the node it is at and the counts there with the calls that read them, and one line saying to work it with map_work. Its reads are named as tool calls, with metaform:// links to the node and the ticket. | read |
| `dispatch_intake` | Start an agent on this project's intake, recording the map as it follows the intake prompt. An open page follows it. It counts as a summoned agent; one intake runs at a time. | write, open world |
| `dispatch_interrupt` | Interrupt the turn of the agent working a ticket, keeping its conversation open. | write, open world |
| `dispatch_link` | Link a file to the element whose functionality it realizes: its path added to the element's refs in the sources layer, which unlocks writing it and places it on the map. Optional `ref`, the ref's name, and `why`. | write |
| `dispatch_merges` | List the agents' merges waiting for the person's review, the soonest first. | read |
| `dispatch_options` | List the settings each agent offers, its model, effort, mode and the rest, as it offered them at its last session in this project, and the ones dispatch_<agent>_<option> gives it. prime=true starts the agent once to read them, with no prompt. | write, open world |
| `dispatch_message` | Send a person's message to the agent working a ticket. | write, open world |
| `dispatch_note` | Send a short note to the agents working other open tickets, by ticket, part of the map, file or topic: information each reads at its next turn, kept on every ticket it touches; it never steers. With wait=<seconds> it is a question, and the call waits for the replies. | write, open world |
| `dispatch_notes` | List your notes, sent and received, with where each stands for each receiver: queued, delivered, read or replied; note=<id> for one note and its replies. | read |
| `dispatch_peers` | See who is at work where: each agent on an open ticket, its Address, the files it touched and what it said last. With at=, file= or topic=, who else is in that part or file, with a note ready to ask them before you edit. | read |
| `dispatch_prep` | Start an agent in a merge's worktree to prepare its code for the person's review. | write, open world |
| `dispatch_propose` | Record a sentinel's proposals for the issue it was raised on, for the person to choose one on the page. Each is presented beside the part of the map it reserves. | write |
| `dispatch_recover` | Return the tickets of dead agent runners to the queue, while the dispatch_recovery setting is automatic. Cleanup it cannot be sure of leaves the work taken. | write, open world |
| `dispatch_registry` | List the agents of the ACP Registry dispatch can start, each with its version and whether it runs here, and pin one: add=<id> installs the version listed now and dispatch starts that version until you pin another. | write, open world |
| `dispatch_reset` | Put agent bookkeeping back in order after a crash, returning tickets no live agent holds to the queue. Dead sessions are recorded as ended; live agents are left alone. | write |
| `dispatch_resume` | Resume an ended agent session in place, so the agent keeps its memory and its thread goes on. It works where the agent can load or resume a session, and waits for your next message. | write, open world |
| `dispatch_review` | Hold a waiting merge for the person's review, cancelling its automatic merge for good. | write |
| `dispatch_sessions` | List the agent sessions of a ticket, or of every ticket, each with its thread. | read |
| `dispatch_signals` | Read the signals raised on agent sessions, such as an agent that stopped with its ticket open. With active=false, the cleared ones too. | write, open world |
| `dispatch_spend` | Read what agents have spent today, on a ticket and by run, in billable tokens and reported cost, against the budgets; sessions that report no usage are named. | read |
| `dispatch_start` | Start an agent on a ticket; it returns at once, and the map shows the agent at work. On a ticket with an agent glyph, the agent then works the glyph's other tickets in turn. | write, open world |
| `dispatch_stop` | Stop the agent working a ticket. | write, open world |
| `dispatch_stop-all` | Stop every agent of the project, or of every project with home=true, and turn Autostart agents off, so nothing starts in their place. | write, open world |
| `dispatch_system` | Start the person's system agent, who talks with them about anything in the project, or reuse the running one; `fresh=true` resumes no earlier conversation. | write, open world |
| `dispatch_tune` | Set the model and effort the agent working a ticket uses, over dispatch_<agent>_<option>; the person's own. A running session takes them at once. Refused to an agent while agents_may_set_control is off. | write |
| `dispatch_talk` | Talk with an agent about a ticket, a node, or an ended agent's session. The ticket may be open or done; an agent at work on it is talked to directly. | write, open world |
| `dispatch_wait` | Wait until a ticket is done, its agent stops with it open, or a signal is raised on it. With no id, until any ticket of the project is, naming which. It answers pending with the call to make next after dispatch_wait_seconds. | read |

### fork

Build and maintain your own repository of Metaform modules.

| Tool | What it does | Effect |
|---|---|---|
| `fork_init` | Create a repository for your own Metaform modules, in a new or empty folder. | write |
| `fork_upkeep` | Bring the older modules of a module repository up to the current template, each as a pull request. | write, open world |

### intake

Serve the intake and record its result as it is reasoned.

| Tool | What it does | Effect |
|---|---|---|
| `intake_element` | Record one element of the intake at its address; recording it again replaces the fields given. | write |
| `intake_finish` | Finish the intake. One recorded in a base of its own is finished beside the active map, which stays active: metaform map activate <its name> --confirm makes it the active one. A verification pass is closed on the map it wrote onto, activating nothing. After finish the metaform changes by refining, metaform map refine, or by another intake. | write |
| `intake_prompt` | Read the intake instructions an agent follows to record this project's map. | read |
| `intake_purpose` | Record one purpose record: a receiver's OP and the elements that serve it, with its EF. Recorded again with an element it holds, the fields given replace its own and new elements are added. | write |
| `intake_remove` | Remove one element, one purpose record, or one element from a purpose record, from the intake being recorded. Each is named by addresses. | remove |
| `intake_schema` | Read the shape the intake records: namespace roots, Upstream and Downstream links, element and purpose record forms. | read |
| `intake_show` | Read the intake being recorded, whole or one receiver at a time. | read |
| `intake_start` | Start recording this project's intake, or resume the one being recorded. On a project whose intake is finished it stays on that map: conditions, notes and refs are written onto it, and recording a new element or purpose record opens a separate intake-<UTC timestamp> metaform, keeping the earlier one untouched. Returns its name; the existing web GUI follows it live. | write |
| `intake_status` | Say whether this project has an intake, and whether one is being recorded. | read |

### map

Read and write this project's functional map and its layers.

| Tool | What it does | Effect |
|---|---|---|
| `map_activate` | Make one of the project's bases the active map. Caution: This changes the active map for every agent and the page of the project. The previous base is kept; map activate <its name> switches back. | write, destructive, person's decision |
| `map_add-base` | Start a new, empty base for the project and make it the active map. Caution: This changes the active map for every agent and the page of the project. The previous base is kept; map activate <its name> switches back. | write, destructive, person's decision |
| `map_answer` | Answer a blind-spot challenge the critic raised: A, B or C. | write |
| `map_bases` | List the project's bases, the maps it keeps, and which one is active. | read |
| `map_challenges` | Read the answer prompt with each challenge of a blind-spot layer and its state. | read |
| `map_children` | List the artifact types one segment toward the leaves from an address. | read |
| `map_citing` | Find everything on the map whose refs hold a key and value, such as a file path. | read |
| `map_clear` | Remove a select or mask set at an address. | write |
| `map_collapse` | Rewrite the current map as a new base of one base layer and make it active; the old one is kept whole. Each element and join is written once, with the same ids. Caution: This changes the active map for every agent and the page of the project. The previous base is kept; map activate <its name> switches back. | write, destructive, person's decision |
| `map_context` | Read the properties that apply at an address, and those attached toward the leaves that are visible there. | read |
| `map_critic` | Start a blind-spot critic run: a new blind-spot layer, and the critic prompt with the whole base. | write |
| `map_cypher` | Ask the map a question in Cypher: a read-only query over the graph of the layers in view or named. | read |
| `map_element` | Read one element: its address, name_length, name, role and short name. | read |
| `map_glossary` | Read the project's glossary: its terms, from the map's element names and those added, each defined in the project's words. | read |
| `map_hide` | Hide a layer from every read in context. Caution: This hides the layer, and every layer built from it, from every agent. | write |
| `map_history` | Read every version of a thing on the map by its id, from the row that added it through each refinement. | read |
| `map_identity` | List every join an element provides for: the receiver, its OP, and the EF that serves it. | read |
| `map_item` | One item at an address by its number, <address>#<n>: its title, why, body and links. | read |
| `map_joins` | List the joins an element receives, or with as=provider the joins it provides for. | read |
| `map_knowledge` | Build a knowledge layer, a CEL on top of the map that agents use to index and understand the AUE. Create it, add, edit and remove its objects one at a time, and finish it. | remove |
| `map_layer` | Read everything one layer holds, or what it holds at one node. | read |
| `map_layers` | List the layers with their kind, tags and state, and whether each is on here. | read |
| `map_links` | List the layer items that link to a node. | read |
| `map_mask` | Stop a layer reaching an address and every address toward the leaves from it. | write |
| `map_messages` | List the questions and messages left for the person at nodes, or move one to another node. | write |
| `map_node` | Read every layer's items at one node, grouped by layer. | read |
| `map_promote` | Give a join an element of its own at an address, keeping the join and its history, memories and work. | write |
| `map_reexamined` | Clear a layer's re-examination mark once its knowledge has been checked against the changed base. | write |
| `map_refine` | Refine the base: change or remove one of its elements or joins as a new version, keeping every earlier one. | write |
| `map_remove-base` | Take one base out of the project; a copy of its store is kept. Caution: Removes the base and its store; a copy is kept under backups/remove-base. The active base is refused. | remove, person's decision |
| `map_reply` | Answer a question at a node, or mark a message read. | write |
| `map_roots` | Read the map's entry: the CQU and the DE with their joins, and every root element. | read |
| `map_search` | Find the layer items whose value holds every word of the text. | read |
| `map_select` | Turn a layer on at an address and at every address toward the leaves from it. | write |
| `map_tag` | Tag a layer, so it can be named by the tag wherever layers are named. | write |
| `map_term` | Add, edit or remove a term of the project's glossary, with its definition, why and source. | write |
| `map_unhide` | Show a hidden layer again. | write |
| `map_untag` | Remove a tag from a layer. | write |
| `map_where` | Read one address on the map: its element, what relies on it, and what it relies on, each with its purpose. How much is held at it and around it is counted, with the calls that read it; with an empty address, the map's entry. | read |
| `map_work` | Work with tickets, the work records on map elements and joins: list, read, add, edit, take and finish them. To work a ticket handed to you: read it with id=; op=plan with the steps you plan; op=step as each finishes, saying what you did and any choice you made with its why; op=done with a resolution and a why when it is complete; when you stop with it open, op=edit its note to say what is true now and where. A ticket never changes the map, and it moves across the board as it is worked. | write |

### memory

A memory graph, presented at each node of the map as the MCP reference memory server.

| Tool | What it does | Effect |
|---|---|---|
| `memory_add_observations` | Add observations to memory entities that already exist, at a node or in the whole memory graph. | write |
| `memory_create_entities` | Record what happened in the work at a node of the map: new memory entities with their observations. What is true of the project goes to the knowledge layers. Without node, they go in the memory graph joined to no node. | write |
| `memory_create_relations` | Relate memory entities to one another, at a node or in the whole memory graph. Relations should be in active voice. | write |
| `memory_delete_entities` | Delete memory entities and their relations, at a node or in the whole memory graph. Caution: Deleting memories removes them from the memory graph for every agent; no copy is kept and it is not undone. | remove, person's decision |
| `memory_delete_observations` | Delete observations from memory entities, at a node or in the whole memory graph. Caution: Deleting memories removes them from the memory graph for every agent; no copy is kept and it is not undone. | remove, person's decision |
| `memory_delete_relations` | Delete relations between memory entities, at a node or in the whole memory graph. Caution: Deleting memories removes them from the memory graph for every agent; no copy is kept and it is not undone. | remove, person's decision |
| `memory_graph` | Read the whole memory graph with its joins to the map: who wrote each, and whether each shows at its node. | read |
| `memory_joins` | List the memory joins that tie entities to map nodes: at a node, of an entity, or all. Each comes with who made it and whether it is orphaned. | read |
| `memory_note` | Read the person's one note at a node of the map; only the web page writes it. | read |
| `memory_open_nodes` | Read memory entities by name, at a node or in the whole memory graph. | read |
| `memory_orphaned` | List the memory joins whose address the active map no longer holds, with what each was attached to. | read |
| `memory_read_graph` | Read the memories at a node of the map, or the whole memory graph without one. | read |
| `memory_rekey` | Move the memory joins and notes at an old address to the address that replaced it. | write |
| `memory_search_nodes` | Search memory entities by name, type and observation text, at a node or in the whole memory graph. | read |
| `memory_unjoin` | Detach one memory join from its node by its id; the entity stays in the memory graph. | remove |

### twilio

Whether the person's phone, through Twilio, is set up; the bridge, calls and texts are the person's own commands, on the
command line only.

| Tool | What it does | Effect |
|---|---|---|
| `twilio_status` | Show whether the phone is set up and why not, the webhook URLs to paste into Twilio, and which credentials are in the environment, by name only. | read |

### elevenlabs

ElevenLabs's voices and Scribe, as a speech engine for voice; it receives what it speaks and hears. `elevenlabs speak` is on the command line only.

| Tool | What it does | Effect |
|---|---|---|
| `elevenlabs_models` | List the text-to-speech models your ElevenLabs account can use. | read |
| `elevenlabs_status` | Show whether the ElevenLabs key is present and the settings in use. | read |
| `elevenlabs_voices` | List each mascot character's voice and the voices on your ElevenLabs account. | read |

### voice

Speech to text: talk to Metaform instead of typing, with Whisper on your own machine. `voice speak` is on the command line only, since it spends the person's ElevenLabs account.

| Tool | What it does | Effect |
|---|---|---|
| `voice_download` | Download a Whisper model once into the Metaform home, showing its size first. | write |
| `voice_models` | List each engine's Whisper models, their sizes and whether they are downloaded. | read |
| `voice_status` | Show which speech engine is in use and why, its device, model and whether it is loaded. | read |
| `voice_transcribe` | Turn an audio file's speech into text, with its segments. | read |

### web

Start and stop Metaform's web GUI, and serve web variants.

| Tool | What it does | Effect |
|---|---|---|
| `web_start` | Start the web GUI, or show the address it already runs at. | write |
| `web_stop` | Stop the web GUI. | write |
| `web_restart` | Stop the web GUI and start it again; it comes back even if your session ends meanwhile. | write |

### workflow

Write, import and run reusable Axiom subroutines.

| Tool | What it does | Effect |
|---|---|---|
| `workflow_add_logic` | Record a named Axiom subroutine on a workflow element or any other project element. | write |
| `workflow_assign` | Hand a workflow skill to a fresh agent: it gets a run id and reads its assignment with resume. | write |
| `workflow_call` | Call an Axiom subroutine on the same agent, keeping the caller's scope. | write |
| `workflow_cancel` | Cancel a run and every run below it; its caller receives the error cancelled. | write |
| `workflow_complete` | Finish a run: deliver its RETURN to the caller, or close an assignment. The interpreter supplies its final variables. | write |
| `workflow_export` | Export a workflow from its stored layer as a portable document, printed or written to a file. | write |
| `workflow_fail` | Fail a run: deliver an error to its caller, for the caller's authored Retry or Catch. | write |
| `workflow_handoff` | Start a callee run for a fresh agent; its run id reaches that agent directly or through the orchestrator. | write |
| `workflow_history` | Read every saved version of one named Axiom subroutine on an element. | read |
| `workflow_import` | Import a portable workflow document into an ordinary knowledge layer. | write |
| `workflow_lexicalize` | Read the prompt-lexicalization script with a prompt as input, to tie its names to map addresses. | read |
| `workflow_lib` | Read one Axiom lib: its shared sections at their newest stored versions. | read |
| `workflow_libs` | List the Axiom libs, each with its first line, its marker. | read |
| `workflow_list` | List the visible workflow elements and the names of their Axiom subroutines. | read |
| `workflow_parallel` | Run independent subroutine calls as branches; the run resumes when every branch returns. | write |
| `workflow_pause` | Pause a run on the person when something its logic does not decide stops it, saying what you found. | write |
| `workflow_preprocess` | Prepare a lexicalized prompt by placing the knowledge visible at its addresses before its address footer. | read |
| `workflow_resume` | Read a workflow run by its id: its current subroutine and values, or its assignment. | write |
| `workflow_run` | Start a workflow run: an entry call to an Axiom subroutine, whose run id the interpreter follows. | write |
| `workflow_runs` | List the open workflow runs, or those in one state, with what stopped a paused one. | read |
| `workflow_scan` | Read the scan skill, which decides the libs a task needs, with a workflow and its task bound as data. | read |
| `workflow_skill` | Read one workflow skill's Axiom, to follow it. | read |
| `workflow_skills` | List discoverable workflow skills with their descriptions and required libs. | read |
| `workflow_submit` | Record a workflow element, which holds Axiom subroutines, in an ordinary knowledge layer. | write |

### metaform

Metaform's own commands: settings, feedback and reports, and the project's history and prompts.

| Tool | What it does | Effect |
|---|---|---|
| `metaform_add_origin` | Establish an origin from the project's current state: the baseline that variants of work are stored against. As metaform add origin does. | write |
| `metaform_add_variant` | Collect a folder, such as a worker's worktree, as a variant of an origin: the work's changes against it. As metaform add variant does. | remove |
| `metaform_clear_project` | Clear the project's map, as metaform clear project does: remove its bases and reports. A backup is made first, and metaform restore project brings it back; its registration, folder, settings, origins, variants and conversations with agents stay. It is the person's decision: it runs only when they say yes in the form their AI tool shows them, and otherwise says what it would remove. | remove, person's decision |
| `metaform_extract` | Write variants out to folders as files you can read or run, with Python alone, as metaform extract does. | write |
| `metaform_feedback` | Save feedback on the Metaform process: a problem, bad semantics, or a trouble report when you cannot continue. Attach your report and the shape you could not submit when you have them. Always available. | write |
| `metaform_instructions` | Read how to use Metaform here: the guide to this folder's modules and state, or one module's instructions. As metaform instructions prints it; with module, that module's full instructions. Always available. | read |
| `metaform_list_origins` | List the project's origins, the baselines variants are stored against, as metaform list origins lists them. | read |
| `metaform_list_reports` | List the report, feedback and shape files saved for this project. Always available. | read |
| `metaform_list_variants` | List an origin's variants, as metaform list variants lists them. | read |
| `metaform_prompt` | Read a stored prompt's text and version, the newest unless a number is given. | read |
| `metaform_prompts` | List the stored prompts, each with its newest version number, as metaform prompts lists them. | read |
| `metaform_read_report` | Read one saved report, feedback or shape file exactly. Always available. | read |
| `metaform_register` | Register this folder as a Metaform project, so its map can be recorded and read. As metaform add project does; a folder already in a project is left as it is. Returns the project and the instructions for it now. Always available. | write |
| `metaform_save_prompt` | Save a named prompt as a new version, creating it or adding an edit; earlier versions stay unchanged. | write |
| `metaform_set` | Save Metaform settings for the server's folder, as metaform set does. | write |
| `metaform_skills` | List discoverable skills, load a skill by name or Address with current prompt-store libraries, or read one of its files. Internal skills remain explicitly loadable. `all=true` lists them for administrative inspection. Always available. | read |

`metaform_skills` takes `op=list|load|read`, `name` for load and read, and
`path` for read. The skill Address is `logic.skill.<kebab-name>` with its
version in frontmatter metadata. At connect, `skill_index=auto` adds a compact
index unless a current completed native deployment is recorded for the actual
client. `on` forces this index and `off` omits it. Internal skills appear in no
ordinary discovery list.
