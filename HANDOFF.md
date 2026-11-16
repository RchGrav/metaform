# Handoff: dispatch owns ACP

As of 2026-11-16, afternoon. Branch `feat/project-tool`. Nothing from this session is committed.

## The assignment

Dispatch is to be the one part of Metaform that speaks the Agent Client Protocol: the registry of harnesses, the
answer to which are available and what each offers, and the launcher of every agent. Other modules ask it through
its verbs, its declared services and the event bus. The person made the agent on this work its owner and long-term
maintainer: the design is the agent's to decide, and is expected to be well reasoned and properly built.

His direction, given during the session:

- Study agentclientprotocol.com and build to it. Run v2 wherever a harness accepts it, v1 as the fallback, laid out
  as the protocol's "Supporting v1 and v2 side by side" section says.
- One unified registry. Dispatch is standards-based as much as possible.
- Models are reached through a harness, never by calling an API directly.
- Work straight through the plan. Do not stop after each step to ask for leave to take the next one.

## Read these first

1. `docs/plans/dispatch-owns-acp.md`: what ACP gives us, the 24 issues found with file and line, the design, the
   decisions with their reasons, and the order of work down to tasks.
2. The ACP pages the design rests on: protocol v1 and v2 overviews, `protocol/v2/migration` (all of it),
   `protocol/v1/session-config-options`, `protocol/v1/initialization`, `protocol/v1/authentication`,
   `get-started/registry`, and the proposals `rfds/session-options`, `rfds/speed-config-category`,
   `rfds/custom-llm-endpoint`, `rfds/acp-agent-registry`. Each has a `.md` form at the same address.

## How to see each issue in the code, and why it is one

Read the code before changing it. For each issue below: where to look, what you will find there, and why it is a
fault. The numbers are the issue numbers in the plan. Line numbers are as of 2026-11-16 and will drift; search for
the names.

### The ACP client cannot be reused (issues 1, 2)

- **Look at** `dispatch/runner.py`, `class Session` (starts near line 1139, ends near 5195). List its methods:
  `grep -n "    async def \|    def " src/metaform/modules/dispatch/runner.py`.
- **You will find** protocol work and ticket work in one class. Protocol: `open_agent` (starts the process, sends
  `initialize`), `capture`, `apply`, `settings`, `apply_options`, `configure`, `session_update`,
  `request_permission`, `create_elicitation`, the `fs` and `terminal` methods, `prompted`. Ticket work in the same
  class: `commit_done`, `ticket_done`, `peer_note`, `guidance`, `rules`, `hand_over`, `track_tool_files`.
- **Also find** in `open_agent`: `protocol_version=acp.PROTOCOL_VERSION` and a `RuntimeError` when the harness
  answers any other version. The imports at the top are from `acp.schema` only, never `acp.experimental.v2`.
- **Why it is a fault:** anything that needs an agent must either go through ticket machinery it does not want or
  write its own client, which is what roundtables did. And dispatch refuses a v2 harness outright, while the
  protocol's guidance is to ask for v2 and fall back.

### Roundtables has a second client and its own harness knowledge (issues 3, 4)

- **Look at** `roundtables/roundtable/harness.py`. Its header says "Negotiated ACP sessions for roundtable seats" and
  it imports `acp`, `acp.experimental.v2` and its own `Session` class (near line 148). Compare with `runner.Session`.
- **Look at** `roundtables/roundtable/config.py`, `AGENTS` (near line 59): start commands with version numbers typed
  in, under a comment saying they are the versions dispatch pins. Compare them with `AGENTS` in
  `dispatch/__init__.py` and with the registry's current list.
- **Look at** `harness.py`, `found` (is the harness installed) and `offers` (what it offers), near lines 913 and 923.
  Dispatch has both already: `located` and `options`.
- **Look at** `roundtables/engine.py` lines 16 and 61: the engine is started with "no Metaform agent identity", and
  line 72 reads the setting `dispatch_<agent>` directly, falling back to its own list when dispatch is off.
- **Look at** `roundtables/roundtable/openrouter.py`: a seat that is a model called over HTTP.
  `grep -rl openrouter src/metaform/modules/roundtables --include=*.py` lists the eleven other files tied to it.
- **History that explains it:** `git show 665d9fbf` (2026-10-21). The engine was a separate program,
  `~/roundtable`, copied in whole because every user without it got "engine not found". The ticket asked for it to
  ship, not to be moved onto dispatch. `git show 541b2c20` (2026-11-04) then grew the copy's client from 522 to 944
  lines.
- **Why it is a fault:** a fix to one client never reaches the other; the two already differ on protocol version;
  seats are not project agents, so they have no project context and do not appear as agents of the project; and a
  model called directly has no tools or files, so it takes part with far less than the agents beside it.

### No module can ask dispatch for an agent of its own (issue 5)

- **Look at** the `Verb(` list at the bottom of `dispatch/__init__.py` and the functions `start` (near 2722),
  `system` (near 2841) and `helper` (near 5425). Read the nouns each takes.
- **You will find** `start` needs a ticket id; `helper` takes a brief and a harness name and reports to the system
  agent's inbox; none takes a model, a thinking level or a folder from the caller. Model and effort come from
  `wanted_options`, which reads the `dispatch_<agent>_<option>` settings and the ticket.
- **Look at** `Provides(` near the end of the file for what dispatch offers other modules. There is
  `dispatch.agents`, `dispatch.option_choices`, `dispatch.models`, `dispatch.seats`. There is no launch.
- **Why it is a fault:** the person's requirement is that a module keeps its own choice of harness, model and
  options and asks dispatch to start the agent. With no such request, a module's only ways are to bend its work
  into a ticket or to start the process itself.

### Dispatch is treated as optional (issue 6)

- **Look for** `SHIPS_DISABLED = True` in `dispatch/__init__.py`; `NEEDED` in `start.py` and `demo/__init__.py`;
  and callers that test for it: `grep -rn "'dispatch'" src/metaform --include=*.py | grep -i "surface\|enabled"`
  (`paperclip/__init__.py` `_on_surface`, `twilio/agent.py`, `fork/review.py`, `mcp/a2a.py`, `web/server.py`).
- **Why it is a fault:** every module that needs an agent needs dispatch, so each of those branches is a second
  code path for a state that should not exist, and one of them (the roundtables fallback) is where a private
  harness list came from.

### Other code reaches into dispatch instead of asking it (issue 7)

- **Look for** reads of dispatch's settings outside dispatch:
  `grep -rn "dispatch_[a-z_{}]*" src/metaform --include=*.py | grep -v modules/dispatch/ | grep -v /tests/`.
  You will find `roundtables/engine.py:72`, `fork/review.py:34,44`, `start.py`, `install.py:255-260`,
  `web/__init__.py:176`, and a write at `web/server.py:2185`.
- **Look for** dispatch's store opened elsewhere: `grep -rn "module='dispatch'" src/metaform --include=*.py | grep -v
  modules/dispatch/`. You will find `web/server.py:3294` and `problem_report.py:129`.
- **Compare with the proper way,** which most callers already use: `module_verb(given, 'dispatch', '<verb>', ...)`
  in `web/server.py`, and `provided(folder, 'dispatch.<service>')`. `twilio/agent.py` says in a comment that it
  reaches dispatch "never by importing dispatch".
- **Why it is a fault:** each of those lines knows a setting name or a table layout that belongs to dispatch, so
  dispatch cannot change them without breaking another module, which is exactly what steps 3 and 4 need to do.

### Harnesses are a table in the code (issues 8, 9, 10, 11)

- **Look at** `AGENTS` in `dispatch/__init__.py` (near line 235): three entries, each a name and a start command
  with a version in it. Then `agent_choices`, `start_command` and `agent_label` just below, each with one branch
  for those three and another for registry pins.
- **Look at** `dispatch/registry.py`: it already reads the ACP Registry, pins a version, checks a binary's sha256
  and builds the start command. Its header explains the format. `BUILTIN` maps `claude` to `claude-acp` and so on.
- **Compare versions:** `metaform dispatch registry` lists what the registry has now against what is pinned. On
  2026-11-16 Claude Code's adapter was pinned at 0.100.0 with 0.107.2 listed.
- **Look at** the loop `for _at, (_agent, (_name, _command)) in enumerate(AGENTS.items())` (near line 744): it
  declares `dispatch_<agent>_<option>` settings, and only for the three names. Then look at `options` (near 5618):
  each setting it returns has a `setting` key, which is `None` for any option of any other harness. In the page,
  `optionSelect` in `session/settings.js` disables a select whose `setting` is empty.
- **Search the page** for the registry: `grep -rn "registry" src/metaform/modules/web/page/app` finds nothing.
- **Why it is a fault:** the registry lists 46 harnesses and changes hourly; a list in source is out of date at
  once. A harness added from the registry can be started but its model cannot be chosen. And two naming schemes for
  the same three harnesses need a mapping table.

### The choice of harness and model lives in five places (issues 12, 13, 16)

- **Look at** each store of a choice:
  1. `dispatch_<agent>_<option>` settings, read by `chosen_options` in `dispatch/__init__.py`;
  2. `tasks/__init__.py` lines 44 to 80: `SLOTS = ('tasks_agent_1', 'tasks_agent_2')` and their model and effort
     settings, labelled "Agent 1" and "Agent 2", and `start` (near line 151), which loops over the two slots and
     gives both the same assignment, `project_agent`;
  3. a ticket's own, `ticket_options` and `tune` in `dispatch/__init__.py`;
  4. the intake window, `drawIntakeSettings` in `session/settings.js`;
  5. the roundtable seat picker, `modelPicker` in `roundtable/stage.js`.
- **Look at** `wanted_options` and `Session.apply_options` to see the order they are merged in at a launch.
- **Look at** `keepAgentOption` in `session/settings.js`: it posts to `/api/settings` and shows a message only when
  the save fails. And `makeDefault` in `agents/pickers.js`: the star sets the default harness, and is disabled when
  the shown harness already is the default.
- **Why it is a fault:** no screen answers "what gets launched for which purpose". A person cannot tell that a pick
  in the call window becomes the default for ticket work and the intake too, that a pick was saved at all, or what
  "Agent 2" is for.

### Fast mode is wired to the wrong option (issue 14)

- **Look at** `CATEGORIES` and `option_key` (near line 506 and 518) and `AGENT_OPTIONS` (near 648) in
  `dispatch/__init__.py`: `('fast', 'Fast mode', 'model_config')`. `option_key` names an option by its ACP category
  when it has one, so every `model_config` option is the one key `model_config`, and that key is Fast mode.
- **See it live:** `metaform dispatch options agent=claude --json`. Claude Code's adapter reports
  `id=ultracode, category=model_config, type=boolean`, and the output gives it `setting: dispatch_claude_fast`.
  Codex reports `id=fast-mode, category=model_config`.
- **Read** `rfds/speed-config-category` on agentclientprotocol.com. It states the fault in the protocol's own words:
  `model_config` says where an option goes, not what it does; the two adapters use the ids `fast` and `fast-mode`;
  the fix is a `speed` category.
- **Why it is a fault:** turning on Fast for a Claude Code ticket turns on Ultracode, a different and far more
  costly thing. It also means two `model_config` options on one harness collide on one key, so only the first can
  ever be set.

### The call window offers Claude Code's subagents (issue 15)

- **Look at** `OWN_OPTIONS` in `dispatch/__init__.py` (near line 650): `'claude': (('agent', 'Agent', 'agent'),)`.
  That line is why the option has a saved setting, `dispatch_claude_agent`.
- **Look at** `agentOptionControls` in `session/settings.js`: it draws every setting the harness reports, in the
  harness's order, under the harness's own label. `sessionSummary` puts Metaform's harness picker above them under
  the label "Agent". So there are two rows named "Agent".
- **See where the entries come from:** `~/.claude/plugins/cache/*/*/*/agents/*.md` on the person's machine, plus the
  project's `.claude/agents/`. They are helpers that plugins start for themselves.
- **Why it is a fault:** every entry except Default turns the whole session into a narrow helper, the pick is saved
  as the default for every later Claude Code session, and the window gives no sign of what the row is. Claude Code
  itself removed its own screen for this list in v2.1.198.

### Some options depend on the folder (issue 17)

- **Look at** `dispatch/offered.py`: one record per harness for the whole home. And `runner.ask`: it asks with
  `cwd=probe.folder`, the project it was called from.
- **See it:** ask Claude Code from `clear-trial` and from `/home/rich/metaform`
  (`metaform dispatch options agent=claude prime=true --json`) and compare the `agent` option's choices. The second
  should add the four in this repository's `.claude/agents`. This was reasoned, not run.
- **Why it is a fault:** the protocol says options can depend on the working folder. A home-level record is right
  for models, modes and thinking levels and wrong for this one, which shows whichever project asked last.

### A record changing is not announced (issue 19)

- **Look at** `offered.keep`: it writes a file and tells nobody. Before this session the same data was a table row
  written with `tx.concern(...)`, which put it on `map.changed`.
- **Look at** `PRECALL` in `session/settings.js`: `Date.now() - PRECALL.at > 30000`, a read kept for 30 seconds.
- **Why it is a fault:** the project's rule is that whatever changes state emits an event and nothing waits on a
  clock. An open picker does not update when a harness is asked again, and the 30-second read is a timer standing
  in for an event.

### What is not yet known (issues 18, 21, 22)

- **Which version the real adapters select.** Send `initialize` with `protocolVersion: 2` to
  `npx -y @agentclientprotocol/claude-agent-acp@<version>` and to the Codex adapter and read `protocolVersion` in
  the answer. `roundtable/harness.py` does this negotiation and is the working example.
- **Whether `session/options` works against a real harness.** `runner.ask` uses it when the `initialize` answer has
  `agentCapabilities.sessionCapabilities.options`. No harness here advertises it, so that branch has only been read.
- **Whether a Claude Code agent has handed work to Codex on its own.** The Codex plugin's
  `agents/codex-rescue.md` tells Claude Code to use it "proactively". Look in session threads for a Bash call to
  `codex-companion.mjs`.

## Done this session: step 1

What a harness offers is kept in the Metaform home by harness, and dispatch asks the harness itself.

- `src/metaform/modules/dispatch/offered.py`, new: one record per harness at `<home>/agents/_offered/<agent>.json`,
  with `state` (`ready`, `needs login`, `cannot start`), the reason, version, settings, logins, extensions and the
  start command it was asked with.
- `dispatch/runner.py`: `Session.remember` writes that record; `ask` replaces `prime` and records a harness that
  needs a login or cannot start instead of raising; it uses `session/options` where a harness advertises it.
- `dispatch/__init__.py`: `catalog_rows`, `offered_option`, `offered_values` and `model_for` read the home and no
  longer take a store; `harness_state`; `options` asks a harness that has no record or whose start command changed;
  `login` asks again after a successful login; `registry remove=` drops the record.
- Page: the call window, the intake window, the ticket's runtime settings, the launch permissions and the roundtable
  seat picker say a harness is being asked, or why it has no choices, instead of printing a shell command.
- Tests that filled the old per-project table now write the home record. One test added.
- `dispatch/README.md` describes the new behaviour.

Checked on the real machine: Codex, which had never run in `clear-trial`, answered in 8 seconds with no prompt
sent; `intake-trial` read the same answer without starting it; the settings screen's Agent 2 model list has 14
choices where it had one. Claude Code was asked the same way. The web server on 7433 was restarted and runs this
code.

Not checked: the chat's "next call" window in a browser, because the person's lead agent was running and was not
stopped. The endpoint that window reads was checked instead.

## Done: step 0 (2026-11-16, evening)

- Fast mode is keyed `speed` (ACP's proposed category, or the `model_config` ids `fast` and `fast-mode`); every
  other `model_config` option goes by its id, so Claude Code's Ultracode is no longer Fast mode.
- The call window, the running session's window and the intake window show Harness (was "Agent"), then mode, model,
  speed and thinking level; everything else sits under "More from <harness>", closed. `agent` is out of
  `OWN_OPTIONS`, so the subagent choice is never saved as a default.
- `test_ticket_fast_ui.py` had three failures left by step 1: its harness record had no start command, so dispatch
  asked the fake agent again. The fixture now records the command; the "unknown until read" case was removed,
  since dispatch now asks instead of waiting.
- Checked headless on the live page (web server restarted on this code). Not checked: a Codex ticket started with
  Fast on, end to end.

## In progress (2026-11-16, evening)

- Step 2a, the ACP layer `dispatch/acp/` (model, connection asking v2 with v1 fallback, v1 and v2 adapters, a
  setting to turn v2 off, the same tests against both through the fake agent), is being built by one Opus agent in the
  worktree `/home/rich/metaform-dispatch-acp`, branch `feat/dispatch-acp`, made from `feat/project-tool` at
  `07950be1`. Its commits are reviewed and merged into `feat/project-tool`, then pushed. Step 2b, moving
  `runner.Session` onto the layer, follows.
- An agent started with the Agent tool's own worktree option is made from `main`, not from this branch: make the
  worktree from `feat/project-tool` yourself and point the agent at it.

## Done 2026-11-16 beside the plan, each committed and pushed

- The 3D map: no namespace line over unrecorded steps; join edges as long as their old path, between surfaces; the
  camera pivot added inside an unrelated commit on 2026-10-18 removed, so a selected element can be dragged again.
- The element panel: the localized view (what an agent assigned there receives, from the project tool's own answer,
  `/api/local-view`), Wants and Wanted by with their details, "Known as" for the element's name.
- The chat: the next call offered after Stop agent; Claude Code's subagent option marked `profile_only` and left out;
  a prompt the harness repeats back no longer shown twice.
- AGENTS.md: "Scope is the assignment" and "Landing work". Bugs found and not fixed: `docs/plans/bugs-to-fix.md`.

## Next, in this order

**Step 2, the connection** (`dispatch/acp/`, v1 and v2 adapters under one model). Its first task is done: all four
adapter versions (Claude Code 0.100.0 and 0.107.2, Codex 2.5.0 and 2.6.0) select v2; see issues 21 and 22 in the
plan. Next in step 2 is the model above the adapters.

Then steps 3 to 7 as the plan lists them.

## State to know about

- Files changed and uncommitted: `dispatch/__init__.py`, `dispatch/runner.py`, `dispatch/offered.py` (new),
  `dispatch/README.md`, `roundtables/__init__.py`, `web/server.py`, four page files under `web/page/app/`
  (`session/settings.js`, `board/board.js`, `agents/permissions.js`, `roundtable/stage.js`), seven test files, and
  `docs/plans/dispatch-owns-acp.md` (new).
- `uv run pyright` is clean. `uv run ruff check src tests conftest.py` has one finding, in an archived skill script
  that this work did not touch.
- The 35 tests run across dispatch, map, roundtables, web and tasks pass. One other dispatch test fails in code
  this work did not touch (issue 24 in the plan). The full suite was not run.
- The home now holds `~/.metaform/agents/_offered/codex.json` and `claude.json`.
- Dispatch's own tables are still on the old store. The earlier handoff below gives the removal order.

## How to check a change here

- One test: `uv run pytest -n 0 src/metaform/modules/dispatch/tests/test_dispatch.py -k <name>`.
- What a harness answers: `metaform dispatch options agent=<agent> --json` from a project folder;
  `prime=true` asks it again.
- The page reads the same through `http://127.0.0.1:7433/api/dispatch-options?project=<project>&agent=<agent>`.
- After changing Python the web server needs `metaform web restart`. Page files are served from disk.
- Browser checks run headless only.

---

# Earlier handoff: what had been done before this session

Branch `feat/project-tool`, pushed. As of 2026-11-16.

## The project store

- A new store for each project's map, on LadybugDB: one database per project under `~/.metaform/maps`.
- One process per home owns the databases. Every other process sends it commands. Writes wait in a queue, are committed in groups, and can be sent twice without being done twice. Reads never wait on a write and share at most four connections per database.
- The map's shape follows one rule: an object is a step in an address, a list is an overlay, a plain value is a field. An element holds five fields: `technical_name`, `name`, `role`, `ref`, `status`.
- Overlays are defined under `<project>.overlay`. A definition holds its description, instruction, and each field's type, rule and example. Input is checked against it, and a refusal says what was wrong and how to correct it.
- Every project is given three overlays: `wants`, `tickets` and `memories`. Tickets and memories use the field names the old system already had.

## The one tool

- One MCP tool, `project`, on the server named `metaform`. Its arguments are one command; the project's name leads every path. It keeps no session.
- No command is a tool any more. Agents run `metaform <module> <verb>` in their shell.
- The old server is deleted: the catalog, every command-as-a-tool, the rule that refused a call until its instructions were read, the records of what each agent had been shown, and the old map views.
- An agent is given its rules and its task at start, and nothing else. An agent on the intake is given its task alone.
- `metaform mcp serve --http` serves the same small server, with the same sign-in checks and A2A beside it.

## Intake

- The intake module serves the new procedure, `digital_typology.xml`, byte for byte, with the request in the procedure's own slot.
- An intake agent records with the `project` tool, into the new store.
- The old intake recording is deleted: the module went from 1,673 lines to 212.

## The page

- The map, the element panel, the Layers control, the board and the Memories section read the new store.
- The board creates, moves, renames and deletes tickets in the new store. Start agent hands the agent the ticket; the agent takes it, notes it and closes it itself.
- The page redraws within about a second of a write.
- Clearing a project removes its map from the new store.
- A project switch takes about 2.5 seconds, down from about 7.
- With no project chosen, the page no longer shows error banners.

## The lead agent

- The chat box is the lead: one agent for the whole home. It lives in a `workspace` project of its own, stays in the chat box across project switches, and can work on any project.
- The chat works with no project registered and before any intake.
- The lead's task text says how to lead a team: team members are Metaform agents started with `metaform dispatch helper`, visible on the page.
- A helper tells the lead it is done itself, with one note its own prompt asks for. Metaform no longer writes that line.

## Faults found by running it for real, and fixed

- The store's service kept running old code after an update. A caller now replaces it.
- Reading connections piled up until the engine reported "buffer pool is full".
- A fault inside the service dropped the caller's connection instead of answering.
- The packaged dependency list did not name the database engine.
- The server behind the `project` tool was not kept running under `hold`.

## Housekeeping

- `CLAUDE.md` describes the server and the store as they are now, and states that the intake procedure and its semantics are the founder's.
- Tests of deleted code were deleted with it. The server, intake and store tests pass.
- All projects were removed from the home on 2026-11-16; `intake-trial` and `clear-trial` were registered afterwards for testing.
