# Map element `upstream.system.reputation`: accolades

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "accolades",
  "name_length": 2,
  "uri": "archaeology/src/metaform/modules/roundtables/roundtable/resources/prompts.xml"
}
```

## What other parts rely on it for (their wants)
- `code.server.tool`: goal: Let participants reward one another's good conduct. Function: Records a participant's rating of another participant's behavior toward accolades and identity. Intent: send

## Layer `owner_statements`
```json
[
  {
    "date": "2026-11-05",
    "statement": "I have agents rate each other's behavior. This leads to accolades and an identity. It weights them higher than other agents to return into the project, and the accolade system is meant to give them reward and stake for doing well, something I reason they deserve."
  }
]
```

## Layer `archaeology`
```json
[
  {
    "finding": "Python scorecard: each participant rates every other by name, 0-5 stars in Efficient, Alert & Aware, Thorough, Coordination, plus a bonus true/false; ranking per session and a rating across sessions; a profile score shown to the agent.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/resources/prompts.xml:343-368; store.py:422-454; stages.py:161; runner.py:1499"
  }
]
```

## Layer `investigations`
```json
[
  {
    "topic": "ownership",
    "note": "Accolades, identity and weighting for return into a project reach beyond one Roundtable (compare topogee's deterministic agent identity and post-retirement recall). Treated as a platform service Roundtable feeds; where it lives and how the weighting is applied is not yet specified."
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "The owner's earlier accolades system, where agents earned recognition.",
  "sources": [
    "owner's earlier system (archaeology, not in this repo)"
  ],
  "built": "Not built here; peer ratings (code.rating.peer) cover part of it.",
  "gaps": [
    "The source path points into ~/roundtable/archaeology, which is not in this repo."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, elephant.built 'Not built here'): Contradicts the code: the code.server.tool want is built as the MCP 'feedback' tool (mcp.rs:22-36, 84-104), which leads to FeedbackGiven keyed by to_session (engine.rs:882-898). That is saved to the identity profile's feedback list (app.rs:533-545) and appended to $ROUNDTABLE_HOME/accolades.jsonl (app.rs:69, 103-111). The session ranking, rating across sessions and profile score shown to the agent are also built (turn.rs:37-50, 516-544). Only the return weighting is missing.
- **GF2** (Major, egm-codebase-details, Properties.uri; archaeology.path): Both cite archaeology/src/.../prompts.xml, which does not exist in the repository. The in-repo copy is docs/owner-sources/roundtable-agent-ratings.md, and the roundtable-accolades.md it cites is not in the repo either.
- **GF3** (Major, egm-codebase-details, owner statement vs code): Not documented: accolades.jsonl receives only mid-table feedback, which adds no points (app.rs:533-534, 703-704). End-of-table ratings add points but are not logged to accolades (app.rs:98-102 against 103-111). The document does not say which path feeds accolades and which feeds the score.
- **GF4** (Nit, egm-codebase-details, investigations weighting): Nothing weights agents for return. Points are used only to sort the identities list (app.rs:547-568) and to label the resume picker (index.html:416-417); worth recording to make 'not yet specified' concrete.
- **GF5** (Major, egm-comprehension, owner_statements, 'accolade'): The element's own name is never defined. It's unclear what an accolade concretely is or how ratings become one, so only a high-level paraphrase is possible.
- **GF6** (Major, egm-comprehension, wants): code.server.tool (never introduced) relies on an element that is 'not built here'. The function 'toward accolades and identity' doesn't say what the dependency delivers today.
- **GF7** (Major, egm-comprehension, properties.uri vs elephant.gaps): The header says paths are relative to the Roundtable folder, so archaeology/... looks in-repo, but the gap says it's in ~/roundtable/archaeology outside the repo. 'Archaeology' is never explained, and the source can't be found.
- **GF8** (Major, egm-comprehension, elephant.built): 'Peer ratings cover part of it' doesn't say which part is covered and which is missing (cross-session rating, profile score, weighting for return). The 0-5 star / true-false bonus scale is never reconciled with the current scale.
- **GF9** (Major, egm-comprehension, investigations): 'topogee', 'deterministic agent identity', 'post-retirement recall', 'platform service', 'return into a project' and agent 'retirement' are all undefined.
- **GF10** (Nit, egm-comprehension, properties / address prefix): This element has no role, unlike the others. The 'upstream.' prefix and the metadata fields (name_length, intent labels) are never explained.

The code for this part is copied into the `source` folder here, under the same paths as above.
