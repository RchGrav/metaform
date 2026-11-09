# Map element `code.rating.peer`: peer rating round

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "peer rating round",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/roundtable/src/turn.rs"
}
```

## What other parts rely on it for (their wants)
- `code.manager.chat.group`: goal: Record how each agent performed when the table ends. Function: Collects every agent's ratings of the others and returns the results. Intent: send_receive

## Layer `rules`
```json
[
  "When a table ends, each agent rates every other in the owner's categories (Efficient 10, Alert & Aware 20, Thorough 30, Coordination 40, bonus +5) using the owner's scoring prompt.",
  "Each agent then receives the owner's results message; ratings are saved to each agent's identity."
]
```

## Layer `owner_statements`
```json
[
  {
    "date": "2026-11-06",
    "statement": "what about agent ratings at the end and saving the agents rating"
  }
]
```

## Layer `references`
```json
[
  {
    "path": "crates/roundtable/resources/session_scoring.md"
  },
  {
    "path": "docs/owner-sources/roundtable-agent-ratings.md"
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "When a table ends, agents rate each other in the owner's categories, and ratings stay with each agent's identity.",
  "sources": [
    "owner, 2026-11-06: \"what about agent ratings at the end and saving the agents rating\""
  ],
  "built": "turn.rs sends the owner's scoring prompt, records each scorecard and sends the owner's results message.",
  "gaps": [
    "Ratings carry to a later table only if that table resumes the agent's earlier session."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Major, egm-codebase-details, rules[0] trigger and participants): 'When a table ends, each agent rates every other' overstates it: the round starts only on chair End (engine.rs:906), the last round (engine.rs:636-639) or two quiet rounds with no limit (engine.rs:647-650). It is skipped with fewer than two ready, named seats (turn.rs:421-425), on a second End (engine.rs:903) and on other ends (engine.rs:791, 840). Departed seats are dropped (engine.rs:723-724) and missing ratings get a notice with no retry (turn.rs:493-497).
- **GF2** (Major, egm-codebase-details, rules[0] categories and weights): The scoring rule is missing: stars clamped to 0-5 times weight/5, plus 5 for the bonus, at most 105 (rules.rs:150-162). Missing or non-numeric categories silently count as 0 (rules.rs:158). The ranking sorts by summed session points, rating = earlier profile score + session points, 'unscored' when there are none (turn.rs:529-544).
- **GF3** (Major, egm-codebase-details, rules[1] saving; elephant.built): turn.rs only adds up points and publishes roundtable.rating (turn.rs:471-484); the core only reads profiles (config.rs:42-50). Saving is the web host's save_rating to $ROUNDTABLE_HOME/identities/<session>.json (app.rs:60-70, 98-102, 498-509), and only tables.rs:151 passes an identity store (spawn passes None, engine.rs:255). The document never names the host or the storage.
- **GF4** (Major, egm-codebase-details, failure modes): Undocumented: JSON taken from the first '{' to the last '}' (turn.rs:450); unreadable JSON records nothing; cards that are not objects are rejected (turn.rs:456-461); names matching zero or several other seats are not recorded (turn.rs:463-467), so two agents with the same name at one table cannot rate each other.
- **GF5** (Major, egm-codebase-details, rules[1] messages): Leaves out the score_received receipt (turn.rs:498-501) and the session_profile line a returning identity gets on its first turn (turn.rs:37-50). Results go only to seats still ready, named and idle, and the table ends once all are sent (turn.rs:551-575).
- **GF6** (Nit, egm-codebase-details, rules[0] 'owner's scoring prompt'): session_scoring.md:3-10 adds the worker rubric table, which the owner's roundtable prompt does not contain (docs/owner-sources/roundtable-agent-ratings.md:57-61, 113), though prompts.rs:92-93 calls the resource verbatim.
- **GF7** (Major, egm-comprehension, rules[0]): The numbers 'Efficient 10, Alert & Aware 20, Thorough 30, Coordination 40, bonus +5' are never explained. They could be maximum points, weights or percentages. The scale of one rating and the bonus criteria are not stated, so you can't tell what a scorecard holds.
- **GF8** (Major, egm-comprehension, rules[1] / elephant.design / elephant.gaps): Ratings are 'saved to each agent's identity', yet only carry over if the session is resumed. 'Identity' is never defined or linked (code.identity.agent), and the storage location is never given. Whether ratings persist can't be told.
- **GF9** (Major, egm-comprehension, wants vs rules[1]): The manager wants the element to 'return the results', while the agents 'receive the owner's results message'. What the results are (scores, totals, rankings) and what goes to the manager versus the agents is not stated.
- **GF10** (Major, egm-comprehension, rules[0], 'table'): 'Table' is never defined, and nothing says what ends one. It's unclear whether the evaluator or chair takes part, and what happens to agents that left or don't answer the scoring prompt.
- **GF11** (Nit, egm-comprehension, references): The reference paths have no note on what each file is. That session_scoring.md is 'the owner's scoring prompt' is implied, not stated. The 'owner' is never introduced.
- **GF12** (Nit, egm-comprehension, owner_statements): The only owner statement is a question. The document doesn't say how it became the specific categories and weights in the rules.

The code for this part is copied into the `source` folder here, under the same paths as above.
