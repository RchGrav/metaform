# Map element `downstream.chair`: user

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "user",
  "name_length": 1,
  "role": "CQU"
}
```

## What it relies on (its wants)
- `code.manager.chat.group`: goal: Get a substantive deliverable for an objective (a specification, a design, software) from several independently reasoning models working together. Function: Runs a turn-based, judged discussion among heterogeneous agents who share a workspace, continuing across topics until the work is produced. Intent: send_receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "1 Theory of Operation",
      "11 Intended Productive Behavior"
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
    "decision": "CQU is the chair: the person who convenes a Roundtable, sets its objective and selects its participants, and whose need for the deliverable drives improvements. The run 1 audit uses the same term (observation-only human chair). 'user' is invalid as a CQU under Intake 3.1, so it is the alias, not the address."
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Let the user start a table, follow the discussion, and hold, guide or end it.",
  "sources": [
    "README.md §1",
    "owner, 2026-11-07: \"the intent is for me to be able to interact with them\""
  ],
  "built": "The web page shows every message, rejection and score, and has hold, resume, guidance and end controls.",
  "gaps": []
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, elephant.built): Scores are not all shown: accepted messages' scores are stored (index.html:234) but never rendered (index.html:343-355). Vetoes show only failed-check reason strings (turn.rs:225; index.html:346).
- **GF2** (Major, egm-codebase-details, wants (function)): 'Continuing across topics until the work is produced' contradicts the defaults: topics off (tables.rs:32-34; config.rs:150-153), 10-round limit (tables.rs:29-30; engine.rs:636-640), unlimited tables end after two unproductive rounds (engine.rs:647-651).
- **GF3** (Major, egm-codebase-details, elephant.built (end control)): First End starts the rating round; the table ends after results (engine.rs:901-908; turn.rs:420-434, 564-575); a second End stops it at once. The page confirm says harnesses are shut down (index.html:406).
- **GF4** (Major, egm-codebase-details, missing detail): Undocumented: advance topic (index.html:119, 405), judging toggle (index.html:108, 407), OpenRouter key settings (index.html:154; app.rs:234-243), past-table replay (app.rs:279-341; index.html:371-401), prompts-received panel (index.html:255, 321-331), identity resume (index.html:412-457).
- **GF5** (Major, egm-codebase-details, unstated assumption): Chair token required on all /api routes plus a Host/Origin check (app.rs:4-7, 170-199); the token comes from the URL fragment printed at startup (index.html:164-168, 468).
- **GF6** (Nit, egm-codebase-details, details): index.html:234 reads d.truncated, which Contribution lacks (events.rs:39-50); the client defaults the limit to 512 against the engine's none (index.html:177); Hold only stops new turns (engine.rs:500); the gaps list is empty.
- **GF7** (Major, egm-comprehension, decisions vs elephant): The decision cites an 'observation-only human chair', while the elephant layer and the owner quote describe an interacting chair (hold, guide, end); the two are not reconciled.
- **GF8** (Major, egm-comprehension, title, Properties, decisions): CQU, Intake 3.1, address vs alias, and why 'user' is invalid are undefined; the element is titled and named 'user' but addressed downstream.chair.
- **GF9** (Major, egm-comprehension, elephant.gaps vs decisions): The decision says the chair sets the objective and selects participants, but built lists neither, and gaps is empty.
- **GF10** (Nit, egm-comprehension, elephant.built (guidance)): What the guidance control does is not stated: who receives it, when, and whether JEV judges it.
- **GF11** (Nit, egm-comprehension, elephant.built): Where the web page is served and how it is reached are not stated; table, rejection and JEV are undefined.
- **GF12** (Nit, egm-comprehension, want from code.manager.chat.group): 'Until the work is produced' doesn't say who decides the work is done.

The code for this part is copied into the `source` folder here, under the same paths as above.
