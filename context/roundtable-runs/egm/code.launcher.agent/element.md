# Map element `code.launcher.agent`: ACP autoselection

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "package": "agent host library (reusable; basis for the chassis)",
  "name": "ACP autoselection",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/acp-host/src/launch.rs"
}
```

## What other parts rely on it for (their wants)
- `code.client.agent`: goal: Start each selected participant's harness. Function: Resolves the harness to a launch command and spawns it with stdio for newline-delimited JSON-RPC. Intent: receive
- `code.roster.participant`: goal: Offer the harnesses a participant can run in. Function: Lists registered harnesses, catalog aliases and user-supplied ACP commands. Intent: receive

## What it relies on (its wants)
- `upstream.registry.agent`: goal: Resolve a selected harness name to a launch command without a bespoke integration per harness. Function: Lists published ACP agents and their distributions (binary, npx, uvx), as used by acpr. Intent: receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "9.2 Universal Harness Discovery"
    ]
  },
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "3 Discovery is not a universal local executable scanner",
      "7.1",
      "7.2"
    ]
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Find and start agents from the ACP Registry, common harness commands and any local ACP command, without code for each harness.",
  "sources": [
    "README.md §9.2",
    "Roundtable_ACP_Integration_Design.md §7.1-7.2"
  ],
  "built": "acp-host/src/launch.rs reads the registry, uses acpr when it is installed, and has built-in entries for Claude Code, Codex, Pi and OpenCode.",
  "gaps": [
    "acpr is not installed on this machine, so registry agents start through npx or uvx directly."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, their wants: code.client.agent): launch.rs does not spawn anything or set up stdio; it only builds LaunchSpec (crates/acp-host/src/launch.rs:14-51). Spawning is process::spawn (crates/acp-host/src/process.rs:61-85), part of code.client.agent.
- **GF2** (Major, egm-codebase-details, their wants: code.roster.participant): No 'catalog aliases' exist, and user-supplied commands are not listed: launch::custom (launch.rs:235-238) is used only for the OpenRouter adapter entry (crates/roundtable-web/src/tables.rs:88); seat commands bypass launch.rs via LaunchSpec::from_command_line (tables.rs:107-108).
- **GF3** (Major, egm-codebase-details, elephant: built / gaps): An installed registry binary on PATH takes precedence over acpr (launch.rs:117-127); without acpr, binary-only entries are unavailable unless installed (launch.rs:128-133), so 'start through npx or uvx directly' covers package entries only.
- **GF4** (Major, egm-codebase-details, missing security rule): Registry-supplied env is filtered: PATH, NODE_OPTIONS, NODE_PATH, PYTHONPATH, PYTHONSTARTUP, BASH_ENV, ENV, HOME and LD_/DYLD_/NPM_CONFIG_ prefixes are refused (launch.rs:168-185); undocumented.
- **GF5** (Major, egm-codebase-details, missing logic): Undocumented: REGISTRY_URL (launch.rs:12); built-ins merged when the registry is reachable, whole built-in catalog plus note when not (launch.rs:214-232); availability via `which` on the command (launch.rs:195-199).
- **GF6** (Nit, egm-codebase-details, built entries): Pinned built-in versions not stated (claude-agent-acp 0.101.0, codex-acp 2.5.0, pi-acp 0.0.34, opencode-ai 1.19.5; launch.rs:85-88); command-line splitter handles quotes, no escapes (launch.rs:240-272).
- **GF7** (Major, egm-comprehension, name): 'ACP autoselection' misdescribes the element; it resolves and spawns what the chair selected and lists options, and nothing is auto-selected.
- **GF8** (Major, egm-comprehension, wants / elephant.built (acpr)): acpr is never defined, and what it adds over direct npx/uvx is not explained.
- **GF9** (Major, egm-comprehension, resolution order; 'catalog aliases', 'registered harnesses', user-supplied commands): Precedence among built-in, registry, acpr and user commands is unstated; 'catalog aliases' is undefined; how a user supplies an ACP command is not described.
- **GF10** (Major, egm-comprehension, failure behaviour): No behaviour is given for an unreachable registry, missing npx/uvx, or a spawned process that fails to start or handshake.
- **GF11** (Nit, egm-comprehension, elephant.design vs references section 3 title): 'any local ACP command' sits against a cited section titled 'Discovery is not a universal local executable scanner' without reconciliation.
- **GF12** (Nit, egm-comprehension, upstream.registry.agent): Registry location and caching are not stated.

The code for this part is copied into the `source` folder here, under the same paths as above.
