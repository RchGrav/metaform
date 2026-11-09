# Map element `code.builder.prompt`: participant turn prompt

This document is one element of the functional map of Roundtable, a program in which several AI agents discuss a user's objective in turns while an evaluator checks each message. The map records what each part of the program must do, what it relies on, and knowledge about it. Paths are relative to the Roundtable folder.

## Properties
```json
{
  "name": "participant turn prompt",
  "name_length": 2,
  "role": "SE",
  "uri": "crates/roundtable/src/turn.rs"
}
```

## What other parts rely on it for (their wants)
- `code.manager.chat.group`: goal: Brief the next participant for its turn. Function: Assembles the participant's turn: the round line, its pending rejection reasons, and the other agents' new accepted messages; on its first turn, the owner's prompts. Intent: receive

## What it relies on (its wants)
- `code.quota.character`: goal: Tell the participant how many characters it may contribute. Function: Reports the participant's current speaking allowance. Intent: receive
- `data.log.discussion`: goal: Tell the participant what happened since its last turn. Function: Provides the accepted contributions since that participant's last turn, its own pending veto or truncation disposition, and the current topic and objective. Intent: receive
- `document.prompt.system`: goal: Give every participant the same explanation of the Roundtable process. Function: Supplies the common participant instructions for the first turn of each session. Intent: receive

## Layer `references`
```json
[
  {
    "path": "README.md",
    "sections": [
      "3 Participant System Prompt (last paragraph)",
      "4.7 steps 2-3",
      "8 Continuity Across Topics"
    ]
  },
  {
    "path": "Roundtable_ACP_Integration_Design.md",
    "sections": [
      "2 item 1",
      "5.1 session/prompt"
    ]
  }
]
```

## Layer `investigations`
```json
[
  {
    "topic": "run 1 prompt failures",
    "note": "Operator reported the OpenRouter prompt was built wrong; prompts grew to 56,837-71,825 tokens; one model returned the same proposal 26 times; rendered prompts were not retained. Source: run 1 audit P01, P02, P07, E06."
  },
  {
    "topic": "spec section 11 vs prompt",
    "note": "README 11 expects agents to contribute established best answers rather than hand decisions back; the participant prompt (README 3) does not say so. Run 20 shows an agent deferring a decision 'to the owner' (archaeology/evidence/roundtable-20-delivered-prompts.txt R3-39). The prompt is owner-authored and is not changed here; raised for the owner."
  }
]
```

## Layer `archaeology`
```json
[
  {
    "finding": "The archive delivered accepted messages through an ordered per-agent inbox in the next session/prompt as 'R3-37 Name: text', with a send-receipt checkpoint and no mid-turn injection.",
    "path": "archaeology/specifications/12-roundtables.md RT-004"
  },
  {
    "finding": "A real delivered-prompt dump from run 20, useful as a reference for prompt shape. Generated agent names and the profile-score line ('Your profile score is 281') belong to the owner's accolade and identity system, not to be removed as gamification (correction 2026-11-05: an earlier note here wrongly called them leaked gamification). Redundant repeated instructions are the part to avoid.",
    "path": "archaeology/evidence/roundtable-20-delivered-prompts.txt"
  },
  {
    "finding": "Reusable fragments: turn allowance line, topic proposal prompt, message-reference convention [R1-1](R1-1) and file:line.",
    "path": "archaeology/src/metaform/modules/roundtables/roundtable/resources/prompts.xml:43-46,635,637-645"
  }
]
```

## Layer `decisions`
```json
[
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "delta delivery",
    "decision": "ACP sessions keep their own conversation, so each turn prompt carries only what is new since that participant's last turn: accepted contributions with canonical ids, its own pending disposition (veto reasons, characters removed), its allowance, and the topic when it changed. The full rendered prompt of every turn is stored in the discussion record."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "reply convention",
    "decision": "The turn prompt states the reply convention (contribution text, PASS, or WORK on the first line) in one short line, alongside the owner's participant prompt rather than inside it."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "kickoff strategy",
    "status": "per owner statements; wording open for owner",
    "decision": "The first turn prompt asks the group to agree a strategy for the objective: how they will coordinate, whether to divide the work or each pursue it with its own strategy, and suggests they elect a head of the table who can choose for the group. Strategy contributions go through the normal loop; no extra phase or gate."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "tools guidance",
    "decision": "The prompts explain the two participant tools in plain words: advance (normally used by the head of the table to end the current topic, optionally naming the next) and feedback (rate another participant's behavior; ratings build accolades and identity). The tools have no role checks."
  },
  {
    "by": "Claude",
    "date": "2026-11-05",
    "topic": "chair guidance",
    "decision": "Chair guidance is delivered to every participant in its next turn prompt, marked as from the chair. It is not judged by JEV: the gate exists to protect participants' attention from each other, not to filter the person they work for."
  },
  {
    "by": "owner",
    "date": "2026-11-07",
    "topic": "no characters line",
    "decision": "The 'You have N Characters to Respond' line is not sent.",
    "owner_statement": "I prefer not to have the message that reads \"You have 512 characters to reply.. I dont like that popping up"
  }
]
```

## Layer `rules`
```json
[
  "Each discussion turn starts with the round line: 'Round N of T', then '3 Rounds Remain', '2 Rounds Remain', '1 Round Remains', 'Final Round'; 'Round N' with no limit.",
  "Then the agent's own rejection reasons, if any, then each other agent's new accepted message as '[R1-2] Name: text'.",
  "No characters line and no instruction to reply.",
  "The first turn is the owner's roundtable prompt with the owner's participant prompt inside it and the first turn after 'Current delivery:'."
]
```

## Layer `elephant` (the project author's account of this element)
```json
{
  "date": "2026-11-07",
  "design": "Give each agent, at its turn, its own rejection reasons first, then the other agents' new accepted messages, in the owner's order.",
  "sources": [
    "README.md §4.7",
    "owner, 2026-11-06: \"Agent1 speaks, get vetoed, agent2, 3, 4 all speak, when it comes back to agent 1 it is informed ...\"",
    "owner, 2026-11-07: start each turn with the round count"
  ],
  "built": "turn.rs builds the turn: the round line, rejection reasons, then \"[R1-2] Name: text\" for each new accepted message. The first turn is the owner's roundtable prompt with the turn after \"Current delivery:\".",
  "gaps": [
    "An agent's work notes reach the others when they are in the same text block as its message (seen 2026-11-07).",
    "The objective appears twice on the first turn."
  ]
}
```

## The review findings to resolve

Two reviewers who had never seen this project read the description above and the code. Their findings follow. Severity: Blocker means the description says something the code does not do; Major means an important gap; Nit means a small one.

- **GF1** (Blocker, egm-codebase-details, decisions: reply convention): Says the prompt states the PASS/WORK convention. No prompt or resource mentions PASS or WORK (src/turn.rs:31-83, resources/roundtable_prompt.md, resources/participant_prompt.md).
- **GF2** (Blocker, egm-codebase-details, decisions: tools guidance; kickoff strategy): No prompt explains the advance or feedback tools, and none asks the group to agree a strategy. participant_prompt.md:19 only says 'You may choose to elect a head of the table upon agreement.'
- **GF3** (Blocker, egm-codebase-details, wants: code.quota.character): 'Reports the participant's current speaking allowance' contradicts the no-characters-line rule. turn_prompt adds no allowance (src/turn.rs:31-83); only the proposal ask names 512 (src/prompts.rs:86).
- **GF4** (Major, egm-codebase-details, decisions: delta delivery; wants: data.log.discussion): Claims the prompt carries characters removed, the allowance, and the objective every turn. Replies are blocked, not truncated (src/turn.rs:128-146), there is no allowance line, and the objective appears only on the first turn (src/turn.rs:69-78).
- **GF5** (Major, egm-codebase-details, rules[1]): Contents are incomplete. Notices also carry the too-long block notice (src/turn.rs:131) and the feedback-not-recorded notice (src/engine.rs:892); there is a 'Current topic:' line when topics are on (src/turn.rs:57-59), 'Chair: text' entries (src/turn.rs:63), and a returning identity's profile line on the first turn (src/turn.rs:37-51).
- **GF6** (Nit, egm-codebase-details, rules[0]): Unstated: the round line and notices go only to discussion turns, floor or review (src/turn.rs:34-36, 52-55); special asks (review, proposal, rating, results) are appended last (src/turn.rs:67).
- **GF7** (Major, egm-comprehension, wants (code.quota.character); decision 'delta delivery'): Relies on the reply-limit element to tell the agent its character allowance and sends 'its allowance' and 'characters removed', but the owner removed the characters line and truncation no longer exists. The dependency and decision are stale but read as active.
- **GF8** (Major, egm-comprehension, decision 'reply convention' vs rules): One decision says the prompt states the PASS/WORK convention; the rules say 'no instruction to reply'. Whether and how agents learn PASS/WORK, which the engine depends on, is unclear.
- **GF9** (Major, egm-comprehension, decisions kickoff strategy / tools guidance / chair guidance vs rules): None of these appear in the rules. The rules describe the first turn as the owner's prompts only, so the reader cannot tell whether turn.rs adds the kickoff and tool text or the owner's prompt already contains it, or where chair guidance goes in the order.
- **GF10** (Major, egm-comprehension, rules; wants (document.prompt.system); terminology): 'Owner's roundtable prompt' and 'owner's participant prompt' are distinct, but only one source is listed, so the roundtable prompt's origin is unknown. Undefined: the 'R1-2' id format, 'Current delivery:', disposition, JEV, ACP, chair, accolades, work notes.
- **GF11** (Major, egm-comprehension, wants (data.log.discussion) / decision delta delivery vs rules): Topic and objective are said to be delivered (topic 'when it changed'), but the rules never mention topic; it is unclear whether a topic change appears in the prompt when topics are on.
- **GF12** (Nit, egm-comprehension, rules (round line)): Unclear whether '3 Rounds Remain'...'Final Round' are added after 'Round N of T' or replace it. The engine document points to decision 'kickoff' but the topic is 'kickoff strategy'.

The code for this part is copied into the `source` folder here, under the same paths as above.
