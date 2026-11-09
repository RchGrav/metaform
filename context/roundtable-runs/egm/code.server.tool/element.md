# Map element `code.server.tool`: participant tools

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "participant tools",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/roundtable/src/mcp.rs"
}
```

## What other parts rely on it for (their wants)
- `code.client.agent`: goal: Give every participant the Roundtable tools in its own harness. Function: Supplies the MCP server configuration passed in session/new (and session/resume) mcpServers. Intent: send

## What it relies on (its wants)
- `code.manager.chat.group`: goal: Let a participant, normally the elected head of the table, move the group forward. Function: Ends the current topic and starts the next one, either with a topic chosen by the caller or through the normal poll. Intent: send
- `upstream.system.reputation`: goal: Let participants reward one another's good conduct. Function: Records a participant's rating of another participant's behavior toward accolades and identity. Intent: send

## Layer `references`
```json
[
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "4 session/new 'optional MCP tools'",
      "ACP v2 workspace/tool distinction"
    ]
  }
]
```

## Layer `owner_statements`
```json
[
  {
    "date": "2026-11-05",
    "statement": "If I say add a way for an agent to end the round or to move onto the next, with the intent that the head of the roundtable can do that, this is not a formalized 'only this role can do this'. It is an option that does what it says and allows an agent to move forward. We'll prompt who should use this, let the agents organize, and give them the feedback tool."
  }
]
```

## Layer `decisions`
```json
[
  {
    "by": "Claude",
    "date": "2026-11-05",
    "decision": "Roundtable serves an MCP server to every participant, passed in session/new mcpServers, with two tools and no role checks. advance: ends the current topic and moves the table on. With a topic argument, that topic becomes the next topic directly (the head choosing for the group); without one, the normal next-topic poll runs. feedback: rates another participant's behavior and passes the rating to the accolade system. The prompts say who should use each tool; the agents organize the rest.",
    "interpretation": "'End the round or move onto the next' is read as ending the current topic, as in the archive's numbering where R3 is the third topic. The optional topic argument comes from the owner's 'a head of the table who can choose for the group'."
  }
]
```

## Layer `gates`
```json
[
  {
    "gate_id": "RT-G11",
    "name": "The advance tool is refused during a topic poll and waits for the floor",
    "status": "active, removal proposed",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G15",
    "name": "A rating or feedback must name exactly one other participant",
    "status": "active, owner disposition pending",
    "registry": "docs/gate-registry.yaml"
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Give agents two tools: advance, to end a topic, and feedback, to rate another agent.",
  "sources": [
    "owner decisions recorded 2026-11-05 (TRACEABILITY I-3, I-4)"
  ],
  "built": "mcp.rs serves both tools over HTTP to each agent with its own token.",
  "gaps": [
    "Whether the feedback tool stays is open with the owner.",
    "advance only works with topics on."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, decisions): Not every participant gets the server: tools are passed only when the harness advertises HTTP MCP; otherwise the seat has none and a warning is recorded (crates/roundtable/src/engine.rs:966-975).
- **GF2** (Major, egm-codebase-details, elephant: built): mcp.rs does not serve HTTP itself (crates/roundtable/src/mcp.rs:1-4, 42-61); the HTTP route, bearer check, batching and 202 are in crates/roundtable-web/src/app.rs:158, 370-397, with TableHandle::seat_token_valid (engine.rs:225-228).
- **GF3** (Major, egm-codebase-details, gates / elephant gaps): Gate RT-G07 (advance refused when topics are off, mcp.rs:67-69) is missing; topics need the setting, judging and a JEV key (engine.rs:377-379), and a pending advance is dropped when JEV is lost (engine.rs:921-923).
- **GF4** (Major, egm-codebase-details, decisions: advance semantics): advance is stored and applied only when no floor or verdict is pending (engine.rs:511-519, 879); a later advance silently replaces a pending one (engine.rs:879); the chair can also issue it (crates/roundtable-web/src/tables.rs:164).
- **GF5** (Major, egm-codebase-details, feedback (missing)): Ratings unchecked: any key other than participant/note passes with any value despite the 0-5 description (mcp.rs:23, 89-96); target matched by genesis name excluding the sender (engine.rs:887); a name matching zero or several others gets a notice at the sender's next turn (engine.rs:888-893); unknown sender dropped (engine.rs:886); saved to identity and accolades log (app.rs:103-111).
- **GF6** (Nit, egm-codebase-details, protocol details): Echoes the client's protocolVersion, default 2025-06-18 (mcp.rs:12, 48); only initialize/ping/tools/list/tools/call answered, others -32601 (mcp.rs:46-56); notifications get no reply (mcp.rs:43).
- **GF7** (Major, egm-comprehension, gate RT-G11): 'Refused during a topic poll and waits for the floor' says both refuse and wait; the actual behaviour and the meaning of 'floor' are unclear.
- **GF8** (Major, egm-comprehension, elephant.gaps ('topics on')): A topics on/off mode is never defined, nor what advance does when topics are off.
- **GF9** (Major, egm-comprehension, elephant.built (per-agent token)): Token issuance, delivery through mcpServers, and purpose (caller identity) are unexplained.
- **GF10** (Major, egm-comprehension, terms: topic, round, poll, floor, head of the table, accolades, upstream.system.reputation): Discussion-model and reputation terms are used without definition; 'R3' archive numbering assumes prior knowledge.
- **GF11** (Nit, egm-comprehension, wants (Intent: send)): The client's want is tagged 'send' though this element supplies config to the client; Intent direction is undefined.
- **GF12** (Nit, egm-comprehension, references; elephant.sources; decisions.by): 'TRACEABILITY I-3, I-4' and the unnumbered 'ACP v2 workspace/tool distinction' section can't be located; a decision attributed only to Claude alongside an open owner question leaves its status unclear.

The code for this part is copied into the `source` folder here, under the same paths as above.
