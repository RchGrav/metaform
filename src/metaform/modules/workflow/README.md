# Workflow

## Purpose

Workflow stores reusable Axiom subroutines in ordinary knowledge layers. The
agent reading a subroutine interprets its conditions, routing, Map, Retry,
Catch and verification. The module carries calls, bound values, errors and
returns, including fresh-agent handoffs by run id. It starts no model.

## Template version

The Unreleased module contract after 0.3.0.

## Declaration

`SUPPORTED_OS` is Linux, macOS and Windows; `DEPENDENCIES` is empty;
`SHIPS_DISABLED` is true; enable it with `metaform enable workflow`.
`MODULE` declares the CLI/MCP verbs, the logic-version
and run tables and the node-read contribution.

## Common base used

`metaform.module` declares commands and context. `metaform.data` supplies
knowledge layers, elements, items, provenance, module tables and bound reads.
Its `runs` table, through `metaform.data`, persists call continuations and
atomically combines branch returns. `metaform.prompt_files` serves the module's authored XML resources.
`metaform.axiom` checks each stored subroutine, MCP-035 and BASE-057.

## Prompts

`resources/prompts.xml` holds the prompt-lexicalization script, module instructions
and call/handoff transport instructions. The shared registry, `metaform.skills`,
owns the canonical `metaform/skills/<name>/SKILL.md` folders and their
`references/procedure.axiom` files, BASE-059. Legacy underscore names still load
the same procedures through workflow skill, serve and assign.

The registry's `skills/resources/prompts.xml` holds the shared library sections
and templates. Libraries use the newest stored sections at load or deployment
time, preserving prompt-store edits and earlier versions. This ownership keeps
skill loading available in builds that omit workflow.

Discoverable skills remain slash commands `/metaform:<skill>`. Internal sentinel
and workflow-evaluator appear in no discovery list and remain callable by name
or Address. The always available MCP `metaform_skills` tool lists discoverable
skills, loads a skill and its libraries, and reads its files. An explicit
`all=true` administrative list includes internal skills.

## Verbs

Write a workflow from a goal, or import an existing prompt or workflow, with
the `write_workflow` and `import_workflow` skills. Read one and follow it, run
it as `/metaform:write_workflow`, or hand it to a fresh agent with `assign`:

```sh
metaform enable workflow
metaform workflow skill write_workflow
metaform workflow skill import_workflow
```

Prepare incoming work with `workflow_builder`, which follows `write_workflow`
and seeds its detailed rules at the affected map nodes. Judge results that
need judgement with `workflow_evaluator` on a separate fresh agent. The
evaluator takes the result, criteria, nodes and evidence, and reports its
verdict and supported findings. It never grades a workflow it wrote or work
it performed, D116. Both roles use the existing transport:

```sh
metaform workflow assign workflow_builder input="<request and target layer>"
metaform workflow assign workflow_evaluator input="<result, criteria, nodes and evidence>"
```

Give each returned run id to the agent holding that role. The builder also has
the MCP prompt `/metaform:workflow_builder`. The internal evaluator is loaded
explicitly with `metaform_skills op=load name=logic.skill.workflow-evaluator`.
All incoming work, including small fixes, goes through the builder under
D117; a small fix may use a single pass so it receives its rules with little
preparation overhead. Automatic routing is not implemented, and its mechanism
and the loop-controller design remain open, BASE-055 and BASE-056.
The builder records an unavailable operation and its dependency
rather than naming a command that does not exist.

Under D118, the builder writes proof into every loop whose passes change code
or specifications: a relevant test command when one exists, otherwise a review
by a fresh evaluator. A completed ticket suffices for a pass that only reads
or reports. Changed artifacts need evidence that they meet the intended
outcome. This policy applies independently of the open controller design.

Read the prompt-lexicalization script with a prompt to lexicalize, LAYER-017:

```sh
metaform workflow lexicalize "<prompt or workflow, verbatim>"
```

Its inputs fill the script's owner placeholders. `MAP_READ` is the `where`
read. `UNRESOLVED_POLICY` is the setting `lexicalize_unresolved`, `keep
wording` until set, and `ADDRESS_PLACEMENT` is `lexicalize_addresses`, `one
block of name -> address` until set. `PROMPT_STORE` names `metaform prompt
save <name> <text>`, or the MCP `save_prompt` tool with `name` and `text`.
Saving creates version 1 or appends a version with the newest as parent.
`parent=` names an earlier version when needed. Text is preserved exactly,
and earlier versions and their provenance links stay unchanged.

After the agent follows the lexicalization script, assemble context from
its prompt body and subject addresses. Supply the body without its footer,
since the assembler writes the canonical names and addresses at the end:

```sh
metaform workflow preprocess "Review the kitchen timer." '["code.timer.kitchen"]'
metaform prompt save prepared-review - < prepared-prompt.txt
```

`preprocess` returns `prompt`, `addresses`, `layers` and `scope`. Over MCP,
use `workflow` with `command: "preprocess"` and arguments `text` and
`addresses`. The body stays verbatim, followed by a JSON block of knowledge
and then the address footer. The agent supplies the name matches, so this
command does no inference. Save the returned `prompt` text, rather than the
whole command result, and hand that prepared text to the working agent.

`preprocess_knowledge` defaults to `context`: only the addressed nodes'
visible knowledge and applying or visible properties accompany the body.
Set `--preprocess-knowledge=whole` when the job needs all visible items of
the layers selected at its addresses. This includes more context and can
cost more tokens. Both modes honor select, mask, hidden and unfinished
layers through the existing reads. As those reads specify, `always_show`
items remain visible at the addressed nodes even when their layer is off,
hidden or masked. Whole mode broadens only the selected layers, while
retaining those local `always_show` items.

The module ships the latest shared sections to the versioned prompt store.
The tools section supplies the implemented commands. Writing and importing
submit the same stored shape:

```sh
metaform workflow submit workflow.quality.code procedures name="Code quality"
metaform workflow add_logic workflow.quality.code procedures review "<Axiom content>"
metaform workflow list
```

`provenance=` accepts the producing prompt, model and role. A workflow may
share its knowledge layer with other knowledge. `selected=` lists knowledge
layers that accompany a workflow's calls. Existing layer lifecycle, selection,
masking and hiding apply. The `add_logic` command also attaches a named subroutine
to any project element, including one a join holds. Its `this` is
that element. Its instructions are stored without content validation.

The four-field logic record has `type`, a system-assigned stable `logic_id`,
`name` and `content`. Submitting another version of the same named logic in
the same layer retains its identity and keeps every earlier content version.
`history <address> <name> <layer>` reads those versions. Calls use address and
name; they never handle the storage id.

Start a call, passing an element by address or using the entry's `this`:

```sh
metaform workflow run '({ok}, {issues}) := workflow.quality.code.review(target=code.engine.game)'
metaform workflow run '({ok}, {issues}) := workflow.quality.code.review(target=this)' element=code.engine.game
metaform workflow run '{verdict} := logic.skill.workflow-evaluator(Result="<result>", Criteria="<criteria>")'
```

Skill calls use their unversioned Address directly, including kebab names, and
return their required libraries beside the unchanged procedure. Skill versions
live in frontmatter metadata.

The returned `run` is the id of the call's run record, which holds its frozen
content, arguments, element values and continuation. `metaform workflow resume
run=<run id>` reads it; over MCP call `workflow_resume` with `run`. The record
is kept in the project, so an agent in another folder adds `--project <id>`;
it keeps the original metaform and layer context, whichever metaform is active
later. Reading a call reveals its current subroutine and values, without its
private caller stack.

While interpreting a call:

```sh
metaform workflow call '{fixed} := workflow.quality.code.fix(target={target})' run=<run id>
metaform workflow handoff '({ok}, {issues}) := workflow.quality.code.review(target={target})' run=<run id>
metaform workflow complete 'RETURN ({ok}, {issues})' run=<run id> variables='{"ok":true,"issues":[]}'
metaform workflow fail SourceUnreadable run=<run id> message="src/game.py"
```

`call` pushes a same-agent frame. `handoff` suspends the caller and returns only
the child run's id to give a fresh agent, directly where the host supports it or
through the orchestrator otherwise. The fresh agent sees only its callee's
instructions and values. Its `complete` closes the child run and resumes the
caller with the result bound to the call's targets. `fail` delivers the error unchanged;
the caller interprets its authored Retry or Catch. At the top of the calls,
results or errors return to the orchestrator. Returns become prompt values,
without implicit writes to the functional map or knowledge layers.

A run that something neither its ticket nor its logic decides stops pauses on
the person, and a run that is no longer wanted is cancelled:

```sh
metaform workflow pause run=<run id> The target code.timer.kitchen is gone from the map and the logic names no other.
metaform workflow answer run=<run id> Use code.timer.oven; the kitchen timer was merged into it.
metaform workflow cancel run=<run id> reason="superseded by ticket 80cafcd9"
metaform workflow runs state=input_required
```

Agents do not ask, MAP-050 as amended 2026-10-08: a choice an agent can undo
is its own to make and record, and is never a pause. `pause` is how an agent
stops a run on something its ticket and its logic leave to the person. An
agent working a ticket has the line added to the ticket's note first, where
the person reads it; if that cannot be written the run is not paused, and the
agent is told to write the note itself. The run is then `input_required`, with
what stopped it as its message and the agent's ticket and session kept on it.
The agent ends its turn; nothing starts again by itself, VIEW-042. A call and
an assignment pause the same way.

`answer` is the person's: on the command line only, and refused whenever a
runner's identity (`METAFORM_ROLE`, `METAFORM_SESSION`, `METAFORM_WORK`) is
set, so no agent answers a run, however it was started. It puts the answer
beside what stopped the run, in a call's current frame or on an assignment,
and `resume` shows both. It adds `Answered <time>: <answer>` to the ticket's
note, and its next step is the `dispatch message` that tells the ticket's
agent to resume the run. An agent told the answer in a message is told, by
every refusal on the paused run, to have the person run `answer`.

`cancel` cancels the run and every open run below it, each keeping its row
with the reason; a run handed from another delivers the error `cancelled` to
its caller in the same transaction, as `fail` would, so the caller's Catch
decides what follows. An agent whose role `roles_without_authority` holds back
cancels no run: a running one it fails, and one waiting or paused it leaves to
the person, with what stopped it in its ticket's note. `runs` lists the open
runs, oldest first, or those in one state, the newest first for an ended
state, 20 at a time with the command for the next page in `more`.

### Run states

A run's `state` is one of the one status vocabulary of work at a node,
`metaform.data.status`, which maps each to the MCP Tasks extension (`io.modelcontextprotocol/tasks`, schema
2026-07-28) and A2A 1.0 task states:

| Run state | Meaning | MCP Tasks | A2A |
|---|---|---|---|
| `running` | its agent is working the current subroutine | `working` | `TASK_STATE_WORKING` |
| `waiting` | waiting on the runs it handed out | `working` | `TASK_STATE_WORKING` |
| `input_required` | paused on the person: something only they decide | `input_required` | `TASK_STATE_INPUT_REQUIRED` |
| `completed` | returned, its result kept | `completed` | `TASK_STATE_COMPLETED` |
| `failed` | returned a named error | `failed` | `TASK_STATE_FAILED` |
| `cancelled` | cancelled, its reason kept | `cancelled` | `TASK_STATE_CANCELED` |

The vocabulary's `submitted` (A2A `TASK_STATE_SUBMITTED`) is for work received
and not yet taken; a run starts running. Workflow runs are the vocabulary's only
user today; tickets and agent sessions are to report it next. Two A2A states
are a state with a reason, `status.a2a`: `input_required` for a login the
person must give is `TASK_STATE_AUTH_REQUIRED`, and `failed` for work refused
before it starts is `TASK_STATE_REJECTED`. `waiting` and `input_required` both pause a run,
but children returning resume a waiting run on their own, while only the person
resumes one paused on them. The last three are terminal. `status.TRANSITIONS`
names every move, and a move it does not name is refused.

`variables=` carries values computed by the interpreter; omitted values keep
the saved scope. Each subroutine's parameters and `this` stay separate from
its caller's scope. `None` uses a PARAM default; without a default it fails
the call. Tuple returns keep their shape across the run record.

For authored Parallel, `parallel calls='["<call>","<call>"]'` returns fresh-agent
run ids. It resumes the caller after every branch returns, including named
errors, and binds the results in the supplied call order. Each branch's return
changes the caller's run in one transaction, so simultaneous branch returns
across processes are all kept. Serial Map, acceptance
loops, retry limits, conditions and error routes remain the interpreting
agent's work, as the authored Axiom language defines.

Export a carried workflow from its stored layer and import it elsewhere:

```sh
metaform workflow export workflow.quality.code procedures file="Code quality.metaform"
metaform workflow import "Code quality.metaform" layer=procedures
```

The file contains the workflow element, selected layer names, exact logic,
saved versions and producing provenance. It contains no source project
ownership. The destination assigns its native identities. Export with no
`file` returns the same portable document. It carries selected layer names;
the knowledge in those layers stays in its own layer store.

Read the libs and skills the workflow agent loads, MCP-034:

```sh
metaform workflow libs
metaform workflow lib lib_axiom
metaform workflow skills
metaform workflow skill write_workflow
metaform workflow scan "<workflow text>" task=write
```

`libs` gives each lib's first line, its marker; an agent loads a lib only when
its marker is not already in its context. `skills` gives each skill with
`about`, what its `# skill:` line says after its name, and the libs its
`# requires:` line names. Each skill's slash command has that same text as
its description in the host's menu, held in its `summary=` attribute; a test
keeps the two equal. `scan` serves the scan skill with the workflow and its
task bound as data.

Hand a skill to a fresh agent by run id:

```sh
metaform workflow assign write_workflow input='Review the kitchen timer'
metaform workflow resume run=<run id>
metaform workflow complete run=<run id>
```

`assign` returns the run id of an assignment and the command that reads it.
`resume` with that id, on MCP `workflow_resume`, serves the skill's libs once
each, then the skill, then the input. `complete` closes an assignment with no
`RETURN`; a call still needs its `RETURN`. An agent dispatch starts over ACP is
sent its skill whole as its first prompt, `workflow serve`, and needs no run.

All commands are available on CLI and MCP from the module's one declaration.
Run `metaform help workflow` or read the MCP `workflow_*` tools for the command
list and each command's arguments.

## Settings

No module-specific settings. Existing project and layer selection apply.

## Events

The chassis publishes map changes after storage commands. Workflow declares
no event handler; call transport is kept in run records.

## Sync and async

All verbs are synchronous short operations; the MCP server runs them through
its standard worker-thread path. Parallel work is handed to independent agents.

## Layers

The caller chooses ordinary knowledge layers. Newly created layers are mutable,
hideable and ready; existing layers retain their lifecycle. Logic is attached
as native layer items with four-field callable records. The module's
`logic_versions` table lives beside the metaform, keyed by `(logic_id, number)`,
and holds name and exact content. Native item deletion removes its history.

Version 2 adds `runs`, at project level so a clear of the metaforms or a change
of the active one keeps it: one row per run, keyed by `run_id`, with its `kind`
(`call` or `assign`), its `state` (`running`, `waiting`, `completed` or
`failed` in version 2; see Run states), its `parent` run, its call `frames`, its caller scope, the children
it waits on and their `branches`, an assignment's skill and input, its
`result`, and when it was made and closed. A returned run keeps its row and
accepts nothing more. Version 1's code still reads and writes the tables.

Version 3 gives runs the one status vocabulary: a run may also be
`input_required` or `cancelled`, `message` holds what stopped it or the reason
for cancelling, and `updated` is when its state last changed, an MCP task's
`lastUpdatedAt`. Every state a version 2 row holds keeps its name and meaning;
the upgrade sets each row's `updated` to its close, or else its creation.
Version 4 adds `ticket` and `session`, the ticket and agent session that
paused a run. The new columns may be empty, so `compatible_from` stays 1:
version 1's code has no runs, and version 2's takes a run in either new state
as ended and refuses it. Version 1 is the last committed; versions 2 and 3
were only in the working tree from 2026-10-11, and their steps are kept so a
database opened from it still upgrades.

## Lifecycle and cleanup

No start/stop hooks or spawned tasks. Storage survives unload. Each completed
call closes its run, which keeps its row and result.

## Modules relied on

Logic reads use the public DAO. Element values include the memory module's
existing public node projection, as the MAP-057 binding already provides.
The chassis and MCP module expose the declared verbs.

## Systems supported

Linux, macOS and Windows, using Python, SQLite and the public data access object.

## Resources owned

Packaged prompts, layer records, the declared history table and the run
records. Export writes only the named destination. No agent process or server
is started by workflow.

## Installed and direct wheel

Resources load through `importlib.resources`; storage uses the normal Metaform
home and selected project's DAO in either packaging form.

## Demonstration

Submit a workflow element and a named Axiom subroutine, then run its call and
resume the returned run id. Complete with its RETURN expression; the examples
under Verbs show same-agent calls, fresh-agent calls and portable export.
