# Map element `code.selector.topic`: next-topic selection

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "next-topic selection",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/roundtable/src/turn.rs"
}
```

## What other parts rely on it for (their wants)
- `code.manager.chat.group`: goal: When topics are on, move the group to its next shared focus once a topic is exhausted. Function: Polls every participant for a proposal and returns the winning topic by summed pairwise sameness. Intent: send_receive

## What it relies on (its wants)
- `upstream.judge.llm`: goal: Find which proposed topic best expresses the group's shared intent. Function: Judges whether two proposed topics express the same underlying intent and returns a confidence for each pair; pairs may be batched in one request. Intent: send_receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "6 Topic Completion",
      "7 Next-Topic Selection"
    ]
  }
]
```

## Layer `rules`
```json
[
  "Topics are off by default: the table works on the objective it was sent.",
  "With topics on and JEV available, two rounds with nothing accepted (or with every agent passing) start a poll; every agent proposes; pairwise sameness is summed; the highest wins; ties join with 'and'.",
  "Sameness is the owner's statement, `{{foo}} is the same as {{bar}}`, with the proposals named in JEV's state."
]
```

## Layer `investigations`
```json
[]
```

## Layer `archaeology`
```json
[
  {
    "finding": "Python asked 'Is proposal A similar to proposal B?' with true = 'concern a shared subject, question or direction'. The spec asks for the same underlying intent, explicitly not broad relatedness.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/resources/prompts.xml:646-648"
  },
  {
    "finding": "Python averaged instead of summing (same ranking when every pair is answered) and joined all tied texts with a blank line.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/topics.py:131-138"
  },
  {
    "finding": "Python skipped busy seats when polling, with 2 attempts and a 30 s window.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/topics.py:15; runner.py:1260-1300"
  },
  {
    "finding": "Tests worth translating: pairs, ties, sole proposal.",
    "path": "archaeology/src/metaform/modules/roundtables/tests/test_topic_selection.py:38-87"
  }
]
```

## Layer `decisions`
```json
[
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "question",
    "decision": "JEV is asked whether the two proposals express the same underlying intent: what the group would actually address next. Shared vocabulary or a related subject is not enough. The question is phrased so that true means same intent, with no negation (Jev reads negation literally, per archaeology prompts.xml:404-411)."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "scoring",
    "decision": "Sum, as specified. Confidence is JEV's probability that the statement is true."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "ties of three or more",
    "decision": "All tied winners are joined with ' and ' in seat order. This generalises README 7.4's purpose: keep every tied expression of intent rather than discard any arbitrarily."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "single proposal",
    "decision": "With one proposal there are no pairs; it becomes the topic. With zero proposals the current topic continues."
  },
  {
    "by": "owner",
    "date": "2026-11-05",
    "topic": "occupied participants at poll time",
    "decision": "Poll every participant that is not occupied, and insert the poll into running ACP v2 sessions. Occupied v1 participants are left out of that selection; the table never waits on independent work."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "JEV off or unavailable",
    "status": "decided, flagged for owner review",
    "decision": "Topic selection never waits on JEV (owner: JEV is optional and its failure never halts). A pair JEV did not judge scores 0. With judging off or JEV down, every proposal therefore ties and all are joined with ' and ' under the tie rule. This follows the spec's own arithmetic, keeps every participant's stated intent, and discards none arbitrarily. Cost: the joined topic can be long with many participants."
  },
  {
    "by": "owner",
    "date": "2026-11-07",
    "topic": "topics off by default",
    "decision": "Topics stay in the code but are off by default; the owner found a way to game the vote: an agent writes its decision into its proposal and wins on 'underlying intent'.",
    "owner_statement": "default is no topics its just the sent in prompt"
  }
]
```

## Layer `superseded`
```json
[
  {
    "date": "2026-11-07",
    "rule": "Every participant proposes a next topic."
  },
  {
    "date": "2026-11-07",
    "rule": "Each unique pair is judged once for sameness of intent: N(N-1)/2 judgments."
  },
  {
    "date": "2026-11-07",
    "rule": "Each pair's confidence is credited to both proposals; S_i = sum over j != i of C_ij."
  },
  {
    "date": "2026-11-07",
    "rule": "Highest sum wins; no 70% threshold."
  },
  {
    "date": "2026-11-07",
    "rule": "Two tied winners are joined with 'and'."
  },
  {
    "date": "2026-11-07",
    "rule": "The 30K-token case-selection alternative is recorded as an alternative only."
  }
]
```

## Layer `gates`
```json
[
  {
    "gate_id": "RT-G07",
    "name": "Topics are off by default and need JEV",
    "status": "active, owner-designed",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G08",
    "name": "Two quiet rounds start a topic poll",
    "status": "active, owner-designed",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G12",
    "name": "A topic proposal that arrives after its poll is discarded",
    "status": "active, owner disposition pending",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G13",
    "name": "Topic proposals are cut at 512 characters",
    "status": "active, removal proposed",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G21",
    "name": "A topic poll waits for every agent",
    "status": "active, owner disposition pending",
    "registry": "docs/gate-registry.yaml"
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "When topics are on, let the agents choose the next topic together; by default the table works on the objective only.",
  "sources": [
    "README.md §6-7",
    "owner, 2026-11-07: \"default is no topics its just the sent in prompt\"",
    "owner, 2026-11-07: \"we need to refine that a bit\""
  ],
  "built": "turn.rs polls every agent and sums pairwise sameness using the owner's line \"{{foo}} is the same as {{bar}}\". Off by default.",
  "gaps": [
    "The owner's refinement of topics is pending.",
    "Gates RT-G11 and RT-G13 are proposed for removal."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, decisions: occupied participants at poll time): Says occupied participants are left out and the table never waits. Busy seats are added to pending and the poll waits for them (src/turn.rs:269-272, 285-303; src/engine.rs:504-507).
- **GF2** (Blocker, egm-codebase-details, decisions: JEV off or unavailable): Says unjudged pairs score 0 and all proposals tie. With judging off or no key, no poll runs (src/engine.rs:377-379); losing JEV mid-poll stops it (src/engine.rs:915-920); a scoring error keeps the current topic (src/turn.rs:379-385).
- **GF3** (Blocker, egm-codebase-details, decisions: question): Says JEV is asked about 'same underlying intent'. The code sends only 'proposals.pA is the same as proposals.pB' (resources/topic_sameness.md:1, src/jev.rs:121-123).
- **GF4** (Major, egm-codebase-details, superseded): Lists N(N-1)/2 pairs, two-way crediting, highest sum wins and 'and' ties as superseded, but all are current (src/rules.rs:122-148) and contradict rules[1].
- **GF5** (Major, egm-codebase-details, rules[1]): Missing: with no limit, quiet rounds end the table rather than poll when the topic had no input (src/engine.rs:647); the advance tool sets a topic or starts a poll (src/engine.rs:514-519, 873-881); a PASS gives no proposal (src/turn.rs:327); proposals are cut to 512 (src/turn.rs:323); zero or one proposal is handled without JEV (src/turn.rs:343-350).
- **GF6** (Nit, egm-codebase-details, elephant gaps): Names RT-G11 as proposed for removal, but RT-G11 is not in the gates layer; it exists at src/engine.rs:872.
- **GF7** (Major, egm-comprehension, Layer superseded vs rules/decisions): The superseded rules (every participant proposes, N(N-1)/2 pairs, the S_i sum, highest wins, ties joined with 'and') are restated almost word for word by the active rules and decisions, and the 'question' decision describes a different question from the owner's statement. What changed on 2026-11-07 cannot be told.
- **GF8** (Major, egm-comprehension, rules / gate RT-G07 vs decision 'JEV off or unavailable'): Topics 'need JEV' vs 'with JEV off every proposal ties and all are joined'; whether a poll runs without JEV is unclear.
- **GF9** (Major, egm-comprehension, rules, elephant, gates RT-G21/RT-G12 vs owner decision on occupied participants): 'Every agent proposes' / 'waits for every agent' conflict with the owner's 'poll only agents that are not busy; never wait on independent work'; RT-G12 (late proposals discarded) adds a third version.
- **GF10** (Major, egm-comprehension, terminology): Undefined: JEV, JEV's state, the {{foo}}/{{bar}} templating, ACP v1 vs v2 and how a poll is 'inserted into running v2 sessions', occupied, and the '30K-token case-selection alternative'.
- **GF11** (Major, egm-comprehension, gates; elephant gaps): The gaps name RT-G11 for removal but RT-G11 is absent from the gates list. RT-G13 (cut at 512 characters) contradicts the owner's no-truncation rule and is not reconciled.
- **GF12** (Nit, egm-comprehension, rules (poll trigger)): 'Nothing accepted (or every agent passing)': an all-pass round already has nothing accepted, so the 'or' adds nothing or means something unstated. The trigger also overlaps the engine's no-limit ending rule.

The code for this part is copied into the `source` folder here, under the same paths as above.
