# Autonomy and self-healing: what isn't working, and what to build

2026-10-18. Written by the system agent at the owner's request, for review (including an outside once-over) before the
remaining work is engineered. Every claim below was checked in the tree or the store on 2026-10-18; file and line
references are to the working tree committed with this report.

## The goal

Metaform is for building things: any project a user brings to it, of any kind. Metaform itself is only the project it
happens to be building right now. Whatever a user specifies should come about, and come about to a high quality, with
the project keeping itself healthy as it is built. Everything below applies to every project built with Metaform, not
to Metaform alone.

Metaform should run a project on its own when the user wants it to. Issues become tickets, tickets get fixed, fixes are
proven, the board stays clean, and the user is asked only about decisions that are theirs. The user chooses how much
autonomy the system has; at full autonomy it does everything.

Today it does not. Work stalls, the board fills with noise, and the user has to notice each problem and say so. The
sections below say why, part by part.

## The intent, as the owner set it

- **What has been built is the functionality.** The map already records every part, what it is for (its operative
  purpose) and what relies on it. That is the specification of what the project does. The work from here is not to
  decide what to build again; it is to make what has been built work, error free and to a high standard.
- **Doing it right needs no permission.** When a part is asked for, it means the part done properly. "Engineer a kanban
  board" means a good kanban board: one that archives finished work, holds one ticket per issue, keeps every ticket
  moving or closed, and never needs the user to clear it. Finishing a part to that standard, fixing it where it falls
  short, and deleting what a better design replaces are not decisions for the user. An agent does not ask "may I fix
  the kanban board the way it should have been"; it fixes it.
- **The user decides what the project is for, not how well it is made.** The user is asked only when a change would
  alter a part's purpose or what it serves, when an act cannot be undone, or when they have chosen a lower level of
  autonomy.
- **Every project keeps itself clean while it is built.** Not Metaform alone: any project built with it. Errors become tickets, tickets get fixed, fixes are proven, the board stays
  workable, and old code is removed when a design changes, all without the user watching. Until it does, the user sees
  only a lot of things broken; getting it to keep itself clean comes before adding more.
- **C(T) comes first, and it is why trouble can always be fixed.** C(T) = { (r_i ∧ p_i ∧ e) }: the project's functional
  core, each receiving element with the purpose it holds and the element that serves it. It is the frozen core that
  allows mutation, not transformation. A specification describes how C(T) is delivered; it is subordinate to C(T). When
  a specification is what causes the trouble, because it blocks a part from serving its purpose or no longer matches what
  serves it, C(T) overrides the specification: the trouble is fixed, and the specification is adapted to match. The user
  is notified when a specification adapts, with what changed and why; no approval is needed, because the fix serves
  what the project is for. What does need the user is a change to C(T) itself: a purpose added, removed or changed.
  Specifications are short-sighted by design: they are written before the thing is built, so they cannot foresee all of
  what building it will show. A specification turning out wrong is expected, not a failure, and it is why C(T), not the
  specification, has the last word.
- **Specifications are followed until they are the problem.** A specification is the problem when it has to change for
  something to work, when it holds the design back, or when it is not the right solution for the functionality it
  describes. Then C(T) wins. How an agent knows the right thing to do: C(T) tells it. The right change is the one that
  lets each receiving element's purpose be served by what provides for it.
- **The loop, in any project:** problems are seen; agents file a ticket; tickets start automatically; the problem is
  fixed against C(T); where a specification had to adapt, the user is told.
- **Agents report trouble, in any project.** Trouble is trouble and a problem is a problem, wherever an agent meets it:
  a failing test outside its ticket, an error in a log, a part that does not do its purpose, a broken page, a confusing
  control, a slow path. Every agent files what it sees as one trouble ticket at the part concerned, with its evidence,
  and the ticket is fixed like any error. An agent never walks past trouble because it is not its ticket. (On
  2026-10-18 six failing tests were found, confirmed as failing before that day's changes, and noted, but no ticket
  was filed for any of them; section 8.)
- **The agent the user talks to is their advisor.** It notices what is not working and says so, with a fix, unasked.

### The quality standard

Whatever is built with Metaform is to be built to a high quality standard: what the user specifies comes about, and
comes about well. That holds for any project, of any kind, not only for Metaform building itself. Working is not enough: a part is done when it does its purpose fully, has no known errors, carries a check
that proves it, leaves no superseded code behind, and reads as if it were designed that way from the start.

Holding that standard is automatic, not something the user asks for each time:
- **An automatic critic pass.** When a change lands, a critic checks the parts it touched against their purpose on the
  map and against this standard, the way a merge like 4f2966c8 should have been checked (section 3). Unlike the review
  flood of 2026-10-18, the critic fixes what falls short, or files one ticket per real gap with its remediation and the
  check that proves it; it never files the same finding twice and never re-reviews work nothing changed. Metaform
  already has the pieces (the critic agent, `map_critic`, the orchestration FQC); they need to be pointed at quality,
  bounded by the guardrails below, and run by events, not timers.
- **Existing work is brought up to the standard too.** What has been built is reviewed part by part against its
  purpose and fixed where it falls short, without the user's permission, starting with the parts the user depends on
  most.

### Is this realistic

Yes, with three conditions, all within reach:
1. **"Working properly" is judged against the map, not taste.** Each element's operative purpose says what it must do
   for what relies on it, so an agent can check a part against its purpose and fix the gap without asking. This is
   Metaform's own design; it only has to be used for quality, not only for placing tickets.
2. **Every fix comes with a check that proves it.** A test, or an error that stays gone (section 4). Without proof, a
   self-healing loop only moves errors around.
3. **Guardrails keep autonomy from turning into churn.** One ticket per issue, one writer per part at a time, design
   changes and irreversible acts held for the user, and spending within the project's budget. 2026-10-18 showed what
   happens without them (section 3).

## 1. Nobody owned the board

- The user-facing agent was defined as "Triage / PM": it writes tickets and queues them; "GCs own ticket execution"
  (`dispatch/resources/prompts.xml` `<system>`, from commit 4f2966c8). Each GC owns one ticket. Nothing owned the board
  as a whole.
- The agent acts only when the user writes to it or a few signals arrive (`dispatch:setup_trouble`,
  `dispatch:wave_ready`). Nothing gives it a turn when the board needs one.
- Result on this project: 23 open tickets sat still. About 11 were held from before agent tickets stopped being held; about
  7 were taken by agents long gone ("Dead runner recovery" is manual by default); 2 had no task, which Full Auto skips
  (e.g. `#1d`, a fault light flashing red for five days); one help-line fix was filed four times.
- Fixed today in the role: the `<system>` prompt now has "Own the board" (every ticket moving, waiting on a decision put
  to the user, or closed with its reason) and "Be the user's advisor" (notice what is not working, unasked, and propose
  fixes at the cause). The role registry (`agents/__init__.py`) says the same.
- Still to build: ticket `code.dispatcher.agent#58` (turns by events, dead runners recovered in code, taskless tickets
  refused, new installs with Full Auto on and recovery automatic).

## 2. The board never archives

- 294 done tickets stay on the board (92 from 2026-10-18 alone, most of them review churn), beside 23 open ones. The user
  cannot see what is going on.
- Normal practice: the Done column shows recent work only; older finished tickets are archived, kept and searchable,
  off the board. A "line in the sand" archives everything finished up to a point.
- To build: the board shows open work and work finished in the last N days (a setting, 7); older done tickets are
  archived, never deleted (each is a record of what happened at its part of the map, readable through ticket history and
  `map_work open=false`); one "line in the sand" action; the system agent keeps it so.

## 3. The orchestration reviews flood the board

From the GC/FQC orchestration merged 2026-10-18 (4f2966c8):
- One finding is filed again and again: one help line as `#c4`, `#f0`, `#f2`, `#f6`; one spec amendment as `#fe`,
  `#100`, `#10b`.
- Reviews queue duplicate assessments of themselves through `orchestration_assess` (at least six on 2026-10-18).
- Results reach the system agent two and three times.
- Ticket titles and tasks are raw JSON: `orchestration/state.py` `_correction` (about lines 845-849) uses `str(fields)`
  when a finding has no title.
- Reviews file and start work by themselves; three agents edited one function (`followIn3d`) within an hour, and a
  restored file twice overwrote a decision the user had made.
- The merge also weakened the connect directive (from "Before you do anything else, read every resource linked below,
  whole" to "Read the applicable instruction resources ... whose contents are due") and dropped the handoff's line asking
  agents to record memory at the node.
- It wraps the person's message to an agent in an assignment block, which breaks three chat tests that pass the
  person's words through as typed (`test_a_metaform_calls_view_runs_in_the_chat...`,
  `test_new_and_clear_end_the_system_agents_conversation...`, `test_chat_shows_busy_and_interrupts...`; failing without
  any 2026-10-18 change).
- Taken together, this one merge broke at least four things: the review flood, the weaker connect directive, the
  dropped memory line, and the person's chat message. It should get a full review of its own before anything more is
  built on it.
- Queued: ticket `code.router.assignment#4` (one ticket per finding, prose titles, no self-assessment, delivered once).

## 4. Errors do not heal themselves

- The log watcher exists as `modules/autoticket` but ships disabled and is off here. It sends a ranked list on a timer,
  reads log files only, and files a ticket only when someone promotes a group.
- Onboarding is meant to set up logging first, so the project is watched while it is built
  (`artifacts/specs-draft/autoticket.md`, "Intake and the connect notice"). It is not built: intake has no logging step
  and no project is watched.
- Queued: `code.scheduler.task#8` (every fault source as an event; a new kind of error files one ticket at the owning
  element; one open ticket per error; caps; on by default), then `code.scheduler.task#9` (a fix closes only when proven;
  a returning error reopens its own ticket; fault lights follow).
- Missing from the queue: the onboarding step that gives a project its logging and points autoticket at it. Add it to #8
  or as its own ticket.

## 5. Autonomy is scattered across settings that fought each other

Each default was chosen against runaway agents after the 2026-10-17 review; together they meant nothing moved unless the
user moved it.

| Setting | Was | Now (2026-10-18) |
|---|---|---|
| Tickets agents write held for approval (`hold_agent_tickets`) | always | option, off |
| Agents ask before starting, stopping, releasing work (`agents_ask_first`) | always | option, off (irreversible acts still ask) |
| Full Auto, renamed from Autostart (`dispatch_autostart`) | off | off; #58 makes it on for new installs |
| Dead runner recovery (`dispatch_recovery`) | manual | manual; #58 makes it automatic |
| Log watcher (`autoticket`) | disabled | disabled; #8 enables it |
| Agents remove superseded code (`dispatch_remove_superseded`) | none | option, on |

### The autonomy panel

One control, in the header beside Full Auto and on the Settings screen, sets all of these together:

| Level | What happens |
|---|---|
| Manual | Agents work only on what the user starts. Agent tickets held; agents ask first. |
| Assisted | Errors and findings become tickets; the user starts them. Agents ask before acting. |
| Full autonomy | Errors become tickets, agents fix them, fixes are proven, the board is kept and archived, superseded code removed. The user is asked only for design decisions and irreversible acts, and gets one short list of what was done. |

Each underlying setting stays available for a user who wants a custom mix; the panel shows "Custom" then.

## 6. Agents could not keep memory

- Memory tools sat behind the tool catalog's `remember` category; a worker saw only `ticket` tools. Orchestration agents
  were told they had two memory tools (`dispatch/runner.py` "relevant" list).
- Fixed today: category renamed `memory`, its tools listed beside every category (`catalog.BESIDE`); every memory tool in
  the runner's list; `metaform://tools` lists every tool by category within a strict 4,500-character limit and never
  cuts the modules' rules.
- 190 memories written before the current memory prompt were deleted (backup:
  `~/.metaform/projects/-home-rich-metaform-001/modules/memory.sqlite3.before-clear-2026-10-18`).
- To decide: one MCP server per module behind a router, so each agent sees modules and loads their tools on demand,
  replacing the catalog (proposal in the 2026-10-18 conversation).

## 7. Old code keeps running

Each agent session, the web server and the user's terminals keep the code they started with. Today's fixes reach them only
after a restart or `/mcp` reconnect. Sessions still on old code at 17:40Z: the user's two Claude Code terminals, the web
server, the system agent `800b54a7`, threads `5decae95` and `05189f53`, run `83a45196` (roundtable), worker `b5b7572b`.
A self-healing system needs to restart its own processes after a fix lands (a handover exists for store layout changes,
code.dispatcher.agent#48, but not for code changes generally).

## 8. Failing tests that were already failing

Confirmed failing at commit 9eb0eed5 too, so not caused today; under self-healing each should become a ticket:
- `test_mcp.py::test_a_dispatched_agent_gets_the_persons_decision_never_its_own_confirm[memory_delete_entities]` and
  `test_cli.py::test_the_command_a_refusal_gives_the_person_runs_when_pasted`: memory deletes no longer need the
  person's decision (code.store.memory#3); tests or code to reconcile.
- `test_dispatch.py::test_cancel_and_tune_are_the_persons_and_tune_takes_only_what_the_agent_offers`.
- `test_mcp.py::test_a_caution_and_a_person_only_change_are_asked_of_the_person_by_form_on_the_july_wire`.
- `test_mcp.py::test_firstrun_is_linked_only_to_the_person_s_own_session_while_the_project_has_no_intake`
  (`assignment_context` raises for a folder with no project).
- `test_dispatch.py::test_the_handoff_asks_to_record_at_the_node_only_while_memory_is_on` (its prompt line was removed).

## 9. The advisor

The user-facing agent should notice all of the above without being told and propose fixes at their cause. It did not:
it relayed each symptom as it came. Written into its role today ("Be the user's advisor"). Whether a separate advisory
agent is also wanted, to sweep a project periodically, is open; a sweep must be event-driven or user-started, never a
timer.

## Changes made on 2026-10-18 (in this commit)

- 3D map: turns around the selected node, including when grabbed mid-flight; label sizing unchanged.
- Object tab no longer flickers or loses a half-written issue when agents write elsewhere.
- Word bubbles: time set by their text (auto), setting in the Agents menu; glass-theme background fixed.
- No pop-up cards to close; chat tab flashes once for a message while minimised; info banners optional
  (`web_notices`, off); the "Project updates" banner removed.
- Broadcasts include the user's own agent by default.
- Web server: a refused POST no longer corrupts the next request on its connection.
- Agent size limited by default; camera-clearance code built from a misread request removed.
- Object tab state shows "built" for a part with no state.
- Settings: `hold_agent_tickets`, `agents_ask_first`, `dispatch_remove_superseded`; Autostart renamed Full Auto.
- MCP: memory tools always listed and bound; `metaform://tools` by category with a strict limit; `remember` category
  renamed `memory`.
- System agent's role: owns the board; is the user's advisor.
- Spec drafts awaiting the owner: `artifacts/specs-draft/view-035-041-agent-size-key-6-2026-10-18.md`,
  `artifacts/specs-draft/mcp-003-memory-beside-tools-by-category-2026-10-18.md`.

## Queued tickets, in order

1. `code.router.assignment#4`: reviews stop flooding the board (taken).
2. `code.scheduler.task#8`: errors file themselves.
3. `code.scheduler.task#9`: fixes proven; returning errors reopen their ticket.
4. `code.dispatcher.agent#58`: the system agent's turns and defaults to own the board.

Not yet filed: the board archive (section 2), the autonomy panel (section 5), onboarding's logging step (section 4), the
module-per-server MCP router (section 6), restart after a code fix (section 7).
