# Metaform workflow prompts

Two prompts make workflows. **workflow-authoring** writes one from a goal. **workflow-ingest** turns an existing prompt or workflow into one. Each prompt is one instruction in two pieces: the shared sections it pins, which the agent reads first, and its own task. The agent gets the whole instruction. The split only decides where each part is kept and versioned.

## Why it is split

| Reason | What it saves |
| --- | --- |
| Both prompts need the Axiom language, the system description and the workflow rules word for word. | One copy instead of two that drift apart. |
| The tools section changes every time a `<<TO FILL>>` tool is built. | Building a tool means one new section version and a pin moved in each prompt; the prompts' text does not change. |
| A future prompt (a refinement run, element-logic authoring) needs the same language and system. | It pins the sections instead of copying them. |

The cost is a few reads at the start of each run, with the `metaform` tool the agent already needs for its work.

## Files

| File | Version | What it is |
| --- | --- | --- |
| `metaform-shared-sections.md` | each section versioned on its own | The six shared sections, below |
| `workflow-authoring.md` | 1.4 | Writes a workflow from a goal |
| `workflow-ingest.md` | 1.7 | Turns an existing prompt or workflow into a workflow |
| `Metaform_Axiom-OS.md` | 1.1 | The compiler |
| `prompt-delexicalization.md` | 1.3 | Standalone delexicalization |
| `Intake_2.1.md` | 2.1 | Builds the metaform |

## Shared sections

| Section | Version | Holds | Pinned by | Changes when |
| --- | --- | --- | --- | --- |
| `axiom-language` | 1 | Modules, operators, subroutines, `this`, control flow, errors, three examples | authoring, ingest | The language grows |
| `metaform-system` | 1 | The map, roles, joins, knowledge layers, element logic and every `this` value, the user | authoring, ingest | The system's model changes |
| `namespace-rules` | 1 | Addressing rules and the reference examples | authoring, ingest | Rarely |
| `workflow-logic` | 1 | Workflow elements, the logic record, the rules every workflow follows, handoffs, returns, storage | authoring, ingest | A workflow rule changes |
| `metaform-tools` | 1 | Built tools and `<<TO FILL>>` tools | authoring, ingest | A tool is built or changes |
| `delexicalization-rules` | 1 | Turning named elements into `{Element_A}` placeholders | ingest | Rarely |

## Set up on MCP

The agent that runs a workflow prompt needs the Metaform MCP server connected, for the `metaform` and `map` tools.

1. **Save each shared section as a prompt.**
   - No MCP tool saves a prompt today. Save through the web GUI's prompt save (its `/api/save-prompt` write: name, text, parent).
   - **Name:** the section name exactly, such as `axiom-language`.
   - **Text:** everything below the section's `=== <name> · version N ===` line, up to the next `===` line. Leave the header line out; the store keeps the version.
   - **Parent:** none for a first save. If you already saved an earlier draft under the same name, save this as its next version with that draft as parent, and move the pins to match.
2. **Check the version numbers.** List prompts (`metaform prompts`). Each section should be at version 1. If the store numbered one differently, change that pin in `{SHARED}` in both prompts, and the table at the top of the shared file.
3. **Save the two workflow prompts** the same way, as `workflow-authoring` and `workflow-ingest`.
4. **Confirm an agent can read them.** `metaform prompt axiom-language 1` should return the section text.
5. **Run a workflow prompt.** Give the agent the prompt and its inputs:
   - **Authoring:** the goal, the run's arguments if any, and the knowledge layer to write the workflow into.
   - **Ingest:** the prompt or workflow text, and the knowledge layer to write it into.

## Versioning rules

1. **A changed section is a new version.** Save it with the current version as its parent. Earlier versions stay.
2. **A prompt reads only the versions it pins.** Saving a new section version changes nothing until a prompt's pin moves.
3. **Moving a pin changes the prompt.** Bump the prompt's own version in its header and save it as a new version.
4. **Keep the shared file's table matching the store.**

## Tools not built yet

These are marked `<<TO FILL>>` in `metaform-tools`. The prompts tell the agent never to invent a command for one, and to stop that step and ask you if it needs one. When a tool exists, replace its `<<TO FILL: ...>>` text with the command and its arguments, save `metaform-tools` as a new version, and move the pins.

| Tool | Used by | What it must do | Depends on |
| --- | --- | --- | --- |
| list layers | authoring: Orient | List the knowledge layers this metaform has. | Layer reads (LAYER) |
| list workflows | authoring: Orient | List workflow elements and their logic requirements' names. | `workflow` root and `logic` records |
| submit workflow | authoring, ingest: Submit | Record a workflow element at an address, in a given knowledge layer (created if it does not exist), with its canonical name and the knowledge layers selected to go with it. | `workflow` root (MAP-055); where a workflow element keeps its selected layers is still to build |
| submit logic | authoring, ingest: Submit | Record one logic requirement, name and Axiom content, on a workflow element. The system assigns `logic_id`. | `logic` record type (MAP-056, BASE-051, MAP-003) |
| submit element logic | authoring: Submit | Record a named logic join on a project element, in a given knowledge layer. | Logic joins on elements (MAP-056) |
| export workflow | authoring, ingest: Submit | Write `<workflow name>.metaform` from the stored workflow. | BASE-051 |
| run | authoring: Start | Hand an entry call to the executor. | The executor: Choice, Parallel, Map, Retry, Catch, error propagation |
| handoff | both: HANDOFF condition | Issue a nonce for a handed-off call, let a fresh agent redeem it, and bring its RETURN back. | Nonce redemption over MCP (MCP-030); host check for agent-to-agent (MCP-028) |

## Commands to verify

These are filled in from the spec and the codebase's own answers. Check them against what is built.

- `metaform prompt <name> <version>` and `metaform prompts`. The codebase reported a `metaform` tool with `prompts` (list) and `prompt <name> [<version>]` (read); the command form is my reading. Every run depends on these, so check them first.
- `metaform map ask`, `tell` and `messages` (MAP-050). MAP-050 also describes an earlier form, a work record with condition `question`. If that form is the one built, change the ask line.
- `metaform map where <address>` (MAP-048). The spec names the read `where`. The exact command form is a reading of the spec.

## Decisions not yet confirmed

These came from workflow-authoring v1.3. Moving some of them into shared sections makes them bind ingest too, so the "Applies to" column matters.

| Decision | Where it lives now | Applies to |
| --- | --- | --- |
| A loop that runs out of attempts RETURNs a failure value, such as `( FALSE, {issues} )`, instead of raising an error. | workflow-logic | authoring, ingest |
| A Catch handler's RETURN goes to the caller of the subroutine that failed, in place of its result. | workflow-logic | authoring, ingest |
| Errors are named in UpperCamelCase and listed in each subroutine's `+> Raises:` line. `[any]` matches every error. A missing key raises `KeyError`. | axiom-language | authoring, ingest |
| `YIELD` returns to the router, so the stages run in sequence. | axiom-language | authoring, ingest |
| A script with one pipeline may route without `@MATCH`. | axiom-language | authoring, ingest |
| A subroutine that receives `None` uses its PARAM default. With no default, the call fails. | workflow-authoring | authoring |
| Element logic goes in the layer the goal names, or else the layer that holds the workflow, so turning that layer off also turns the element logic off. | workflow-authoring | authoring |

## Changes from workflow-authoring v1.3

- **Knowledge layers.** "Workflow-owned layer" is gone. A workflow is written into a knowledge layer given as `{Target_Layer}`; "workflow layer" just means a knowledge layer that holds a workflow. Knowledge layers that go with a workflow are *selected*, if any, not *included*.
- **Roots.** `workflow` is described as existing only in knowledge layers, matching `namespace-rules`.
- **CQU.** Worded as you defined it: the explicit receiver which benefits from and drives the improvements on the artifact.
- **Tools.** Added `metaform prompt` and `metaform prompts` (built, needed to read the sections) and `export workflow` (to build, for the `.metaform` file).
- **Ingest.** Now reads the same language, system and workflow rules as authoring. Its `Raises:` lines list only errors the workflow states, so ingest still adds nothing the text doesn't say.

## Same text in two places

- `axiom-language` extends the syntax in Metaform Axiom-OS 1.1. Control flow, errors, `this`, `YIELD`, `RECURSE` and `APPLY` are defined only in the section. The next compiler version should take `axiom-language` as its reference, so every compiled script shares one definition.
- `namespace-rules` is taken from Intake 2.1, plus the knowledge-layer root rule. Intake 2.1 still carries its own copy; pointing it at the shared section is your call, since it is tested as it stands.
- `delexicalization-rules` matches the constraints of prompt-delexicalization 1.3.
