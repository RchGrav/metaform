# Map element `upstream.agent.coding`: ACP harness

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "ACP harness",
  "name_length": 2,
  "uri": "https://agentclientprotocol.com/protocol/v1/overview"
}
```

## What other parts rely on it for (their wants)
- `code.client.agent`: goal: Hold a continuing working session with each participant. Function: Accepts initialize, session/new with the shared cwd, set_config_option and session/prompt, and streams session/update messages, tool activity and completion. Intent: send_receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "9.1 Agent Client Protocol",
      "9.3 Common Agent Harnesses"
    ]
  },
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "4 Concrete ACP RPC map",
      "7.2 Common installed harnesses"
    ]
  }
]
```

## Layer `investigations`
```json
[
  {
    "topic": "known harnesses",
    "note": "Claude Code (claude-agent-acp), Codex (codex-acp), Pi (pi-acp), OpenCode (opencode-ai acp), plus any registered or user-supplied ACP command."
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "The coding agents that take part: Claude Code, Codex, OpenCode, Pi and other ACP agents.",
  "sources": [
    "README.md §9.3"
  ],
  "built": "Recorded runs: Claude Code and Codex used ACP v2; OpenCode used v1. Pi has never run.",
  "gaps": [
    "Of the registry agents checked by their source on 2026-11-07, only Claude Code and Codex use ACP v2."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Major, egm-codebase-details, investigations: known harnesses): The list leaves out the in-repo openrouter-acp harness, which the catalog always offers first (crates/roundtable-web/src/tables.rs:76-99) and which speaks ACP v1 (adapters/openrouter-acp/src/adapter.ts:3).
- **GF2** (Major, egm-codebase-details, investigations: known harnesses): The built-in fallback versions are pinned and not recorded: @agentclientprotocol/claude-agent-acp@0.101.0, @agentclientprotocol/codex-acp@2.5.0, pi-acp@0.0.34, opencode-ai@1.19.5 with `acp` (crates/acp-host/src/launch.rs:78-90). They are used when the registry cannot be reached, or added when the registry does not list them (launch.rs:212-231).
- **GF3** (Nit, egm-codebase-details, properties.uri): The uri points to the ACP protocol v1 overview, while elephant.built says Claude Code and Codex use ACP v2. The element covers both versions.
- **GF4** (Nit, egm-codebase-details, wants; elephant): The supplied source (crates/acp-host/src/launch.rs) only covers launching. I could not check the RPC list in the want (initialize, session/new, set_config_option, session/prompt) or the claims about recorded runs and registry ACP versions against it.
- **GF5** (Major, egm-comprehension, elephant gaps): 'Only Claude Code and Codex use ACP v2' is listed as a gap without its consequence: whether Roundtable needs v2, supports both, or what breaks on v1 (the design doc calls v2 a draft; the uri points to v1).
- **GF6** (Major, egm-comprehension, wants): The method list doesn't say which ACP version it describes, though the element says the versions differ.
- **GF7** (Nit, egm-comprehension, elephant built): 'Pi has never run' gives no reason or support status.
- **GF8** (Nit, egm-comprehension, elephant gaps): 'Checked by their source' is ambiguous.

The code for this part is copied into the `source` folder here, under the same paths as above.
