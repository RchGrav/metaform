# The old Roundtable: what the code did

Read from the source of `archaeology/src/metaform/` by an independent read-only agent on 2026-11-05. Nothing was run.

This file records what the code **did**. It is not what the old documents said (`OLD-SPEC-CONSOLIDATED.md`) and not the owner's design.

**Path prefixes:**

| Prefix | Path |
|---|---|
| E/ | `modules/roundtables/roundtable/` (the engine) |
| M/ | `modules/roundtables/` (the bridge) |
| D/ | `modules/dispatch/` |
| W/ | `modules/web/` |
| T/ | `modules/roundtables/tests/` |

## 1. Table lifecycle

- **Opening:**
  - The bridge writes a `tables` row and starts a detached follower that reserves one dispatch slot per seat, then calls the engine's MCP `open` (M/__init__.py:259-397; M/follow.py:91-193).
  - The engine `open` validates, fixes the rules in a snapshot (criteria, floors, `message_ids`, `reply_credits`) and spawns a detached runner (E/server.py:162-243; E/store.py:360-408; E/runner.py:116-129).
- **The runner:**
  - It owns the table through a heartbeat every 5 s and treats an owner as stale after 30 s; writes are fenced.
  - States: running/held/ending/ended (E/store.py:50, :225-230, :491-511; E/runner.py:219-351).
- **Seats** are created lazily, and their ACP sessions open on the first exchange (E/runner.py:426-439; E/harness.py:841-857). `seat_all` is dead code.
- **Sessions** (`chain`):
  - The web UI always sends `chain`, so every web table is a session.
  - A finished topic goes to topic selection; after the last topic come scoring, farewells and the end (E/runner.py:1246-1258, :1503-1513).
  - Sessions never run synthesis, ranking or a host summary; only non-session staged tables do (E/runner.py:1076-1093).
- **Ending:**
  - `finish` waits for busy seats unless the chair ended the table.
  - Completed replies are recorded unjudged, and a mechanical record is written. Sessions get no model report.
  - The bridge saves a safe record and memory. Sessions are zipped and pushed to branch `roundtables/<session>` (E/runner.py:247-256, :1588-1625; M/follow.py:364-380, :552-562; M/chain.py).

## 2. Turn order and scheduling

- **Turns ran concurrently.** Each loop iteration starts at most one new turn in seat rotation as an asyncio task. Several seats' turns run at once, and only JEV judging is serialized by a lock (E/runner.py:148, :634-699, :948).
- **A seat is skipped when it is:**
  - busy;
  - gone;
  - terminal (§7);
  - unusable without a due probe;
  - covered while another reply awaits JEV;
  - one that passed this round with no new message since (E/runner.py:520-522, :680-691).
- **Busy ACP seat:** process alive and connection up, plus any of activity not idle, unfinished background work, permission waits, an in-flight prompt, a pending response or a pending completion (E/harness.py:587-593). Busy and unusable seats are excluded from the round quorum.
- **Waiting** is event-driven:
  - `wait_work` waits on task completion or a chair event.
  - `wait_busy` waits on native readiness.
  - `recover` sleeps until the earliest retry (E/runner.py:529-606).

## 3. Speaking allowance

- **limit = base × (1 + credit)**, with base `reply_limit` 512 and no cap (24 passes give 512 × 25) (E/allowance.py:22-99; T/test_reply_allowance.py:439-450).
- **Credit changes:**

  | Event | Effect on credit |
  |---|---|
  | Own pass | +1 |
  | Own accepted contribution | minus the credits offered with that reply |
  | Own veto or no reply | unchanged |
  | A peer's accepted message while this seat is busy (same topic; always in sessions) | +1 |

  Source: E/allowance.py:141-172.
- Waiting for JEV earns nothing (E/allowance.py:118-120).
- The bank carries across topics in sessions and is per topic otherwise. Handoff and reopen wipe it; `reset` is dead code (E/allowance.py:26-35, :175-185; E/store.py:775-777).
- The limit is stated each turn. OpenRouter `max_tokens` grows with it (E/openrouter.py:409-418).

## 4. Reply kinds

- **PASS:** a full match of `\W*(?:T\d+\W*)?pass\W*`, case-insensitive, never judged (E/render.py:27-32; E/runner.py:958-968).
- **A contribution** is any other text: a leading `T###:` is stripped, the text is cut to the limit, and the original is kept if it was truncated (E/runner.py:976-992).
- **Truncation is not told to participants:** the status prompts are empty (prompts.xml:230-231). A vetoed reply is removed from the author's own conversation (E/seat.py:143-150).
- **An empty or missing reply** is recorded as kind `none` with a reason: empty, timeout or gone (E/runner.py:928-932).
- **Work: there is no "work" token.** Native work is inferred from ACP v2 `state_update` activity and background reports. A v2 reply completes when the foreground goes idle, and reported background work keeps the seat busy afterwards (E/harness.py:282-297, :737-742).

## 5. JEV judging

- POST `<openrouter>/alpha/decisions` with `{model, state:{xml}, questions}`. The model must be a fixed version; the default is `typesafe/jev-1.13` (E/judge.py:30, :200-251; E/config.py:46).
- **Three nouls,** with the wording in prompts.xml:415-433:
  - `new_context`: "Does this add anything to the discussion which has not been already stated, or does it express a position on a matter which was recently mentioned?"
  - `valuable`
  - `on_topic`
- **Floors** default to 0.70 each, captured at open. Every noul must reach its floor (E/config.py:28-31; E/judge.py:164-165).
- **State:**
  - XML with the original instructions, the topic, and the recent accepted responses and chair comments of the **current topic**, newest first while they fit, whole messages only, then the candidate.
  - Tokens are estimated as len/3.
  - Cap: min(50,000, 0.8 × 65,536) per request and 0.8 × 32,000 per question (E/judge.py:108-156).
- **Retries** on 408, 429 and 5xx back off 2/4/8 s, all within `jev_wait` = 300 s.
- **On failure the table holds**, and the reply waits for Continue (E/runner.py:368-377, :987-988; E/openrouter.py:182-239).
- Repeat detection (NEAR = 0.95) is dead code (E/judge.py:29, :54-69).

## 6. Vetoes and feedback

- A veto is recorded with its nouls and never shown to peers (E/render.py:60-62, :266-295).
- The author gets one line per failed check at the start of its next turn (prompts.xml:624-631).
- The chair sees the vetoed text and scores (E/server.py:498-518).

## 7. Topic completion and next topic

- **Judged tables:**
  - `quiet_rounds` is reset by any acceptance.
  - Each seat's last two outcomes are tracked: PP, VV and VP are terminal; PV is not.
  - A topic finishes after 2 or more quiet rounds with every participant terminal, with correction turns for seats that aren't (E/store.py:582-642).
- **Unjudged tables:** a topic finishes when every participant passes in the same round (E/store.py:629-632).
- **Other ends:** chair `advance`, or 120% of the token budget (E/runner.py:273-277, :389-414).
- **Session topic selection:**
  - Each seat gets 2 attempts; busy seats are skipped.
  - Collection deadline: 30 s from the first request, once a candidate exists.
  - JEV is asked "Is proposal A similar to proposal B?" for each pair; each proposal's score is the mean, the highest wins, and ties are joined with blank lines.
  - A sole proposal wins without JEV. No proposal puts the table on hold (E/runner.py:1260-1349; E/topics.py).

## 8. Continuity and context

- **Delivery is pull-based:** at its turn a seat receives the accepted messages it hasn't seen. `seen` advances on the transport receipt (E/runner.py:888-907; E/seat.py:114-141).
- **Turn prompt order:** private feedback → allowance → budget notice → shared continuation (if the context is fresh) → the new messages (E/runner.py:905-909).
- Sessions keep their conversations across topics. Independent staged tables rebuild per topic (E/runner.py:441-452).
- **Context handoff** happens only in non-session tables, at a 24,000-token estimate: carry-forward notes, an editor, and seats reset (E/runner.py:711-845).
- **Native `/compact` between session topics** is optional (E/runner.py:1333-1364).

## 9. Agent harnesses and ACP

- **Launch:**
  - Pinned `claude-agent-acp@0.100.0`, `codex-acp@2.5.0`, and antigravity through an adapter, each in its own process group.
  - `ANTHROPIC_*`, `OPENAI_API_KEY`, `CODEX_API_KEY` and `ROUNDTABLE_*` are stripped from the environment (E/config.py:59-63; E/harness.py:45, :383-435).
- **Versions:** v2 offered first; a fresh v1 connection only on initialize-level evidence. Initialize and session creation are each limited to 120 s (E/harness.py:437-484).
- **Session:**
  - cwd is the workspace.
  - MCP servers are the table's `seat_mcp` (HTTP only).
  - Resume uses v2 `resume_session`, otherwise v1 resume or load with replay suppressed (E/harness.py:486-516).
- **Model and mode:**
  - A `model` option is required.
  - Offered choices are cached, and the model resolves by exact value, then the newest of its family, then name.
  - `set_config_option` is limited to 30 s. A missing model or mode makes the seat gone (E/harness.py:530-578).
- **Prompt turns have no deadline.** v1 completes on the response; v2 completes on the response and then idle. Cancel waits 15 s (E/harness.py:665-870).
- **Permissions:**
  - approve-all and approve-reads are answered automatically with allow_once.
  - Otherwise requests are relayed to the person with no timeout. Elicitation is declined (E/harness.py:343-358, :623-647).
- **Close:** `close_session` (15 s), then SIGTERM to the group, 10 s, then SIGKILL (E/harness.py:799-830).

## 10. OpenRouter participants

- `vendor/model` or `openrouter:` seats are called directly through chat completions, not over ACP. They send the conversation since the topic start (E/openrouter.py:320-396).
- `max_tokens` is 1,024 plus credits, reasoning effort is "low", and caching is used for qwen and anthropic (E/openrouter.py:133-150; E/config.py:48-52).
- **Errors:**
  - A 402 makes only that seat unavailable, then a probe after 60 s, and also holds the table.
  - Other 4xx errors mark the seat refused.
- The model list `/v1/models` is cached for 600 s. Spend defaults to $2 per table and holds the table when reached (E/web.py:38, :319-327; E/runner.py:287-289).

## 11. Seat health

- active → degraded after 2 failures → unavailable after 4. Credit, refused and gone go straight to unavailable (E/health.py:46-65).
- Probes run at 300 s (60 s for credits) and double up to 3,600 s. A gone seat comes back only through reseat (E/health.py:26-77).
- Changes are announced as events (E/runner.py:184-193).
- With no usable seat, the table holds `held_empty`.
- There is no stall timer on ACP turns.

## 12. Chair controls and the interface

- **Engine MCP chair tools:**
  - open, comment (entered unjudged at the next gap), hold, continue, advance, end, abort, reseat, budget, permit;
  - read tools: status, list, read, review, submission (E/server.py:246-622).
- **Web stage:**
  - **Setup:** question, seats, permissions, 1-20 roundtables, compression, base allowance, token budget, judging.
  - **Live:** Hold/Continue, End discussion, End session, Abort, comments, budget, permissions.
  - **Display:** 3D seats with speech bubbles; the transcript is paced at 1,500 ms per turn (stage.js).
- **Past tables:** the stage only re-attaches to a running table. The engine's own page lists tables (refreshing every 5 s) and polls the store every 1 s for its event stream (E/resources/web/app.js:78-110; E/web.py:39, :200-226).

## 13. Participant tools

- **No Roundtable MCP tools were given to seats.** The bridge never passed `seat_mcp`; seats used their own native tools (M/follow.py:177-186).
- The engine's MCP server has the chair and read tools, plus `turn`/`submit` for outside agents (E/server.py:537-598).
- The `reference` verb resolves R-ids, `file:line` and bounded `rg` searches (M/references.py).

## 14. Identity, naming, ratings and accolades

- **Names:**
  - Each seat gets an FNV-1a adjective+noun name from a random UUID, retrying up to 64 times on collision.
  - Aliases persist by source and occurrence.
  - `participants.md` lists the names. Prompts forbid disclosing the model (E/identity.py:24-98; D/names.py:37-44).
- **Ratings** (sessions only):
  - Efficient ×10, Alert & Aware ×20, Thorough ×30 and Coordination ×40, each stars/5 × weight, plus a bonus of 5.
  - Points received are summed into the profile score, ratings and sessions.
  - "Your profile score is X…" goes into later system prompts (E/stages.py:34-36, :161-192; E/store.py:428-444; E/render.py:234-243).
- **Accolades: not implemented.**

## 15. Records and persistence

- **Engine SQLite** `~/.roundtable/roundtable.sqlite3` holds about 20 tables: discussions, seats, submissions, judgments, events, profiles, scorecards, topic proposals and decisions, permission requests, and others (E/store.py:67-163).
- **Message ids** `R<topic+1>-<n>` (E/store.py:677-683).
- **Reports:** a mechanical record, a model report for non-session tables, and a JSON export.
- **Saved shared record:** `docs/roundtables/<N>-<slug>/export.json` and `mechanical-report.md`, listing accepted messages only, with identities replaced (M/follow.py:382-421; E/export.py).
- The minutes and the live Haiku summary are dead code.

## 16. Workspace and deliverables

- The notes folder is `docs/roundtables/<N>-notes`, or the session folder (E/config.py:123-127).
- The prompts mention `shared.md` and `next-topic.md`, but no code uses either.
- There is no path gate on agents' file edits (E/harness.py:3-6).
- At the end of a session the folder is zipped and pushed to a git branch (M/chain.py).

## 17. Prompts

- **System:** "You are participating in a roundtable discussion as <seat/>. The seats, in speaking order: …" (prompts.xml:26-41).
- **Rules:** "Write one message or PASS when you have nothing to add." "Your turn limit grows after a pass or accepted messages missed while busy." (prompts.xml:16-20)
- **Per turn:** "Your limit for this turn is <limit/> characters. Write one message or PASS. Text beyond this limit is truncated." (prompts.xml:635)
- **Topic proposal:** "Propose the next topic in at most <limit/> characters…" (prompts.xml:637-645)

## 18. Timers, timeouts, budgets and caps

**Runner**

| Item | Value |
|---|---|
| Heartbeat | 5 s |
| Stale | 30 s |
| Report wait | 900 s |

**Waits and probes**

| Item | Value |
|---|---|
| `agent_wait` (not ACP) | 300 s |
| `topic_proposal_wait` | 30 s |
| `jev_wait` | 300 s |
| `probe_wait` | 300 s, doubling to 3,600 s |
| Credit probe | 60 s |

**ACP harness**

| Item | Value |
|---|---|
| Start | 120 s |
| Setting | 30 s |
| Cancel | 15 s |
| SIGTERM → SIGKILL | 10 s |

**OpenRouter and outside agents**

| Item | Value |
|---|---|
| OpenRouter timeout | 180 s |
| Backoff | 2/4/8 s |
| Outside agent poll | 0.25 s |
| Engine web store poll | 1 s |
| Page table refresh | 5 s |

**Budgets and limits**

| Item | Value |
|---|---|
| Spend | $2 |
| `seat_tokens` | 1,024 |
| `context_tokens` | 24,000 |
| JEV context cap | 50,000 |
| Reply LIMIT | 512 |

**Unbounded:** ACP turn deadlines and permission waits.

## 19. Other

- **Token budget:** notices at 50, 80 and 100%, and the phase is forced to end at 120% (E/budget.py; E/runner.py:389-414).
- Each seat holds a dispatch slot for the follower's life. `adopt` turns an idea into a ticket, and old Metaform tables can be imported.
