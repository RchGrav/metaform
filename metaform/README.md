# Metaform

Metaform is a functional topology. It forms intake from intent, greenfield to brownfield, for any kind of project, code or not; it takes in a specification, refines and organizes it, and saves it in an improved form; it serves as a formboard that agents use to realign a code base that is hard to refactor; and it is a context management system inside any project (`SPEC.md`, section 1). Its maps chain: any element can own a deeper map (R-4.15). This folder is Metaform's own project inside this private repository. Metaform is tested and maintained here, used and refined for general development, and later replaces the earlier private `metaform` repository (`DECISIONS.md`, "Where Metaform lives").

The intake procedure and its semantics are proven over six months and many intakes. They are protected: do not edit them without the founder's direct instruction (`AGENTS.md`).

## What is here

| Path | What it is |
|---|---|
| [SPEC.md](SPEC.md) | The specification the build follows |
| [docs/documentation-set.md](docs/documentation-set.md) | The founder's documentation set: storage, namespace rules, fields and roles, layers, the stored and agent views, validation errors, the export report. Copied unchanged from the founder's folder, 2026-11-02 version. |
| [Intake.md](Intake.md) | The intake procedure, Digital Typology Intake 3.1 (protected) |
| [Intake.xml](Intake.xml), [intake.mmd](intake.mmd) | The older intake prompt and its diagram |
| [metaform.schema.json](metaform.schema.json) | The stored-document schema |
| [mcp-tools.proposed.json](mcp-tools.proposed.json) | The one tool's contract |
| [SPECIFICATION.md](SPECIFICATION.md) | The older draft, which still carries the contract appendix |
| `server/` | A Node test harness for the contract, built in minutes. It is not the design and never a source for it. The server is being built in Rust (`SPEC.md` R-4.6) from the founder's documentation set. |
| `tests/`, `verification/`, `tools/` | Contract tests, their results, and the Boat sandbox check |
| `agents/` | The founder's sources for the Metaform skill and the layer agent; the packaged copies are in `.claude/` |
| `docs/` | Designs, the preprint, concepts and proposals |

The intake prompts sit beside the schema and tool contract on purpose: `Intake.md` names them by relative path, so they move together.

## Checks

```
python3 metaform/tests/check_contract.py
python3 metaform/tests/check_tool_input.py
(cd metaform/server && npm test)
python3 tools/verify_bootstrap.py
```
