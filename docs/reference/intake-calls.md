# Intake calls

[Documentation](../README.md) · [Reading a metaform](../guides/reading-a-metaform.md) · [Working with Metaform](../guides/working-with-metaform.md)

An intake is an assigned task for analyzing a project. An agent reads its instructions, examines the project, and records the project's functional map through the intake tools on the Metaform MCP server. This page lists those calls and their fields. The task's instructions are editable text.

## Call notation

A call is written as the server, the tool and the command, followed by its fields as keyword arguments:

```
mcp.<server>.<tool>.<command>( field=value, ... )
```

| Segment | Meaning |
|---|---|
| `mcp` | An MCP call. `mcp` is not a namespace root, so the form never collides with a logic address such as `logic.workflow.quality.code.review(...)`. |
| `<server>` | The MCP server, here `metaform`. |
| `<tool>` | The tool on that server, such as `intake`. |
| `<command>` | The tool's command, such as `element`. |
| `( ... )` | The command's fields. |

The protocol method, `tools/call`, is the same for every tool call and is left out of the notation.

### What the notation sends

The dotted notation is documentation shorthand. Each intake command is an MCP tool named `intake_<command>`, with its fields passed directly as the tool's arguments.

```
mcp.metaform.intake.element( namespace_address="downstream.cqu.engineer.context", role="CQU" )
```

is sent as:

```json
{
  "method": "tools/call",
  "params": {
    "name": "intake_element",
    "arguments": {
      "namespace_address": "downstream.cqu.engineer.context",
      "role": "CQU"
    }
  }
}
```

A host may prefix the tool name, for example `mcp__metaform__intake_element`. Use the tool name or catalog route advertised by that host. The tool's input schema describes its fields.

Two protocol methods are not tool calls and have their own forms:

| Notation | Protocol method |
|---|---|
| `mcp.metaform.resource( uri="metaform://intake/schema" )` | `resources/read` |
| `mcp.metaform.prompt( name="intake" )` | `prompts/get` |

### Types come from the tool's schema

The tool's schema describes each field's type, allowed values and optionality. The agent reads those when making a call.

The task instructions describe the requested analysis, terminology and working method.

### Reading and assigning the task

Read or assign the named intake task:

```bash
metaform tasks read name=intake
metaform tasks assign name=intake text="Map the current project."
```

Over MCP, use `tasks_read` or `tasks_assign` with `name="intake"`. Assignment keeps the selected instructions and the supplied assignment input separately. The assigned agent follows the instructions and makes the tool calls.

The default source is `intake/resources/intake.xml`. Its extension describes the authored file. The runtime reads it as opaque UTF-8 text, with no required tags, headings or method phases. Only the declared common task bindings apply: `{project}` and, when supplied, `{name variable}`. Markdown, plain prose and unfinished markup are otherwise delivered as written. Task reads and `intake prompt` use the same selected prompt version, and edits to the instructions are retained.

A field that holds several values is a list, `elements=[...]`. A field that holds structured data takes objects, `refs=[{"key": "path", "value": "src/timer.py"}]`.

## Order of calls

1. `tasks.read name=intake` and `intake.schema`: read the assigned instructions and the shape of the map. `intake.prompt` also returns those instructions.
2. `intake.start`: open the intake.
3. `intake.element` and `intake.purpose`, as each object is reasoned, one object per call. The map is never held back and recorded at the end.
4. `intake.show`: read back what was recorded and correct it with `intake.element`, `intake.purpose` or `intake.remove`.
5. `intake.finish`: finish and make the recorded metaform the active one.

## Reference

### intake.prompt

```
mcp.metaform.intake.prompt( text, mode )
```

Returns the effective intake task instructions with the declared project binding applied. A nonempty request follows the complete instruction text under `## Intake request`, with two newlines before the heading, two after it, and a final newline after the request. Existing trailing newlines are preserved. Request text is literal, and strings such as `{prompt}` in the instructions are left untouched.

| Field | Meaning |
|---|---|
| `text` | The target or task for the intake. Left out, the target is this project. |
| `mode` | Optional `fresh`, `refine` or `resume`. A dispatched intake retains its launch mode when it rereads the procedure. |

The same instructions are available through `tasks read name=intake`, `metaform://tasks/definitions/intake` and `metaform://intake/procedure`.

Set `--intake-file=<path>` to use any UTF-8 instruction file. Its contents and selected prompt edits are shared by task reads, task assignments and `intake prompt`. The runtime does not interpret its filename or markup as a procedure contract. The separate schema remains available through `intake schema`.

### intake.schema

```
mcp.metaform.intake.schema()
```

Returns `resources/metaform.xml`: the namespace roots, the upstream and downstream links, and the element and purpose record forms the intake records. The same XML is served as the resource `metaform://intake/schema`.

### intake.start

```
mcp.metaform.intake.start( model, role )
```

Opens the intake, or resumes the one being recorded. On a project whose intake is finished it stays on that map: refs recorded on its elements and purpose records are written onto it, and recording a new element or purpose record opens a separate metaform named `intake-<UTC timestamp>`, keeping the earlier one untouched. Returns the metaform's name. An open web view follows the intake live.

| Field | Meaning |
|---|---|
| `model` | The model performing the intake. Recorded on the intake layer, so a later reader knows which model produced the map. |
| `role` | The role of the agent performing it. |

### intake.element

```
mcp.metaform.intake.element( namespace_address, name_length, name, role, block, within, refs )
```

Records one element, or records it again. Fields given replace the ones the element had; fields left out are kept.

| Field | Meaning |
|---|---|
| `namespace_address` | The element's dotted address, formed as the intake procedure describes, such as `code.timer.kitchen`. |
| `name_length` | How many of the address's last segments form the element's name, counted from 1. |
| `name` | The element's name as the project calls it. |
| `role` | CQU, DE, SE or NE, as the intake procedure defines them. The artifact under examination is not an element; its DE stands for it, MAP-042. |
| `block` | Optional numbered ICE block identifier, such as `BLOCK_001`, stored as native element metadata. |
| `within` | Optional namespace address of the element containing this element, stored as native element metadata. |
| `refs` | Where the element is found: a list of references, each a key and a value, such as `path` and `src/timer.py`. Stored in the `sources` layer. |

For `block` and `within`, an omitted field preserves its recorded value, a string assigns it, and explicit JSON `null` clears it. On the CLI these fields take JSON values, so retain the double quotes around a string inside shell quotes:

```bash
metaform intake element code.alarm.audible 'block="BLOCK_001"' 'within="code.timer.kitchen"'
metaform intake element code.alarm.audible block=null within=null
```

`map refine` accepts the same fields and null semantics. Native element reads, `map where` and XML output retain this metadata. Recording it creates no knowledge layer, critic note or repair ticket.

### intake.purpose

```
mcp.metaform.intake.purpose( receiver, elements, purpose, ef, ifd, refs )
```

Records one purpose record: the receiver's purpose, served by the elements the purpose record holds. Recorded again with an element it already holds, the fields given replace its own and new elements are added. A part folded into its parent during annealing is an ordinary element held by a purpose record one level deeper, with the element it is part of as the receiver.

| Field | Meaning |
|---|---|
| `receiver` | The address of the receiving element, the RE, that holds the purpose record. |
| `elements` | The addresses of the providing elements, the PEs, that serve the receiver's purpose. |
| `purpose` | The receiver's operative purpose, the OP. |
| `ef` | The encounter function, the EF: what the providing elements do for the receiver, in active voice. |
| `ifd` | The information flow direction: `sends`, `receives` or `both`. |
| `refs` | Where the purpose record is found: a list of references, each a key and a value. |

### intake.show

```
mcp.metaform.intake.show( receiver )
```

Returns the intake being recorded, or the finished map when none is: every element with its fields and refs, every purpose record with the elements it holds and its refs under `purposes`, the CQUs whose root purpose records the map comes off as `roots`, the elements no root purpose record reaches as `disconnected`, and the addresses never described. An element includes `block` and `within` only when their values are set.

| Field | Meaning |
|---|---|
| `receiver` | Limits the result to one receiver's purpose records and the elements they hold. Left out, the whole intake is returned. |

### intake.remove

```
mcp.metaform.intake.remove( receiver, provider, namespace_address )
```

Removes one recorded object while the intake is open. The fields given decide what is removed:

| Fields given | What is removed |
|---|---|
| `namespace_address` | The element. The purpose records that held it let it go, and its open marks are closed. |
| `receiver` and `provider` | The purpose record of that receiver holding that element. |
| `receiver`, `provider` and `namespace_address` | The element at `namespace_address`, taken out of that purpose record only. |

### intake.finish

```
mcp.metaform.intake.finish( report, feedback )
```

Finishes the intake and makes the recorded metaform the active one, keeping the earlier one whole. The result counts the recorded elements as `elements` and purpose records as `purposes`. `metaform map activate <previous-name>` switches back. After `finish`, the metaform changes by refinement, `metaform map refine`, or by another intake, which writes refs onto it and opens a new metaform only for new shape.

| Field | Meaning |
|---|---|
| `report` | The report on the project examined: what is broken, what needs fixing, what does not work or works only in part. |
| `feedback` | Feedback on the intake process itself: unclear terms, a tool that did not match its schema, where the agent got stuck. |

### intake.status

```
mcp.metaform.intake.status()
```

Returns whether the project has an intake and whether one is being recorded. The intake procedure does not use it. It is for the agent that starts the intake, to check whether one exists or was left unfinished.

## Calls around the intake

A first run in a new folder uses two more calls before the intake starts:

```
mcp.metaform.metaform.register( id )
mcp.metaform.web.start()
```

| Call | What it does |
|---|---|
| `metaform.register` | Registers this folder as a project. `id` defaults to the folder's name. Returns the instructions for the newly registered folder. |
| `web.start` | Starts the browser view on this machine and returns its address, so the person can watch the intake as it is recorded. |
