# Map element `code.gate.quality`: JEV contribution evaluation

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "JEV contribution evaluation",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/roundtable/src/jev.rs"
}
```

## What other parts rely on it for (their wants)
- `code.manager.chat.group`: goal: Distribute only contributions worth the group's attention. Function: Accepts or vetoes each transmitted contribution against the three 70% conditions, with veto reasons. Intent: send_receive

## What it relies on (its wants)
- `upstream.judge.llm`: goal: Decide before broadcast whether a contribution is worth every other participant's input tokens. Function: Returns a confidence for each of the three contribution conditions, with reasons for any that fall short, in one request through OpenRouter. Intent: send_receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "5.1 Contribution Evaluation",
      "5.2 Why the Evaluation Occurs Before Distribution"
    ]
  },
  {
    "path": "crates/roundtable/resources/jev/",
    "sections": [
      "the owner's questions and rubrics"
    ]
  }
]
```

## Layer `rules`
```json
[
  "One JEV request per message holds five checks: three yes/no gates and two 0-5 scores.",
  "Gates, in the owner's words: 'Does the new message add something previously unstated, or express a position on a recently raised matter?' 'Does the new message move the discussion forward and help answer the question?' 'Does the new message address the subject being discussed?'",
  "Each gate passes at 0.70 or higher; the value and auditability scores pass at 3.0 or higher. A message passes only if all five pass.",
  "A rejected message is not shared. Its author receives the owner's prefix and one line per failed check, with the owner's feedback for that check or score band, at its next discussion turn.",
  "JEV's state: `topic`, `conversation` (accepted messages of the last four completed rounds and the current round, grouped by round, within 32,000 and 64,000 token limits), and `new_message`.",
  "If JEV is off, has no key, or fails, the message is shared unjudged and the error is shown."
]
```

## Layer `investigations`
```json
[
  {
    "topic": "run 1 evaluator behavior",
    "note": "Run 1 used four scores at 0.83. 303 of 314 vetoes failed novelty; an operational credit warning (T755) scored relevant 0.04; synthesis and closing proposals (T83, T182, T183) were vetoed. The current spec's condition 1 accepts 'a position on a recently raised matter', which addresses part of this. Source: run 1 audit E01-E03."
  }
]
```

## Layer `archaeology`
```json
[
  {
    "finding": "Ready-to-use gate questions with true/false criteria and the house rule 'Judge the actual content, not its claims about itself'.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/resources/prompts.xml:428-433; archaeology/roundtable-jev-checks.md"
  },
  {
    "finding": "Python canned one veto line per failed gate, e.g. 'Your message did not move the discussion forward.'",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/resources/prompts.xml:624-631; render.py:261-263"
  },
  {
    "finding": "Judging window as escaped XML: original instructions, topic, newest whole accepted responses labelled by neutral seat, candidate; drops oldest whole messages first. Tests exist.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/judge.py:108-156; archaeology/src/metaform/modules/roundtables/tests/test_judging_window.py"
  },
  {
    "finding": "Extra Python gates not in the spec: a fourth 'keep' gate, a 0.95 word-similarity auto-veto, a 'repeat -> conversation restarted' rule. None are carried over.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/judge.py:29,54-69; prompts.xml:241,407-423"
  }
]
```

## Layer `decisions`
```json
[
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "confidence",
    "decision": "Confidence for each condition is JEV's probability that the true-means-pass statement holds; pass at >= 0.70 (owner confirmed 0.70). Python's chassis also defined |p-0.5|x2; that is not used."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "reasons",
    "decision": "JEV returns probabilities, not prose. The veto reason delivered at the next turn names each failed condition in plain words with its confidence, so the participant knows which condition to address."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "judging context",
    "decision": "JEV sees the objective, the current topic, the accepted contributions of the current topic (newest whole messages first, oldest dropped first) and the candidate. The window size is a setting; Jev's documentation says accuracy falls as irrelevant state grows, so the default stays well under the 64K limit and is tuned by test."
  },
  {
    "by": "owner",
    "date": "2026-11-05",
    "topic": "JEV is optional; failure never halts",
    "owner_statement": "If JEV is down this doesn't halt, it continues. You can surface a setting to the user in the GUI, but JEV is an optional thing. It doesn't stop the agents from completing their task, which is more important. By halting you are losing the agents' caching and many compress. Halting can prove more expensive than not.",
    "decision": "Judging is a chair setting (on by default, switchable in the GUI). When it is off, contributions are truncated to the allowance and distributed unjudged. When it is on and JEV fails or does not answer within a short deadline, the contribution is distributed unjudged, marked 'unjudged: JEV unavailable' in the discussion record, and the chair is notified on the event bus. No blocking retries, and the table never waits on JEV. An unjudged distributed contribution counts as accepted for allowance and round accounting.",
    "supersedes": "Claude's earlier decision that the table waits while JEV is unavailable. That was wrong: it put an optional efficiency gate ahead of the agents completing the task, and idle agents lose prompt caches and pay for extra compression."
  },
  {
    "by": "owner",
    "date": "2026-11-07",
    "topic": "the owner's questions",
    "decision": "The three gates use the owner's questions word for word, with no TRUE/FALSE criteria and no field names. On the same message, relevance rose from 0.70 to 0.94.",
    "owner_statement": "How about using my prompts exactly and removing the contribution text use these questions exactly in my words change nothing"
  },
  {
    "by": "owner",
    "date": "2026-11-07",
    "topic": "threshold",
    "decision": "The gates pass at 70%. 60% was tried and removed.",
    "owner_statement": "60 was trying to push through the faulty wording that doesn't work right."
  },
  {
    "by": "owner",
    "date": "2026-11-07",
    "topic": "value and auditability",
    "decision": "Two scores from the owner's evaluation specification: value (decision usefulness) and auditability (whether the moderator can inspect the reasoning from the messages alone).",
    "owner_statement": "plus it makes the roundtable actually able to be read and understood and not just a ball of cryptic wasted tokens."
  }
]
```

## Layer `superseded`
```json
[
  {
    "date": "2026-11-07",
    "rule": "Three conditions: (1) new contribution or a position on a recently raised matter, (2) value toward answering the question, (3) relevance to the subject."
  },
  {
    "date": "2026-11-07",
    "rule": "Each condition needs at least 70% confidence; all three must pass."
  },
  {
    "date": "2026-11-07",
    "rule": "The three judgments may be requested in one inference."
  },
  {
    "date": "2026-11-07",
    "rule": "Evaluation happens once, before distribution."
  }
]
```

## Layer `gates`
```json
[
  {
    "gate_id": "RT-G01",
    "name": "The five message checks",
    "status": "active, owner-designed",
    "registry": "docs/gate-registry.yaml"
  },
  {
    "gate_id": "RT-G17",
    "name": "JEV sees only recent rounds, within its token limits",
    "status": "active, owner-designed",
    "registry": "docs/gate-registry.yaml"
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Share only messages that pass the owner's five checks, and tell the author exactly why a message was rejected.",
  "sources": [
    "owner's message evaluation specification, 2026-11-07",
    "owner's three questions, 2026-11-07"
  ],
  "built": "jev.rs asks JEV the five checks in one request; turn.rs shares a message only if every gate is at 0.70 or higher and both scores at 3.0 or higher.",
  "gaps": [
    "The token count for JEV's limits is an estimate.",
    "JEV requests are not saved in the table record, so a decision can only be rebuilt afterwards."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, wants (both lines)): Say 'three 70% conditions' and that JEV returns 'reasons'. There are five checks (src/jev.rs:43-59) and ask() returns numbers only (src/jev.rs:163-173); the reasons are the owner's fixed feedback files (src/prompts.rs:26-54).
- **GF2** (Blocker, egm-codebase-details, decisions: reasons): Says the veto names each failed condition with its confidence. The author gets '- Label: <owner feedback>' with no confidence (src/prompts.rs:44-54); confidences go only to the chair-facing event (src/turn.rs:225).
- **GF3** (Blocker, egm-codebase-details, decisions: JEV is optional): Claims truncation when judging is off, a 'short deadline', and 'the table never waits on JEV'. Nothing is truncated (src/turn.rs:128-150), there is no deadline (src/jev.rs:3), and the next turn waits for the verdict (src/turn.rs:170-173, src/engine.rs:510-513).
- **GF4** (Blocker, egm-codebase-details, decisions: judging context): Says JEV sees the objective and the current topic's messages, with the window as a setting. The state is topic, last 4 rounds plus the current one, and new_message, with no objective (src/jev.rs:78-103); the limits are constants (src/jev.rs:62-66).
- **GF5** (Major, egm-codebase-details, rules[4]): Unstated: the conversation includes chair guidance (src/jev.rs:85); a message that cannot fit is shared unjudged with a loud notice (src/jev.rs:97-98, src/turn.rs:161-167); the topic is the one from when the turn started (src/turn.rs:160); missing or out-of-range answers are errors (src/jev.rs:168-171); after-work replies do not block turns (src/turn.rs:170).
- **GF6** (Nit, egm-codebase-details, superseded; rules[5]): 'Evaluation happens once, before distribution' is listed as superseded but is still current (src/turn.rs:125-182). With judging off or no key, no error is shown, only an event note (src/turn.rs:148-154).
- **GF7** (Major, egm-comprehension, wants (both directions) vs rules; decision 'reasons'): The engine's dependency says 'three 70% conditions' and the upstream dependency says 'three conditions with reasons', while the rules say five checks including two 0-5 scores. The 'reasons' decision (probabilities, not prose) conflicts with the upstream 'reasons' and with the per-check owner feedback rule.
- **GF8** (Major, egm-comprehension, decision 'judging context' vs rules (JEV's state)): The decision gives objective + topic + current topic's messages under '64K'; the rule gives topic + last four rounds + current round under '32,000 and 64,000 token limits'. The two limits are unexplained, the objective is missing from the rule, and what 'topic' holds when topics are off is unstated.
- **GF9** (Major, egm-comprehension, owner decision 'JEV is optional'; rules; engine gate RT-G10): The decision says 'truncated to the allowance' though truncation was removed; the failure marking and chair notice vs 'the error is shown' (where?) are not reconciled. RT-G10 'next turn waits for JEV's verdict' contradicts 'the table never waits on JEV'.
- **GF10** (Major, egm-comprehension, terminology): JEV is never expanded or linked, nor is 'Jev's documentation'. Undefined: owner's prefix, score band, value/auditability rubrics (pointed to only by a directory), moderator, true-means-pass statement, Python's chassis, 'no TRUE/FALSE criteria and no field names'.
- **GF11** (Nit, egm-comprehension, Layer superseded): 'Evaluation happens once, before distribution' and 'may be requested in one inference' are marked superseded, yet the current rules still describe one evaluation in one request before sharing; what replaced them is not said.
- **GF12** (Nit, egm-comprehension, elephant gaps): 'A decision can only be rebuilt afterwards' is unclear (it seems to mean it cannot be audited directly) and sits awkwardly with the auditability goal.

The code for this part is copied into the `source` folder here, under the same paths as above.
