# Map element `code.bus.event`: event bus

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "package": "event bus library (reusable; basis for the chassis)",
  "name": "event bus",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/bus/src/lib.rs"
}
```

## What other parts rely on it for (their wants)
- `code.client.agent`: goal: Surface every session change as it happens so nothing has to poll. Function: Carries session updates, tool activity, completion, permission decisions and process exits as events. Intent: send
- `code.manager.chat.group`: goal: Run without blocking on any participant and without polling. Function: Carries Roundtable events out and delivers commands, ACP updates and observations in as events. Intent: send_receive
- `code.monitor.activity`: goal: Make activity observations available to subscribers as they happen. Function: Carries observation events to subscribers. Intent: send

## Layer `owner_statements`
```json
[
  {
    "date": "2026-11-05",
    "statement": "We are building two things here: an ACP system that must be reusable by the chassis, with the ACP autoselection and an event bus. Never poll what can surface as an event. What we do here will be used as a basis for the chassis, but this is a standalone tool."
  }
]
```

## Layer `rules`
```json
[
  "Never poll what can surface as an event: state changes, ACP updates, activity observations, chair commands and JEV results are all published as events.",
  "The bus has no dependency on Roundtable, so the chassis can adopt it unchanged."
]
```

## Layer `decisions`
```json
[
  {
    "by": "Claude",
    "date": "2026-11-05",
    "decision": "Typed in-process bus. Each subscriber has its own unbounded queue, so publishing never blocks and nothing is dropped; a global sequence number assigned under the same lock as enqueueing gives every subscriber one consistent order. Taps receive every event as an Envelope with lazy JSON, for the discussion record and the GUI. Built on futures channels, with no async-runtime dependency, so the chassis can bridge it into Bevy.",
    "tradeoff": "A subscriber that never reads holds its backlog in memory until dropped. Chosen over bounded or lossy channels because blocking a publisher or losing an event would break never-halt or the complete record."
  }
]
```

## Layer `tests`
```json
[
  {
    "path": "crates/bus/tests/bus.rs",
    "covers": [
      "typed delivery only of own type, in order",
      "tap sees all types in global order, JSON and downcast",
      "publishing never blocks on unread or dropped subscribers; unread subscriber loses nothing (10,000 events)",
      "4 concurrent publishers produce one identical order for two taps"
    ],
    "result": "4 passed, clippy clean, 2026-11-05"
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Carry every Roundtable event in one order without polling, as the basis of the chassis's event bus.",
  "sources": [
    "owner, 2026-11-05: \"never poll what can surface as an event\"",
    "Roundtable_ACP_Integration_Design.md §6"
  ],
  "built": "crates/bus gives every event one global sequence number; every subscriber sees every event in that order; publishing never blocks.",
  "gaps": [
    "No stored log or replay: a subscriber that joins late misses earlier events."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, elephant.built): Says every subscriber sees every event; a typed Subscription<E> receives only type E (crates/bus/src/lib.rs:138-141, 149-155; tests/bus.rs:22-36). Only Tap receives all events (lib.rs:142-145).
- **GF2** (Blocker, egm-codebase-details, wants (code.manager.chat.group); rules[0]): Chair commands are not delivered on the bus: they use a tokio mpsc Command channel (crates/roundtable/src/engine.rs:33-46, 199, 268, 447-451). JEV results return via the Internal mpsc (engine.rs:134-139; turn.rs:177-180). Only their effects are published.
- **GF3** (Major, egm-codebase-details, rules / edge cases): Event-name uniqueness is enforced only by debug_assert! (lib.rs:135-136); release builds silently accept two types under one NAME, making records ambiguous. Undocumented.
- **GF4** (Major, egm-codebase-details, missing API): Undocumented: Event trait and bounds (lib.rs:34-36), Delivery (lib.rs:94-99), Envelope seq/at/name/to_json/downcast (lib.rs:39-66), recv()/Stream on both receivers, streams end only when every Bus clone drops (lib.rs:166, 194), seq starts at 1, dropped receivers pruned on publish (lib.rs:140, 144).
- **GF5** (Nit, egm-codebase-details, decisions): publish takes the registry mutex (lib.rs:132), so it can wait briefly on other publishers or subscribe calls; poisoned locks are recovered silently.
- **GF6** (Nit, egm-codebase-details, decisions (lazy JSON)): A failed serialization is cached as None and re-attempted on every to_json call (lib.rs:55-59), so 'serialized once' holds only on success.
- **GF7** (Major, egm-comprehension, elephant.built vs decisions/tests): 'Every subscriber sees every event' contradicts typed delivery of only the subscriber's own type; per the decision, only taps see everything.
- **GF8** (Major, egm-comprehension, chassis (throughout)): The chassis justifies the whole design (no Roundtable dependency, no runtime, Bevy bridge) but is never defined.
- **GF9** (Major, egm-comprehension, owner_statements, rules, decisions, elephant.sources): ACP, ACP autoselection, JEV, chair commands, never-halt, and Integration Design §6 are used without definition or summary.
- **GF10** (Nit, egm-comprehension, decisions (tap, Envelope)): Tap vs subscriber and Envelope are undefined; it is not said how a tap is created or whether it is typed.
- **GF11** (Nit, egm-comprehension, elephant.gaps): Late subscribers miss events, but the document doesn't say whether the discussion-record tap is guaranteed to attach before the first event.
- **GF12** (Nit, egm-comprehension, Properties, wants): Map fields role SE, name_length and the Intent values are undefined.

The code for this part is copied into the `source` folder here, under the same paths as above.
