# Map element `code.quota.character`: reply limit

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "reply limit",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/roundtable/src/rules.rs"
}
```

## What other parts rely on it for (their wants)
- `code.builder.prompt`: goal: Tell the participant how many characters it may contribute. Function: Reports the participant's current speaking allowance. Intent: receive
- `code.manager.chat.group`: goal: Keep messages concise without cutting them. Function: Gives each discussion turn its reply limit (none by default; 1,024 once after a busy skip) and blocks a message over a set limit. Intent: send_receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "4.1 Speaking Allowance",
      "4.3 Passing",
      "4.4 Independent Work",
      "4.5 Oversized Contributions",
      "4.6 Vetoes and Deferred Feedback"
    ]
  }
]
```

## Layer `rules`
```json
[
  "No reply limit by default (the owner's length experiment).",
  "When a limit is set, a message over it is blocked and not shared; it is never cut.",
  "After an agent was skipped while busy, its next discussion reply gets the recovery limit (1,024) once, then the limit returns to normal. Several skips give it once.",
  "No credits: passing and skipping add nothing."
]
```

## Layer `investigations`
```json
[
  {
    "topic": "run 1 divergence",
    "note": "Run 1 excluded five submissions for exceeding 512 characters (513-523 chars). The current spec truncates instead. Source: ~/topogee/docs/roundtables/1-embodied-ai-in-a-3d-physics/Roundtable_1_First_Run_Analysis_and_Failure_Audit.md P09."
  }
]
```

## Layer `archaeology`
```json
[
  {
    "finding": "Python credited +512 per accepted peer message missed while busy, not per skipped turn: allowance = 512 x (1 + pass credits + missed accepted messages).",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/allowance.py:161-170"
  },
  {
    "finding": "Python spent the offered credits when a reply was accepted and kept them on veto; the bank carried across topics only in session mode.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/allowance.py:26-29,163-164,175"
  },
  {
    "finding": "Python never reported characters removed by truncation: status_kept_truncated is empty and private_feedback ignores truncation.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/resources/prompts.xml:231; render.py:285-287"
  }
]
```

## Layer `decisions`
```json
[
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "veto",
    "decision": "A vetoed contribution neither credits nor spends the allowance: it never reached the group, and README 4.6 only says it earns no credit."
  },
  {
    "by": "owner",
    "date": "2026-11-05",
    "topic": "accepted contribution",
    "decision": "An accepted contribution spends the whole bank; the allowance returns to 512."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "topics",
    "decision": "The allowance carries across topic changes, because README 8 says topic changes do not reset the collaboration."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "characters",
    "decision": "Characters are Unicode scalar values (Rust char). Truncation cuts at the last grapheme-cluster boundary within the allowance so no character is split; the notice reports the removed count in the same unit."
  },
  {
    "by": "owner",
    "date": "2026-11-07",
    "topic": "credits removed",
    "decision": "The credit system is gone; a busy skip earns one larger reply instead.",
    "owner_statement": "it doesnt matter 1024 is plenty and yes remove the credits messsage"
  },
  {
    "by": "owner",
    "date": "2026-11-07",
    "topic": "no cutting",
    "decision": "Messages are never truncated; an over-limit message is blocked.",
    "owner_statement": "we arent going to be truncating if we add limits in we will block messages for being too long"
  }
]
```

## Layer `superseded`
```json
[
  {
    "date": "2026-11-07",
    "rule": "Starts at 512 characters per participant."
  },
  {
    "date": "2026-11-07",
    "rule": "+512 for each pass."
  },
  {
    "date": "2026-11-07",
    "rule": "+512 for each skipped turn while occupied with independent work."
  },
  {
    "date": "2026-11-07",
    "rule": "No credit for a veto."
  },
  {
    "date": "2026-11-07",
    "rule": "Oversized contributions are truncated to the allowance before evaluation, never rejected for length; the removed character count is reported at the next turn."
  }
]
```

## Layer `gates`
```json
[
  {
    "gate_id": "RT-G02",
    "name": "Reply length limit blocks long messages",
    "status": "active, owner-designed",
    "registry": "docs/gate-registry.yaml"
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Keep messages concise: no limit for now, and a message over a set limit is blocked, never cut.",
  "sources": [
    "owner, 2026-11-07: \"we arent going to be truncating if we add limits in we will block messages for being too long\"",
    "owner's evaluation specification: 1,024 characters after a busy skip"
  ],
  "built": "No limit by default. When set, an over-limit message is blocked; one reply after a busy skip gets 1,024 characters.",
  "gaps": [
    "The block notice is the builder's wording and awaits the owner's text."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, rules[2]; elephant built; manager want): The 1,024 recovery limit applies only when a base limit is set: limit_for returns None when base_allowance is None (src/engine.rs:396-399), and that is the default (src/config.rs:157-158). Tests always set a base (tests/engine.rs:32).
- **GF2** (Blocker, egm-codebase-details, wants: code.builder.prompt): 'Reports the participant's current speaking allowance' is not done. Prompts carry no allowance (src/turn.rs:31-83); only the chair's FloorGiven event does (src/engine.rs:611).
- **GF3** (Blocker, egm-codebase-details, decisions: veto, accepted contribution, topics, characters): These describe a bank that resets to 512, allowance carry-over and grapheme truncation as current, and are not marked superseded. The code has no bank (src/engine.rs:83-86) and blocks rather than cuts (src/turn.rs:128-146).
- **GF4** (Major, egm-codebase-details, rules[1]): 'Never cut' ignores topic proposals, which are cut to 512 by this element's truncate_to (src/rules.rs:19-38, src/turn.rs:323). Unstated: a blocked reply counts as a Failed opportunity and skips JEV (src/turn.rs:145).
- **GF5** (Major, egm-codebase-details, decisions: credits removed ('one larger reply')): The recovery limit replaces the base without comparing, so a base above 1,024 makes it smaller (src/engine.rs:398). Only give_floor skips set recovery_due (src/engine.rs:573), not floor-to-work (src/engine.rs:670-676); review prompts use it up (src/engine.rs:595, 603-605).
- **GF6** (Nit, egm-codebase-details, rules[0]): The unused DEFAULT_BASE = 512, commented 'Default reply limit', contradicts no limit by default (src/rules.rs:7-8). Validation rejecting 0 limits (src/config.rs:113-115) is undocumented.
- **GF7** (Major, egm-comprehension, rules (recovery limit); owner decision 'credits removed'): Described as 'one larger reply', but with no default limit, 1,024 after a busy skip restricts a reply that would otherwise be unlimited. Whether 1,024 applies with no base limit, or when a set limit is above 1,024, is unstated.
- **GF8** (Major, egm-comprehension, Layer decisions (veto, accepted contribution, topics, characters)): Active decisions still describe the removed scheme (credits, the bank returning to 512, carrying the allowance across topics, grapheme-boundary truncation) without being marked superseded. The unit of length mixes Unicode scalars and grapheme clusters.
- **GF9** (Major, egm-comprehension, wants from code.builder.prompt): The prompt builder relies on this element to tell the agent its allowance, but the characters line was removed; when a limit is set, how an agent learns it before being blocked is unstated.
- **GF10** (Major, egm-comprehension, rules (blocking)): What a blocked message becomes (a veto, a failed turn, something else), whether the length check runs before or instead of JEV, and when the author is told are all unstated.
- **GF11** (Nit, egm-comprehension, rules ('when a limit is set')): Who sets the limit, and where (a chair setting, config), is not stated; 'the owner's length experiment' is unexplained.
- **GF12** (Nit, egm-comprehension, investigations; references; terminology): The run 1 note says 'the current spec truncates instead', which is stale (the current rule blocks). 'Bank', 'session mode' and 'busy skip' are undefined here. The README 4.x references appear to describe the superseded scheme.

The code for this part is copied into the `source` folder here, under the same paths as above.
