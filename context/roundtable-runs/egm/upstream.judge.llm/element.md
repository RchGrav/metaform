# Map element `upstream.judge.llm`: JEV

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "JEV",
  "name_length": 2,
  "uri": "README.md#5-jev--judgment-engine"
}
```

## What other parts rely on it for (their wants)
- `code.gate.quality`: goal: Decide before broadcast whether a contribution is worth every other participant's input tokens. Function: Returns a confidence for each of the three contribution conditions, with reasons for any that fall short, in one request through OpenRouter. Intent: send_receive
- `code.selector.topic`: goal: Find which proposed topic best expresses the group's shared intent. Function: Judges whether two proposed topics express the same underlying intent and returns a confidence for each pair; pairs may be batched in one request. Intent: send_receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "5 JEV — Judgment Engine"
    ]
  },
  {
    "path": "~/topogee/docs/roundtables/1-embodied-ai-in-a-3d-physics/Roundtable_1_First_Run_Analysis_and_Failure_Audit.md",
    "note": "Run 1 used typesafe/jev-1.13 with four scores (new, valuable, relevant, keep) at 0.83; the current spec specifies three conditions at 0.70."
  }
]
```

## Layer `investigations`
```json
[
  {
    "topic": "operating characteristics",
    "note": "64K input, millisecond responses, no output charge, ~$0.42/M input are owner-supplied characteristics; the integration design states they are not separately verified provider guarantees. Verify against OpenRouter before relying on cost or latency."
  }
]
```

## Layer `archaeology`
```json
[
  {
    "finding": "Model typesafe/jev-1.13 (dated snapshot -20260917) through OpenRouter POST /api/alpha/decisions. Request {model, state, questions}; each question {type:'noul', instructions, criteria:{true,false}}. Response answers[name].noul = probability true.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/config.py:46-47; archaeology/src/metaform/jev.py:81-90; judge.py:200-251"
  },
  {
    "finding": "Documented Jev weaknesses: leans toward the first option, does not count, accuracy falls as irrelevant state grows, state can argue for its own answer.",
    "path": "archaeology/src/metaform/jev.py:28-38 (cites docs.typesafe.ai/model-jaggedness/jev-1.13.md)"
  },
  {
    "finding": "PRICE CONFLICT: the archive records $0.042 per million input tokens; README 5 says ~$0.42. Unverified.",
    "path": "archaeology/src/metaform/jev.py:97"
  }
]
```

## Layer `owner_statements`
```json
[
  {
    "date": "2026-11-05",
    "statement": "0.70 is better for this purpose.",
    "applies_to": "code.gate.quality threshold (confirms README 5.1 over run 1's 0.83)"
  },
  {
    "date": "2026-11-05",
    "statement": "JEV isn't a semantics tool. It is a real system, one model that answers a prompt with a confidence level, used as a programmatic if or case statement.",
    "consequence": "Every JEV use in Roundtable is a reasoned question whose wording carries the logic; confidence is consumed as a decision value or a number, never as a similarity distance."
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "JEV judges each message cheaply before it reaches the group.",
  "sources": [
    "README.md §5"
  ],
  "built": "Called as ~typesafe/jev-latest through OpenRouter's decision route; about $0.00005 per message for five checks.",
  "gaps": []
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, wants: code.gate.quality): 'Returns a confidence for each of the three contribution conditions, with reasons for any that fall short' is false. The request has five questions: three noul gates (contribution, usefulness, relevance) and two 0-5 scores (value, auditability) (crates/roundtable/src/jev.rs:42-59). Only one number per question is read back, and no reasons (jev.rs:152-175). The rejection text is built by Roundtable from the failed names and values (crates/roundtable/src/turn.rs:204-216). This also contradicts the document's own elephant ('five checks').
- **GF2** (Major, egm-codebase-details, references note): 'The current spec specifies three conditions at 0.70' is incomplete. The code checks three gates at GATE_PASS 0.70 (crates/roundtable/src/rules.rs:13-15) and two scores against SCORE_PASS (crates/roundtable/src/turn.rs:207-210).
- **GF3** (Major, egm-codebase-details, whole document): The request shape and limits are undocumented. A `score` question type carries ordered criteria levels (jev.rs:20-40). The message state holds the topic, the last 4 completed rounds plus the current round, and new_message, with the oldest messages dropped to stay within 32,000 tokens for state plus the longest question and 64,000 for the whole request (jev.rs:61-103). Tokens are estimated at one per 3 bytes (jev.rs:68-72). Answers outside their range are errors (jev.rs:163-171).
- **GF4** (Major, egm-codebase-details, whole document): Failure behaviour is undocumented: no key, or a message that cannot fit, means it is shared unjudged (crates/roundtable/src/turn.rs:152-167); a JEV error means it is shared unjudged with a loud notice (turn.rs:199-203); there is no timer (jev.rs:1-3); HTTP error bodies are cut to 300 characters (jev.rs:158-160).
- **GF5** (Nit, egm-codebase-details, wants: code.selector.topic): Accurate. For the record: the question text comes from resources/topic_sameness.md with {{foo}}/{{bar}} replaced (jev.rs:116-123), and pairs are batched under the names p{a}_{b} (crates/roundtable/src/turn.rs:354).
- **GF6** (Major, egm-comprehension, elephant built): 'Five checks' per message conflicts with the three conditions in the gate want and owner statements; the three conditions are never named.
- **GF7** (Major, egm-comprehension, elephant / archaeology): The model changed from typesafe/jev-1.13 to ~typesafe/jev-latest with no explanation of '~' or of dropping the pinned snapshot; 'decision route' only connects to POST /api/alpha/decisions through archaeology.
- **GF8** (Major, egm-comprehension, investigations / archaeology): The price conflict ($0.042 vs ~$0.42/M) is open, and the $0.00005-per-message figure doesn't say which price it assumes.
- **GF9** (Nit, egm-comprehension, archaeology): 'noul' and the request shape are not explained.
- **GF10** (Nit, egm-comprehension, references): A '~/topogee/docs/...' path breaks the header's rule that paths are relative to the Roundtable folder.

The code for this part is copied into the `source` folder here, under the same paths as above.
