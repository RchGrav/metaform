# Start here

This folder is the development copy of **Metaform**, the context tool for development agents. It also holds **Roundtable**, the multi-agent discussion tool written in Rust. Both were gathered from `~/topogee` and related folders on 2026-11-08. The sources were not changed.

Topogee, the shared world, is a separate project and is not copied here. Only the parts of it that explain Metaform are kept, under `context/`.

The owner is the person who directs this project. Documents under `metaform/` and `context/` call the same person "the founder".

## Read in this order

1. [OWNER_REVIEW_SPEC.md](OWNER_REVIEW_SPEC.md): what Metaform is meant to do, in plain English, with the owner's open questions.
2. [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md): for developers. It covers what was copied and from where, how the code is set up, which document governs what, and the known conflicts.
3. [metaform/README.md](metaform/README.md): the project's own README, unchanged.
4. [metaform/SPEC.md](metaform/SPEC.md): the specification the build follows (not yet reviewed by the owner).

Agents also load [CLAUDE.md](CLAUDE.md), which brings in [TASTE.md](TASTE.md) (how to write) and [EXPECTATIONS.md](EXPECTATIONS.md) (how to handle design gaps).

## Layout

| Path | What it is | Edit? |
|---|---|---|
| `metaform/` | Metaform's project folder: spec, intake procedure, schema, tool contract, the three forms (`rust/`, `node/`, `python/`), the graph workspace, the conformance set, tests | Yes, this is the working copy |
| `roundtable/` | Roundtable (Rust), the refined version from `~/topogee/roundtable` | Yes, this is the working copy |
| `TASTE.md`, `EXPECTATIONS.md` | Owner's writing and engineering guidance (copies of the current versions) | Owner's call |
| `CLAUDE.md` | Agent entry point written for this folder | Yes |
| `context/topogee-repo/` | Metaform-related files from `~/topogee`, at their original relative paths (decisions, owner statements, designs, reference evidence, experiments, agent definitions) | No, preserved evidence |
| `context/brain/` | The owner's personal source notes from `~/brain` | No, owner's originals |
| `context/roundtable-original-2026-11-05/` | The earlier standalone `~/roundtable` (Rust) with its reviews and proposals | No, history |
| `context/roundtable-runs/` | Output of the Elephant-Goldfish Model (EGM) layer runs on the Roundtable map | No |
| `context/claude-memory-topogee-sessions/` | Agent memory notes from the `~/topogee` sessions | No |
| `context/git-history/` | Exported git logs for the copied paths, and the repository state at copy time | No |
| `MANIFEST.sha256` | Checksums of every file at preparation time. `tools/verify_bootstrap.py` uses it to check that `context/` is unchanged. | No |
| `tools/verify_bootstrap.py` | Checks preserved hashes, that `context/` is unchanged, links and contract appendices | Yes |
| `.mcp.json`, `.codex/config.toml`, `.github/workflows/validate.yml` | MCP servers (`metaform`, `boat-docs`) and CI, carried over from the original repository | Yes |

## Checks

The full list, with what each check establishes, is in [metaform/README.md](metaform/README.md), "Checks". The shortest useful set:

```sh
python3 metaform/tests/check_contract.py
python3 metaform/tests/check_tool_input.py
python3 tools/verify_bootstrap.py
(cd metaform/rust && cargo build --release -p metaform-server -p metaform-web && METAFORM_LAUNCHER= cargo test)
python3 metaform/conformance/run.py --form rust   # then --form node, and --form python
```

The `metaform` MCP server in `.mcp.json` runs the Rust form's release binary, so build it before you start an agent here. After a rebuild, the server that is already running for a home still runs the old build until it is ended; the next agent that connects starts the new one.

## Path note

Documents inside `metaform/` refer to files such as `DECISIONS.md`, `TOPOGEE.md` and `docs/designs/storage.md` by their old repository paths. Those files are now under `context/topogee-repo/` at the same relative paths. For example, `docs/designs/storage.md` is `context/topogee-repo/docs/designs/storage.md`.
