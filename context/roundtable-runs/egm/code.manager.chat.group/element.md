# Map element `code.manager.chat.group`: Roundtable

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "package": "roundtable (standalone tool)",
  "name": "Roundtable",
  "name_length": 3,
  "role": "DE",
  "uri": "crates/roundtable/src/engine.rs"
}
```

## What other parts rely on it for (their wants)
- `code.server.tool`: goal: Let a participant, normally the elected head of the table, move the group forward. Function: Ends the current topic and starts the next one, either with a topic chosen by the caller or through the normal poll. Intent: send
- `downstream.chair`: goal: Get a substantive deliverable for an objective (a specification, a design, software) from several independently reasoning models working together. Function: Runs a turn-based, judged discussion among heterogeneous agents who share a workspace, continuing across topics until the work is produced. Intent: send_receive

## What it relies on (its wants)
- `code.builder.prompt`: goal: Brief the next participant for its turn. Function: Assembles the participant's turn: the round line, its pending rejection reasons, and the other agents' new accepted messages; on its first turn, the owner's prompts. Intent: receive
- `code.bus.event`: goal: Run without blocking on any participant and without polling. Function: Carries Roundtable events out and delivers commands, ACP updates and observations in as events. Intent: send_receive
- `code.client.agent`: goal: Give each participant its turn and collect its action without waiting on the others. Function: Delivers turn prompts over each participant's continuing ACP session and returns the participant's reply, or reports that its previous prompt is still in progress (occupied). Intent: send_receive
- `code.gate.quality`: goal: Distribute only contributions worth the group's attention. Function: Accepts or vetoes each transmitted contribution against the three 70% conditions, with veto reasons. Intent: send_receive
- `code.identity.agent`: goal: Give each agent a stable identity across tables. Function: Derives the agent's name from its first session id. Intent: receive
- `code.monitor.activity`: goal: Show whether a silent participant is working, waiting, gone or unknown. Function: Provides independent activity observations correlated to each participant. Intent: receive
- `code.quota.character`: goal: Keep messages concise without cutting them. Function: Gives each discussion turn its reply limit (none by default; 1,024 once after a busy skip) and blocks a message over a set limit. Intent: send_receive
- `code.rating.peer`: goal: Record how each agent performed when the table ends. Function: Collects every agent's ratings of the others and returns the results. Intent: send_receive
- `code.roster.participant`: goal: Seat the participants the chair selected. Function: Provides each seat's harness and, where applicable, its OpenRouter model id. Intent: receive
- `code.selector.topic`: goal: When topics are on, move the group to its next shared focus once a topic is exhausted. Function: Polls every participant for a proposal and returns the winning topic by summed pairwise sameness. Intent: send_receive
- `collection.workspace.shared`: goal: Produce the chair's deliverable, not a discussion summary. Function: Holds the artifacts the participants create and refine independently or together. Intent: receive
- `data.log.discussion`: goal: Keep the continuing collaboration, every disposition and every topic change. Function: Stores each turn outcome in order with its canonical turn number. Intent: send

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "1 Theory of Operation",
      "4 Roundtable Discussion Loop",
      "11 Intended Productive Behavior",
      "12 Functional Boundaries"
    ]
  },
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "2 Functional Roundtable loop being supported",
      "6 End-to-end execution design"
    ]
  }
]
```

## Layer `decisions`
```json
[
  {
    "by": "Claude",
    "date": "2026-11-05",
    "decision": "Address chosen as code.manager.chat.group (group chat manager), the industry term (e.g. AutoGen GroupChatManager) for the component that runs a shared multi-agent conversation and selects who acts next. Roundtable's defining function is that conversation plus gated distribution in service of the chair's deliverable."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "turn order",
    "decision": "Discussion opportunities are sequential in seat order: one participant holds the floor at a time. Python prompted every ready seat at once and judged replies in a queue, which conflicts with 'turn-based' and 'identify the next participant' (README 4, 4.7) and made busy-drafting indistinguishable from independent work.",
    "evidence": "archaeology/src/metaform/modules/roundtables/roundtable/runner.py ~905-915; archaeology/src/metaform/modules/roundtables/tests/test_panel_scheduler.py:131-133"
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "signalling contribute / pass / work",
    "decision": "ACP defines no pass or work method, so the turn prompt defines a reply convention. A reply that is exactly PASS is a pass. A reply whose first line is WORK declares independent work: the table moves on at once, the participant's ACP turn keeps running untouched, and the participant is occupied until that turn completes; its closing text is recorded as a work note and is not judged as a contribution. Any other reply is a contribution. Occupied = its previous ACP prompt has not completed (v1 stopReason / v2 state_update idle).",
    "safety": "No WORK, PASS or occupancy rule ever cancels an ACP turn; session/cancel is sent only on the chair's explicit request."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "deliberation window",
    "status": "decided, flagged for owner review",
    "decision": "If a participant holding the floor has neither replied nor declared WORK within a configurable window, the table treats it as occupied and moves on: its turn continues untouched, it earns +512 per skipped opportunity like any occupied participant, and whatever it eventually replies is judged as its contribution at that point. Without this, one hung provider halts the whole table, which conflicts with README 4.7 ('agents performing independent work do not prevent the rest of the Roundtable from progressing'). This is not a termination timeout: nothing is cancelled."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "rounds",
    "decision": "A round is one pass through the seat order in which every seat has had one opportunity (contributed, passed, declared work, skipped as occupied, or failed at its provider). A nonproductive round is a round with zero accepted contributions. 'All participants pass' means every seat that was given the floor passed and none contributed. Topic progression needs two consecutive qualifying rounds. Python added a 'PV correction turn' rule and, with judging off, accepted one all-PASS round; neither is carried over.",
    "evidence": "archaeology/src/metaform/modules/roundtables/roundtable/store.py:582-641"
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "ending",
    "decision": "A Roundtable has no automatic end: no topic count, budget ending, convergence vote or summary phase. It runs until the chair ends it. Python's fixed topic counts, token-budget endings, synthesizer, rankings and reporter are not carried over (README 1, 11; Integration Design intent boundary)."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "operational problems",
    "decision": "Provider failures (HTTP 402/429, empty replies, resets) are observed by Roundtable directly and published to the chair on the event bus. Participants are not relied on to relay them through the discussion, where JEV would rightly judge them off-topic (run 1 T755). A failed turn is recorded with its error, earns no credit, and the table continues."
  }
]
```

## Layer `owner_statements`
```json
[
  {
    "date": "2026-11-05",
    "statement": "This roundtable must do everything it can not to get stuck. In general this is largely autonomous.",
    "consequence": "Nothing in the loop waits on a person or on an optional service: permission requests are answered automatically, a silent participant is treated as occupied after the deliberation window, provider failures are recorded and the table continues, and JEV failure lets contributions through unjudged. The only pause is an explicit chair hold."
  },
  {
    "date": "2026-11-05",
    "statement": "If JEV is down this doesn't halt, it continues. JEV is an optional thing. It doesn't stop the agents from completing their task, which is more important. By halting you are losing the agents' caching and many compress. Halting can prove more expensive than not.",
    "consequence": "Agents completing the task outranks every gate. Optional services (JEV, AgentSight) fail open. Idle time is a real cost (cache expiry, compression), so stopping is never the default response to a fault."
  },
  {
    "date": "2026-11-05",
    "statement": "We will be developing an interface where the user can hold the roundtable, to give them time to walk away and return, or to say their part and give guidance.",
    "consequence": "Chair controls are planned: hold, resume, chair guidance, and settings such as judging on/off. A hold stops new discussion opportunities; participants already doing independent work continue untouched and earn no skip credit while held, since no turns pass. The interface itself is future work."
  },
  {
    "date": "2026-11-05",
    "statement": "These agents will be coordinating together and should treat the kickoff of a roundtable as a choice: approach it in coordination, or each on its own with a strategy.",
    "consequence": "See code.builder.prompt decision 'kickoff'."
  },
  {
    "date": "2026-11-05",
    "statement": "Even with JEV they must coordinate. They must understand the process of the roundtable. The prompt can suggest they elect a head of the table who can choose for the group. As a general rule I don't add extra logic and gates to things. We control the flow and the logic; we'll prompt who should use the tools, let the agents organize, and give them the feedback tool. That's what strategy is about.",
    "consequence": "Coordination belongs to the agents, guided by prompts and two plain tools (advance, feedback in code.server.tool), not to system rules. No role is enforced. Any future proposal that adds a gate or a system-side rule needs a reason strong enough to override this principle and is put to the owner first."
  },
  {
    "date": "2026-11-07",
    "statement": "make it by default 10 rounds"
  },
  {
    "date": "2026-11-07",
    "statement": "unlimited must have some kind of end though like no more good input or all agents state done.."
  }
]
```

## Layer `investigations`
```json
[
  {
    "topic": "OPEN - idle loop cost",
    "note": "Smoke test 2026-11-05: when every seat passes, the spec's rules cycle topic after topic indefinitely (fake agents ran ~1,590 topic cycles in seconds); with real agents each cycle spends inference. Built: a warning notice after two consecutive topics with nothing accepted and no work (information only). Not built: any automatic hold. Whether the table should hold itself when idle is the owner's call (cost vs never-halt)."
  }
]
```

## Layer `reviews`
```json
[
  {
    "date": "2026-11-05",
    "by": "Sonnet (claude-acp) and Sol (codex-acp gpt-6.1-sol), seated in a Roundtable on this build",
    "findings": "review/FINDINGS.md (24 ranked + open items)",
    "resolution": "review/RESOLUTION.md: all 24 resolved with tests or live evidence; M2/M3 verified and fixed; M4 kept with prompt guidance, open for the owner",
    "verification": "31 workspace tests, clippy clean, live tools check with real Claude Code and Codex (record t1e3688c3c1f1)"
  }
]
```

## Layer `rules`
```json
[
  "A table runs 10 rounds by default, then the rating round. With no round limit it ends when two rounds bring no accepted message.",
  "The table waits while fewer than two agents are free; a lone free agent is told once to review the workspace.",
  "A busy agent's turn is skipped and never cancelled; it receives every missed message when it returns."
]
```

## Layer `gates`
```json
[
  {
    "gate_id": "RT-G03",
    "name": "The table waits until two agents are free",
    "status": "active, owner-designed",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G04",
    "name": "A busy agent's turn is skipped",
    "status": "active, owner-designed",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G05",
    "name": "The table ends after its rounds",
    "status": "active, owner-designed",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G06",
    "name": "A table with no round limit ends when there is no more good input",
    "status": "active, owner disposition pending",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G10",
    "name": "The next turn waits for JEV's verdict",
    "status": "active, owner disposition pending",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G14",
    "name": "An empty reply counts as a failed turn",
    "status": "active, owner disposition pending",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G16",
    "name": "Rejection reasons wait for the agent's next discussion turn",
    "status": "active, owner disposition pending",
    "registry": "docs/gate-registry.yaml"
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Run a turn-based discussion among agents of different models and harnesses toward the user's objective, with a shared workspace for the real work.",
  "sources": [
    "README.md §1-4 and §8",
    "owner, 2026-11-07: 10 rounds by default",
    "owner, 2026-11-06: \"we need atleast two agents to have a debate\""
  ],
  "built": "engine.rs gives turns in seat order, skips busy agents, waits while fewer than two are free, ends after the set rounds and runs the rating round.",
  "gaps": [
    "The end when all agents state they are done is not built; it needs the owner's wording.",
    "engine.rs is about 990 lines, over the 500-line limit."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, decisions: signalling contribute / pass / work): Says a first-line WORK reply declares work; the code has no WORK convention. Work is detected from ACP tool activity (src/engine.rs:6-8, 666-676), classify only knows Pass/Contribution/Empty (src/rules.rs:50-59), and PASS is case-insensitive with trailing dots allowed (src/rules.rs:54).
- **GF2** (Blocker, egm-codebase-details, decisions: deliberation window; owner_statements consequence line 113): Describes a configurable window after which a silent agent is treated as occupied and earns +512 per skip. The code has no timers (src/engine.rs:12) and no credits.
- **GF3** (Blocker, egm-codebase-details, owner_statements consequence line 113): 'Nothing in the loop waits on an optional service' and 'the only pause is an explicit chair hold' are false. The next turn waits for JEV's verdict with no timeout (src/engine.rs:510-513, src/turn.rs:170-173, src/jev.rs:3); the table waits while fewer than two are free (src/engine.rs:541-552) and while a poll waits for every agent (src/engine.rs:504-507).
- **GF4** (Blocker, egm-codebase-details, decisions: ending): Says there is no automatic end and no rankings. The table ends after its configured rounds, 10 by default (src/engine.rs:636-640, src/config.rs:164), or after two quiet rounds with no limit (src/engine.rs:647-651), and it builds a session ranking (src/turn.rs:516-549).
- **GF5** (Major, egm-codebase-details, rules[0]): The no-limit end applies only when topics are off or the topic had no input; otherwise two quiet rounds start a poll (src/engine.rs:647, 654-656). Rounds of all passes or busy skips also count (src/rules.rs:107-110). The 'end' is the rating round starting.
- **GF6** (Major, egm-codebase-details, wants lines; missing logic): The gate want says 'three 70% conditions' but there are five checks (src/turn.rs:205-210). The quota want implies 1,024 after a busy skip by default, but with no base limit there is none (src/engine.rs:397). Undocumented: two-step End (src/engine.rs:901-907), turns start only once every seat has started (src/engine.rs:499-500), the table ends when no seats are left (src/engine.rs:789-792), rating needs at least two named seats (src/turn.rs:422-425), and the review notice is sent once per waiting episode (src/engine.rs:554-556).
- **GF7** (Major, egm-comprehension, Layer decisions (ending, deliberation window, rounds) vs rules): Active decisions contradict the current rules and there is no superseded layer: 'no automatic end, no rankings, runs until the chair ends it' vs '10 rounds then the rating round'; '+512 per skipped opportunity' though credits were removed; topic progression though topics are off by default. Nothing says which statement wins.
- **GF8** (Major, egm-comprehension, rules ('waits while fewer than two agents are free') vs owner_statements): Waiting for two free agents conflicts with 'do everything it can not to get stuck' and 'the only pause is an explicit chair hold'. No bound on the wait, and no account of what happens if every agent stays busy.
- **GF9** (Major, egm-comprehension, rules (no-limit ending) vs code.selector.topic trigger): 'Two rounds with no accepted message' both ends a no-limit table and starts a topic poll; precedence when topics are on and there is no round limit is unstated.
- **GF10** (Major, egm-comprehension, whole document (terminology)): Undefined project terms: JEV (the opening says only 'an evaluator'), ACP v1/v2 stopReason/state_update/session/cancel, chair, seat, harness, head of the table, rating round, AgentSight, Python/archaeology, PV correction turn, run 1 T755, M2/M3/M4.
- **GF11** (Major, egm-comprehension, wants from code.server.tool): Advance starts the next topic 'through the normal poll', but topics are off by default; what advance does with topics off is not stated.
- **GF12** (Nit, egm-comprehension, Properties; investigations; elephant gaps): role 'DE', name_length 3, name 'Roundtable', package and the Intent values are unexplained (applies to all elements). The OPEN idle-loop investigation is not updated now that topics are off and rounds are limited; the '500-line limit' has no source.

The code for this part is copied into the `source` folder here, under the same paths as above.
