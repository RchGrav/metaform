# Intake calls

[Documentation](../README.md) · [Reading a metaform](../guides/reading-a-metaform.md) · [Working with Metaform](../guides/working-with-metaform.md)

An intake is the first analysis of a project. An agent reads the project, follows the intake procedure, and records the project's functional map, its elements and the purpose joins between them, one object at a time through the `intake` tool on the Metaform MCP server. This page lists every call the intake uses, what each field means, and how the calls are written inside an Axiom script.

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

Every Metaform tool takes the same three fields: `command`, `arguments` and `help`. The notation maps onto them directly.

```
mcp.metaform.intake.element( namespace_address="downstream.cqu.engineer.context", role="CQU" )
```

is sent as:

```json
{
  "method": "tools/call",
  "params": {
    "name": "intake",
    "arguments": {
      "command": "element",
      "arguments": {
        "namespace_address": "downstream.cqu.engineer.context",
        "role": "CQU"
      }
    }
  }
}
```

In Claude Code the same tool appears as `mcp__metaform__intake`, with the input `{"command": "element", "arguments": {...}}`. Sending `help` with a command name returns that command's fields instead of running it.

Two protocol methods are not tool calls and have their own forms:

| Notation | Protocol method |
|---|---|
| `mcp.metaform.resource( uri="metaform://intake/schema" )` | `resources/read` |
| `mcp.metaform.prompt( name="intake" )` | `prompts/get` |

### Types come from the tool's schema

A script never states a field's type, its allowed values or whether it is optional. The agent reads those from the tool's schema when it makes the call. Restating them in a script makes a second copy that drifts from the tool.

What a script does state is meaning the procedure owns: the role terms and their definitions, conventions such as `refs` with the key `path` for a member's location, and rules such as recording one object per call.

### Writing calls in an Axiom script

A script binds each call to a short name once, at the top, and uses the name in its steps:

```
@RECORD:
  START    := mcp.metaform.intake.start
  ELEMENT  := mcp.metaform.intake.element
  JOIN     := mcp.metaform.intake.join
  READBACK := mcp.metaform.intake.show
  FINISH   := mcp.metaform.intake.finish
```

```
  ELEMENT( namespace_address={CQU_Base}.<cqu type>, role=CQU )
  JOIN( receiver={CQU address}, elements=[DE address],
        purpose=the CQU's OP, ef=the DE's EF for this encounter, ifd=... )
```

The binding block lists every tool the script depends on in one place, and a renamed tool changes one line. The agent running the script makes each real call. Nothing in Metaform parses the script.

A field that holds several values is a list, `elements=[...]`. A field that holds structured data takes objects, `refs=[{"key": "path", "value": "src/timer.py"}]`. A variable in braces, `{Task}`, is a value of the script, and a quoted-key object, `{"key": ...}`, is data.

## Order of calls

1. `intake.prompt` and `intake.schema`: read the procedure and the shape of the map.
2. `intake.start`: open the intake.
3. `intake.element` and `intake.join`, as each object is reasoned, one object per call. The map is never held back and recorded at the end.
4. `intake.show`: read back what was recorded and correct it with `intake.element`, `intake.join` or `intake.remove`.
5. `intake.finish`: finish and make the recorded metaform the active one.

## Reference

### intake.prompt

```
mcp.metaform.intake.prompt( text )
```

Returns the intake procedure for this project, with the procedure's prompt slot filled.

| Field | Meaning |
|---|---|
| `text` | The path to the target of the intake. Left out, the target is this project. |

The same text is served as the resource `metaform://intake/procedure`. Subagents and some hosts cannot read MCP resources, so the command is the form to use when handing the procedure to another agent.

### intake.schema

```
mcp.metaform.intake.schema()
```

Returns the shape of the metaform: the namespace roots, the upstream and downstream links, and the element and join forms the intake records. The same text is served as the resource `metaform://intake/schema`.

### intake.start

```
mcp.metaform.intake.start( model, role )
```

Opens the intake, or resumes the one being recorded. When the active metaform already has an intake, a separate metaform named `intake-<UTC timestamp>` is created and the earlier one is kept untouched. Returns the new metaform's name. An open web view follows the intake live.

| Field | Meaning |
|---|---|
| `model` | The model performing the intake. Recorded on the intake layer, so a later reader knows which model produced the map. |
| `role` | The role of the agent performing it. |

### intake.element

```
mcp.metaform.intake.element( namespace_address, name_length, name, role, refs, within, condition, note )
```

Records one element, or records it again. Fields given replace the ones the element had; fields left out are kept.

| Field | Meaning |
|---|---|
| `namespace_address` | The element's dotted address, formed as the intake procedure describes, such as `code.timer.kitchen`, or `core` for the core element. |
| `name_length` | How many of the address's last segments form the element's name, counted from 1. |
| `name` | The element's name as the project calls it. |
| `role` | AUE, CQU, DE, SE or NE, as the intake procedure defines them. The core element has none. |
| `refs` | Where the element is found: a list of references, each a key and a value, such as `path` and `src/timer.py`. Stored in the `sources` layer. |
| `within` | The address of the element that holds this one, or `core`. |
| `condition` | The part's state: `unbuilt`, `under-construction`, `built` or `broken`. Left out when the state is not in question. Any other word is refused before anything is recorded. |
| `note` | Free text kept with the element. An exclusion is a note that starts with `exclude:`. |

### intake.join

```
mcp.metaform.intake.join( receiver, elements, purpose, ef, ifd, refs, condition, note )
```

Records one purpose join: the receiver's purpose, served by the elements the join holds. Recorded again with an element it already holds, the fields given replace its own and new elements are added. A part folded into its parent during annealing is recorded as a join one level deeper, with the element it is part of as the receiver.

| Field | Meaning |
|---|---|
| `receiver` | The address of the receiving element, the RE, whose purpose the join records. |
| `elements` | The addresses of the providing elements, the PEs, that serve the receiver's purpose. |
| `purpose` | The receiver's operative purpose, the OP. |
| `ef` | The encounter function, the EF: what the providing elements do for the receiver, in active voice. |
| `ifd` | The information flow direction: `sends`, `receives` or `both`. |
| `refs` | Where the join is found: a list of references, each a key and a value. |
| `condition` | As for `intake.element`. |
| `note` | Free text kept with the join. |

### intake.show

```
mcp.metaform.intake.show( receiver )
```

Returns the intake being recorded: every element with its fields, `within`, refs, open condition and note, every join with the elements it holds, the root, and the elements that are disconnected or never described.

| Field | Meaning |
|---|---|
| `receiver` | Limits the result to one receiver's joins and the elements they hold. Left out, the whole intake is returned. |

### intake.remove

```
mcp.metaform.intake.remove( receiver, provider, namespace_address )
```

Removes one recorded object while the intake is open. The fields given decide what is removed:

| Fields given | What is removed |
|---|---|
| `namespace_address` | The element. The joins that held it let it go, and its open marks are closed. |
| `receiver` and `provider` | The join of that receiver holding that element. |
| `receiver`, `provider` and `namespace_address` | The element at `namespace_address`, taken out of that join only. |

### intake.finish

```
mcp.metaform.intake.finish( report, feedback )
```

Finishes the intake and makes the recorded metaform the active one, keeping the earlier one whole. `metaform map activate <previous-name>` switches back. After `finish`, the metaform changes only by refinement, `metaform map refine`.

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
