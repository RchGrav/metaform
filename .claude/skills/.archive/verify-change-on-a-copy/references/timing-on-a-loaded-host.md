# Timing on a loaded host

Use this file when timing a benchmark, a frame p95/p99, or a browser test's time window on a CPU other agents load, or when a long run would block the chat.

## Check the load before you trust a number
- Run `uptime; nproc`. When the 1-minute load average is near the core count, a single timing is noise, and a slower "after" may be the machine, not the code.
- Measure the hot work itself inside the process: warm up, then time thousands of iterations and report the per-iteration cost. A whole-page frame probe under load mostly measures the load.
- Compare before and after in alternating rounds (at least three), so both sides see the same load. Report every round with the load beside it, and claim a difference only when the rounds agree.
- Do not read a regression from one run taken during a load spike; rerun later, or say the result is unmeasured.
- Report median, p95 and p99 for any frame timing. A p95 that moves between rounds is unresolved, not a win.
- On a GPU the person also uses for their live display, a headless frame probe competes with that display. Say so before running it, and keep p95 as unresolved when the rounds disagree rather than calling it a regression or a win.
- Name the load and the round count in the report next to the numbers.

## Keep the chat reachable during long work
- Anything longer than about a minute (a test run, a trace, a build, a benchmark, a wait loop) goes to a background run or a subagent. The foreground turn stays short, so the person can always message and get an answer.
- Start the run in the background, say in one line what it checks, and reply in the same turn. Answer questions while it runs; do not poll in your own turn.
- Wait with a background `until grep -q 'passed\|failed' FILE; do sleep 5; done` and read the output file when it notifies. A foreground `sleep N; cat FILE` is blocked by the harness, and chaining shorter sleeps to get around it is not a fix.
- This binds the agent the person talks to, the system agent included: test runs, traces and fixes go to a subagent or a ticket, even when the work looks small.
- Give a subagent the observed failure, the files and the check that proves the fix, and ask for a report under a word limit.
- When the result arrives, report what passed, what failed, and any check that did not run.

Why: a person who cannot reach you during a long run cannot steer it, and a turn blocked for minutes reads as a stalled agent.
