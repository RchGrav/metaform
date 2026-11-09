# The old Roundtable specification, consolidated

What the old system's documents say Roundtable should do. Source: `archaeology/`, the old Python "Metaform" roundtables module and its specifications.

This is the old documents' **stated intent**. It is not the owner's design (`README.md`, `Roundtable_ACP_Integration_Design.md`) and not what the old code did (see `OLD-FUNCTIONALITY.md`).

**Citations** (paths relative to `archaeology/`):

| Short | File |
|---|---|
| RT | `specifications/12-roundtables.md` (the "current design" of 5 Nov 2026, carrying the owner's corrections recorded in VIEW-052) |
| V | `specifications/09-viewer.md` (VIEW-052 is lines 974-1006) |
| B | `specifications/04-chassis-modules.md` |
| MR | `src/metaform/modules/roundtables/README.md` |
| CL | its `CHANGELOG.md` |
| JC | `roundtable-jev-checks.md` |
| AH | `docs/reference/acp-conversation-history.md` |
| RA | `docs/reference/roundtable-agent-ratings.md` |
| AC | `docs/reference/roundtable-accolades.md` |
| GN | `docs/reference/agent-genesis-naming.md` |
| AI | `docs/reference/actor-identity.md` |
| DG | `review/design-gaps.md` |
| OI | `evidence/roundtable-original-recognition-instruction.md` |
| DP | `evidence/roundtable-20-delivered-prompts.txt` |
| AID | `rich/technical/agent_identity.md` |
| ME | `rich/technical/mcp_events.md` |
| TS | `rich/technical/revision/03-technical-specification.md` |

**Provenance:** [OWNER DOC] marks the owner's own files under `rich/`. [OWNER INSTRUCTION] marks the owner's original roundtable instruction. Everything else was written by the builder.

## 1. Table lifecycle

- A roundtable session is "a continuing group of agents discussing successive topics and creating shared work"; the chair can follow, steer, hold or end it (RT:5).
- **Opening:** `open <topic> [address=] [seats] [host=] [synthesizer=] [judging=] [reply_limit=] [spend=]`.
  - Seats are listed in speaking order.
  - The host defaults to the first seat.
  - The question is the table's one topic (MR:40; CL:15).
  - The Address became optional on 2026-10-19 (CL:14).
- **Several roundtables:** `chain=<n>` runs a session of n discussions (MR:238-240).
  - The sequence is: Start → Discuss → (quiet completion | End discussion | 120% budget) → private proposals → select → optional compression → Discuss.
  - After the last topic: private scorecards → farewells → save (RT:160-178).
  - Hold resumes the phase it interrupted (RT:180).
- **Final phases:** scorecards, aggregate results, then farewells. Busy productive work continues first (RT-011, RT:133; MR:260-261).
- **Engine stages:** a synthesizer names the ideas, seats rank them and explain, and a host summarises, scored by Borda count (MR:9, :183, :295).
- **Admission:** a table needs one dispatch slot per seat. It is refused if slots are short or if `spend` exceeds `roundtables_spend` (MR:40, :284; CL:16-18).
- **Ending:**
  - "End session" saves and stops the remaining phases.
  - "Abort" archives the run and clears it from the page (RT-011; MR:47-49; V:993).
  - A follower ends with its table and frees its slots (MR:63, :369).
- **Continue:** starting from a completed table gives fresh seat contexts from the saved host summary, keeps the same identities, and appends a topic (MR:42; B:1140).
- [OWNER INSTRUCTION] "You will be participating in 5 roundtable discussions, there will be a topic for each roundtable which must be followed or your messages will be vetoed by the system automatically". Between sessions, agents "communicate freely and co-operate", agree on materials, decide the next topic and who writes it into `next-topic.md`; "this will continue until all sessions are finished" (OI:10). Later superseded (§7).

## 2. Turn order and scheduling

- Seats speak in their configured order (MR:40; DP:82).
- **RT-003, busy participants skip their opportunities:**
  - Ready participants continue.
  - A busy skip supplies no PASS, veto or reply and creates no obligation to make the turn up.
  - No one participant can impose a group barrier (RT:31-40).
- At most one foreground request per participant (RT:37).
- When everybody is busy, the runner waits for actual activity or chair events "without timed cycling" and never manufactures empty rounds (RT:36; MR:240; V:988).
- **Late replies:**
  - A late reply to a closed topic is saved unjudged under its original topic.
  - A late reply on the same topic can enter the current rotation (RT:37).
- Chair comments enter at the next gap between turns (MR:42).
- Native work is owned until ACP completion or a real exit. `agent_wait` is not a work deadline (RT-002; MR:211-212).
- Delivered prompt: "Other participants continue while you work." (DP:7, :84)
- [OWNER DOC] "A busy agent's events join its pending queue and can accompany the next natural turn." (TS:631)
- [OWNER DOC] MCP Events let agents react to state changes "without constantly polling"; an idle agent consumes "zero LLM tokens" until an event arrives (ME:1, :67).

## 3. Speaking allowance

- **RT-004:** a returning participant's reply allowance is `512 × (1 + PASS credits + missed accepted peer messages)` characters (RT:47).
  - A rejected message earns no credit.
  - An actual PASS banks one base allowance.
  - Acceptance spends only the credits offered with that reply.
  - A missing or rejected reply spends nothing (RT:48; MR:103-110; V:984).
- The allowance is frozen per request (RT:48).
- A reply is truncated to the allowance before judging (RT:48).
- The credit ledger is private (RT:48; MR:109).
- The base is configurable as `reply_limit`, default 512 (MR:40; RT:51, :205).
- Topic proposals are limited to 512 characters (DP:206).
- **Delivered text:**
  - "The base reply limit is 512 characters. Each turn states its current limit." (DP:159)
  - Observed limits of 1,024, 2,048 and 4,096 (DP:318, :453, :584).
- **RT-010, a token budget** (separate from the character allowance), per participant per discussion, default off (RT:116-125; MR:70-79, :141-150):
  - It counts uncached input plus output.
  - Notices go out at 50%, 80% and 100%.
  - At 120% the discussion advances.

## 4. Reply kinds

- **PASS:** voluntary, not judged, banks one allowance, counts as outcome P, gets no public ID (RT:48, :65, :76, :141).
- **A contribution** is judged by three checks:
  - Accepted: it gets the public ID `R{panel}-{n}`.
  - Vetoed: outcome V (RT:141; V:983).
  - With judging off, every reply is kept within the limit (MR:182; RT:69).
- **Work:**
  - A skip is not an outcome.
  - A returning participant may give one catch-up reply citing several IDs, or PASS (RT:34, :47).
- A missing reply, a failure or a skip supplies no outcome, uses no ID, and is never replaced by an invented PASS (RT:74; MR:126-132; V:1000).
- Delivered: "Write one message or PASS when you have nothing to add." (DP:153)

## 5. JEV judging

- **RT-005:** three independent checks in one request, with no fourth combined score (RT:53-69):
  - `new_context`: "Does this add anything to the discussion which has not been already stated, or does it express a position on a matter which was recently mentioned?"
  - `valuable`: "Does this message move the discussion forward and help answer the question?"
  - `on_topic`: "Does this message address the subject being discussed?" (RT:58-62)
  - Criteria in JC:5-27.
- **Thresholds:** each check must reach its own threshold, default 0.70, captured when the table opens; one check cannot make up for another (RT:65-67; MR:177-181).
- Repeated positions get no automatic veto (RT:66).
- **Judging context:**
  - It contains the full original instructions, the topic, the candidate, and the newest whole accepted messages plus chair clarifications.
  - Size: a 50,000-token target, also bounded by 80% of 65,536 and 80% of 32,000.
  - The oldest whole messages are dropped first (RT:66; MR:190-200).
- JEV sees neutral seat positions (MR:194).
- **Judging is optional:**
  - Judged tables need JEV and an OpenRouter key.
  - ACP-only unjudged single tables need neither.
  - "Sessions with subsequent topics still use Jev for private topic comparison." (MR:40, :177; RT:69)
- **JEV service** (CHANGE-ORDER-2026-10-07 §6): `decide(state, questions)` returns probabilities, "or nothing when the service is off or the key is missing, so every caller keeps its current behavior"; "Never a gate on an agent's inference."
- **Failure:**
  - `jev_wait` is 300 s.
  - Pending judgments finish before completion is assessed.
  - Ambiguously sent paid requests are not replayed (RT:74, :151-155, :212).
- **History:** commit 541b2c20 (2026-11-04) set the novelty thresholds to zero, and the current text restores the gates (MR:84-90; V:997).

## 6. Vetoes and feedback

- Only the author gets a plain-language veto explanation naming the failed checks. Peers see no rejected text, notices, ratings or thresholds (RT:144; MR:156-160; V:1002).
- Delivered: "If your message is blocked, only you receive its failed condition at the start of your next turn… A block earns no extra characters." (DP:155-156)
- [OWNER INSTRUCTION] Off-topic messages "will be vetoed by the system automatically" (OI:10).

## 7. Topic completion and next-topic selection

- **RT-006 quiet completion** (RT:71-80):
  - It needs two actual quiet cycles among the ready participants and no acceptance.
  - Each ready participant must have two outcomes since the last acceptance.
  - PP, VV and VP are finished; PV needs another chance.
  - Busy participants do not block.
- With judging off, one full unanimous PASS rotation finishes the topic (RT:77).
- "End discussion" and the 120% budget each advance the topic (RT:77).
- A context handoff invalidates earlier PASS votes (MR:136-137).
- **History:**
  - 2026-10-22 (b8b0db19): quiet completion was removed and unanimous PASS required. Round caps, sufficiency judging and token-budget endings were also removed (CL:7; B:1138).
  - 2026-11-04 (541b2c20): novelty set to zero, and a JEV-free DONE/file phase added.
  - Current (owner corrections of 2026-11-04/05): gates and quiet completion restored, private topics (MR:84-90; V:997).
- **RT-007 private next-topic selection** (RT:82-92):
  - Each available participant gets at most two proposal attempts.
  - Busy participants are skipped.
  - `topic_proposal_wait` is 30 s.
  - Participants never see the proposals.
- **Comparison:**
  - A sole proposal wins.
  - Otherwise JEV asks whether each pair is "similar". The probability is credited to both proposals and averaged, and the highest wins, with no threshold.
  - Ties are joined verbatim.
  - If no proposal arrives, the table reports it.
- Removed: the between-topic collaboration phase, the DONE barrier and `next-topic.md` (RT:111).
- [OWNER INSTRUCTION] The original process: agents agree on materials, then "decide upon the topic of the next discussion, decide which of you will write the topic and write it in the file …/next-topic.md" (OI:10). Superseded.

## 8. Continuity and context

- **RT-001:** topic advance, continue and reseat keep the native session, its history and the shared files. "A topic transition does not start a fresh agent." (RT:9-18)
- **RT-004 ordered inbox:**
  - Accepted peer messages queue while a participant works, including across topics.
  - The checkpoint is the native send receipt (RT:45; MR:228-232).
- **RT-008:** optional native compression between topics, off by default. A failure causes no hold (RT:94-103).
- **Legacy handoff** for independent tables: 24,000 tokens, carry-forward notes, a synthesizer edits the continuation, and seats restart. Not used by continuous sessions (MR:185-188; RT:214).
- Resume uses `session/resume` if supported, otherwise `session/load` with replay suppressed (AH:7-9, :50).
- [OWNER DOC] "Agents may handoff based on % of context used, or based on satisfying a goal"; compaction "starts a new epoch"; "A closed context can always be called back" (AID:5, :22).
- [OWNER DOC] A handoff carries the goal, progress, decisions, revisions, event cursor and references. When a configured usage fraction is reached, emit handoff-needed and continue at the next turn boundary. "Unknown capacity is reported as unknown." (TS:684, :688)

## 9. Agent harnesses and ACP

- **Seats:** `claude/`, `codex/` and `antigravity/` run on ACP. Any other id is an OpenRouter model (MR:40).
- Launch: `npx -y @agentclientprotocol/claude-agent-acp@0.89.1`, `codex-acp@2.2.2`, antigravity through an adapter (B:821).
- **ACP version:**
  - Roundtable connections offer v2 and keep v1, each using its negotiated protocol.
  - v2's `state_update` reports activity and completion.
  - v1 is negotiated afresh when a peer rejects v2 (MR:263-271; RT-002; V:987).
  - Verified 2026-11-04: Claude 0.100.0 and Codex 2.5.0 speak v2; Antigravity 1.4.5 negotiates v1 (MR:273-274).
  - Conflict: dispatch "speaks ACP v1" (B:820).
- **RT-002:**
  - Track foreground activity, permissions and background activity; missing information means "unknown".
  - Hold, topic change and budget never cancel native work.
  - A provider error is distinct from a transport loss (RT:22-27).
- **Waits:** native startup 120 s; model/mode setting 30 s; cancellation acknowledgement 15 s; `agent_wait` 300 s, for external responses only (RT:211-217).
- **Sessions:** IDs are persisted; `reseat` reconnects to the saved conversation (MR:41, :208-209).
- **Permissions:**
  - The project is the workspace.
  - `permit` returns the person's choice.
  - Setup shows the permission controls once per agent type.
  - "Metaform sets no Claude-specific tool allowlist or file permission gate." (MR:51-56, :287)
- **Models:**
  - "The person picks every agent, model and thinking level … Nothing in Metaform chooses one for them" (B:1128-1130, citing the owner's decision of 2026-10-25).
  - Short names resolve to the newest release; an unoffered model is refused, naming the nearest (MR:80).

## 10. OpenRouter participants

- Any non-ACP id is an OpenRouter model, for example `deepseek/deepseek-v4.1-flash` (MR:40, :395).
- `OPENROUTER_API_KEY` is needed for judging and for OpenRouter seats (MR:385).
- `roundtables_spend` defaults to 2 USD and is the person's setting; credit recovery needs an explicit Continue (MR:69, :138-139, :285).
- An OpenRouter seat has no ACP session but is a full participant (AI:21-24).

## 11. Activity monitoring and seat health

- Readiness comes from ACP foreground and background reports; "unknown" is not "empty" (RT:26).
- `probe_wait` is 300 s before probing a temporarily unavailable participant (RT:213).
- A departed participant does not block anything (MR:131-132).
- Seat-loss and operational events go to the person (MR:278).
- A provider error is not called a disconnection without transport evidence (RT:154).

## 12. Chair controls and the interface

- **Verbs:** comment, hold, continue, advance, reseat, end (MR:41).
- **RT-011:**
  - Hold pauses new requests.
  - Continue resumes.
  - End discussion finishes only the current topic.
  - End session saves and stops.
  - Abort is separate (RT:127-136).
- Comments queue while held. End discussion is disabled during selection, scoring and farewells (RT:132; MR:42-48).
- **References:** message IDs, `file:line` and quoted `rg` searches open in a reader, with no shell (MR:60-62, :112-114).
- Notes lists the shared files, rendered without scripts (MR:116-117).
- Setup remembers the lineup and exposes judging, permissions and compression (MR:50-54, :177).
- **Past tables:**
  - `tables` lists them newest first, plus `status` and `events`.
  - The page keeps results across visits.
  - Report and export links (MR:57-59, :295, :299).
- **History:** chair controls were removed from the page on 2026-10-21 (CL:13) and restored later (B:1141; V:978).

## 13. Participant tools

- No MCP tools for participants are specified; harnesses use their own tools (MR:286-287).
- The module verbs are also MCP tools for agents (B:1146; CL:13).
- [OWNER INSTRUCTION] Agents should "seek to understand the projects context using the map and any other files in the project" (OI:10).

## 14. Identity, naming, ratings and accolades

- **Generated names:**
  - A private alias maps a model source to an opaque identity and a profile key.
  - Peers see generated names; models are visible only to the chair (MR:162-170; RT:144).
  - Delivered: "Do not disclose which model a participant runs." (DP:157)
- [OWNER DOC] **The genesis naming rule:**
  - "An agent is born with its genesis context… The id of that session is the seed."
  - FNV-1a 32-bit → fold to 16 bits → adjective + noun (256 each).
  - "There are 65,536 names; two live agents can share one, and nothing rehashes." (AID:7-18; GN:14-25)
  - Conflict: the old allocator used random UUIDs and retried collisions (GN:27-31; DG:3).
- [OWNER DOC] An identity keeps messages, tool calls and commits, and can be called by name (AID:24-34).
- [OWNER DOC] D07: "Same logical identity on deliberate handoff; a new identity on independently proceeding fork." (TS:674, :836)
- **Scoring:**
  - Efficient (×10), Alert & Aware (×20), Thorough (×30) and Coordination (×40), each 0-5 stars, plus a bonus worth +5; maximum 105 (RT:136; RA:98-111).
  - The rubric is in the project-worker prompt but not in the roundtable prompt (DG:4).
  - Validation: rate every other participant, no self-rating, exactly the four categories plus bonus (RA:117-122).
  - Ranking is the sum of points; profiles accumulate per session; `session_profile` is shown in later prompts (RA:92-95, :138-142).
- [OWNER INSTRUCTION] "you will see the final ranking at the end including your rank in the line up, additionally this score will be added to your agents identity as part of your profile in future sessions as well as accolades and recognition for your efforts." (OI:10)
  - No accolade mechanism is defined (AC:19-23; DG:5).

## 15. Records, persistence and reports

- **Saved record:** `docs/roundtables/<n>-<topic>/` holds `export.json` and `mechanical-report.md` (MR:297).
- A memory at the Address holds the question, the host answer and the top 3 ideas (MR:298).
- **Events:** `roundtables.event` kinds are turn, veto, stage, ideas, rankings, summary, state, seat_lost, operational, end, adopted (MR:278).
- **Engine DB:** `~/.roundtable/roundtable.sqlite3` (AH:16-18; RA:128-136).
- **RT-013 durable recovery:** fenced ownership; no replay of paid requests (RT:149-158).
- **Public IDs** `R{panel}-{n}`, contiguous (RT:141).
- [OWNER INSTRUCTION] "The participating agents must create these documents together; no automatic summary or minutes are provided." (OI:10)
- **Report history:** the engine reporter, then the system agent, then a Planner, then Follow-through; now "The engine's reporter output is not saved or shown." (CL:11, :14; B:1144; MR:291)

## 16. Workspace and deliverables

- **RT-009:** participants create the requested artifacts in the shared folder during discussion. "A generated transcript does not stand in for a requested specification, diagram or code sample." (RT:105-114)
- Participants may elect a coordinator, with equal permissions and no extra vote (RT:111; MR:152-154; DP:165).
- No final owner, filenames or completeness check is enforced (RT:114; DG:8).
- [OWNER INSTRUCTION] "discuss and summarize what you believe came out of the session that was most valueable write these up and save them to a file, you can create diagrams code samples, or any material … Work together to organize your shared document folder … All jointly authored documents belong there." (OI:10)

## 17. Prompts delivered

- **Prompt sets:** connect, instructions, rules, opening_question, opening, session_*, outcome_*, adopted*. The texts are in `prompts.xml` (MR:33-36; RT:197).
- **Round Table 20 shape** (DP:82-206):
  - Name, order and rules; the TASTE writing register; the ID and citation format.
  - The catch-up rule, the coordinator, the profile score, the per-turn limit.
  - "Roundtable k of N. The topic: …", then new accepted messages, then "Write one message or PASS."
  - A private topic request.
- [OWNER INSTRUCTION] The TASTE writing register (owner, 2026-11-02), delivered verbatim (OI:12-77; DP:11-80).

## 18. Other

- **Purpose:** brainstorming; the question is the table's whole frame (MR:9).
- **Engine origin:** Roundtable 2, from RchGrav/roundtable at 65359b27 (MR:387-389; CL:13).
- `adopt` turns an idea into a ticket. Follow-through runs Researcher → Architect → Intake → Planner → Decomposer → Facilitator (MR:64, :301-344).
- **Verification:** fake ACP clients, no paid calls (RT:234).
- "Preserving work through Hold, elapsed time and phase changes is the owner's product policy implemented on that protocol." (RT:232)

## Conflicts and changes within the old documents

- The completion rule changed three times.
- Token-budget endings were removed, then the 120% advance was restored.
- Handoff rebuild versus continuous sessions.
- Web chair controls removed, then restored.
- Report authorship changed repeatedly.
- `next-topic.md` collaboration became private proposals.
- Default seats changed.
- Antigravity 1.4.1 versus 1.4.5.
- ACP v1 versus v2-with-fallback.
- Genesis naming versus UUID aliases.
- The rating rubric is not delivered to seats.
- The accolade promise has no mechanism.
