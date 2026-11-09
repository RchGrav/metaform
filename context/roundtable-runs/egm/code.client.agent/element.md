# Map element `code.client.agent`: ACP client

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "package": "agent host library (reusable; basis for the chassis)",
  "name": "ACP client",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/acp-host/src/harness.rs"
}
```

## What other parts rely on it for (their wants)
- `code.manager.chat.group`: goal: Give each participant its turn and collect its action without waiting on the others. Function: Delivers turn prompts over each participant's continuing ACP session and returns the participant's reply, or reports that its previous prompt is still in progress (occupied). Intent: send_receive
- `code.monitor.activity`: goal: Relate observations to the right participant. Function: Provides the launched harness process id and its ACP session ids. Intent: receive

## What it relies on (its wants)
- `code.adapter.agent`: goal: Talk to OpenRouter-model participants through the same ACP lifecycle as every other harness. Function: Serves the ACP agent side for any OpenRouter model id. Intent: send_receive
- `code.bus.event`: goal: Surface every session change as it happens so nothing has to poll. Function: Carries session updates, tool activity, completion, permission decisions and process exits as events. Intent: send
- `code.launcher.agent`: goal: Start each selected participant's harness. Function: Resolves the harness to a launch command and spawns it with stdio for newline-delimited JSON-RPC. Intent: receive
- `code.server.tool`: goal: Give every participant the Roundtable tools in its own harness. Function: Supplies the MCP server configuration passed in session/new (and session/resume) mcpServers. Intent: send
- `collection.workspace.shared`: goal: Put every participant in the same working directory. Function: Supplies the directory passed as cwd on session/new. Intent: send
- `upstream.agent.coding`: goal: Hold a continuing working session with each participant. Function: Accepts initialize, session/new with the shared cwd, set_config_option and session/prompt, and streams session/update messages, tool activity and completion. Intent: send_receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "9.1 Agent Client Protocol",
      "10.1 ACP Activity Information"
    ]
  },
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "4 Concrete ACP RPC map",
      "5 Actual wire examples"
    ]
  },
  {
    "url": "https://github.com/agentclientprotocol/rust-sdk"
  }
]
```

## Layer `rules`
```json
[
  "Follow the protocol version negotiated by initialize; never apply v2 semantics to a v1 harness.",
  "v1: the session/prompt response with stopReason ends the turn. v2: the response only acknowledges insertion; completion is state_update idle.",
  "One persistent session per participant; topic changes happen inside the session.",
  "session/cancel only on explicit request, never because a participant is busy or silent."
]
```

## Layer `archaeology`
```json
[
  {
    "finding": "Python offered v2 first and fell back to a fresh v1 connection only on initialize-level evidence (error -32022 with data.supported, legacy agentInfo fields). Verified: claude-agent-acp 0.100.0 and codex-acp 2.5.0 speak v2; antigravity-acp 1.4.5 returns legacy fields.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/harness.py:420-480; archaeology/src/metaform/modules/roundtables/README.md"
  },
  {
    "finding": "Resume with session/resume when offered, else session/load with replay suppressed.",
    "path": "harness.py:508-516"
  },
  {
    "finding": "set_config_option: configId + type:'id' on v2; order mode, model, model_config, thought_level.",
    "path": "harness.py:569-578; archaeology/src/metaform/modules/dispatch/README.md:211"
  },
  {
    "finding": "A cancelled SDK future does not cancel the wire request; keep the slot and await the real reply.",
    "path": "harness.py:716-730"
  },
  {
    "finding": "v2 prompt acknowledgement is not completion; wait for state_update idle. Permission waits must not consume deadlines.",
    "path": "archaeology/src/metaform/modules/roundtables/tests/test_acp_v2.py:60-160"
  },
  {
    "finding": "Reply text = the last non-empty agent message block.",
    "path": "harness.py ~793"
  },
  {
    "finding": "Python removed ANTHROPIC_API_KEY, OPENAI_API_KEY and similar from the harness environment so subscription logins are used. Billing choice; not yet decided for the Rust build.",
    "path": "harness.py:45,383-387"
  },
  {
    "finding": "Fake ACP agent for tests.",
    "path": "archaeology/src/metaform/modules/roundtables/tests/fake_agent.py"
  }
]
```

## Layer `decisions`
```json
[
  {
    "by": "owner + Claude",
    "date": "2026-11-05",
    "topic": "permission requests",
    "status": "decided; SAFETY-RELEVANT",
    "owner_statement": "Auto inside workspace, or auto across project. This roundtable must do everything it can not to get stuck. In general this is largely autonomous.",
    "decision": "Roundtable answers every session/request_permission itself and never waits on a person. Scope = the project root that contains the shared workspace. Reads, searches, edits, moves and deletes whose locations are all inside scope are allowed. Command execution is allowed, because producing software needs builds and tests. Requests naming any location outside scope are rejected at once with the reason, so the agent can continue another way instead of stalling. Every permission decision is written to the discussion record and published to the chair.",
    "residual_risk": "Roundtable can check the paths a request names, but it cannot confine what an allowed shell command does; a command can reach anything the user account can. Where a harness advertises an OS sandbox mode that confines writes to its cwd (for example codex workspace-write), Roundtable selects it through session/set_config_option. Harnesses without one rely on this policy alone."
  }
]
```

## Layer `investigations`
```json
[
  {
    "topic": "ACP Rust SDK 5.0.0 (released 2026-11-02)",
    "note": "v1 is stable via Client.v1(); draft v2 is opt-in through the unstable_protocol_v2 feature with Client.v2(). The process feature spawns agents (AcpAgent). The SDK is runtime-agnostic (futures) and works with tokio. Notifications and permission requests arrive through typed handlers (on_receive_notification / on_receive_request), which map straight onto bus events without polling. v1::ActiveSession reads updates from its own stream; v2 prompt acceptance and completion are separate. 5.0.0 made many breaking changes three days before this check, so the dependency is pinned exactly."
  }
]
```

## Layer `verified`
```json
[
  {
    "date": "2026-11-05",
    "note": "Live: claude-agent-acp 0.101.0 (Sonnet 5.5, mode default) and codex-acp 2.5.0 (gpt-6.1-sol, mode workspace-write) over ACP v1: initialize, session/new with HTTP MCP server, set_config_option, prompt, reply extraction. ACP v2 not implemented."
  }
]
```

## Layer `gates`
```json
[
  {
    "gate_id": "RT-G09",
    "name": "Only the text after the last tool call becomes the message",
    "status": "active, owner disposition pending",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G18",
    "name": "Permission requests naming a path outside the workspace are refused",
    "status": "active, owner disposition pending",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G19",
    "name": "One prompt at a time per agent session",
    "status": "active, owner disposition pending",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G20",
    "name": "Agent processes are killed on a timer at shutdown",
    "status": "active, removal proposed",
    "registry": "docs/gate-registry.yaml"
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Talk to every agent through ACP sessions: open one continuing session per agent in the shared workspace, send turns, and read replies and tool activity.",
  "sources": [
    "Roundtable_ACP_Integration_Design.md §4",
    "owner, 2026-11-06: \"we were using v2 in the otherr system with a fallback to v1\""
  ],
  "built": "acp-host/src/harness.rs speaks ACP v2 first and v1 as a fallback, answers permission requests, and closes sessions at the end.",
  "gaps": [
    "One prompt at a time per session, although ACP v2 allows messages while an agent works (gate RT-G19).",
    "Agents are killed on a timer at shutdown (gate RT-G20, removal proposed).",
    "harness.rs is about 1,330 lines, over the 500-line limit."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, decisions: permission requests (scope)): Scope is not the project root containing the workspace: it is cfg.scope, defaulting to the workspace itself (crates/roundtable/src/engine.rs:405, crates/roundtable/src/config.rs:144-146), and the web page never sends scope (crates/roundtable-web/assets/index.html:484-489).
- **GF2** (Blocker, egm-codebase-details, decisions: permission requests (rejected with the reason)): The agent receives only a reject option or Cancelled, never the reason (crates/acp-host/src/harness.rs:945-950, 968-973); the reason goes only to the bus as PermissionDecided (harness.rs:920-928).
- **GF3** (Major, egm-codebase-details, verified): 'ACP v2 not implemented' contradicts the current v2-first negotiation with v1 fallback (crates/acp-host/src/harness.rs:8-12, 187-230); the entry is not marked superseded.
- **GF4** (Major, egm-codebase-details, decisions: residual_risk): Sandbox mode is not chosen from what a harness advertises; it is hard-coded by harness id in the roundtable crate (crates/roundtable/src/config.rs:212-218; OpenCode via env, config.rs:198-210); other seats only get a warning (crates/roundtable/src/engine.rs:992-995).
- **GF5** (Major, egm-codebase-details, permission policy edge cases (missing)): Undocumented: requests naming no paths are allowed for any kind (crates/acp-host/src/permission.rs:130-131); relative paths with unknown cwd are refused (permission.rs:58-60); symlinks resolved up to 40 links (permission.rs:68-119); a v2 command's cwd is scope-checked (harness.rs:964); an allow becomes a reject when no allow option is offered (harness.rs:910-914); one-time options preferred (harness.rs:905-909).
- **GF6** (Major, egm-codebase-details, wants (upstream.agent.coding) / lifecycle (missing)): Undocumented: auth retry via authenticate or auth/login (harness.rs:309-384); session/resume or session/load with replay suppressed (harness.rs:386-459, 727-732); set_config only for advertised options (harness.rs:465-482); SSE refused on v2 (harness.rs:1118-1131); idle ends a turn only after seen active (harness.rs:848-860); open prompts fail on exit (harness.rs:268-269); session/close at shutdown (harness.rs:598-644); 1 s/2 s grace then SIGKILL of the group (crates/acp-host/src/process.rs:25-27, 108-111, 132-148); stderr tail 40x2000 bytes (process.rs:17-18); env removals before explicit env (process.rs:63-70).
- **GF7** (Major, egm-comprehension, verified vs elephant.built / rules): verified (2026-11-05) says ACP v2 is not implemented while elephant.built (2026-11-07) and the rules say v2-first with v1 fallback; the document does not say which is current or whether v2 has been verified live.
- **GF8** (Major, egm-comprehension, decisions (permission requests) vs gate RT-G18): Permission scope is the project root containing the workspace in the decision but the workspace itself in RT-G18; the governing boundary is ambiguous.
- **GF9** (Major, egm-comprehension, archaeology (reply text) vs gate RT-G09): Reply is 'last non-empty agent message block' in archaeology but 'text after the last tool call' in RT-G09; which rule governs is not stated.
- **GF10** (Major, egm-comprehension, wants / Intent field): The direction semantics of send/receive/send_receive are undefined and look inconsistent (MCP config and cwd received by the client are tagged 'send').
- **GF11** (Major, egm-comprehension, terms: harness, chair, chassis, occupied, role SE, name_length): Core project terms, especially 'harness' vs agent vs participant, are used without definition.
- **GF12** (Nit, egm-comprehension, archaeology paths; elephant.gaps): Short paths like 'harness.py:508-516' lack a base, and the '500-line limit' has no cited source.

The code for this part is copied into the `source` folder here, under the same paths as above.
