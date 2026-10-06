# Implementing the knowledge module in metaform

For the agents building the system. The spec is the authority; record IDs are cited so you can check each
step against it. Where this kit's code assumes a signature, the record wins.

## What this is

Four reference libs and five task skills, served by the metaform MCP server so every agent in every host
gets the same text, loads each lib once, and can be handed a skill as a task.

```
libs/        lib_axiom, lib_metaform, lib_workflow, lib_quality
sources/     workflow-authoring v1.4 and workflow-ingest v1.7, the procedures folded into the write and import skills
skills/      scan, write_workflow, import_workflow, workflow_efficiency, prompt_efficiency
module/knowledge/   __init__.py (MODULE declaration), resources/prompts.xml, tests/
server.py    the same tools as a standalone MCP server, for a host without metaform
```

A lib is the shared text no skill should repeat: the grammar, the system, the rules, the quality bar. It is
loaded once per agent; its first line is its marker (`# lib_axiom · ...`). A skill is the playbook for one
task: its procedure, its checks, and the examples of that task (naming a workflow and its subroutines, a
subroutine with PARAM, acceptance, Retry, Catch and RETURN, logic linked at an element with `target=this`, a
Map, a Parallel fan-out with a merge, a handoff by nonce). A skill's `# requires:` line names its libs, and
the rule every skill carries is: call `lib` only for a name whose marker is not already in your context.

| skill | requires |
|---|---|
| scan | nothing |
| write_workflow | lib_axiom, lib_metaform, lib_workflow |
| import_workflow | lib_axiom, lib_metaform, lib_workflow |
| workflow_efficiency | lib_axiom, lib_metaform, lib_workflow, lib_quality |
| prompt_efficiency | lib_axiom, lib_quality |

## Step 1. The module (BASE-035, BASE-015, BASE-019, BASE-037)

Place `module/knowledge/` at `src/metaform/modules/knowledge/`. It exports `MODULE`, a `Module` whose id
equals the folder name (BASE-037). `SUPPORTED_OS`, `DEPENDENCIES`, `SHIPS_DISABLED` are top-level literals in
`__init__.py`, read with `ast` before import (BASE-015). Add `README.md` and `CHANGELOG.md` per BASE-019 and
BASE-034's heading list.

Verbs (each becomes `metaform knowledge <verb>` on the CLI and a command of the `knowledge` tool over MCP):

| verb | nouns | returns |
|---|---|---|
| `lib` | name | the lib text, verbatim |
| `libs` | | the lib names with their first lines |
| `skill` | name | the skill's Axiom |
| `skills` | | the skills and what each requires |
| `scan` | workflow, task? | the scan skill with the text bound as `<<DATA>>` |
| `assign` | skill, input? | a nonce line `metaform <nonce>` for a fresh agent (see Step 4) |
| `complete` | | closes the assignment's nonce |

`__init__.py` is written to the `Module(id, summary, purpose, verbs=...)`, `Verb(name, run, summary, nouns=...)`,
`Noun(name, help, required=...)`, `Stop(message, next_step)` and `Context.nouns` shapes BASE-035 gives. Verify
each signature against the record; adjust the sketch, not the record.

## Step 2. The prompts (MCP-031)

Every text an agent reads is an element in `resources/prompts.xml`, named for it, read by name with
`metaform.prompt_files.text(...)`. The file in this kit holds: the module's `instructions` element (what the
server's instructions list under "modules available."), one element per lib, one per skill, and a
`<commands>` block. No prompt words in Python (MCP-031 acceptance: "No line of a prompt file's prompts appears
in any Python source outside tests").

To change a lib or a skill, edit `libs/` or `skills/` and regenerate `prompts.xml` (the libs and skills are the
source; the XML is built from them). Keep the marker as the first line of every lib.

## Step 3. Over MCP (CLI-037, MCP-003)

One tool per module: the host sees a tool named `knowledge` that takes `command` and `arguments`. A call with no
command lists the commands with one-line summaries; `help` with a command name returns its schema. Nothing to
build for this beyond the verbs: the chassis composes the tool from the declaration. An agent reads a lib as
tool `knowledge`, command `lib`, arguments `{name: lib_axiom}`.

## Step 4. Skills as tasks, system-wide (BASE-050, MCP-032)

Three ways to call a skill, one text:

1. **An agent calls it.** `knowledge skill write_workflow` returns the Axiom; the agent follows it, loading
   only the libs it is missing.
2. **A person runs it.** Each skill is a `<commands>` child in `prompts.xml`, so the server lists it as an MCP
   prompt and the host shows `/metaform:write_workflow` (MCP-032/033). Its text is the skill plus the lib rule.
3. **The orchestrator hands it to a fresh agent.** `knowledge assign write_workflow input='...'` requests a
   nonce from `metaform.nonce` (BASE-050) whose function is `assign` and whose value is the skill and input.
   The orchestrator passes the one line `metaform <nonce>` to a new agent; that agent runs it and receives
   the skill's required libs, the skill, and the input, with nothing else. `metaform <nonce> complete` closes
   it. This is the host-independent path: the agent needs no skill folder and no MCP registration beyond the
   `metaform` CLI, and the nonce record survives the session.

Nothing here is a workflow run: BASE-051's executor is Open, and the write and import skills say so. `assign`
hands a skill, not a workflow step; it uses only what BASE-050 says is built.

## Step 5. Tests (QUAL-006, QUAL-009, E4, QUAL-014)

`tests/test_knowledge.py` sketches three: every lib and skill is a prompt element (MCP-031), each skill is a
slash command (MCP-032), `assign` issues a nonce that serves the skill with its libs once and closes
(BASE-050). Each carries `@pytest.mark.req` and `@pytest.mark.kind("fixture")`. Write them against the real
loader and an isolated Metaform home, failing before the module exists. The `prompt_file` and `run` fixtures
are the chassis test helpers; use the names the test suite already has.

## Step 6. The standalone server (until the module is merged)

`server.py` serves the same prompts.xml over stdio with the MCP Python SDK (`pip install "mcp>=2"`): tools
`lib`, `libs`, `skill`, `skills`, `scan`; one MCP prompt per skill. Register with
`claude mcp add --transport stdio --scope user knowledge -- python /path/to/server.py` (the MCP-016 form). It
was exercised with a real stdio client: 5 tools, 5 prompts, libs returned verbatim. It has no `assign`; that
needs the chassis nonce service.

## What is in the libs, and what was left out

- `lib_axiom`: the grammar only: modules, operators, subroutines, control flow, errors (axiom-language v1,
  unchanged) and a note on which dialect applies where. No examples; those are in the skills.
- `lib_metaform`: metaform-system v1, namespace-rules v1, metaform-tools v1 whole, then the spec records that
  changed the shape after they were written (MAP-020/021/030 join shape, MAP-055/056/057 workflow root and
  `this`, LAYER-027, BASE-050 nonce API, BASE-051 what is unbuilt, D115 "add logic"), each as its Requirement
  line, with a four-line consequence note. The spec wins where they disagree (00-index).
- `lib_workflow`: workflow-logic v1 and delexicalization-rules v1 whole, plus what is built and unbuilt.
- `lib_quality`: the Axiom-OS 2.0 syntax rules and lint rules (what a linter checks), host honesty and
  tagging, the compile/lint/optimize command definitions, CLI-036, LAYER-021, BASE-051's amortization
  sentence, ENGINEERING_REGISTER v1.2.
- `sources/`: workflow-authoring v1.4 and workflow-ingest v1.7 unchanged, for provenance. Their procedures,
  conditions and checks are folded into `write_workflow` and `import_workflow`; their pinned `{SHARED}`
  names are inside the libs.
- Left out of the libs: the Axiom-OS TUI, job model and kernel; the intake result schema; the external link
  schemas; the chassis best-practices layer and plugin template. None is needed to write, import or judge a
  workflow. They are in the earlier archive's `sources/` if a lib for module authors is wanted later.

## Known conflicts to decide, not fixed here

1. The corpus join fields (`verb, non_goal, name, refs, parts`, subtype joins) vs MAP-020/021/030. The libs
   carry both and say the spec wins; `metaform-system` may deserve a version 2.
2. Two Axiom dialects. Your engines are v1 and would WARN under 2.0 lint L3/L9; the libs say which applies.
3. `metaform-tools`' `<<TO FILL>>` list is confirmed unbuilt (BASE-051). The skills stop and ask at those steps.
