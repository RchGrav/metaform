# The old Roundtable compared with the intended design

**Intended** means the owner's specification (`README.md` = R, `Roundtable_ACP_Integration_Design.md` = D), the owner's documents in `archaeology/rich/` ([OWNER DOC]), and the owner's decisions given in session, recorded in `docs/TRACEABILITY.md` sections L and M.

**Old spec** is `OLD-SPEC-CONSOLIDATED.md`. **Old code** is `OLD-FUNCTIONALITY.md`.

**Verdict:**
- MATCH: the old code did what is intended.
- DIVERGED: the old code did something else.
- MISSING: intended, but not in the old code.
- EXTRA: in the old code, not intended.

The current Rust build is assessed separately in `docs/TRACEABILITY.md`.

## Turn-taking and work

| Area | Intended | Old spec | Old code | Verdict |
|---|---|---|---|---|
| Turn order | Sequential: "Agent1 speaks… agent2, 3, 4 all speak, when it comes back to agent 1…" | Seats speak in order; busy seats skip | Turns run **concurrently**: a new turn starts each loop while others are still running; only JEV is serialized | DIVERGED |
| How work is known | Agents do not announce work ("Saying work, thats not a thing"); a busy agent is working, observed through ACP (D §6) | Readiness from ACP foreground and background reports | Inferred from ACP v2 `state_update` activity and background reports; no work token | MATCH |
| Busy agents | Skipped, not terminated; the discussion continues (R §4.4, §10.3) | Busy skip; no group barrier | Busy seats skipped and excluded from the quorum; no deadline on ACP turns | MATCH |
| Few agents free | If everyone, or everyone but one, is busy, the table waits; the lone free agent is told to review the materials | When all are busy, wait for activity, never manufacture rounds | Waits on events when all are busy. With one free agent it keeps prompting it; only a seat that already passed is held back until a new message | DIVERGED (no review prompt; one free agent keeps being prompted) |
| Timers | None anywhere | Many (startup, setting, cancel, `jev_wait`, proposal window, probes) | About 40 timers and polls (`OLD-FUNCTIONALITY.md` §18) | EXTRA |

## Allowance, replies and feedback

| Area | Intended | Old spec | Old code | Verdict |
|---|---|---|---|---|
| Base limit | 512 by default; the user sets it, agents cannot change it | `reply_limit`, default 512 | `reply_limit` captured at open | MATCH |
| Credit | "credited for missed chats… because they have more to respond to"; no double credit for one skip; no credit for another agent being skipped. Exact rule awaits the owner | `512 × (1 + PASS credits + missed accepted peer messages)` | An own pass always earns +1, even when nothing was said; each peer message accepted while this seat is busy earns +1; acceptance spends the credits offered | DIVERGED (a pass earns credit with nothing new to respond to, which allows banking; per-message credit can exceed one per skip) |
| Veto and allowance | No credit; the bank is unchanged | No credit; nothing spent | Unchanged | MATCH |
| Truncation notice | At the next turn: "Message went past your 512 Character Limit, 23 Characters Lost" | Truncate before judging | Truncated, **but the participant is never told** (empty prompts) | DIVERGED |
| Veto reason | At the next turn | Author only, at the start of the next turn | One line per failed check, at the start of the next turn | MATCH |
| Next-turn order | Truncation notice → veto reason → each agent's message → "You have N Characters to Respond" | — | Feedback → allowance → budget notice → messages | DIVERGED (allowance before messages) |
| PASS | A reply of PASS | "Write one message or PASS" | Whole-reply regex; never judged | MATCH |
| Empty reply | (Kept as a loud error: run 1 had 44 empty replies) | No invented outcome | Recorded as kind `none` with a reason | MATCH |

## JEV and topics

| Area | Intended | Old spec | Old code | Verdict |
|---|---|---|---|---|
| Checks | The three R §5.1 conditions at 0.70 | Same three, 0.70 | Same wording, floors 0.70 | MATCH |
| JEV context | "previously unstated" (R §5.1); 64K context | Newest accepted messages, 50K-token target | **Current topic only**, 50K cap | DIVERGED (current topic only) |
| JEV failure | Optional; continues unjudged; "a reply or an error"; no time limit | Retries within `jev_wait` 300 s; failures hold | **The table holds** until Continue; retries within 300 s | DIVERGED |
| Topics without JEV | No topic mechanism; agents work toward the opening prompt | Unjudged: one unanimous PASS rotation finishes the topic | Unjudged tables finish on one all-PASS round | DIVERGED |
| Topic completion | Two nonproductive rounds, or two all-pass rounds; a skip counts as a pass | Quiet cycles plus terminal PP/VV/VP states; correction turns | Same as the old spec; 120% budget also ends | DIVERGED (extra terminal-state rule, budget ending) |
| Topic poll | Ask the free agents; busy agents are not waited for | Up to 2 attempts; a 30 s window | Up to 2 attempts; a 30 s deadline once a candidate exists | DIVERGED (attempts, timer) |
| Sameness question | Same underlying intent, not similar words (R §7.1) | "similar" | "Is proposal A similar to proposal B?" | DIVERGED |
| Scoring | Credited to both, **summed**, highest wins, no threshold | Averaged | Mean (same ranking when every pair is answered) | MATCH in outcome |
| Ties | Two ties joined with "and" | Joined verbatim | All ties joined with blank lines | DIVERGED |
| Proposal length | 512 (broadcast cost, R §1.2) | 512 | Cut to the base limit | MATCH |

## Continuity and ACP

| Area | Intended | Old spec | Old code | Verdict |
|---|---|---|---|---|
| Continuity | Same sessions across topics (R §8) | RT-001 continuous | Sessions keep conversations | MATCH |
| Message delivery | Each other agent's message at the next turn | Ordered inbox, checkpoint at send receipt | Pull-based at the turn; `seen` advances on receipt | MATCH |
| Context handoff | Not in the R/D spec. [OWNER DOC] AID: "Agents may handoff based on % of context used, or based on satisfying a goal" | Legacy 24K handoff for independent tables only; optional `/compact` | Same | Owner-doc item outside the current spec; ask the owner |
| ACP version | Negotiated; v2 where supported (D §4) | v2 offered, v1 fallback | v2 first; fresh v1 on initialize-level evidence | MATCH |
| ACP authenticate | When required (R §9.1) | — | Not called | MISSING |
| ACP load/resume | Restore context (R §9.1) | Resume or load | v2 resume; v1 resume, else load with replay suppressed | MATCH |
| `set_config_option` | Only advertised options (D §4) | The person picks every model; an unoffered model is refused | Cached offered choices; a missing model or mode makes the seat gone | Partial MATCH (gone on a missing mode is EXTRA) |
| ACP close | `session/close` where advertised; cancel only on request | Explicit Stop/End may cancel | `close_session` 15 s → SIGTERM → 10 s → SIGKILL | MATCH in shape (timers EXTRA) |
| Permissions | Automatic: inside the workspace, or across the project; never stuck | The person chooses the policy | approve-all and approve-reads automatic; otherwise relayed to the person, **waiting with no timeout** | DIVERGED (the default relays and waits on a person) |

## OpenRouter, monitoring and the chair

| Area | Intended | Old spec | Old code | Verdict |
|---|---|---|---|---|
| OpenRouter participants | Model id from the published catalog; run through an ACP runtime (Pi, or the Agent SDK behind an ACP adapter) (R §9.4, D §7.3) | Any non-ACP id is an OpenRouter model | **Direct chat completions, outside ACP**; model list cached | DIVERGED |
| Spend and budget | Not in the spec | `$2` spend; token budget 50/80/100/120% | Spend cap holds the table; token budget forces an advance at 120% | EXTRA |
| AgentSight | Independent observation of process, tool, file and network (R §10.2, D §8) | — | Not implemented | MISSING |
| Seat health | Busy is not failure; no automatic termination | Probes; departed seats do not block | degraded/unavailable states, probes at 300 s to 3,600 s, `held_empty` hold | EXTRA |
| Crash | A bug: fail loudly, then fix | Seat-loss event to the person | Seat marked gone; event; reseat to restore | Partial MATCH (an event, not a loud failure; `held_empty` hold is EXTRA) |
| Chair controls | Hold, resume, guidance, end; the owner's later hold interface | Comment, hold, continue, advance, reseat, end, abort | All of these, through MCP and the web stage | MATCH (more than intended) |
| Reviewing past tables | Owner: the chair can review prior roundtables | `tables`, `status`, `events`; page keeps results | Stage re-attaches only to a running table; the engine's own page lists tables by **polling every 1 s and 5 s** | DIVERGED (polling; not on the stage) |
| Never poll | Owner: "never poll what can surface as an event" | Event-driven control | Engine web polls the store every 1 s; outside agents poll every 0.25 s; table refresh every 5 s | DIVERGED |

## Tools, identity and records

| Area | Intended | Old spec | Old code | Verdict |
|---|---|---|---|---|
| Participant tools | `advance` (head of the table, no role checks) and `feedback` (owner) | None for seats; module verbs callable by agents | **No Roundtable tools given to seats** | MISSING |
| Agent names | [OWNER DOC] name from the genesis session id (FNV-1a → fold → adjective+noun) | Generated names; model hidden | FNV-1a of a **random UUID**, retrying up to 64 times on collision | DIVERGED (seed and retry) |
| Ratings | Agents rate each other, building accolades and identity, weighting their return (owner) | Four weighted categories plus bonus, summed into a profile | Scorecards at the end of a session; profile score in later prompts | MATCH (at session end, not as a tool) |
| Accolades | Reward and stake for doing well (owner) | Promised, no mechanism | Not implemented | MISSING |
| Summaries | "not a conversation summarization system" (R §1); [OWNER INSTRUCTION] "no automatic summary or minutes are provided" | Synthesis, ranking, host summary and reports for independent tables; reporter history | Non-session tables run synthesis → ranking → host summary → report; minutes and Haiku summary are dead code | EXTRA for independent tables; sessions MATCH |
| Records | A complete record (every event, every prompt sent) | Engine DB plus safe shared export | SQLite with ~20 tables; safe export; mechanical record | MATCH |
| Message ids | Kept (run 1 had turn-label drift) | `R{panel}-{n}` | `R<topic+1>-<n>` | MATCH |
| Workspace | Shared folder; deliverables, not summaries (R §2, §11) | RT-009 | Notes or session folder; no path gate | MATCH |
| Participant prompt | R §3 verbatim, plus the turn format | Builder prompts; [OWNER INSTRUCTION] TASTE writing register delivered | Builder prompts; TASTE delivered; "do not disclose model" | DIVERGED (the R §3 prompt was not used). Ask whether TASTE applies |

## What the old version got right

These match the intended design and are worth studying, not copying blindly:
- Work inferred from ACP activity (`state_update`), with no announcement.
- ACP v2 with v1 fallback; session resume and load with replay suppressed.
- Pull-based delivery of others' messages at each agent's turn.
- The veto reason at the start of the next turn.
- Stable message ids.
- No deadline on agent turns.
- The owner's rating categories.

## Where it went wrong

Each item breaks something the owner intended:
- Concurrent turns instead of sequential turns.
- Passes earn credit with nothing new to respond to, so agents can bank allowance.
- Truncation is never reported to the agent.
- The table holds when JEV fails.
- Topics run without JEV.
- About 40 timers and several polling loops.
- OpenRouter seats bypass ACP.
- Permissions wait on a person.
- Spend and budget gates that hold or end the table.
- Seat-health machinery.
- Summaries and synthesis stages.
- Similarity instead of same-intent judging.
- No participant tools.
- No AgentSight.
- No accolades.
- Names seeded randomly instead of from the genesis session.

## Questions for the owner raised by this comparison

1. **Context handoff.** Your AgentIdentity note says agents may hand off by percentage of context used or by satisfying a goal. Is handoff part of Roundtable, or a later platform feature?
2. **TASTE.** Your writing register was delivered to agents in the old version. Should Roundtable agents receive it?
3. **Hiding models.** Should models be hidden from peers? That rule came from the old builder's documents.
4. **Ratings.** Collected at the end of a session as scorecards (old), as a `feedback` tool during the table (your instruction), or both?
