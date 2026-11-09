# P1: Sources and authority

**Status:** Panel conclusions. Owner acceptance is not established.

## Relies on

Nothing earlier. P1 is the first panel.

## Sources read directly

| Source | Authority (cited) |
|---|---|
| `docs/world-ideas.md` | "Nothing here is decided, and nothing here is part of `TOPOGEE-SPEC.md`." Owner ideas and agent suggestions are kept apart. |
| `TOPOGEE-SPEC.md` | The build specification. Statuses: Decided, Proposed by the owner, Proposed, Open (lines 9–17). Implementation status is separate. |
| `DECISIONS.md` | Owner decisions. Current owner decisions take precedence over the spec (`CLAUDE.md`). |
| `docs/designs/metaform-server-design.md` | Design of the map server. Rejects Alternative C. |
| `TOPOGEE.md` | Opening statement. Older than the spec in places (see C-2). |
| `mcp-server/src/` | Implemented contract. Node. |
| `metaform.schema.json`, intake schemas | Protected. No edits from this roundtable (`AGENTS.md`). |

## Rule: track each source claim as decided or proposed (Sol, agreed)

- A claim from world-ideas is never a decision. Cite it as "owner idea" or "agent suggestion".
- A spec requirement keeps its own status. R-4.6 (Node map server) is Proposed.
- An agent suggestion the owner has not accepted stays Proposed. Example: "a contraption's busstone links can be read as wants."

## Field-name crosswalk (Astra T64, T81; Fable T65; Astra source check after T85)

| Concept (intake term) | Spec R-3.4 / R-3.6 | Schema and code (`metaform.schema.json`, `mcp-server/src/commands.ts:39`) |
|---|---|---|
| OP, Operative Purpose | `why` | `goal` |
| EF, Encounter Function | `how` | `function` |
| IFD, Information Flow Direction | `intent` | `intent` |

| Flow relative to the element holding the want | Spec R-3.6 | Current schema |
|---|---|---|
| Receives the satisfying substance | `inbound` | `receive` |
| Sends the satisfying substance | `outbound` | `send` |
| Both directions | `two-way` | `send_receive` |

- R-3.4 status (`TOPOGEE-SPEC.md:111`): "The store and the form still use the earlier names until the code changes."
- R-3.6 new intent values (`TOPOGEE-SPEC.md:170`): "Not built."
- Current field names match the documented interim contract (`mcp-server/src/commands.ts:39`, `mcp-server/src/store.ts:14`, `metaform.schema.json:253`). See C-1.
- This source check establishes vocabulary. It does not establish runtime correctness or acceptance of a migration.
- The crosswalk preserves the intake concepts. `Intake.xml:14` defines OP as "The **why**"; `Intake.xml:15` defines EF as "The **how** of what is delivered."
- Intent excludes the request (`metaform.schema.json:255`, R-3.6). The receiver owns the want (R-3.5).
- Reports distinguish specified names from implemented names. The source check did not edit schemas, prompts or code.

## Scope evidence

`docs/world-ideas.md:87` states: "Metaform is not a system for making games. Making them is one thing it can do".
This is recorded owner context within a brainstorm. It supports judging non-world projects without promoting the brainstorm into requirements.

## Decisions Made

1. Each source claim carries decided or proposed status. World-ideas content is never decided.
2. Reports use schema names (`goal`, `function`, `intent`) and give the spec names in the crosswalk.
3. Protected schemas stay unedited.
4. C-1 is recorded as a documented transition.

## Open Questions Handed Forward

| Question | Decision trigger |
|---|---|
| When do the store and form adopt `why`, `how` and the new intent values? | Direct owner authorization for implementation, followed by compatibility checks. R-3.4 records the intended transition. |
| The owner's control scheme is unrecorded (world-ideas, Agents). | The owner records it. |
