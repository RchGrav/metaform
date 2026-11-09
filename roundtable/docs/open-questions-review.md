# Review of every open question against EXPECTATIONS.md (2026-11-07)

Every open question from the Roundtable work was worked through as the owner's `EXPECTATIONS.md` asks: decide where the evidence supports an answer, and leave open only what depends on the owner. The 145 proposals the resolution check had marked "no owner source" were each decided in `egm-resolution-check/decide1.md` to `decide4.md`: 57 adopted, 86 adopted with changes, 1 rejected, 1 left for the owner.

## Specification updates

Built on branch `roundtable-settings` (commits 4f82985 and c30bcd8), tested:

1. **Every gate with a sensible "off" or limit is a setting** that only the chair can change, at `/settings` or `/api/settings/...`. Changing one is the owner's disposition of that gate. Saved settings store only what was set, show each value's source, refuse bad values with the allowed range, and reset to the default (the owner's settings design, C-9 to C-17).
2. **Permissions are rules per request kind.** Each ACP request kind (read, edit, delete, move, search, execute, think, fetch, other) is answered "inside" (today's behaviour), "allow" or "refuse". `permissions.scope` picks the workspace, the project, or a path.
3. **A topic proposal over its limit is blocked, never cut.** The owner: "we arent going to be truncating if we add limits in we will block messages for being too long". The words are general, and blocking keeps one rule for every text an agent sends.
4. **A topic poll asks only the agents that are free.** This follows the owner's decision of 2026-11-05: "the table never waits on independent work". `topics.poll_busy_agents` brings the wait back.
5. **A table needs at least two seats.** The owner: "atleast 2 agents available to debate".
6. **Each rejection label shows JEV's result,** for example "- Relevance (0.42): …". The evaluation spec says: "Labels include the dimension and returned numeric result".
7. **"No more good input" means `table.quiet_rounds` rounds in a row with nothing accepted, default 2.** These are the owner's own words: "2 rounds with no good input".
8. **JEV is required (owner, 2026-11-07).** No judging switch, no table without JEV's key, and a message JEV could not evaluate is not shared: the chair sees the error, the author is told it was not rejected, and the table continues. Before, such a message was shared unjudged. See `gate-development-log.md`, 2026-11-07-05.
9. **The shutdown kill can be switched off.** With `shutdown.force_stop` off, an agent's input is closed and Roundtable waits for it to exit, with no signal. It stays on until the owner decides on RT-G20.

Decided, not yet built:

10. **A JEV call gets a deadline (proposed setting `jev.deadline_seconds`, default 30).** When the deadline passes, the message is not shared and the chair and author are told, which is the path a JEV error now takes.
11. **A refused permission request reaches the agent at its next turn,** through the same channel as rejection reasons, because ACP's permission answer has no field for a reason.
12. **Table creation fails, with the operating-system error, when the workspace folder cannot be created.** Today the error is ignored, and the permission boundary is built over a path that does not exist.
13. **The length notice uses the owner's rejection format:** the owner's prefix, then "- Length (N of M characters): …". The sentence after the label stays the builder's until the owner writes his own.
14. **During the rating round, the chair sees which agents have not rated yet.** There is no timer; the chair can end the round.
15. **The chair token is accepted in the URL query only for the event stream.** Every other route takes it in the header only.
16. **The 143 decided map proposals** in `decide1.md` to `decide4.md` are applied to the map through the map server.
17. **The two remaining files over 500 lines are split:** `acp-host/src/harness.rs` (1,324 lines) and `agent-monitor/src/capture.rs` (558 lines).

## Decision rationale

- **JEV deadline (10).** The owner's statement is "If JEV is down this doesn't halt, it continues". A connection that hangs without closing is JEV being down, yet today it stops the table: the HTTP client has no timeout, and the next turn waits for the verdict (RT-G10). The comment "No timer: it gets a reply or an error" also holds with a deadline, because a deadline turns a hang into an error. Session decision 14 ("no timeouts") is about agents running long. It does not cover a call to an outside service. Confidence is high on the need. Thirty seconds is a judgement: JEV answers in about one to two seconds.
- **Topic poll and free agents (4).** The owner decision of 2026-11-05 governs. The opposite rule came from README §7, which the owner said "was never my spec". There is no test for the new default path.
- **Rounds still count turns skipped while busy.** The 10-round bound exists for cost, and "a busy agent's turn is skipped" is owner-designed (RT-G04). Agents' work is not stopped at the last round: the rating round asks each busy agent only once its work ends (`rating.rs`, `start_rating`). An earlier note that "work in progress stops at the last round" was wrong.
- **Defaults keep today's behaviour,** except where an owner decision says otherwise (3, 4 and 5).

## Open decisions for the owner

1. **Pending gates.** Only the owner disposes of a gate (Gate Burden). Each can now be switched by setting, without editing code. Recommendations:
   - **RT-G20, shutdown kill.** Turn `shutdown.force_stop` off, add a chair "stop" control for agents still running, and keep killing leftover process groups when the Roundtable server itself exits. Keep the timers only if tables are often left unattended after End and cost matters more than work in progress.
   - **RT-G11, advance refused during a poll.** Remove it: there is no witness, and topics are off by default.
   - **RT-G13, topic proposal limit.** Keep it at 512 now that it blocks instead of cutting.
   - **RT-G21, poll waits for busy agents.** Remove the waiting code after the topic refinement. It is off by default already.
   - **Keep, because each has a witness:** RT-G09, RT-G10 (with the deadline), RT-G12, RT-G14, RT-G15, RT-G16, RT-G18 and RT-G19.
2. **How agents state "done" in unlimited mode.**
   - Dependency: a clean signal needs a new participant tool, and new tools need the owner's decision.
   - Option A, a `done` tool: unambiguous, and it costs one tool definition. This is the recommendation.
   - Option B, a message that says "done": no new tool, but it is fragile, and JEV may reject it.
   - Option C, no "done": quiet rounds alone end the table.
   - Until the owner decides, unlimited tables end on quiet rounds.
3. **One immediate retry after a rejection** (the owner's own idea).
   - Recommended: one retry, with the reasons, before the next agent speaks. In the EGM run 240 of 386 messages were rejected, and the reasons are most useful while the agent's context is fresh. The cost is one JEV call (about $0.00005) and a short delay for the next agent.
   - The alternative is today's behaviour: the reasons arrive at the agent's next turn. It is better if tables must move fast.
   - This changes the turn order, so it needs the owner.
4. **AgentSight capture.** Today the only working setup is running the whole server as root, which makes every agent and every allowed command root.
   - Recommended: give only the capture helper the kernel capabilities it needs (`setcap cap_bpf,cap_perfmon`), and change the root check to a capability check.
   - The alternative is to leave capture off.
   - This depends on what privileges the owner will grant on his machine.
5. **The scoring prompt's rubric** (code.rating.peer, row 7). The prompt combines two owner texts that the owner has not approved together.
   - Recommended: keep it, because every word is his and the rubric gives the weights meaning.
   - Go back to the exact roundtable scoring prompt if the rubric was left out on purpose.
6. **What "R" counts in "[R1-2]".** It counts topics, so with topics off every ID starts "R1".
   - Recommended: keep it, because the IDs are stable and old records stay valid.
   - Count rounds instead if the owner reads "R" as "round" when following a table.
7. **The text of the length notice and of "done".** These are owner texts.
8. **Mid-turn delivery to ACP v2 agents.**
   - Recommended: deliver only chair messages mid-turn. Discussion messages already reach a busy agent when it returns.
   - This depends on how much the owner wants to steer working agents.

## Risks and verification

Safety-relevant first:

1. **A hung JEV call stops the table** until item 10 is built.
2. **Agents are killed on any connection end, not only at shutdown,** while `shutdown.force_stop` is on (the default). SIGKILL can damage workspace files, git state and session records.
3. **Agents' shell commands are not confined.** An allowed command can reach anything the user account can, and it sees the environment except Roundtable's three secrets. For Pi and OpenCode seats that share the OpenRouter key, any command the agent runs can read the key. This is the residual risk recorded with the owner's permission decision; `permissions.execute = refuse` now closes it for tables that do not need commands.
4. **The chair token in a URL query can reach logs and browser history** until item 15 is built.
5. **Running the server as root for AgentSight makes every agent root** (open decision 4).
6. **A workspace folder that cannot be created is ignored** until item 12 is built.
7. **The registry's environment filter misses some loader variables** (PYTHONHOME, package-index and certificate overrides), and npx and uvx entries show as available without checking that the command exists (`decide4.md`).

Verification done:
- `cargo test --workspace` passes, with five new tests: permission rules per kind, the settings store, gates and settings agreeing, a topic proposal blocked over its limit, and the settings API.
- A live server served `/settings` and saved one change, writing only that key.

Verification still needed:
- A live table run on the new branch.
- A test of the topic poll with `topics.poll_busy_agents` off.
- A live check of `shutdown.force_stop` off, with an agent that ignores its closed input.
- A check that the new-table form starts from the saved settings in a browser.
