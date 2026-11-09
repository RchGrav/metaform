# Map element `code.identity.agent`: agent genesis names

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "agent genesis names",
  "name_length": 3,
  "role": "SE",
  "uri": "crates/roundtable/src/names.rs"
}
```

## What other parts rely on it for (their wants)
- `code.manager.chat.group`: goal: Give each agent a stable identity across tables. Function: Derives the agent's name from its first session id. Intent: receive

## Layer `rules`
```json
[
  "An agent's name comes from its first session id (FNV-1a, folded to 16 bits, one of 256 adjectives and 256 nouns); a resumed session keeps its name.",
  "Agents see each other's names, not their models; the chair sees both."
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Give each agent a stable name derived from its first session.",
  "sources": [
    "owner's agent identity document (earlier system)"
  ],
  "built": "names.rs derives the name; a resumed session keeps it.",
  "gaps": [
    "Two agents can share a name; ratings are kept by session, not by name."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Major, egm-codebase-details, want: stable identity across tables): A seat that is not resumed opens a new session and so gets a new name and a new profile (engine.rs:822). Identity is stable only when the chair chooses to resume (index.html:412-456 sets resume_session); the document does not say so.
- **GF2** (Major, egm-codebase-details, rules[0] 'a resumed session keeps its name'): The mechanism is not stated: the name is derived from the id the harness returns (engine.rs:822), and acp-host returns the requested id unchanged (acp-host/src/harness.rs:427). The input is SeatConfig.resume_session (config.rs:23-28) and must go to the harness that holds the session. With neither session/resume nor session/load the seat fails to start, with no fallback (harness.rs:403-410, engine.rs:834-841).
- **GF3** (Major, egm-codebase-details, elephant.gaps shared names): Session-keyed storage is right (app.rs:426-430, config.rs:46-48), but the document leaves out that two same-named agents at one table cannot rate or give feedback to each other, because matching by name rejects ambiguous matches (turn.rs:463-467, engine.rs:886-891).
- **GF4** (Nit, egm-codebase-details, rules[0] algorithm): Missing: offset 2166136261 and prime 16777619; fold (h ^ h>>16) & 0xFFFF; high byte picks the adjective, low byte the noun, each capitalised (names.rs:11-19); word lists in resources/names/*.txt (names.rs:8-9); 'agent' fallback for a short list (names.rs:17).
- **GF5** (Major, egm-comprehension, rules[0], 'session id' / 'resumed session'): The document doesn't say whose session this is, who issues the id, what makes a session 'first', or how resuming works. The whole design rests on these terms.
- **GF6** (Major, egm-comprehension, wants vs elephant.gaps): The want is a stable identity across tables, but the name only survives on resume, names can collide, and ratings are keyed by session. The real identity key is never named, so the name doesn't meet the stated want.
- **GF7** (Major, egm-comprehension, rules[1], 'the chair'): 'Chair' is undefined. The header mentions only agents and an evaluator, and it's unclear whether the chair is the evaluator, the user or the manager.
- **GF8** (Major, egm-comprehension, rules[0], derivation): It doesn't say how the 16 bits map to the two lists, where the word lists live, what a name looks like, or what 'genesis' in the title means.
- **GF9** (Nit, egm-comprehension, rules[1]): No reason is given for hiding models from agents. This visibility rule is a different job from name derivation and isn't marked as such.
- **GF10** (Nit, egm-comprehension, elephant.sources): 'owner's agent identity document (earlier system)' has no path or link, so it can't be checked.

The code for this part is copied into the `source` folder here, under the same paths as above.
