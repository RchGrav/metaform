# Map element `collection.workspace.shared`: shared workspace

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "shared workspace",
  "name_length": 2,
  "role": "SE",
  "uri": "README.md#2-participants-and-shared-workspace"
}
```

## What other parts rely on it for (their wants)
- `code.client.agent`: goal: Put every participant in the same working directory. Function: Supplies the directory passed as cwd on session/new. Intent: send
- `code.manager.chat.group`: goal: Produce the chair's deliverable, not a discussion summary. Function: Holds the artifacts the participants create and refine independently or together. Intent: receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "2 Participants and Shared Workspace",
      "4.4 Independent Work"
    ]
  }
]
```

## Layer `investigations`
```json
[
  {
    "topic": "concurrent edits",
    "note": "The spec gives every participant the same directory and names no edit-coordination mechanism. Roundtable 7 proposals discussed conflicting edits as a topic. Open gap for the build."
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Hold the real work: documents, designs and code the agents create and refine, alone or together.",
  "sources": [
    "README.md §2",
    "owner's evaluation specification: extra detail goes in files named with the agent's name"
  ],
  "built": "Every agent's session opens in the table's workspace folder; agents read and write each other's files there.",
  "gaps": [
    "Files are not checked by JEV; the owner accepted that on 2026-11-07."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Major, egm-codebase-details, edge cases): Workspace creation failure is ignored: 'let _ = create_dir_all' and a canonicalize fallback (engine.rs:402-404). No notice is raised; the failure surfaces only when session open fails.
- **GF2** (Major, egm-codebase-details, elephant.built): Write access depends on ScopePolicy over cfg.scope, which defaults to the workspace but is configurable (engine.rs:405-406; config.rs:144-146; tables.rs:137), and on the harness routing permissions via mode or env (config.rs:189-218); otherwise only a warning (engine.rs:992-995). Not documented.
- **GF3** (Major, egm-codebase-details, wants (code.client.agent)): Resumed seats pass the cwd via session/resume or session/load, not session/new (engine.rs:976-978; acp-host harness.rs:392-427).
- **GF4** (Nit, egm-codebase-details, missing detail): Relative paths resolve against the server cwd (tables.rs:132); the path is published in TableOpened (engine.rs:411); nothing prevents tables from sharing one folder.
- **GF5** (Nit, egm-codebase-details, properties.uri): The uri is a README anchor; the implementing code (config.rs:142-146; engine.rs:401-440, 949-997) is never named.
- **GF6** (Nit, egm-codebase-details, gaps): Not stated: tool activity sets worked_in_topic, which affects table ending and idle-topic warnings (engine.rs:368-372, 647, 672; turn.rs:399-407). The concurrent-edits gap from investigations is still open but missing from the elephant gaps.
- **GF7** (Major, egm-comprehension, Properties.uri, elephant.built): The document doesn't say who creates the table's workspace folder, how its path is chosen, or whether it is new or existing; the uri points only to a README section.
- **GF8** (Major, egm-comprehension, elephant.sources): The convention 'extra detail goes in files named with the agent's name' is not explained: what extra detail is, and what rule it relieves. The owner's evaluation specification is not defined or linked.
- **GF9** (Major, egm-comprehension, want from code.manager.chat.group): Intent is receive, but the document doesn't say what the manager receives from the workspace or how; 'chair' is undefined.
- **GF10** (Nit, egm-comprehension, investigations): 'Roundtable 7 proposals' is undefined, and current behaviour under conflicting edits is not stated.
- **GF11** (Nit, egm-comprehension, elephant.gaps with elephant.sources): Files are unjudged and agents are told to put detail in files; the document doesn't say whether this bypass of the evaluator is intended.
- **GF12** (Nit, egm-comprehension, wants, Properties): ACP, session/new, JEV, and the map fields role, name_length and Intent are undefined.

The code for this part is copied into the `source` folder here, under the same paths as above.
