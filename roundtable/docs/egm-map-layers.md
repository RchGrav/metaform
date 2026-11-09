# EGM layers on the Roundtable map

This document says how the Elephant-Goldfish Model (EGM) adds two layers to every element of the Roundtable map, and how a Roundtable then works through each element's goldfish layer.

- The map is the project `roundtable` in the map server, for the folder `topogee/roundtable`. It is exported as `roundtable/metaform.json`.
- A layer is an object or an array on an element, for example `goldfish: {}` (owner, 2026-11-07). Every element gets both layers.
- Only the map server writes the map. Layers are written by importing the updated map document through it.

## The two roles

| Role | Context | Writes |
|---|---|---|
| Elephant | The whole project: the owner's design documents, the owner's decisions, the code, the history | `elephant: {}` on every element |
| Goldfish | Only what it is given: the element's map entry and the element's source files. No conversation, no history | `goldfish: {}` on every element |

The elephant is the agent that holds the project context, the root agent in EGM. A goldfish is a fresh subagent with no earlier context. EGM's own reviewer prompts are used: `egm-comprehension` (a naive reader) and `egm-codebase-details` (does the description match the code).

## Step 1: the elephant layer

For each element, the elephant writes what the owner's design asks of it and what the code does now:

```json
"elephant": {
  "date": "2026-11-07",
  "design": "What the owner's design says this element must do, in plain words.",
  "sources": ["README.md §5.1", "owner, 2026-11-07: ..."],
  "built": "What the code does now.",
  "gaps": ["Where the code and the design differ, or what is not built."]
}
```

The elephant states only what its sources support. Owner decisions are quoted, not paraphrased.

## Step 2: the goldfish layer

The elephant gives each goldfish only:

1. the element's map entry, including its elephant layer, as a document; and
2. the paths of the element's source files.

Each goldfish reviews in `Mode: REVIEW` with its own lens and returns findings. The elephant records them unchanged:

```json
"goldfish": {
  "date": "2026-11-07",
  "lenses": ["egm-comprehension", "egm-codebase-details"],
  "paraphrase": "The goldfish's own account of what this element is.",
  "findings": [
    {"id": "GF1", "lens": "egm-codebase-details", "severity": "Blocker | Major | Nit",
     "scope": "rules[2]", "finding": "What is wrong or missing, with the code location."}
  ]
}
```

To keep the number of subagents reasonable, one goldfish reviews a group of elements with one lens. Each element is still reviewed with no conversation context.

## Step 3: a Roundtable for each goldfish layer

Each element's goldfish layer is worked through by its own Roundtable:

- **Rounds:** 3.
- **Seats:** the owner's usual roster.
- **Workspace:** a new folder holding `element.md` (the element's map entry and both layers, written readably) and the paths of its source files.
- **Objective,** in plain words, with no project shorthand:

  > Resolve the review findings for the part of Roundtable called "<name>". The part's description and the findings are in element.md in this folder; its code is at <paths>. For each finding, decide whether it is right. If it is, say what should change in the code or in the description, and why. If it is not, explain why. Write the decisions to resolution.md in this folder.

- **Checks:** the owner's five message checks, as in any table.

When the table ends, the elephant records the outcome on the element:

```json
"roundtable": {
  "table": "t…",
  "date": "2026-11-07",
  "rounds": 3,
  "seats": 5,
  "accepted_messages": 0,
  "rejected_messages": 0,
  "ended": "ended by the chair",
  "workspace": "/home/rich/roundtable-runs/egm/<element>",
  "resolution_file": "docs/egm-resolutions/<element>.md",
  "resolution": "the full text of resolution.md"
}
```

Each resolution is also kept in the repo at `roundtable/docs/egm-resolutions/<element>.md`.

The Roundtable's decisions are proposals. Changes to code, to the owner's design, or to the map's description are made only with the owner's approval.

## What the first run showed (2026-11-07)

- All 26 tables wrote a resolution. Across them, 146 messages were accepted and 240 rejected.
- **Rounds pass quickly when agents work in files.** A round counts every turn opportunity, including turns skipped because an agent is busy. A table where agents mostly write files can finish its 3 rounds in about a minute. The agents' file work continues regardless.
- **The rating round waits for every agent.** One table's rating round waited about 40 minutes on an agent whose turn never ended; the chair ended it. Roundtable has no timers by design, so a stalled agent holds the table until the chair acts.

## Order of work

1. Write every elephant layer and import the map.
2. Run the goldfish reviews, write every goldfish layer and import the map.
3. Run one 3-round Roundtable per element, a few at a time.
4. Write every roundtable layer and import the map.
5. Export the map to `roundtable/metaform.json` and commit it.
