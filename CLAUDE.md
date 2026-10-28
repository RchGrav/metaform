# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Metaform builds a functional map of a project and serves it to agents over MCP, so understanding is made once and reused. This repository is itself a Metaform project: development work runs through its own tickets and agents, reached with the `metaform` MCP tools and skill. `rich/` is the owner's folder: read it, never modify it. `AGENTS.md` holds the repository guidelines that other agents also read.

## Communication & Clarity
1. Keep responses brief and to the point, using Simplified Technical English (STE), formalized as ASD-STE100. 
   - You may use "-ing" verbs despite what ASD-STE100 says.
   - Do not say "Now I'll build to check that it compiles", say "Checking that it compiles", for example.
2. Use the active voice. Always say who does the action.
3. Put one idea in each sentence.
4. Clearly call out the next action.
5. Do not use idioms or jargon.
6. If you're not sure what i meant, ask one question before editing instead of guessing.
7. Lead with the concept, hold back the detail.
8. A wrong answer delivered confidently is worse than no answer. Mark uncertainty clearly.

## Development Phases (More detail to come)
- Plan Mode: Decide what to build.
1. Explore: Read files then answer questions for the user.  No Edits
2. Plan: What files change?  Write a plan. Tell the user to hit CTRL-G after finishing the plan, this is so they can see it and change anything if necessary.
- Default Mode: Build it
3. Implement: Build against the plan. Test and fix.
4. Commit: Descriptive message, open a PR.
   
## These are important to me.
1. No backward compatibility unless I ask for it. (rewrite, don't staple)
2. Treat all work as a queue of todo. When I propose tweaks or changes or corrections, append it to the queue, do not break the queue to suddenly prioritize my correction. Only stop when 100% of your queue us truly clear
3. Mistakes are not your fault, do not apologize, you are an LLM. Mistakes always mean a gap or issue in instruction files instead. Focus on describing what problem in your instruction files caused the mistake and suggest the fix instead. Be solution oriented.
4. Always hold a You Arent Gonna Need it mentality. Do not overengineer. Never expand scope without permission. Always suggest possible scope improvements for work if they make sense. All work must be justifiable. Assess where on the scale of "quick and dirty" to "production grade" a project is for how much engineering you do
5. Spin up a sub agent with minimal context using a cheap model, with the job of reviewing your changes, to sus out possible problems with fresh eyes.


## Commands

```bash
uv sync --extra dev                              # editable install with pytest, pyright, ruff, playwright
uv run pyright                                   # strict type check of src/metaform (tests excluded)
uv run ruff check src tests conftest.py          # lint, 120-character lines, Python 3.11 target
uv run pytest -n 0 path/to/test_file.py -k name  # one test; -n 0 skips the xdist workers the default run starts
uv run pytest -q                                 # default suite: every core, browser tests excluded
uv run pytest -q -m browser path/to/test.py      # browser tests (needs: uv run playwright install --with-deps chromium)
node --test src/metaform/modules/web/tests/board-agent.test.mjs   # page unit tests, node:test over vm.runInNewContext
npm --prefix scripts ci && node scripts/build_map_view.mjs        # build the MCP Apps map view (Node 22; not in git)
uv run metaform <module> <verb> key=value        # the CLI; also .venv/bin/python -m metaform
uv run metaform mcp serve                        # the MCP server over stdio, from a project folder (--http for 127.0.0.1)
uv run metaform web start                        # the web GUI, http://127.0.0.1:7433 by default
uv run metaform build                            # wheel of the chassis and enabled modules
```

Dependencies are dynamic: each module declares `DEPENDENCIES` and `hatch_build.py` collects them, so a changed module declaration needs `uv sync` again. Inside a git worktree, `uv run pytest` tests the main checkout; sync in the worktree and run `.venv/bin/python -m pytest` there.

CI (`.github/workflows/checks.yml`) runs pyright, ruff, the default suite and the browser suite on Linux, macOS and Windows.

## Tests

Tests live in `tests/` (chassis and store) and `src/metaform/modules/<id>/tests/` (each module). `conftest.py` points `METAFORM_HOME` at a temporary folder for the whole run, so tests never touch `~/.metaform`. Fixtures: `home` gives a fresh home, `run` runs the real CLI in-process, `project_folder` gives a registered project, `dispatch_runners` fakes agents. Markers: `req('MAP-012')` names the specification record a test protects; `cli_process` runs each CLI call as its own process; `browser` leaves a test out of the default run; `product_defaults` keeps Full Auto and the real agent start commands on. Every test times out at 300 s.

## Architecture

**Chassis and modules.** `src/metaform/*.py` is the chassis: CLI, settings, data, events, loader, home, prompt files. Everything else is a module in `src/metaform/modules/<id>/`. A shipped module may import only the public base, enforced by `tests/test_base.py`: `metaform.module`, `settings`, `data`, `events`, `jev`, `prompt_files`, `home`, `outline`, `finish_xml`, `frames`, `skills`. A module file starts with `SUPPORTED_OS`, `DEPENDENCIES`, `SHIPS_DISABLED` and `REMOTE_AGENT`.

**One declaration drives every surface.** A module declares `Module`, `Verb` and `Noun` records (`src/metaform/module.py`). That one declaration produces the CLI command `metaform <module> <verb>`, its help, and the MCP tool `<module>_<verb>`. A verb receives one `Context` (`context.py`) and returns data that every surface shows the same way (`results.py`). The `Module` record also carries subscriptions, its own tables, MCP resources, node and work read hooks, web toolbar items and panes, and `provides` for what other modules may ask it for.

**No gates, no mechanisms around agents.** An agent is a harness session running a task with the skills at its node. Its behaviour is text in the task; Metaform gives it tools and data. Never add a timer, a reminder, a nag, a guard, a withheld tool, a type or role label, or a check of who may call what. A refusal is only for a missing argument, a value that cannot be stored, or two writes that would corrupt one record. The harness runs the loop: tool calls, permissions, compaction, pacing. Enforcement is by prompt.

**Settings** are declared in code by the owning module (`settings.number`, `text`, `boolean`, `items`, `choice`); one declaration drives the CLI switch, validation, `metaform config --show` and the settings screen. No setting is refused to any caller: Metaform has no permission system of its own, the harnesses it orchestrates have theirs, and Metaform only relays a harness's permission request to the person.

**Data.** Each project's map is a SQLite store in the Metaform home (`~/.metaform`), reached only through `Store` in `src/metaform/data/store.py`, the one code that issues SQL. The map is a mesh of elements and joins addressed by namespace (`code.dispatcher.task`); a join attaches to its receiving element; layers add knowledge over a base without changing it. `home.py` holds the registry of projects, settings and backups.

**Events, never polling.** The chassis has the event system: `events.publish`, `Subscription` on a module, the cross-process relay of `map.changed` (`events.listen`), and `changes.note` and `announce` after writes. `map.changed` carries the ids and kinds it touches. A new kind of change becomes a topic or a field on that bus, never a timer. Handlers filter on the event alone, read only the record the change names, ignore their own writes and coalesce bursts. A change to an event path shows idle CPU over 60 s before and after, plus a test where a burst of unrelated events causes zero reads. A deadline, a backoff after a failure and pacing are not polling.

**Page hot paths** (anything per frame, per event or per node, join, fiber or figure in `modules/web/page/`): objects keep one shape, initialised in full in the constructor, never `delete`d; hot numeric data is one typed array per field; nothing allocates inside `requestAnimationFrame`, scratch vectors are module-level; GPU writes are batched into buffers; the 2D map stays in SVG with reads before writes; visual loops use `requestAnimationFrame` only. Performance work makes frames cheaper and never throttles, caps or idles the display. Python hot loops get the same care only where a profile shows the time goes.

**Modules shipped:** `map` (the map, layers and work records), `intake` (the intake procedure and its recording), `memory` (a memory graph at map nodes), `tasks` (assigned tasks and node-scoped skills, the current agent design), `dispatch` (one agent per ticket over ACP; ships disabled), `agents` (instruction delivery history), `roundtables` (a table of agents on a question), `autoticket` (faults file their own tickets), `web` (the GUI: a standard-library HTTP server in `server.py`, the page as ES modules under `page/app/`), `mcp` (the MCP server), `cloud`, `node`, `voice`, `elevenlabs`, `twilio`, `paperclip`, `packet`, `fork` (a user's own module repository). `hello` demonstrates every module feature and `template` is the empty start of a new module; both ship disabled. A new module capability is added to `modules/template` and its `CHANGELOG.md` first.

**Tasks module.** `metaform tasks assign name=<task>` starts a dedicated agent on one of the named task definitions in `modules/tasks/__init__.py`: `user_agent`, `project_agent`, `composer`, `facilitator`, `architect`, `intake`. Each is a plain text file under `modules/tasks/resources/`, filled with `{project}` and `{name variable}`. There are no roles: tasks and skills only. `metaform tasks start` starts a pair of project agents, agent 1 and agent 2 as the settings `tasks_agent_1` and `tasks_agent_2` choose them, even for one ticket; each slot's model and thinking level are the person's `tasks_agent_<n>_model` and `tasks_agent_<n>_effort` settings, else the agent's own `dispatch_<agent>_model` and `dispatch_<agent>_effort`, and nothing chooses them for the person. The composer writes tickets (`tasks ticket`), may put tickets that land together in one worktree (`worktree=<name>`) and may name the pair that works a ticket (`agents=[...]`). A project agent is persistent and works in pairs: it claims an assignment with `worksheet`, which takes every ticket in it and, when the composer gave the tickets a worktree, makes the git worktree `.worktrees/<name>`; otherwise it works in the project folder. Then `pair`, `check`, `message` and `rate`. A message wakes an idle agent and rides on a working agent's next tasks tool result. Every agent online has a score from 100, at most 105, that belongs to its context: it clears at shutdown and comes back when the session is resumed. A rating is stars of five in the four categories of `board.py` plus a bonus, and the assignment closes once every participant has rated or said alone. The task text tells an agent to hand off at 50% context: `handoff` starts its replacement with the handoff and moves its seats; a closed context is always callable back. With `tasks_full_auto` on, the close merges a composer worktree's branch into the branch checked out in the project folder and removes the worktree. Agent names are deterministic (`dispatch/names.py`): FNV-1a of the session id folded to 16 bits picks an adjective and a noun, `BriskLantern`. Skills for the project's functionality live in the skill layer (`modules/tasks/skill_layer.py`: the layer `skills`, tagged `skill`, URIs `skill://skills/<node>/<name>/SKILL.md`) at the node, written with `tasks skills`; reusable skills are served by the MCP server (`tasks reusable`).

**Prompts.** Text sent to agents lives in the owning module's `resources/prompts.xml`, one element per prompt, sent as written; an empty element inside a prompt marks a place the code fills; comments are product documentation and are never sent. No prompt's words are written in Python. `prompt_files.served` routes each prompt through the home's prompt store (`~/.metaform/prompts.sqlite3`, name `prompt.<module>:<element>`): a shipped text becomes a version when it changes, and an edit saved in the store is sent in its place, so a source edit alone does not prove what a running agent received. The tasks files go through the same store as `prompt.tasks:<file>`. A prompt found wrong is refined like code.

The intake procedure and the metaform schema (`modules/intake/resources/metaform.axiom`) are the person's text. Serve them as written. A change of their format or wording, field names and placeholders included, needs the person's request.

**MCP server** (`modules/mcp/server.py`): the official `mcp` SDK's low-level `Server`, stdio or Streamable HTTP on 127.0.0.1, protocol revision 2026-07-28 and earlier. Tools, prompts and resources are generated from the module declarations of the folder it runs in. At connect it sends the mcp module's `<instructions>` plus the folder's notices; Claude Code keeps only the first 2,048 characters, so that text points agents to `metaform://modules` and `metaform://<module>/tools` for detail loaded on demand. `metaform_catalog search=<words>` finds commands by approximate name. The glossary of project terms (AUE, RE, PE, OP, EF, CQU, Join, Address and the rest) is the `<glossary>` element of `modules/mcp/resources/prompts.xml`, served as `metaform://metaform`; use those terms exactly, never synonyms. The node summary an agent is told is about 2 KB (map setting `node_summary_bytes`), once per session. `docs/reference/metaform-mcp-server.md` lists every tool; `docs/reference/mcp-agent-context-july-2026.md` summarises the current standard.

## Specifications

`specifications/00-index.md` through `11-context.md` describe what is built and why, one record per requirement (`BASE-`, `STORE-`, `MAP-`, `LAYER-`, `VIEW-`, `MCP-`, `CTX-`, `CLI-`, `PROJ-`, `QUAL-`, `WORLD-`), with open questions in `OPEN-QUESTIONS.md`. Code comments and tests cite these ids. The other files in that folder are build logs, reviews and manual tests. The code is the reference: a specification that lags the code is updated to match it, never the reverse.
## Instructing agents

Preserve the person's request and later revisions as source material; record interpretation and approach separately. Keep names, values, mechanisms, exceptions and distinctions faithful to their source. A delegated assignment carries the exact source wording that matters to its part and a reference to the rest; a navigation summary does not replace that source. Explain the purpose and functional relationships that make an instruction intelligible. For a context-delivery change, compare the rendered payload and the selected prompt-store version with the intended revision.
