# RusticEquity — working analysis of GF1–GF12

## Scope constraint (important for adjudication)
`source/` contains only:
- `crates/roundtable/src/prompts.rs`
- `crates/roundtable/src/turn.rs`
- `crates/roundtable/resources/roundtable_prompt.md`
- `crates/roundtable/resources/participant_prompt.md`

Findings cite `engine.rs`, `config.rs`, `events.rs`, `acp-host/events.rs`, `README.md`,
`Roundtable_ACP_Integration_Design.md`. Those are NOT in this folder. element.md's
`references` layer names them, but the files themselves are absent.

Two kinds of finding:
1. **Documentation-gap findings** (about what element.md fails to say): fully judgeable
   from element.md itself.
2. **Code-behavior findings**: judgeable only where the cited behavior lives in
   prompts.rs / turn.rs; where a claim rests ONLY on a missing file, I mark it
   "not verifiable from the provided source" and reason from internal consistency.

## Verifiable facts from provided files
- `roundtable_prompt.md` is the OUTER template: `You are {{AgentName}} ... {{roundtable_subject}}`
  plus `{{custom_roundtable_prompt}}`, `{{artifact_directory}}`, `{{delivery_json}}`.
- `participant_prompt.md` is the INNER template, substituted into `{{custom_roundtable_prompt}}`;
  it itself takes `{{roundtable_prompt}}` = the user objective (prompts.rs:12-14).
- `prompts.rs:73-83 roundtable_prompt()` fills, in order: `{{AgentName}}`,
  `{{artifact_directory}}`, then (via NUL-sentinel trick so free text can't be re-substituted)
  `{{roundtable_subject}}`, `{{custom_roundtable_prompt}}`, `{{delivery_json}}`.
- turn.rs:69-81: on `seat.first`, build the roundtable prompt with:
  - `agent_name = seat.name.as_deref().unwrap_or(&seat.label)` (identity name, else label)
  - `topic = self.topic()`
  - `custom = participant_prompt(&self.cfg.objective)` (objective substituted)
  - `workspace = self.cfg.workspace.display().to_string()`
  - `delivery = parts.join("\n\n")` — plain text with blank lines, NOT JSON.
- turn.rs:31-68 `parts` order: round_label (if discussion), [session_profile if first && returning
  identity], notices (if discussion), "Current topic:" line (only if topics_active && !first &&
  seen_topic!=topic_index), other agents' log messages / Chair lines, then `ask` (special request).
- turn.rs:87 `commit()` sets `seat.first=false` once a prompt was actually sent.
- `roundtable_prompt.md:8` always states JEV evaluation ("Your message is evaluated independently
  for contribution, usefulness, relevance, value, and auditability. Each true/false gate must
  reach 0.7; both 0–5 scores must reach 3...").
- turn.rs:148-155: judging off -> `accept(..., note "unjudged: judging is off")`;
  no OpenRouter key -> "unjudged: no OpenRouter key"; 161-167 JEV state build failure -> shared
  unjudged with a loud notice; 199-203 JEV `Err` -> shared unjudged. So messages ARE shared
  unjudged in those cases; the prompt's line 8 is unconditional.
- `participant_prompt.md:17` "Topics may change" is unconditional text.
- element.md elephant.gaps[0] = `"Topics may change" is not true while topics are off.`
- `prompts.rs:57` doc comment: "Sent once, on an agent's first turn."
- `roundtable_prompt.md:17` placeholder literally named `{{delivery_json}}` but filled with plain text.
- name "Participant System Prompt" has 3 words; `name_length: 2` in properties.
- decisions layer mentions "credit sentence and the length and truncation lines were deleted";
  no such lines exist in either resource file.
- investigations.delivery note advises "use a harness extension (e.g. Claude
  _meta.systemPrompt on session/new) only where that harness advertises it" — framed as an
  option, not as something built.
- element.md "built": "Sent on each agent's first turn, with the participant prompt inside the
  roundtable prompt."
- element.md references: participant_prompt.md appears in `references`; roundtable_prompt.md is
  the `uri`. uri == roundtable_prompt.md, name == "Participant System Prompt".

## Per-finding verdict sketch
- GF1 Major: "Sent on seat's first prompt of any kind at each table... Resumed sessions receive
  it again, so it is not once per session." The description claim under attack is
  `elephant.built` "Sent on each agent's first turn" and the user-facing "Tell every agent, once".
  From turn.rs, `seat.first` is per-seat state set false in commit(); I cannot see engine.rs to
  confirm resumed sessions reset `first`. Verifiable part: it is per-first-turn-of-a-seat, not
  "once" globally. The finding's core = description overstates "once"/"once per session". RIGHT
  in substance: reword elephant.built/design. Resumed-session specifics not verifiable here.
- GF2 Major: placeholder mapping undocumented. RIGHT. element.md has zero mapping. Verifiable:
  AgentName=name-or-label (turn.rs:73); artifact_directory=workspace (71); delivery_json=plain
  text (68, join); roundtable_prompt=objective (prompts.rs:12-14); roundtable_subject=topic
  (turn.rs:74) — "defaulting to objective" is an engine.rs claim, not verifiable here.
- GF3 Major: missing gap — line 8 always claims JEV evaluation but messages shared unjudged.
  RIGHT. Fully verifiable (turn.rs 148-155,161-167,199-203 vs roundtable_prompt.md:8). element.md
  elephant.gaps does not list it. Add gap/fix code or note.
- GF4 Major: first-turn delivery contents undocumented. RIGHT. Verifiable from turn.rs:31-68.
  element.md says nothing about round line / session_profile / notices / others' messages / chair /
  special request / "Current topic:" on later turns. Add to description.
- GF5 Nit: no harness-extension delivery exists; prompt always session-prompt content. Claims
  rely on engine.rs:599 (absent). Verifiable: nothing in the provided files references
  _meta.systemPrompt or session/new; investigations note only *recommends* the extension. So
  within scope, the finding is consistent: the description's investigations note names an
  unimplemented option as if relevant. RIGHT as a doc nit — clarify no such path is built.
- GF6 Nit: name vs uri mismatch; gaps[1] should say only final block after last tool call becomes
  the message. First part RIGHT (name=Participant System Prompt, uri=roundtable_prompt.md; also
  GF7). Second part cites engine.rs:691-699 & acp-host/events.rs:147-149 (absent) — not
  verifiable from scope; but the *current* gaps[1] text "Nothing tells an agent that its reply is
  the message the others receive" is itself a real gap. I'd treat the "should say only final
  block" as plausible-but-unverifiable; recommend rewording gap to the verifiable fact if the
  code claim can't be checked.
- GF7 Major: document doesn't say whether element = roundtable prompt, participant prompt, or
  composition. RIGHT. name/uri/references/built are ambiguous. Fully judgeable from element.md.
- GF8 Major: "while topics are off" refers to a mode never introduced. RIGHT. Fully judgeable:
  "topics off" appears only in elephant.gaps, never defined, no setter, no default stated.
- GF9 Major: credit sentence + length/truncation lines not described; consequence unstated.
  RIGHT. decisions mentions their deletion but element.md never describes what they were or
  that truncation/vetoes exist; verifiable that neither resource file contains them. Major doc gap.
- GF10 Nit: doesn't say which delivery path chosen or what happens on restart. RIGHT. element.md
  investigations + built are silent on chosen path and restart. (Overlaps GF1/GF5.)
- GF11 Nit: name_length 2 but name has 3 words; field undefined. RIGHT. Pure property error,
  fully judgeable. Either fix value to 3 or define field as word count of something else.
- GF12 Nit: undefined jargon (ACP, harness, session/prompt, session/new, _meta.systemPrompt,
  evaluation specification, role, Intent). RIGHT as a doc nit — these appear in element.md with
  no definition. Note `Intent` appears verbatim in wants; `role:"SE"` undefined; etc.

## Cross-cutting recommendation
Most findings are documentation defects, not code defects. The cleanest resolution: element.md
is a *map/description* artifact; fix it by (a) stating that the element is the COMPOSITION
(outer roundtable prompt wrapping inner participant prompt), (b) adding the placeholder map,
first-delivery contents, unjudged-sharing gap, topics-mode definition, deleted-lines note,
defined jargon/glossary, correct name_length, and the "per first turn of a seat, re-sent on
resume" wording. Only GF3 and GF6(part) hint at code changes; the unjudged case arguably wants
a code fix (conditionally soften line 8) but the owner's "verbatim" decision forbids rewording,
so the right fix is a documented gap, not a code edit.
