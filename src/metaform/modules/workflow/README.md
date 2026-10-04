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

## Prompts

`resources/prompts.xml` holds the authored workflow-authoring and workflow-ingest
prompts, their six shared sections, module instructions and call/handoff
transport instructions. Serving a workflow prompt or call registers its
shipped prompts lazily. Pins follow the deployed shared-section versions;
previous prompt versions remain available.

## Verbs

Read the authoring or ingest prompt with its inputs:

```sh
metaform enable workflow
metaform workflow author "Improve code quality" procedures
metaform workflow ingest "<existing prompt, verbatim>" procedures
```

Read the prompt-lexicalization script with a prompt to lexicalize, LAYER-017:

```sh
metaform workflow lexicalize "<prompt or workflow, verbatim>"
```

Its inputs fill the script's owner placeholders. `MAP_READ` is the `where`
read. `UNRESOLVED_POLICY` is the setting `lexicalize_unresolved`, `keep
wording` until set, and `ADDRESS_PLACEMENT` is `lexicalize_addresses`, `one
block of name -> address` until set. `PROMPT_STORE` is null because no
command saves a prompt yet, so the script halts and names it.

The module ships the latest authored prompts and their pinned shared sections
to the versioned prompt store. The tools section supplies the implemented
commands. Authoring and ingest submit the same stored shape:

```sh
metaform workflow submit workflow.quality.code procedures name="Code quality"
metaform workflow logic workflow.quality.code procedures review "<Axiom content>"
metaform workflow list
```

`provenance=` accepts the producing prompt, model and role. A workflow may
share its knowledge layer with other knowledge. `selected=` lists knowledge
layers that accompany a workflow's calls. Existing layer lifecycle, selection,
masking and hiding apply. The `logic` command also attaches a named subroutine
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
