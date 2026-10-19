# Draft amendments for code.interface.graphical#87 (650bc855), for the owner's approval

Written 2026-10-15 to match what is built. Not yet in `specifications/`.

## VIEW-002 (specifications/09-viewer.md, after the 2026-10-15 hung-server amendment)

Sentences the code now contradicts, in that amendment: "Every 5 s the watchdog asks `/api/health`. It starts the
server again when the server's process ends, when nothing listens where an adopted server served, when health answers
503 because a page read is stuck, or after 20 s with no healthy answer." and "The page (`page/app/core/health.js`) asks
`/api/health` every 2 s, and at once when a read fails or gets a 503."

Proposed bullet:

- Amendment, 2026-10-15, nothing asks the server on a clock, written to match what is built, ticket
  code.interface.graphical#87 (650bc8554b964967bc1baf3c892fab08): the watchdog asks `/api/health` nothing. It follows
  its own server by the server's standard output pipe, kept open past the ready line: a line `{"stuck": cause}`, then
  the pipe's close as the process ends. It follows a server it handed over to by the system's own event of that
  process's exit (a pidfd on Linux, kqueue on macOS, the process handle on Windows); where a system gives none, it
  ends that server and starts its own. A hang is the server's own deadline: a page read whose work still runs 20 s
  after it began is logged, and under the watchdog the server writes why on the pipe and exits with code 75, so the
  watchdog starts it again with that cause. The page asks `/api/health` once each time something says the server may
  be gone or slow (the events stream's error, a read that failed, got a 503, or still waits after 3 s) and once each
  time it may be well again (the stream's open, a read answered while the banner shows); it never asks on a timer.
  The banner says the same things; the not-answered banner says the watchdog starts the server again as soon as it
  ends. Before: the watchdog woke every 5 s (1284 wake-ups a minute measured at idle) and an open page asked every 2 s
  (30 requests a minute). Why: the owner's rule that Metaform is event driven and nothing polls. Acceptance:
  `test_a_read_stuck_past_its_deadline_ends_a_server_under_the_watchdog_saying_why_on_its_pipe`,
  `test_the_watchdog_wakes_on_its_servers_pipe_and_on_a_handed_over_servers_exit_never_on_a_clock`,
  `test_the_page_asks_the_servers_health_only_when_its_stream_says_the_server_went_and_came_back`,
  `test_nothing_in_the_web_server_its_watchdog_the_page_or_the_views_waits_on_a_clock_to_see_a_change`.

## VIEW-018 (the live stream)

Proposed bullet:

- Amendment, 2026-10-15, a page reads only what a change concerns, written to match what is built, ticket
  code.interface.graphical#87: the page reads map.changed's `kinds` and `work_ids` (dispatcher#38's fields). It reads
  the agents' sessions again only for a change to a session, a signal, a permission or a question, and the open chat
  only for a change to its own ticket; a change that names neither is read whole as before. A change to an agent's
  thread lines alone reads no workspace pane. A page that closes its stream is dropped as its socket closes, and the
  server says each open and close of a project's page to the home's other processes as `map.changed`
  `{tables: ['web.pages'], kinds: ['pages'], pages: N}`. A voice model's download progress comes to the page as the
  topic `voice.download`, pushed as each whole percent arrives. Before: each agent line read every session and every
  claim (266 requests a minute at two lines a second). Acceptance:
  `test_an_agents_thread_lines_read_no_session_again_and_a_change_to_its_session_reads_them`,
  `test_a_page_opening_and_closing_its_stream_is_said_to_the_homes_other_processes_as_it_happens`,
  `test_a_voice_model_download_pushes_what_has_arrived_to_the_open_pages_as_it_arrives`.

## VIEW-042 (the agent starter)

Proposed bullet:

- Amendment, 2026-10-15, the agent starter runs only for changes that can start work, written to match what is built,
  ticket code.interface.graphical#87: a change whose `kinds` name no ticket, message or question starts it only when
  it names a glyph, ticket-setting, eligibility, dispatch-setting, claim or raised table; any other change is judged
  by its tables as before, and one that names none may have changed anything. The merges' review timers (VIEW-044)
  are read again only for a change to the merges table, a `merge` kind, or a change that says nothing. Before: every
  runner announcement with no table detail ran the starter and a `metaform dispatch merges` process (a full core at
  two a second in a scratch home). Acceptance: `test_change_triggers_only_relevant_dispatch_checks`,
  `test_a_change_runs_the_agent_starter_and_the_merges_read_only_when_it_can_need_them`.
