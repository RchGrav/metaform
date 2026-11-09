# Resolution — Participant System Prompt

Basis: the description in `element.md` and the code copied in `source/` (two prompt text files, `prompts.rs`, `turn.rs`). Each decision below states: what the code actually does in plain operational terms, whether the finding is right, exactly what should change (description or code), why it matters, and how to check the claim (a specific file/line or a search a reader can repeat). The findings also cite `engine.rs`, `config.rs` and `acp-host events.rs`. These are not in this element's `source/`, but byte-congruent copies exist in sibling element folders of the same codebase (e.g. `collection.workspace.shared/source/crates/roundtable/src/engine.rs`, `code.identity.agent/.../config.rs`), and the cited line numbers were checked against them (see the Addendum). Claims resting on those files are therefore verified, not assumed; `source/`-only checks are noted as such where they matter.

## GF1 — Upheld (Major)
**What happens in the code:** When a seat's first prompt of any kind is built, `turn_prompt` (`turn.rs`) puts the full prompt (outer template with the inner prompt inside it) in front of that turn's content, because a flag on the seat (`seat.first`) is still set. After that prompt is sent, `commit` clears the flag, so no later prompt gets the full template again. A discussion turn is only one kind of prompt; review, topic-proposal and rating prompts also count as "first" if they happen to be first.
**Decision:** the finding is right. The description's "first turn of each session" is wrong in a way that matters: a reader would expect the full template only on the first discussion turn and would misjudge what a seat that is first asked a review or rating prompt actually receives.
**Change (description only):** replace "first turn of each session" with "first prompt of any kind for that seat (while its `first` flag is set)".
**Check:** read `turn_prompt`'s `if seat.first` branch and `commit` setting `first = false`. The resumed-session half of the finding is confirmed by the sibling `engine.rs`/`config.rs` copies (Addendum): `resume_session` only selects the harness session open path (`engine.rs:976-977`), `first` is initialized `true` for every seat at `Table::new` (`engine.rs:324`) and cleared only by `commit`, so a resumed seat retains `first == true` and receives the full template again.

## GF2 — Upheld (Major)
**What happens in the code** (`prompts.rs` `roundtable_prompt`, `turn.rs` `turn_prompt`):
- `{{AgentName}}` → the seat's human name if it has one, otherwise its seat label.
- `{{roundtable_subject}}` → the current topic text returned by `self.topic()`, initially the configured nonblank topic or otherwise the objective (sibling `collection.workspace.shared/source/crates/roundtable/src/engine.rs:306`).
- `{{custom_roundtable_prompt}}` → the second owner text, with the objective substituted into its own placeholder.
- `{{artifact_directory}}` → the configured workspace folder path as text. Sibling `engine.rs:402–404` creates the directory, attempts canonicalization, falls back to the original path on failure, and writes the result into `cfg.workspace`. Thus “canonical workspace” describes the successful case, not an unconditional guarantee.
- `{{delivery_json}}` → the turn's content parts joined by blank lines. Despite the name, this is plain text, not structured data.
**Decision:** the finding is right. Without this table, nobody can predict what any given seat reads, because five different values are substituted into one template.
**Change (description only):** add this table to the element and flag `delivery_json` as a plain-text misnomer.
**Check:** the five substitutions are each one line in `prompts.rs` / `turn.rs`; no other code fills them.

Also document the inner template's `{{roundtable_prompt}}` → `cfg.objective` substitution (`prompts.rs:12–14`). The same name here denotes the objective, not the outer template.

## GF3 — Upheld (Major)
**What happens in the code:** The outer template always contains a paragraph saying the seat's message is scored by an automated checker (JEV) and can be rejected. But in `submit` (`turn.rs`), a message is instead shared with everyone without any checking in three cases: judging is switched off; the checker has no API key; the checker errors or cannot fit the message. In those cases the message still reaches the other seats, with an internal note saying it was unjudged.
**Decision:** the finding is right. The first prompt tells every seat something that is not always true, so seats may write defensively or blame themselves for rejections that cannot happen.
**Change (description only; code change is the owner's call):** record as a gap that the prompt always promises JEV evaluation while the code shares messages unjudged in the three cases above. Do not change the prompt text unilaterally: both prompt texts are the owner's, kept verbatim by design (`prompts.rs` header comment).
**Check:** `turn.rs` branches `if !self.judging`, `if !self.jev.configured()`, and the checker-error branch each call the same "accept unjudged" path.

The inner `participant_prompt.md:15` makes the same unconditional evaluation promise; record the gap against both templates. “Unjudged” does not bypass length enforcement (`turn.rs:125–145`), and the delivery shown to peers does not itself include the internal unjudged note.

## GF4 — Upheld (Major)
**What happens on the first prompt, in order** (`turn.rs` `turn_prompt`): (1) a round line like "Round 2 of 5" — discussion prompts only; (2) if the seat is a returning identity with past ratings, its profile score, rating count and session count; (3) any pending notices for that seat — discussion prompts only; (4) on later prompts, a "Current topic: …" line when topics are enabled and the topic changed since the seat last spoke; (5) every other seat's accepted messages and any chair messages the seat has not yet seen, each prefixed with an ID or "Chair:"; (6) any special request attached to this prompt (review, topic proposal, or rating request).
**Decision:** the finding is right. This is the complete list of what a seat reads on its first prompt; omitting it makes the element unusable for judging whether seats have what they need.
**Change (description only):** document items (1)–(6) above, in that order.
**Check:** each item is a separate `parts.push(...)` in `turn_prompt`.

## GF5 — Upheld (Nit)
**What happens in the code:** The full template is built as an ordinary string and sent as the content of the seat's prompt. There is no code anywhere in `source/` that passes it through an optional harness extension field (the investigation's example was a `_meta.systemPrompt` field that some agent harnesses accept).
**Decision:** the finding is right but small: the investigation describes an option the code never uses, so a reader cannot tell what was actually chosen.
**Change (description only):** reword the investigation to state the chosen path: "delivered as prompt content; the optional harness-extension path is not implemented." Independently checked sibling `collection.workspace.shared/source/crates/roundtable/src/engine.rs:597–601` builds the text, passes it to `harness.prompt`, then commits after success. The broader search reported below supports the absence of the alternative path; the four local files alone would not establish that negative.
**Check:** search `source/` for `_meta` or `systemPrompt` — zero hits.

## GF6 — Upheld in full (Nit)
**Naming part — right.** The element is called "Participant System Prompt" but its single file pointer (`uri`) is `resources/roundtable_prompt.md`, which is the *other* owner text. A reader following the pointer gets a different file than the name promises.
**Gap-wording part — right.** The finding proposes replacing the existing gap ("Nothing tells an agent that its reply is the message the others receive") with "only the final block after the last tool call becomes the message." The sibling `engine.rs:691-699` confirms this: `// gate: RT-G09 only the text after the last tool call becomes the message ... the turn's final message, not its narration before tool calls`, and `resolve_reply(i, &event.final_message, ...)` consumes that final text. `acp-host/events.rs:147-149` is likewise not in this folder, but the engine-side comment and the `final_message` field are direct evidence.
**Change (description only):** fix the name/pointer mismatch (see GF7); adopt the more precise gap wording so the description matches the reply-resolution mechanism.
**Check:** sibling `engine.rs:691-699` (RT-G09 comment + `event.final_message`); `turn.rs` `resolve_reply` receives that text as the seat's message.

## GF7 — Upheld (Major)
**What the element actually covers:** a composition of two owner texts. The outer template (`roundtable_prompt.md`) is sent once per seat; the inner text (`participant_prompt.md`) is inserted into it at the `{{custom_roundtable_prompt}}` slot. Neither text alone is the element.
**Decision:** the finding is right. Because the element never says which of the three (outer, inner, composition) it is, every other statement in it — including the name in GF6 — is ambiguous.
**Change (description only):** add one sentence: "This element covers the composition of the two owner prompt texts; `uri` points at the outer template as the composition's entry point." No code change. The URI need not change once scope is explicit; the inner prompt is actually rendered before the outer one in `turn_prompt`. Explain that “System Prompt” is a display name, not a claim about the ACP transport role.
**Check:** `turn_prompt` builds `custom = prompts::participant_prompt(...)` and passes it into `prompts::roundtable_prompt(...)` as one string.

## GF8 — Upheld (Major)
**The problem:** the gap "'Topics may change' is not true while topics are off" uses a switch ("topics") that the element never defines: what it does (lets the group move to new subjects), who turns it on (the chair/table configuration), and whether it is on by default.
**Decision:** the finding is right. A gap statement that depends on an undefined switch cannot be acted on.
**Change (description only):** add one defining sentence — what topics mode is, who sets it, and its default — or rephrase the gap without the term.
**Check:** the words "topics" appear in `element.md` only inside that one gap; no definition exists anywhere in the element.

The sibling `collection.workspace.shared/source/crates/roundtable/src/config.rs:150–153` defines `TableConfig.topics` with `#[serde(default)]`, confirming it is off by default. Its comment identifies the next-topic poll and `advance` tool as the controlled functions. Sibling `engine.rs:374–378` additionally requires judging and a configured evaluator key. Document these actual controls and conditions. “Topics may change” expresses possibility, so topics being off is not a strict contradiction; the actionable gap is missing mode awareness.

## GF9 — Upheld (Major)
**What happens in the code:** The prompt texts contain no mention of reply length limits (the owner deleted those lines). Limits are instead enforced after the fact: a contribution longer than an applicable seat character limit is blocked from group delivery (`turn.rs` `submit`), and on that seat's next prompt it receives a notice stating the length and the limit, plus any rejection feedback. So seats *are* told about limits, but only reactively, after violating them.
**Decision:** the finding is right. The decision record says the lines were deleted without saying whether anything replaced them; a reader would reasonably conclude seats are never told, which is false.
**Change (description only):** append to the decision: "Contribution limits are not stated in the common templates; when a limit applies, over-limit contributions are blocked in full, with feedback queued for the next discussion prompt." Sibling `code.rating.peer/source/crates/roundtable/resources/feedback/too_long.md` explicitly says the message was not shared and gives its length and limit. Topic proposals are different: `prompts.rs:85–86` announces their limit and `turn.rs:320–324` truncates them. Describe the deleted sentences' historical purpose only from an available original; do not reconstruct what the deleted credit sentence said.
**Check:** `turn.rs` `submit` blocks over-limit replies and pushes a `too_long` notice onto the seat's pending notices; `turn_prompt` delivers those notices on the next discussion prompt.

Qualification from sibling `collection.workspace.shared/source/crates/roundtable/src/config.rs:154–158`: the base contribution allowance is optional and defaults to no limit. The chair sets it. The missing advance guidance matters when a limit applies; the default does not impose a hidden finite base allowance.

## GF10 — Upheld (Nit)
**The problem:** the investigation presents two delivery routes (prompt content vs. harness extension) without saying which one the code uses, and says nothing about what happens if a session is restarted.
**Decision:** the finding is right, and its answer is now known from GF5: the code always uses prompt content. Restart behaviour is the GF1 question, and it is confirmed by the sibling `engine.rs`/`config.rs` (Addendum): `resume_session` only selects the harness open path and never resets `first`, which stays `true` from `Table::new` until `commit`, so a resumed seat receives the full template again.
**Change (description only):** state the chosen route (per GF5) and the restart behaviour: a resumed session keeps `seat.first == true` (Addendum, `engine.rs:324,976-977`), so the full template is sent again.
**Check:** GF5's search (no `_meta` usage anywhere in the egm tree; `session/new` appears only for MCP/auth in `acp-host/harness.rs`) plus GF1's `seat.first` logic in `source/` and the sibling `engine.rs`.

## GF11 — Upheld (Nit)
**The problem:** the properties block says `name_length: 2` for a three-word name, and the field is defined nowhere — so the reader cannot tell whether 2 is a mistake or means something else (for example, the number of prompt texts the element covers, which genuinely is 2).
**Decision:** the finding is right as far as it goes: the value is at minimum unexplained.
**Change (description only):** link or define the authoritative map schema, then validate the value. Change it to 3 only if the schema defines word count. Do not invent “number of owner prompt texts covered” as a definition merely because there are two texts. No supplied source reads this field; the rest of the map tooling is absent.
**Check:** `name: "Participant System Prompt"` = 3 words; no definition of `name_length` exists in `element.md`. Cross-element comparison confirms it is NOT a word count: `code.manager.chat.group` name "Roundtable" (1 word) has `name_length: 3`, `code.builder.prompt` name "participant turn prompt" (3 words) has `name_length: 2`, `code.identity.agent` "agent genesis names" (3 words) has 3, `downstream.chair` "user" (1 word) has 1. So changing this value to 3 would be a guess; the schema must be consulted.

## GF12 — Upheld (Nit)
**The problem, in plain terms:** the element uses several technical terms without explaining them for a reader who only has this document: the agent-protocol name (ACP), "harness" (the program that runs/pass-throughs a seat's agent), the session/prompt and session/new message types, the optional extension field name, "evaluation specification" (the owner's scoring document), and the map's own field labels `role` and `Intent`.
**Decision:** the finding is right from the standpoint of a reader of this element alone. Note the practical consequence is limited: `role` and `Intent` are map-wide labels presumably defined once for the whole map, so the fix needed *here* is only for the integration terms GF5/GF10 use.
**Change (description only):** add a short glossary for the integration terms, or expand each use into a plain sentence (e.g. "the program that runs the agent" instead of "harness").
**Check:** each term appears in `element.md` with no definition in the same document.

## Summary
- Upheld fully: GF1, GF2, GF3, GF4, GF5, GF6, GF7, GF8, GF9, GF10, GF11, GF12. (GF6's naming and its "final block after the last tool call" gap wording are both confirmed by the sibling `engine.rs:691-699`; see the qualifiers in CarnalChange's note below — that text is only a *candidate* message, still subject to classification, the length block and JEV veto, and ratings use a separate path.)
- Rejected outright: none.
- Code changes required: none to runtime behaviour or the owner's verbatim prompt texts. Every upheld finding is a description change. Comment-only corrections (CarnalChange, below) are appropriate. The only candidate behavioural change (GF3: making the evaluation paragraph conditional) edits an owner's verbatim text and is the owner's explicit call.
- Claims that cite `engine.rs` / `config.rs` / `acp-host events.rs` (GF1 resume, GF2 objective-default, GF6 final-block, GF8 topics-default, GF5/GF10 delivery path) are **verified** against congruent copies in sibling element folders; none are left unverified. The one field that is genuinely undefined is `name_length` (GF11): cross-element data shows it is not a word count, so its value cannot be "fixed to 3" without the map schema.

## CarnalChange — implementation-comment corrections and output-boundary qualification

The findings also justify small source-comment corrections, without changing owner templates or runtime behavior. `turn.rs:124` says “Truncate, then judge” although `submit` blocks contributions; `turn.rs:22–25` and the `prompts.rs` module header refer to a default characters line that `turn_prompt` never assembles. Update those comments to describe current behavior. Thus the summary's “no code changes” means no runtime changes; comment fixes remain appropriate.

For GF6, the verified final-block wording must describe a **candidate** contribution. `resolve_reply` still classifies it, `submit` can block it, and judging can veto it. Special prompts such as ratings use separate handling. It would be incorrect to state that every final assistant block necessarily becomes a message shared with the group. The name/URI ambiguity is resolved by documenting composition, not by treating differently named files as inherently erroneous.

For GF12, define ACP as Agent Client Protocol, `session/new` as session creation, and `session/prompt` as submitting content to a session; identify the actual owner evaluation document/version when available. Link the schema for `role`, `Intent`, and `name_length`; their meanings should not be guessed from labels. See `CarnalChange-evidence.md` for independently checked source locations.

## Addendum (UnseenBobcat): resolved sub-claims GF1 resume, GF2 default-topic, GF6 final-block

The two sub-claims above were flagged unverifiable because `engine.rs`/`config.rs`
are not in `source/`. They are verifiable: the same `crates/roundtable/src/engine.rs`
and `config.rs` are copied into sibling element folders in this workspace (e.g.
`collection.workspace.shared/source/crates/roundtable/src/`). The findings cite
these exact paths; all map elements reference the same codebase. Observed lines:

- **GF2 default-topic** — `engine.rs:306`:
  `let topic = cfg.topic.clone().filter(|t| !t.trim().is_empty()).unwrap_or_else(|| cfg.objective.clone());`
  Topic falls back to the objective. Confirms GF2's "roundtable_subject = topic,
  defaulting to the objective."
- **GF1 resume** — `config.rs:23-28` defines `resume_session: Option<String>`;
  `engine.rs:976-977`:
  `let opened = match &seat.resume_session { Some(id) => harness.resume_session(workspace, id, servers).await, None => harness.open_session(workspace, servers).await };`
  Resume only chooses the harness session; it does not touch the seat's `first`
  flag (set `true` for every seat in `Table::new`, `engine.rs:324`, cleared only
  by `commit`). So a resumed seat still has `first==true` and receives the full
  roundtable prompt again. Confirms GF1's "resumed sessions receive it again."
- **GF6 final-block** — `engine.rs:691-695`:
  "gate: RT-G09 only the text after the last tool call becomes the message. The
  agent's message is what it says once it has finished: the turn's final message,
  not its narration before tool calls." Confirms GF6's proposed gap wording.
- **GF8 topics mode** — `engine.rs:374-378`: topics are "a table setting, off by
  default," active only when `cfg.topics && self.judging && self.jev.configured()`.

Recommended action: adopt GF1's resume half and GF6's replacement wording, and
record GF2's default-topic line as verified. This changes the summary to: GF6
upheld in full (naming and wording), GF1 upheld including resume. It does not
change any code action; all fixes remain description changes in `element.md`.
Caveat (UnseenBobcat): byte-identity between sibling copies was inferred from the
shared, cited paths. This caveat is now removed (see the checksum addendum below).

## Addendum (RusticEquity): byte-identity of sibling copies — closes the "unverifiable" objection

AnalogCarbine's stated condition for flipping GF1's resume half and GF6's wording
was "if the resume code does re-set the flag and the reply handling does take only
the final text block." Both are confirmed below. The remaining worry — that sibling
copies might differ from the codebase the reviewers cited — is settled by checksum:

- `md5sum` of every `crates/roundtable/src/engine.rs` in the egm tree (4 copies:
  `code.manager.chat.group`, `code.quota.character`, `code.server.tool`,
  `collection.workspace.shared`) = `93c53f8c13f5a6a8cce054977e8f46ee` — identical.
- `md5sum` of every `crates/roundtable/src/config.rs` (4 copies:
  `code.identity.agent`, `code.quota.character`, `code.roster.participant`,
  `collection.workspace.shared`) = `2b11ea2f26e6dbb295b5e9cec553b475` — identical.
- The canonical `collection.workspace.shared/.../engine.rs` is 997 lines; the exact
  cited lines read: 306 topic→objective fallback; 324 `first: true`; 374-378
  topics off by default / `topics_active()`; 599 `harness.prompt(&session, text)`
  (prompt-content delivery, no `_meta.systemPrompt`); 691-699 RT-G09 final-block
  with `resolve_reply(i, &event.final_message, false)`; 976-977 resume only selects
  the harness open path.

Reproduce with:
`find /home/rich/roundtable-runs/egm -name engine.rs -path '*/roundtable/src/*' -exec md5sum {} \; | sort`
and the same for `config.rs`, then `nl -ba <canonical> | sed -n '306p;324p;374,378p;599p;691,699p;976,977p'`.

Conclusion: the four sub-claims (GF1 resume, GF2 objective-default, GF6 final-block,
GF8 topics-default) are verified against a single byte-identical codebase shared by
all map elements; the "unverifiable" framing is a false negative and is withdrawn.
A repo-wide search confirms zero `_meta` / `_meta.systemPrompt` / `systemPrompt`
occurrences (only `session/new` for MCP/auth in `acp-host/harness.rs`), so GF5/GF10's
"no harness-extension path" is verified, not merely inferred from a 4-file `source/`.
All fixes remain description changes in `element.md`; no code or owner-template edits.
