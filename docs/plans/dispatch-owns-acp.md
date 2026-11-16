# Dispatch owns ACP

Status: design, 2026-11-16. Steps 0 and 1 are built; the rest is in order below.

## The goal

One module, dispatch, is the only part of Metaform that speaks the Agent Client Protocol (ACP). It knows which
harnesses exist, which can run on this machine, what each one offers, and it starts every agent. Any other module
that needs an agent asks dispatch through the channels that already exist: dispatch's verbs, the services it
declares, and the event bus. No module starts an agent process or speaks ACP on its own.

Dispatch is therefore required. It ships enabled, and other modules assume it.

## What ACP gives us to work with

Read from agentclientprotocol.com on 2026-11-16 (protocol v1, the v2 draft, and the open proposals).

- **A harness says what it can do in two steps.** `initialize` answers with its name, version, capabilities and
  login methods. `session/new` answers with its config options: model, thinking level, mode and anything else,
  each with its choices and its current value.
- **Options depend on more than the harness.** The protocol says they can depend on the working folder and on the
  account that is logged in. So what a harness offers is knowledge about a harness version on this machine, and
  each session's own answer is the final word for that session.
- **There is no stable way to ask for options without a session.** A proposal, `session/options` (drafted
  2026-11-03), adds exactly that, and lets a client pass its chosen values on `session/new`. A harness that
  supports it says so with the `sessionCapabilities.options` capability. Until a harness does, a client makes a
  session, reads the answer, and closes and deletes the session without sending a prompt.
- **Choices are set with `session/set_config_option`.** The answer is always the full list, because one choice can
  change another's values (a model changes the thinking levels on offer). Order matters: model first.
- **Modes are the old form of one config option.** A client that reads config options ignores modes.
- **The registry lists 46 harnesses.** Each entry names how it is started: an npm package through `npx`, a Python
  package through `uvx`, or a binary archive per platform. Every listed harness supports a login through ACP.
- **"Any model" is not in the stable protocol.** A harness serves the models its own provider gives it. A proposal,
  Configurable LLM Providers (`providers/list`, `providers/set`), lets a client point a harness at another endpoint.
  It is a draft; we use it for a harness that advertises it and claim nothing for one that does not.
- **v2 is a draft, and the protocol's own guidance is to support v1 and v2 side by side** (Migrating from v1,
  "Supporting v1 and v2 side by side"). The client asks for version 2. A v1-only harness answers 1, and the client
  carries on in v1 or reconnects with a v1 `initialize` when it needs what a v2 request left out (client files,
  terminals, terminal login). One connection speaks exactly one version after `initialize`. What differs in v2:
  - `session/prompt` only acknowledges the message. The turn's progress and its end arrive as `state_update`
    (`running`, `idle`, `requires_action`), and the stop reason is on the idle update.
  - Messages and tool calls are updated by id: a field left out is unchanged, `null` clears it, a value replaces it,
    chunks append. Plans are replaced whole by `planId`.
  - The client's file and terminal methods and session modes are gone. Modes are config options; client-side tools
    are MCP servers passed at session setup.
  - Capabilities are one `capabilities` object with `info`, session features under `session`, presence instead of
    booleans, and list, resume, close, prompt and cancel are always there. `session/load` is `session/resume` with
    `replayFrom`. `authenticate` is `auth/login`.
  - Unknown enum values and update kinds are kept, never rejected.
  The guidance is explicit on structure: two thin protocol layers behind shared application logic, one chosen
  after `initialize`; adapters, not blanket conversions between the versions' structures; v2 behind a flag until it
  stabilises; and both versions exercised by the same tests.

## Where the code stands

Dispatch's protocol handling is sound: capabilities, config options, modes as a fallback, logins, session
close and delete are all handled as the protocol describes. The faults are in how it is organised.

1. **What a harness offers is stored per project, and only after it has run there.** Every picker reads one
   function, `catalog_rows`, backed by a table in the project's store. A new or cleared project knows nothing, and
   the page prints a shell command instead of asking the harness.
2. **Three harnesses are written into the code** (`AGENTS`). Registry harnesses can be added only from a shell, and
   their options cannot be chosen at all, because the option settings are declared for those three names.
3. **The choice of harness, model and thinking level lives in five places:** a default per harness, the two pair
   slots of the tasks module, each ticket, the intake window, and the roundtable seat picker.
4. **No module can ask for an agent of its own.** Dispatch starts agents for a ticket, a helper brief, the chat and
   the intake. A module cannot say which harness, model, options and folder.
5. **The ACP client is one 4,000-line class** (`runner.Session`) that also holds ticket work, commits, peer notes
   and merges. Nothing else can reuse the client part.
6. **Roundtables carries a second ACP client,** copied in with its engine, with its own harness list as a fallback.
7. **Dispatch ships disabled,** so every caller carries a branch for its absence.

## The design

### The registry

Dispatch keeps one registry of harnesses, in the home, and it is built on the ACP Registry's own format rather
than one of ours.

- **The record is the registry's manifest, `agent.json`, kept as published:** `id`, `name`, `version`,
  `description`, `distribution` (`binary` per platform, `npx`, `uvx`), `icon`, and the rest of its schema
  (`agent.schema.json`, which dispatch already carries and checks entries against). Dispatch adds nothing to it and
  changes nothing in it.
- **The catalogue is the published list,** `registry.json`, read from the registry's address or from a file of the
  same form, which is how a team keeps a private list. It is cached in the home and read again on demand or after a
  day.
- **An installed harness is a manifest pinned at one version,** `<home>/agents/<id>/<version>/agent.json`, with a
  binary harness's archive checked against its `sha256` and unpacked beside it. The registry's list moves hourly, so
  a pin is what keeps a harness the same from one start to the next. Upgrading is choosing the version listed now.
- **The id of record is the registry's id** (`claude-acp`, `codex-acp`, `gemini`). Claude Code, Codex and
  Antigravity stop being a table in the code: they are the three manifests a new home has pinned. Their short names,
  `claude`, `codex` and `antigravity`, are kept as names a person may type, resolved to the id in one place.
- **What Metaform knows beyond the manifest is kept beside it, never in it:** what the harness answered when asked
  (below), and the person's choices for it.
- **A harness the person runs from their own command has no manifest,** since the schema has no distribution for a
  local command. It is a record of the same fields with `command` in place of `distribution`, marked as local. A
  harness meant for others goes in a registry file.

For each harness dispatch keeps what it learned by asking it, in the protocol's own shapes:

- `state`: ready, needs login, cannot start (with the reason), or not asked yet;
- its `initialize` answer: name, version, capabilities and login methods;
- its config options with their choices, from `session/options` where the harness has it, or else from one session
  made and closed without a prompt.

This is asked by dispatch itself: when a harness is installed, when its start command changes, after a login, and
when someone asks for a harness that has no record. It is never asked on a timer. Each real session refreshes the
record with its own answer.

Whether a harness can run here is told in three ways. From the manifest, for every entry of the list: whether it
has a distribution for this platform and the runner that distribution needs (`npx`, `uvx`). As a hint for the page's
ordering: whether the program it wraps is found on the PATH. Truthfully, for a harness the person installs: asking
it, as above.

Remote agents reached over A2A are described by Agent Cards, a different standard, and are not harnesses. They are
out of this registry.

### Profiles

There is no one way today to say how an agent is launched: its harness, model and thinking level are kept in five
places, its startup prompt in a sixth, and what it may do nowhere. A profile is that one way. It is a named, saved
definition of everything that can be set about an agent at its start, and every launch is made from one.

A profile holds:

- `name` and `description`;
- `harness`: a registry id (step 3), so the profile and the harness manager share one list;
- `options`: values for the harness's config options, keyed as dispatch keys them (`mode`, `model`, `speed`,
  `thought_level`, or the option's id). An option left out is the harness's own. Values are checked against what
  the harness offers, and one it does not offer is reported, not dropped silently;
- `prompt`: the startup prompt, text or a prompt-store name, and whether it is added to the harness's own system
  prompt or replaces it (ACP's `systemPrompt` modes `append` and `override`);
- `permission`: Metaform's answer level for the harness's permission requests (`dispatch_prompts`), kept apart from
  the harness's mode so a mode such as Claude Code's plan never changes it;
- `tools`: switches by source (the harness's own tools, each MCP server, subagents), each shown with whether this
  harness can enforce it;
- `skills`: names from the skills catalogue.

Profiles are one library for the whole home, one file each at `<home>/profiles/<name>.json`, beside the harness
records, and are owned by dispatch, with verbs `metaform dispatch profiles list|show|save|delete`. Prompts and
skills stay with their owners; a profile names them.

**Assignments** say which profile each kind of launch uses: the chat, the intake, ticket work, the second member of a
pair, a helper, a review, a roundtable seat. Dispatch owns the table; one screen shows and edits it; every picker
reads it. A project may name different profiles for its own launches.

**A launch resolves in this order, later over earlier:**

1. the harness's own values (nothing is sent);
2. the profile: the one the caller names, or else the one assigned to the launch's purpose;
3. what the caller gives for this launch: a ticket's own model, a module's own options, its own prompt.

**A caller may override the profile's prompt.** A workflow whose own prompt would be interfered with by another
gives its own, or none, and the profile's prompt is then not sent. The rest of the profile still applies. The intake
is one such caller: it is given the procedure as its task and nothing else, so its launch always overrides the
profile's prompt with none, and a profile can choose the intake's harness, model and thinking level but never
adds to or wraps the procedure.

**How each part reaches the harness, standards first:**

- Options: ACP's `configOptions` on `session/new` where the harness takes them (Claude Code's v2 adapter does),
  else `session/set_config_option` after it, model first, as today.
- Prompt: ACP's `systemPrompt` on `session/new` with `append` or `override`, where the harness advertises
  `session.systemPrompt` and the mode (Claude Code 0.107.2 both modes; Codex 2.6.0 advertises it, modes not yet
  read). A harness without it gets the prompt at the head of its first message, and the profile screen says so.
  The Python SDK in use (1.0.0rc2) has no `systemPrompt` field on v2's `NewSessionRequest`; the v2 adapter sends it
  as a raw field until the SDK has it.
- Tools: ACP has no tool list. Which MCP servers a session gets is standard and works on every harness. A
  harness's own tools need its own extension: Claude Code's `_meta.claudeCode.options` `disallowedTools` and
  `tools`; Codex's `CODEX_CONFIG`, per-tool keys unconfirmed; any other harness none. Where a harness cannot
  enforce a switch, the profile shows it as not enforced. Metaform does not refuse the agent's calls in the
  harness's place: deciding who may call what is not Metaform's.
- Permission: Metaform's own answers to `session/request_permission`, as now.
- Profiles are applied at start. Claude Code rebuilds a session whose tools change, so a running session is not
  re-profiled.

Claude Code's own `agent` option, which runs a session as one of its subagent definitions, is Claude Code's form of
a profile. It is not a chat setting; a Claude Code profile may name one.

### Toward a software factory

The aim of profiles is a software factory the person builds: agents in roles, each started from its profile, with
work moving between them. The pattern is proven (StrongDM, Stripe's Minions, MetaGPT, BMAD, Augment's Cosmos
Experts, GitHub Copilot's custom agents, IndyDevDan's ADWs), and Metaform follows it rather than inventing another.
What those factories share, and where Metaform already holds the part:

| Part of a factory | What the proven ones do | Metaform |
|---|---|---|
| Role definition | Model, prompt, tools, context, harness and thinking level per role, in one file (IndyDevDan's "core four" YAML, Cosmos Experts, Copilot `.agent.md`, MetaGPT's name, profile, goal, constraints) | The profile |
| Context per role | The hardest part: a role-scoped slice of approved definitions, recorded per run (Atlan); AGENTS.md, path rules, skills on use (Rattner) | The map: knowledge inherited along an address, memories bound to it, overlays. A role's context is addresses and overlays |
| Handoffs | Structured artifacts, not chat (MetaGPT's PRD, design, tasks; BMAD's story files); JSON checked against a required shape, with an envelope of task, plan and expected report (IndyDevDan) | Overlay records, checked against the overlay's definition, whose refusal says how to correct |
| Who hears what | A publish-subscribe pool; a role acts once its inputs exist (MetaGPT); team messages between members | Agents' messages to each other land in the recipient's inbox; the event bus and `map.changed` tell a role what changed at its addresses |
| The chain | Plain code runs the phases and the quality checks (lint, tests) and routes a failure back to the builder; agents do the judgment (IndyDevDan, Stripe's blueprints, two CI rounds then a person) | The workflow module, with dispatch's launch service |
| Which roles a role may start | Cosmos Experts' workers | A profile names the profiles it may launch |
| Model stacks | Cheap models build, strong models plan and review | Any registry harness and its models, per profile |
| Verification apart from the builder | Scenarios kept where the builder cannot read them (StrongDM's holdouts, "satisfaction") | An overlay outside the builder's addresses |
| Triggers | Chat, ticket board, schedule, webhook, events | The chat, the board, the bus |
| Seeing it work | Each run's compiled prompt, tools and cost per phase | The page's agents and threads; the prompt shown in sections with token counts |

Where Metaform can be better than the factories above is that the whole factory sits on one map of what the project
does. The intake records the project's functional map; agents' notes and handoffs are overlay records on that
map's elements. In the factories above a handoff is a document in a folder, related to the code only by what its
text says. Here each one is at the address of the functionality it concerns, so:

- a role is given the notes on the parts it works on, because they are at their addresses, and nothing else;
- what one role learns about a part is there for the next role that touches that part, in this run or a later one;
- a handoff is checked against its overlay's definition, so the next role gets the shape it expects;
- the person sees the factory's work on the map itself.

Messages between agents are a feature of their own, apart from overlays: an agent sends a message to another agent
and it lands in that agent's inbox, which wakes it for a turn (`tasks message`, the inbox `tasks` verbs carry;
dispatch's peer messages). That is a factory's direct channel between roles, as a team message is in the
factories above.

### Launch

Dispatch declares one launch service. The caller gives: the purpose, a profile if it names one, its own options or
prompt over the profile's if it needs them, the folder, an owner id of its own and the first message. It gets a session id. It sends further messages,
interrupts and stops by that id.

What the agent does comes back on the event bus, each event carrying the session id and the owner id, so a handler
decides from the event alone whether it concerns it. Chunks of one turn are coalesced by dispatch before they are
published.

Ticket work, the chat, the intake and helpers become callers of the same service. That requires splitting
`runner.Session` in two: the ACP connection and the work that uses it (tickets, commits, peer notes).

### The connection

The connection is built as the protocol's guidance lays out, in `dispatch/acp/`:

- **`connection`** starts the harness process, sends `initialize` asking for version 2, reads the version the
  harness selected, and hands the stream to that version's adapter. A harness that selects 1 gets a v1 adapter, on a
  fresh v1 `initialize`, which carries what the v2 request left out, such as a terminal login.
- **`v1` and `v2`** are the two adapters. Each owns its version's capabilities, validation and lifecycle, and
  nothing outside them sees a wire shape.
- **One model above them,** which is what dispatch's work and every other module deal with. It follows v2, because
  v2 is where the protocol is going and it can express everything v1 can:
  - a turn is `running`, `idle` with a stop reason, or `requires_action`. The v1 adapter reports `idle` when the
    `session/prompt` response arrives.
  - messages and tool calls are records with ids, updated in place. The v1 adapter gives chunks an id per message
    and treats `tool_call` as the first update of its id.
  - settings are config options, by `configId`. The v1 adapter presents modes as one option of category `mode` and
    sets it with `session/set_mode`.
  - resume takes "replay from the start" or not. The v1 adapter uses `session/load` for the first.
  - client files and terminals are not offered in either version (see step 2). Client-side tools for both versions
    are MCP servers passed at session setup, which Metaform already does with its own.
  - whatever a version cannot express is reported as unsupported by its adapter, never dropped silently.
- **v2 first, v1 as the fallback.** The client asks for version 2 on every connection, and a harness that knows
  only v1 selects 1. Asking costs nothing, and v2 removes what the v1 code works hardest around: the end of a turn
  is a signal of its own, records have ids, session list, resume and close are always there, and modes are options.
  A setting, on by default, turns v2 off, for the day a change to the draft breaks a harness.
- **The same tests run against both adapters:** a turn to its end, a cancel, a permission request, a resume with
  replay, a config option set, and a v2 request answered by a v1-only harness.

The roundtables engine already negotiates v2 with a v1 fallback on the Python SDK's `acp.experimental.v2`. That
code is the starting point for `connection`, and is deleted from roundtables once dispatch has it.

### Roundtables

Its engine keeps the room: who is seated, whose turn it is, judging, the record. Its ACP client, its harness list
and its permission relay are deleted, and each seat is a launch asked of dispatch.

Every seat is a harness agent. The seats that call a model's API directly (`roundtable/openrouter.py`) are deleted:
a model reached that way has no tools, no files and no project context, so it takes part with far less than the
agents beside it. A model from another provider is seated through a harness that serves it, such as one of the
registry's multi-provider harnesses, or one pointed at a provider where it supports ACP's Configurable LLM Providers.

## Issues found

Each was read in the code or seen on the live system on 2026-11-16. The step that settles it is in brackets.

**How the code is organised**

1. The ACP client is one class of about 4,000 lines, `runner.Session`, that also holds ticket work, commits, peer
   notes and merges. Nothing else can use the client part. [2]
2. Dispatch speaks v1 only. The only v2 code is in the roundtables copy. [2]
3. Roundtables carries its own ACP client (`roundtable/harness.py`), its own fallback harness list with versions
   typed by hand (`roundtable/config.py:59`), its own installed check and options read, and its own permission
   relay. Its seats are started with no Metaform identity (`roundtables/engine.py:16,61`), so they are not project
   agents. [6]
4. Roundtables seats models by calling an API directly (`roundtable/openrouter.py`, and eleven other engine files
   that mention it). [6]
5. No module can ask for an agent of its own. Dispatch launches for a ticket (`start`), a helper brief (`helper`),
   the chat (`system`) and the intake (`intake`). None takes harness, model, options and folder from the caller. [5]
6. Dispatch ships disabled (`SHIPS_DISABLED = True`), `start.py` lists it as needed, and each caller checks whether
   it is on. [7]
7. Other code reaches into dispatch's internals instead of asking it:
   - reads its settings: `roundtables/engine.py:72` (`dispatch_<agent>`), `fork/review.py:34,44`, `start.py:389-435`,
     `install.py:255-260`, `web/__init__.py:176`; `web/server.py:2185` also writes `dispatch_agent`;
   - opens its store: `web/server.py:3294`, `problem_report.py:129-151`. [5, 7]

**The registry**

8. Three harnesses are written into the code (`AGENTS`, `dispatch/__init__.py`). An intake reads that table as what the
   project uses: the `metaform` map of 2026-11-16 records the harness element (`upstream.code.harness.agent`) as
   known as "Claude Code, Codex, Google Antigravity", where the project in fact works any harness of the ACP Registry. The other 43 of the registry can
   be added only with `metaform dispatch registry add=<id>` in a shell; the page has nothing for it. [3]
9. The pinned versions are stale: Claude Code's adapter 0.100.0 against 0.107.2 listed, Codex's 2.5.0 against 2.6.0,
   Antigravity's 1.4.1 against 1.5.0. [3]
10. Option settings exist only for the three names (`dispatch_<agent>_<option>`, declared in a loop over `AGENTS`),
    so the options of a harness added from the registry cannot be chosen. [3, 4]
11. Dispatch's names (`claude`, `codex`, `antigravity`) are not the registry's ids (`claude-acp`, `codex-acp`,
    `antigravity-acp`); a table maps one to the other (`registry.BUILTIN`). [3]

**Choices and the windows that show them**

12. The choice of harness, model and thinking level is kept in five places: a default per harness, the two pair
    slots of the tasks module (`tasks_agent_1`, `tasks_agent_2`), each ticket, the intake window, and the roundtable
    seat picker. [4]
13. "Agent 1" and "Agent 2" are the two members of the pair `tasks start` launches. Both get the same assignment;
    the number is a position, not a purpose. [4]
14. Fast mode is wired to the wrong option. Dispatch treats any on/off option in ACP's `model_config` category as
    Fast mode. Claude Code's adapter reports Ultracode there, so `dispatch_claude_fast` and a ticket's Fast toggle
    switch Ultracode. ACP's own proposal names this fault and the fix: a `speed` category, with the two adapters'
    current ids, `fast` and `fast-mode`, until they adopt it. [fix now, before 2]
15. The call window has two rows named "Agent": Metaform's harness picker, and Claude Code's own option that runs
    the whole session as one of its subagent definitions (`OWN_OPTIONS`, written by hand). Its entries come from the
    person's Claude Code plugins. Picking one breaks the chat, and the pick is saved as the default for every later
    Claude Code session. [fix now, before 2]
16. The window saves a choice without saying so, and the star (make this harness the default) reads as something
    about the model. [4]
17. Some options depend on the folder: Claude Code's subagent list is the project's `.claude/agents` plus the
    plugins'. The home keeps one record per harness, so that list shows whichever project asked last. Models, modes
    and thinking levels do not depend on the folder. [3]
18. A Claude Code agent can hand work to Codex on its own through the Codex plugin's `codex-rescue` subagent, which
    is written to be used without being asked. That is outside dispatch, unseen and uncounted. Not checked whether
    it has happened. [open]

**Left from step 1**

19. Writing a harness's record fires no event. A page reads it when a picker is drawn, and the call window keeps
    its read for 30 seconds (`PRECALL`, `session/settings.js`). [3]
20. The per-project `catalog` table is still declared and no longer used, as `spend` is, to avoid a layout change
    on a store that is being removed. It goes when dispatch leaves the old store. [with the store removal]
21. The `session/options` path is coded and has not run against a real harness. Claude Code's adapter 0.107.2
    advertises it (`capabilities.session.options`) under v2; the pinned 0.100.0 does not, nor does Codex's 2.6.0.
    It runs for real once step 3 upgrades the pin. [3]
22. Settled 2026-11-16 by `initialize` with `protocolVersion: 2` (and v2's `info` and `capabilities`; a v1-shaped
    request is refused as invalid params): Claude Code's adapter 0.100.0 and 0.107.2 and Codex's 2.5.0 and 2.6.0 all
    select 2. So the v2 adapter carries both real harnesses, and the v1 adapter is exercised by the fake agent and by
    registry harnesses that know only v1. Both advertise `providers` (Configurable LLM Providers), which bears on
    seating another provider's model through a harness (step 6). Claude Code's also advertises
    `session.systemPrompt.mode.override`; Codex's advertises `session.systemPrompt` with no mode.
23. `specifications/04-chassis-modules.md` line 835 still describes the per-project table.
24. One dispatch test fails in code this work did not touch:
    `test_the_agents_key_read_makes_the_same_few_queries_however_many_sessions_have_ended` expects an `intake`
    field in a session's state. Lint has one finding, in an archived skill script under `web/page/app/.claude/`.

## Order of work

Each step is complete on its own and checked on the live page before the next. Work goes straight through the
list; a question to the person is for a decision only they can make, never for leave to take the next step.

**0. Two faults that are wrong today** (issues 14 and 15)

- Key Fast mode by ACP's `speed` category, and by the ids `fast` and `fast-mode` in `model_config` for the two
  adapters that predate it. Every other `model_config` option is keyed by its own id. Touches `CATEGORIES`,
  `option_key`, `AGENT_OPTIONS` and seven uses of `'model_config'` in `dispatch/__init__.py`, `APPLY_ORDER` and one
  check in `runner.py`, `board.js:115`, and the fixture id in `web/tests/test_ticket_fast_ui.py`.
- In the call window show the harness, then the options in ACP's categories (mode, model, speed, thinking level).
  Everything else a harness reports goes under "More from <harness>", closed by default. Label Metaform's row
  "Harness". Remove `agent` from `OWN_OPTIONS` so the subagent choice is never a saved default.
- Check: Claude Code's window shows no second "Agent" row and no Ultracode switch among the main rows; Codex's Fast
  mode still works on a ticket.
- Built 2026-11-16. `option_key` names Fast mode `speed`; every other `model_config` option goes by its id
  (`ultracode`). A running session's settings carry the same `key`, so the page groups them by one rule
  (`groupedControls` in `session/settings.js`), in the call window, the running session's window and the intake
  window; the summary line names only the main options and switches that are on. The one-time migration of
  `dispatch_agent_options` reads a stored `model_config` entry as Fast mode, which is what it meant when written.
  Checked headless on the live page: Claude Code shows Harness, Mode, Model, Effort, then "More from Claude Code"
  (Ultracode, Agent) closed; Codex shows Fast mode among the main rows, Collaboration mode under More.

**1. Harness knowledge in the home, asked by dispatch itself.** Built 2026-11-16, on the existing v1 client.

**2. The connection, `dispatch/acp/`** (issues 1, 2, 22)

- First find out what each adapter selects when asked for version 2, with a ten-line script against the real
  Claude Code and Codex adapters. That decides how much of the work is exercised by real harnesses.
- Write the model above the adapters: turn state, messages and tool calls by id, config options by `configId`,
  permission requests, logins, capabilities.
- `connection`: start the process, `initialize` asking for 2, read the selected version, hand over to its adapter.
- Client files and terminals (v1's `fs/*` and `terminal/*`) are removed, not carried into the connection
  (2026-11-16). ACP made them for code editors, so an assistant's reads see unsaved buffers and its edits land in
  open documents; Metaform has no editor, so the offer serves nothing here. The harnesses never used it: Claude
  Code's adapter only passes the methods through, and none of the 50 recorded dispatch sessions read or wrote a file
  through the client. v2 removed them, and offering them would have kept every session on v1. File placement and
  command output come from what the harnesses report on their tool calls, in both versions. If Metaform gains an
  editor, the v2 way is client tools offered as an MCP server.
- `v2` adapter on the SDK's `acp.experimental.v2`, starting from `roundtable/harness.py`. `v1` adapter from what
  `runner.Session` does today.
- Move `runner.Session` onto the connection one concern at a time, in this order, with the dispatch tests passing
  after each: open and initialize; session new, resume and close; the prompt turn; updates; permissions and
  elicitation; config options; logins; the probes (`ask`, `logged_in`, `login`).
- The setting that turns v2 off. Extend the fake agent (`dispatch/tests/fake_agent.py`, which already has a v2
  mode) so the same tests run against both adapters: a turn to its end, a cancel, a permission request, a resume
  with replay, a config option set, and a v2 request answered by a v1-only harness.
- Check: a ticket worked by Claude Code and one by Codex, each from the page, on whichever version it selects, and
  again with v2 turned off.
- For the move, from the layer's builder (2026-11-16): Claude Code's v2 adapter advertises no `_session/steering`
  (only `_meta.claudeCode.promptQueueing`), so a steer is an ordinary prompt on v2 where steering is not advertised;
  login status is read from `capabilities.auth.status`, `capabilities._meta.authStatus` (Claude Code) and
  `capabilities.auth._meta.authStatus` (Codex), and `_auth/status_update` is an `auth` event; subagent updates arrive
  as `other` events under the child's session id; notices and compaction are raw dicts; diffs keep their wire form
  (v1 `path`/`oldText`/`newText`, v2 `changes`/`patch`), so `tool_detail`, `track_tool_files`, `changed_files` and
  `filed` read both; usage from either version lands in `Turn.usage`; the v1 adapter absorbs the prompt echo, so the
  runner's `prompt_echo` goes; permission and elicitation withdrawal is the layer's, `Client.withdrawn`; the runner
  keeps reading stderr and its own process handling (its own starter to `connect`); `connect(timeout=)` covers
  `initialize` only; an `Unsupported` ask is still said in the thread.

**3. The registry** (issues 8, 9, 10, 11, 17, 19)

- Every harness is a pinned manifest under its registry id. The three in `AGENTS` become three pins a new home
  starts with; `claude`, `codex` and `antigravity` resolve to the ids in one function. Existing homes are moved once.
- The list in the page: installed first, then those that can run here (a distribution for this platform and its
  runner present), then the rest; install, upgrade, remove; each harness's state and login.
- Options for any harness, kept by option id beside the manifest, not as declared settings per name.
- Folder-dependent options kept per project on top of the home's record.
- A harness's record changing is announced on the bus, and the 30-second read in the call window goes.

**4. Profiles and assignments** (issues 12, 13, 16; needs steps 2 and 3)

- `dispatch/profiles.py`: the record, one file per profile in the home, the verbs, checking against what the harness
  offers. A home starts with one profile per pinned harness, made from its current per-harness option settings.
- The assignment table, purpose to profile, with the project's own over the home's.
- Applying a profile at launch in the order above, including the caller's prompt override; the intake always
  overrides with none.
- The page: an Agent profiles screen (list, new, duplicate, delete; harness and options with the call window's
  controls; permission; prompt in sections with token counts, edited through the prompt store; skills; tools as a
  switch grid by source with each harness's enforcement shown). The call window's first field becomes Profile, its
  harness shown with it; the intake window and a ticket's choice the same; each says when a choice is saved.
- `tasks_agent_1`, `tasks_agent_2`, their model and thinking-level settings, and the per-harness option settings
  fold into profiles and assignments and are deleted.
- Check: a profile with Bash off and approve-reads, called from the chat: the session shows the profile's model and
  thinking level, and Claude Code refuses a shell command; the same profile on Codex shows Bash as not enforced; an
  intake started with a profile that has a prompt receives the procedure alone.

**5. The launch service** (issues 5, 7)

- One declared service: harness, options, folder, purpose, owner id, system prompt, first message; a session id
  back; message, interrupt and stop by that id. Events on the bus with the session id and owner id, a turn's chunks
  coalesced.
- `start`, `helper`, `system` and `intake` become callers of it.
- The settings reads and store opens of issue 7 are replaced by asking dispatch.

**6. Roundtables** (issues 3, 4)

- Each seat is a launch asked of dispatch. `roundtable/harness.py`, the fallback harness list, the installed
  check, the options read, the permission relay and `roundtable/openrouter.py` are deleted, with what in the other
  eleven files served only them.
- Check: a table opened from the page with Claude Code and Codex seats, each visible as a project agent.

**7. Dispatch required** (issue 6)

- `SHIPS_DISABLED` off, the `NEEDED` lists and every "is dispatch on" branch deleted.

Step 2 is the largest. Steps 0, 3 and 4 settle what the person sees on the page.

## Decisions and their reasons

- **Knowledge of a harness is kept in the home, by harness.** What a harness offers follows its version and the
  account logged in, which are the machine's. A project-level copy went stale when projects were cleared and was
  empty for every new one.
- **It is kept as one file per harness beside the registry's pinned entries** (`<home>/agents/_offered/`). It
  belongs with the harness records already there, and it must not sit in the old project store, which is being
  removed.
- **Dispatch asks; nobody is told to run a command.** The protocol's own answer to "what does it offer before a
  session" is to ask the harness. A person should never be the one to do it.
- **The registry is the list, and its manifest is the record.** Forty-six harnesses change weekly; a list in the
  source is out of date the day it is written, as the three pinned versions already are (Claude Code's adapter is
  pinned at 0.100.0 and the registry lists 0.107.2). Using the published format means a harness added to the
  registry tomorrow works here with no change to Metaform, and a team's private list is a file of the same form.
- **Standards first.** Where ACP or its registry defines a shape, dispatch stores and passes that shape. Metaform's
  own data sits beside it.
- **Requests go through verbs and declared services; events come back on the bus.** Both already exist and are how
  every other module reaches dispatch. No new mechanism.
- **No claim that any model runs on any harness.** We show what each harness says it offers.
- **Models are reached through a harness, never by calling an API directly.** The harness is what gives a model its
  tools, its files and its place in the project.

## Open

- Whether Metaform ships starting roles (a planner, a builder, a reviewer) as templates the person copies, as Cosmos
  ships Template Experts, or ships none. The roles removed in October 2026 were procedures Metaform imposed; a
  template the person chooses and edits is not that, but whether to offer them is the person's call.
- Where a list of a harness's own tools comes from: ACP publishes none. Candidates are a list the harness reports
  in its own extension, or the tool names seen in past sessions. Not yet read in the adapters.
- The names of the purposes in the assignment table follow the roles in use. They are listed above as the launches
  that exist today; they are the person's to rename.
- Jev's judging of roundtable contributions also calls a model's API directly. It decides and never acts as an
  agent, so it is not a seat; whether it stays as it is has not been decided.
