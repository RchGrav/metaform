# Workflow

## Purpose

Workflow stores reusable Axiom subroutines in ordinary knowledge layers. The
agent reading a subroutine interprets its conditions, routing, Map, Retry,
Catch and verification. The module carries calls, bound values, errors and
returns, including fresh-agent nonce handoffs. It starts no model.

## Template version

The Unreleased module contract after 0.3.0.

## Declaration

`SUPPORTED_OS` is Linux, macOS and Windows; `DEPENDENCIES` is empty;
`SHIPS_DISABLED` is true; enable it with `metaform enable workflow`.
`MODULE` declares the CLI/MCP verbs, the logic-version
table and the node-read contribution.

## Common base used

`metaform.module` declares commands and context. `metaform.data` supplies
knowledge layers, elements, items, provenance, module tables and bound reads.
`metaform.nonce` persists call continuations and atomically combines branch
returns. `metaform.prompt_files` serves the module's authored XML resources.
`metaform.axiom` checks each stored subroutine, MCP-035 and BASE-057.

## Prompts

`resources/prompts.xml` holds the six shared sections, the
prompt-lexicalization script, module instructions and call/handoff transport
instructions. Serving a lib, a skill or a call registers the shipped sections
in the prompt store lazily; previous prompt versions remain available.

The same file holds the workflow agent's libs and skills, MCP-034. `lib_axiom`,
`lib_metaform` and `lib_workflow` are composed at serve time from the newest
stored version of each shared section they carry, so an edit saved in the
prompt store reaches them. `lib_quality` and the seven skills are held whole.
Each skill is a child of `<commands>`, so it is a slash command,
`/metaform:<skill>`, as well as a command.

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

Give each returned nonce to the agent holding that role. The same skills are
MCP prompts `/metaform:workflow_builder` and `/metaform:workflow_evaluator`.
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
```

The returned nonce holds the call's frozen content, arguments, element values
and continuation. `metaform <nonce>` redeems it; on MCP call the `workflow`
tool with `command: "resume"` and `arguments: {"nonce": "<nonce>"}`. It works
from a fresh agent's folder because the nonce carries the original project
and metaform context. Reading a call reveals its current subroutine and values,
without its private caller stack.

While interpreting a call:

```sh
metaform <nonce> call '{fixed} := workflow.quality.code.fix(target={target})'
metaform <nonce> handoff '({ok}, {issues}) := workflow.quality.code.review(target={target})'
metaform <nonce> complete 'RETURN ({ok}, {issues})' variables='{"ok":true,"issues":[]}'
metaform <nonce> fail SourceUnreadable message="src/game.py"
```

`call` pushes a same-agent frame. `handoff` suspends the caller and returns only
the nonce to give a fresh agent, directly where the host supports it or through
the orchestrator otherwise. The fresh agent sees only its callee's instructions
and values. Its `complete` closes the child nonce and resumes the caller with
the result bound to the call's targets. `fail` delivers the error unchanged;
the caller interprets its authored Retry or Catch. At the top of the calls,
results or errors return to the orchestrator. Returns become prompt values,
without implicit writes to the functional map or knowledge layers.

`variables=` carries values computed by the interpreter; omitted values keep
the saved scope. Each subroutine's parameters and `this` stay separate from
its caller's scope. `None` uses a PARAM default; without a default it fails
the call. Tuple returns keep their shape across nonce persistence.

For authored Parallel, `parallel calls='["<call>","<call>"]'` returns fresh-agent
nonces. It resumes the caller after every branch returns, including named
errors, and binds the results in the supplied call order. Atomic nonce updates
preserve simultaneous branch returns across processes. Serial Map, acceptance
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

Hand a skill to a fresh agent by nonce:

```sh
metaform workflow assign write_workflow input='Review the kitchen timer'
metaform <nonce>
metaform <nonce> complete
```

`assign` returns `metaform <nonce>`. Run through it, on MCP as `resume` with
the nonce, it serves the skill's libs once each, then the skill, then the
input. `complete` closes an assignment with no `RETURN`; a call nonce still
needs its `RETURN`.

All commands are available on CLI and MCP from the module's one declaration.
Run `metaform help workflow` or open the MCP `workflow` tool for the command
list and each command's arguments.

## Settings

No module-specific settings. Existing project and layer selection apply.

## Events

The chassis publishes map changes after storage commands. Workflow declares
no event handler; call transport is kept in nonce records.

## Sync and async

All verbs are synchronous short operations; the MCP server runs them through
its standard worker-thread path. Parallel work is handed to independent agents.

## Layers

The caller chooses ordinary knowledge layers. Newly created layers are mutable,
hideable and ready; existing layers retain their lifecycle. Logic is attached
as native layer items with four-field callable records. The module's version-1
`logic_versions` table lives beside the metaform, keyed by `(logic_id, number)`,
and holds name and exact content. Native item deletion removes its history.

## Lifecycle and cleanup

No start/stop hooks or spawned tasks. Storage survives unload. Each completed
call closes its nonce; closed numbers stay reserved by the nonce service.

## Modules relied on

Logic reads use the public DAO. Element values include the memory module's
existing public node projection, as the MAP-057 binding already provides.
The chassis and MCP module expose the declared verbs.

## Systems supported

Linux, macOS and Windows, using Python, SQLite and the public nonce service.

## Resources owned

Packaged prompts, layer records, the declared history table and requested
nonces. Export writes only the named destination. No agent process or server
is started by workflow.

## Installed and direct wheel

Resources load through `importlib.resources`; storage uses the normal Metaform
home and selected project's DAO in either packaging form.

## Demonstration

Submit a workflow element and a named Axiom subroutine, then run its call and
redeem the returned nonce. Complete with its RETURN expression; the examples
under Verbs show same-agent calls, fresh-agent calls and portable export.
