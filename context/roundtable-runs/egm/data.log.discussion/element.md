# Map element `data.log.discussion`: discussion record

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "discussion record",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/roundtable/src/record.rs"
}
```

## What other parts rely on it for (their wants)
- `code.builder.prompt`: goal: Tell the participant what happened since its last turn. Function: Provides the accepted contributions since that participant's last turn, its own pending veto or truncation disposition, and the current topic and objective. Intent: receive
- `code.manager.chat.group`: goal: Keep the continuing collaboration, every disposition and every topic change. Function: Stores each turn outcome in order with its canonical turn number. Intent: send

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "4.6 Vetoes and Deferred Feedback",
      "4.7 The Continuing Loop",
      "8 Continuity Across Topics"
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
    "decision": "The spec requires accepted contributions to be distributed, dispositions deferred to a participant's next turn, and context to continue across topics, but names no store. The discussion record is the append-only source for all three. It holds every submission with its canonical turn number, its outcome, the JEV scores and reasons, truncation counts, topic changes and seat availability.",
    "evidence": "Run 1 audit E05, E06, D01-D05: missing judge traces, missing per-seat context, turn-label drift, null report and missing seat availability made the run unauditable."
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Keep a complete record of a table: every event, every prompt each agent received and every reply.",
  "sources": [
    "owner, 2026-11-06: could not see what agents receive"
  ],
  "built": "record.rs writes every event of a table to record.jsonl, including each prompt text.",
  "gaps": [
    "JEV's requests are not recorded; the request for one message had to be rebuilt on 2026-11-07."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, wants (code.builder.prompt)): The record does not supply prompt content: record.rs only appends (record.rs:38-57). turn_prompt reads the in-memory Table.log and Seat.notices (turn.rs:54-66; engine.rs:89-90, 150).
- **GF2** (Blocker, egm-codebase-details, wants (code.manager.chat.group); decision): No canonical turn number exists. Accepted ids are R{topic}-{n}, a per-topic accepted count (turn.rs:237-238); rejected contributions have id None (turn.rs:135, 220); Pass/Skipped carry no number (events.rs:51, 54).
- **GF3** (Blocker, egm-codebase-details, decision): Not the source for distribution or dispositions (engine memory is). No truncation counts: over-limit replies are blocked and recorded with limit and a reason only (turn.rs:127-145); proposals are cut to 512 with no count (turn.rs:322-325).
- **GF4** (Major, egm-codebase-details, elephant.built): Not every event is recorded: the recorder stops at roundtable.ended (record.rs:51-53), while SessionClosed and HarnessExited from shutdown are published afterwards (engine.rs:936-939; acp-host/src/harness.rs:602-639). Events whose table cannot be resolved are dropped (record.rs:47).
- **GF5** (Major, egm-codebase-details, edge cases): Write errors are silently discarded (record.rs:50 'let _ = writeln!'); unserializable payloads are written as data:null (record.rs:17). Contradicts the complete-record claim.
- **GF6** (Major, egm-codebase-details, missing detail): Undocumented: path <ROUNDTABLE_HOME|~/.roundtable>/tables/<id>/record.jsonl (app.rs:60-62; tables.rs:147), line schema (record.rs:11-19), table routing via table field or harness prefix (record.rs:24-35), readers (app.rs:279-341).
- **GF7** (Major, egm-comprehension, decisions vs elephant vs wants): The decision describes a turn-outcome store and the elephant layer a full event log of every prompt and reply. It is unclear whether the prompt builder actually reads record.jsonl or whether the record is only an audit trail.
- **GF8** (Major, egm-comprehension, wants, decisions, elephant): JEV, disposition, veto, truncation, canonical turn number, seat, seat availability, topic and table are undefined.
- **GF9** (Major, egm-comprehension, decisions.evidence): 'Run 1 audit E05, E06, D01-D05' and 'turn-label drift' are opaque codes with no link, so the rationale cannot be checked.
- **GF10** (Nit, egm-comprehension, elephant.built): The location of record.jsonl (whether one per table, and which directory) is not stated.
- **GF11** (Nit, egm-comprehension, elephant.gaps): 'Request had to be rebuilt' is vague, and it contradicts the 'complete record' claim without saying what else is missing.
- **GF12** (Nit, egm-comprehension, Properties, wants): Map fields role, name_length and the Intent values are undefined.

The code for this part is copied into the `source` folder here, under the same paths as above.
