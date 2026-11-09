# Map element `code.roster.participant`: participant selection

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "participant selection",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/roundtable-web/src/tables.rs"
}
```

## What other parts rely on it for (their wants)
- `code.manager.chat.group`: goal: Seat the participants the chair selected. Function: Provides each seat's harness and, where applicable, its OpenRouter model id. Intent: receive

## What it relies on (its wants)
- `code.catalog.model`: goal: Offer the OpenRouter models a participant can use. Function: Lists current OpenRouter model ids. Intent: receive
- `code.launcher.agent`: goal: Offer the harnesses a participant can run in. Function: Lists registered harnesses, catalog aliases and user-supplied ACP commands. Intent: receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "9 Universal Agent Harness and Model Selection"
    ]
  },
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "3 Discovery is not a universal local executable scanner",
      "9 Integration traceability"
    ]
  }
]
```

## Layer `rules`
```json
[
  "Harness selection and model selection are separate dimensions; an OpenRouter model id is not an ACP harness.",
  "Locally installed or unregistered ACP commands must be selectable."
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Let the chair seat agents from different harnesses and OpenRouter models.",
  "sources": [
    "README.md §9.3-9.4"
  ],
  "built": "roundtable-web/src/tables.rs builds the seats from the chair's choices; the page offers the harness catalog and the models.",
  "gaps": []
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Major, egm-codebase-details, built / wants (missing)): The openrouter-acp adapter entry added at the front of the catalog is not mentioned (crates/roundtable-web/src/tables.rs:73-99); its script path is fixed at compile time from CARGO_MANIFEST_DIR, and it is unavailable with a build note when missing (tables.rs:85-96).
- **GF2** (Major, egm-codebase-details, missing logic: defaults): Catalog seats get default_env (OpenCode permission routing) and default_settings (claude mode default, codex workspace-write) (tables.rs:116-119; crates/roundtable/src/config.rs:198-218); order is defaults, then seat settings, then model (tables.rs:123-126); custom-command seats get no defaults (tables.rs:107-108).
- **GF3** (Major, egm-codebase-details, their wants / relies-on wants): 'where applicable, its OpenRouter model id' is narrower than the code: model is a generic session option for any harness (tables.rs:59-61, 124-126); the 'catalog aliases' want names a concept that does not exist.
- **GF4** (Major, egm-codebase-details, missing seat fields): Undocumented: share_openrouter_key (page auto-ticks it, crates/roundtable-web/assets/index.html:436-441), resume_session with the identity picker (index.html:412-450; tables.rs:127), and removal of Roundtable secrets from agents (config.rs:52-81).
- **GF5** (Major, egm-codebase-details, validation rules (missing)): A seat needs a harness or command (tables.rs:121); command wins over harness (tables.rs:106-109); unknown or unlaunchable ids are errors (tables.rs:114-115); names 1-40 allowed chars, unique ignoring case (config.rs:96-131); relative workspace resolved against the server's cwd (tables.rs:132).
- **GF6** (Nit, egm-codebase-details, page): Harness ordering (available first, non-built-in before built-in, then name; index.html:469) and unavailable entries shown disabled (index.html:420) are undocumented.
- **GF7** (Major, egm-comprehension, rules / 'where applicable'): It does not explain how harness and model combine: whether OpenRouter seats use the OpenRouter adapter as their harness, and whether non-OpenRouter harnesses accept a model choice.
- **GF8** (Major, egm-comprehension, terms: chair, seat, table): Central terms are undefined, including whether the chair is a human or an agent.
- **GF9** (Major, egm-comprehension, constraints): Seat count limits, duplicates, and whether the evaluator is chosen here are not specified.
- **GF10** (Nit, egm-comprehension, Properties uri / scope): Unclear whether the element is UI only or also validates and stores the roster; the package property is missing, unlike siblings.
- **GF11** (Nit, egm-comprehension, references vs elephant.sources): References cite README 9 and design 3/9 while elephant cites README 9.3-9.4.

The code for this part is copied into the `source` folder here, under the same paths as above.
