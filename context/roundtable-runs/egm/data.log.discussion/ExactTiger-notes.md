# ExactTiger: checks that change the proposed resolutions

1. **A serialization error currently produces no record line.** `line()` converts it to `data:null` (`record.rs:17`), but `spawn_recorder` then calls `table_of(null)`, gets `None`, and continues before the write (`record.rs:47–50`). Adding a top-level `data_error` marker alone leaves that routing failure intact. A real fix needs independently available routing identity or an out-of-band diagnostic plus incomplete-capture status. This qualifies GF5 without dismissing its loss finding.

2. **Missing prompt fields in this crate do not establish missing prompt capture.** This recorder accepts arbitrary bus envelopes and explicitly routes ACP/monitor events. Prompt text may be in a publisher not included here. Inspect that publisher before adding a duplicate `PromptSent` event or declaring every prompt absent. This distinguishes persistence of prompts from serving conversation history to the prompt builder (GF1/GF7).

3. **Do not fix table shutdown by waiting indefinitely for a shared bus to close.** A table needs a recorder completion boundary after its own publishers finish, followed by draining and awaiting the recorder task. Other tables can remain active. A discussion-ended event need not also mean harness capture ended (GF4).

4. **Turn identity groups events; bus sequence orders them.** A floor assignment, judge result and final contribution can share one logical turn while each has a different envelope sequence. Skips may occur without a floor grant. If retaining the canonical-turn requirement, allocate at the scheduled opportunity rather than only at `FloorGiven`, and keep the counter across topic changes (GF2).

The per-finding decisions and proposed changes are in `resolution.md`. Only `record.rs` and `events.rs` were supplied; application paths, sequence reset behavior, historical incidents and reconstruction methods must not be invented from missing integration files.
