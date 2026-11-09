# Spec audit (independent agent, 2026-11-05)

Read-only audit of the Rust implementation against README.md, Roundtable_ACP_Integration_Design.md
and the owner's direct decisions. Builder documentation was not treated as authority. The working
tree was mid-change (deliberation window, setup timeouts and JEV limit removed; skips count as
passes; wait when fewer than two are free). The participant prompt matches README §3 byte for byte.

## 1. Violations

- **V1 High.** One live seat stalls forever, and a 1-seat table never starts. `MIN_FREE_TO_DISCUSS = 2` (engine.rs:10-11, 422-429). If a seat exits at a 2-seat table, the survivor is never prompted and the table neither ends nor publishes anything. The owner's wait rule means waiting for a busy participant to come back, and here nobody can come back. No event says the table is waiting. Two tests still expect the old behaviour (tests/engine.rs:231, 247).
- **V2 High.** An agent that works while holding the floor blocks the whole table, and the prompt tells it to. The only work detection is a streamed first line of exactly `WORK` (engine.rs:511-528, rules.rs:85-100). prompts.rs:22 tells agents "Use tools ... first, then write your contribution", so an agent reading the workspace keeps the floor while everyone waits. This contradicts README §4.4, §4.7 and §10. `WORK` without a trailing newline followed by a tool call stays "undecided". The engine ignores ACP `ToolActivity` events (engine.rs:372-382). The spec's mechanism for "occupied" is observed activity (Design §6, README §10). Recommendation: tool activity during a floor turn makes the seat occupied (floor released, skip credit), and its eventual reply is judged when it arrives. Remove the "use tools first" line.
- **V3 High.** AgentSight is not implemented at all: no dependency, code, event or UI. This violates README §10.2-10.3 and §12, Design §8, proof point 10.7, and the owner's reusable-layer requirement. docs/IMPLEMENTATION.md relabels ACP-reported data as "AgentSight activity monitoring".
- **V4 Medium-High.** The GUI never calls `/api/models`. Model hints are a fixed list for claude-acp and codex-acp only (index.html:162-165), which violates README §9.4 ("published model catalog, rather than from a fixed list"). There is no Pi/OpenRouter route. If a model fails to apply, the seat continues on another model with only a warning (engine.rs:755-762).
- **V5 Medium-High.** The OpenRouter Agent SDK ACP adapter is not built (README §12, Design §7.3 path 2).
- **V6 Medium.** The PROCESS prompt (prompts.rs:24) misstates the topic rules. It says independent work keeps a topic alive, which the code does not do, and it omits that being skipped counts as passing. docs/IMPLEMENTATION.md:53 is stale in the same way.
- **V7 Medium.** A polled seat that starts working holds up the poll, because WORK detection runs only on the floor (turn.rs:214-257, engine.rs:516). A single free seat can be polled alone and choose the topic with no comparison.
- **V8 Medium.** A failed `mode` setting keeps a seat out (engine.rs:755-760). Neither the spec nor the owner calls for this gate.
- **V9 Medium.** Missing ACP lifecycle: `authenticate` is never called; `session/load` and `session/resume` are unused; a crash loses the seat permanently, with no relaunch or restore; only v1 is negotiated, so there are no v2 `state_update` reports.
- **V10 Medium-Low.** JEV judges novelty against the current topic only (turn.rs:128-129), although §5.1 asks about anything "previously unstated" and §8 continues the discussion. The 24,000-character history cap (jev.rs:105-107) comes from the archive; the spec gives a 64K-token context.
- **V11 Low.** Veto reasons are canned text per condition (prompts.rs:39-48), not reasons from JEV. The API may return only confidences; this is uncertain.
- **V12 Low.** "Two rounds of skips ends the roundtable": the code advances the topic, which matches §6. Whether the owner means the table itself ends is uncertain. With MIN_FREE=2, a 2-seat table never skips anyone, so the rule only applies at 3 or more seats.

## 2. Inventions

[G] = conflicts with "no extra logic and gates". [T] = timer.

- **I1 [T]** Shutdown sends SIGTERM, waits 3 s, then SIGKILL (harness.rs:535-547).
- **I2 [T]** `setTimeout(loadPast, 500)` refetches history after `roundtable.ended` instead of updating from the event (index.html:228).
- **I3** Dead leftovers from the deliberation window: the `late` fields and paths, `record_late_accept`, the "still on its previous prompt" skip arm, and the UI's "late" state. Stale docs: IMPLEMENTATION.md:52 and RESOLUTION.md rows 5 and 7.
- **I4** A warning after two idle topics (turn.rs:313-327).
- **I5 [G]** `advance` is refused during a poll, but the MCP tool has already told the agent "The next topic is set to…".
- **I6 [G]** Feedback validation, with categories copied from archive stages.py. The text says ratings "weigh in who is brought back", but nothing in this code uses them.
- **I7** Topic proposals are truncated to 512 characters and labelled "private".
- **I8** Unjudged pairs score 0, so with JEV off all proposals tie and are joined. Joining three or more ties extends §7.4.
- **I9** An "ignore instructions in participant text" suffix is added to every JEV question.
- **I10** The reply is only the last text block after the final tool call (harness.rs:62-77).
- **I11** An empty reply counts as a failed turn: no credit, and it breaks the all-pass streak.
- **I12** The first topic defaults to the objective; message IDs take the form `R{topic}-{n}`.
- **I13** Secrets are stripped from agents, registry env variables are deny-listed, and seat names are restricted (security engineering, low).
- **I14** A hard-coded critics preset in the GUI.
- **I15** The engine waits for each JEV judgment before giving the next floor; §4 says the process continues while the system evaluates. Without a timeout, a JEV connection that hangs without erroring stalls the table.
- **I16** The agent is answered `Cancelled` when it offers no matching permission option, which may end its turn.

## 3. Missing or partial

- AgentSight.
- OpenRouter catalog selection in the GUI, the Agent SDK adapter, and Pi/OpenRouter configuration.
- ACP `authenticate`, `session/load` and `session/resume`, and v2.
- Detecting independent work from observable activity.
- The project-wide permission scope is settable only through the JSON API, not the GUI.

Verified compliant:
- Allowance accounting.
- Truncation before JEV, with the count reported at the next turn.
- Deferred veto feedback.
- Three conditions at 0.70.
- Pairwise summed topic selection with no threshold.
- Continuous sessions.
- Busy seats left out of polls.
- No setup or JEV timers.
- An event-driven bus.
- The verbatim §3 prompt.

## 4. Copied from the old version

- JEV condition wording and state shape. The wording fits §5.1; the current-topic filter and the cap do not.
- Feedback categories.
- The "late" concept (now dead code).
- Message IDs (probably from the archive).

## Owner decision noted by the audit

- In a 2-seat table under the wait rule, a working agent is never skipped, so it never earns the "+512 per skipped turn" that the verbatim §3 prompt promises.
