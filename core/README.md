# Metaform, archive of 2026-11-15

This folder is one version of Metaform: the specification, the tool, and the files the tool is built from. It was prepared on 2026-11-15 from the repository folder `/home/rich/metaform`, branch `fable-climb`, commit `1798c6e`.

## Read in this order

1. [SPECIFICATION.md](SPECIFICATION.md) is the one specification. It says what Metaform is, how the one tool works, and what is built, decided or open.
2. [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) says what this folder holds and where each file came from. It also says what was left out and why, and how to build and test the tool.

## What is here

| Path | What it is |
|---|---|
| `SPECIFICATION.md` | The specification. It governs where any other file here disagrees with it. |
| `PROJECT_CONTEXT.md` | The inventory and the record of how this folder was prepared. |
| `MANIFEST.sha256` | A SHA-256 checksum for every other file in this folder. |
| `metaform/rust/` | The tool: a Cargo workspace of four crates. Copied unchanged. |
| `metaform/intake/procedure/` | The whole intake procedure, one Markdown file for each section. The build compiles this folder into the server. Copied unchanged. |
| `metaform/metaform.schema.json` | The schema of the stored form of a map. |
| `metaform/mcp-tools.proposed.json` | The contract that the server checks every command against. |
| `metaform/mcp-tool.published.json` | The short definition of the tool that the server publishes to agents. |
| `metaform/tool-help.json` | What `{"help": "<command>"}` returns. |
| `metaform/tool-examples.json` | The founder's examples of commands and answers. |
| `metaform/intake-example.json`, `metaform/metaform-canonical.json` | Two stored maps that the tests read. They are test data. |
| `founder/intake_best.xml` | The founder's working copy of the intake procedure, in XML. The tool does not read it. |
| `guidance/` | The rules that agents follow when they work on Metaform: `CLAUDE.md`, `TASTE.md` and `EXPECTATIONS.md`. |

## Check the folder

```sh
sha256sum --check --quiet MANIFEST.sha256
```

The command prints nothing when every file matches its checksum.

## Build and test the tool

```sh
cd metaform/rust
cargo build --release -p metaform-server
METAFORM_LAUNCHER= cargo test
```

`PROJECT_CONTEXT.md` states what these commands need and what the tests showed on 2026-11-15.
