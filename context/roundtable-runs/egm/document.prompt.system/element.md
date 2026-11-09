# Map element `document.prompt.system`: Participant System Prompt

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "Participant System Prompt",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/roundtable/resources/roundtable_prompt.md"
}
```

## What other parts rely on it for (their wants)
- `code.builder.prompt`: goal: Give every participant the same explanation of the Roundtable process. Function: Supplies the common participant instructions for the first turn of each session. Intent: receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "3 Participant System Prompt"
    ]
  },
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "2 Common participant prompt",
      "ACP compatibility note"
    ]
  },
  {
    "path": "crates/roundtable/resources/participant_prompt.md"
  }
]
```

## Layer `investigations`
```json
[
  {
    "topic": "delivery",
    "note": "ACP has no universal system-prompt setter. Deliver as content of the first session/prompt; use a harness extension (e.g. Claude _meta.systemPrompt on session/new) only where that harness advertises it."
  }
]
```

## Layer `decisions`
```json
[
  {
    "by": "owner",
    "date": "2026-11-07",
    "topic": "prompt texts",
    "decision": "Two owner texts: the roundtable prompt (from the evaluation specification) and the participant prompt. The credit sentence and the length and truncation lines were deleted at the owner's request; nothing was reworded."
  }
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Tell every agent, once, what the roundtable is, its objective and how its messages are judged, in the owner's words.",
  "sources": [
    "resources/roundtable_prompt.md and resources/participant_prompt.md (owner's texts)"
  ],
  "built": "Sent on each agent's first turn, with the participant prompt inside the roundtable prompt.",
  "gaps": [
    "\"Topics may change\" is not true while topics are off.",
    "Nothing tells an agent that its reply is the message the others receive."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Major, egm-codebase-details, wants; elephant.built): Sent on a seat's first prompt of any kind at each table (turn.rs:37, 69-81; engine.rs:324). Resumed sessions (config.rs:23-28; engine.rs:976-977) receive it again, so it is not once per session.
- **GF2** (Major, egm-codebase-details, missing logic): Placeholder mapping undocumented: AgentName = genesis name or label; roundtable_subject = topic, defaulting to the objective (engine.rs:306); artifact_directory = canonical workspace; roundtable_prompt = objective; delivery_json = plain text, not JSON (prompts.rs:12-14, 73-83; turn.rs:69-78).
- **GF3** (Major, egm-codebase-details, gaps): Missing gap: roundtable_prompt.md:8 always describes JEV evaluation, but messages are shared unjudged when judging is off, there is no key, or JEV fails (turn.rs:148-155, 161-167, 199-203).
- **GF4** (Major, egm-codebase-details, missing detail): First-turn delivery contents undocumented: round line, returning-identity session_profile (turn.rs:37-50), notices, others' messages and chair guidance, special request; later turns add 'Current topic:' when topics are on (turn.rs:57-59).
- **GF5** (Nit, egm-codebase-details, investigations): No harness-extension delivery (e.g. _meta.systemPrompt) exists; the prompt is always the content of the session prompt (engine.rs:599).
- **GF6** (Nit, egm-codebase-details, properties; gaps): Named 'Participant System Prompt' but the uri is roundtable_prompt.md. The second gap should say only the final block after the last tool call becomes the message (engine.rs:691-699; acp-host events.rs:147-149).
- **GF7** (Major, egm-comprehension, Properties.name/uri vs references vs elephant.built): The document doesn't say whether this element is the roundtable prompt, the participant prompt, or their composition. It is named Participant System Prompt but its uri is roundtable_prompt.md.
- **GF8** (Major, egm-comprehension, elephant.gaps): 'While topics are off' refers to a mode that is never introduced: what it is, who sets it, and whether it is the default.
- **GF9** (Major, egm-comprehension, decisions): The credit sentence and length/truncation lines are not described, and the consequence (whether agents are told about limits anywhere, given that truncation and vetoes exist) is unstated.
- **GF10** (Nit, egm-comprehension, investigations vs elephant.built): The document doesn't say which delivery path was chosen (first-prompt content or _meta.systemPrompt) or what happens on a session restart.
- **GF11** (Nit, egm-comprehension, Properties.name_length): name_length is 2 but the name has three words; the field is undefined.
- **GF12** (Nit, egm-comprehension, investigations, decisions, Properties): ACP, harness, session/prompt, session/new, _meta.systemPrompt, evaluation specification, and the map fields role and Intent are undefined.

The code for this part is copied into the `source` folder here, under the same paths as above.
