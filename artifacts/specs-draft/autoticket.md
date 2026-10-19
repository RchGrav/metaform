# autoticket: a log watcher that ranks errors by how often they happen (draft for Rich, 2026-10-15)

Status: design draft, nothing built. Worked out with Rich on 2026-10-15. Open points are marked **Open**.

## What it is and why

autoticket watches a project's logs while work goes on, and turns repeated errors into a ranked list the orchestrating agent acts on. Agents otherwise see only code and the map. This shows them what the running system does wrong, ranked by how often, without anyone reading logs. It matters most during large refactors: a new kind of error is seen as soon as it appears, while the change that caused it is small and fresh, not after more work has been built on it. When a fix lands, its group's counter stops rising, which is evidence that the fix worked. A counter that rises again later is a regression.

## Module

- `src/metaform/modules/autoticket`, shipped with Metaform and off until enabled.
- Settings:
  - `autoticket_interval_minutes`, default 15. It times the ranked list, and the first list sets the baseline.
  - `autoticket_similarity`, default 0.45. The Dice threshold for "the same kind of line".
  - `autoticket_capture`, default errors. What counts as an error: level words such as ERROR, FATAL, CRITICAL, Traceback and Exception.
  - The list of watched logs.

## Watching

- A watched log is a local file, or a file on a host reached with the system's own `ssh <host> tail -F <path>`. Rich's `~/.ssh/config`, keys and agent apply, and Metaform stores no credentials.
- Lines are read as they arrive. The log is never copied or stored.
- Reading is event driven: a local log at its end is followed through the system's own change notification (inotify on Linux, kqueue on macOS), and a remote log through the stream `ssh <host> tail -F` sends; nothing looks at a log on a timer. Why: a watch runs for hours beside the work it watches, and a look on a timer costs CPU all that time to learn that nothing changed. The interval below times the list, never the reading. (Change, 2026-10-15, dispatched ticket 2ede3067 (code.system.management.knowledge#32), the no-polling rule: before, a local log at its end was looked at every 0.25 s.)
- An agent may add capture rules as regular expressions. Matching lines are grouped exactly as errors are.

## Entries

- An entry is one logical event, not one physical line. A Python traceback, a Java or JavaScript stack trace, and any line followed by indented continuation lines are joined into one entry, up to the next line that starts a new record: a timestamp or level prefix at column zero. An entry is closed after 2 s of quiet, so the last one is never held back.
- An entry is captured when any of its lines matches the capture rules.

## Grouping: Rich's method from his onhold log viewer (src/viewer/filter.c), used as it is

- An entry's fingerprint is the set of its alphanumeric words of two or more characters, lowercased and hashed with FNV-1a, at most 64.
- Two entries are the same kind when the Dice coefficient of their fingerprints, twice the shared words divided by both counts, is at least `autoticket_similarity` (default 0.45, onhold's value).
- An entry joins the first group it matches; otherwise it starts a new group. This matches how onhold's viewer filters similar lines: proven accurate there, with no model and no embeddings.

Per group the module stores only: its fingerprint, one example entry with secrets masked (keys, tokens, passwords and bearer values by pattern, plus the configured secret settings' values), a counter, first-seen and last-seen times, and the agents and tickets active at first-seen.

## Reliability

- Rotation and truncation: local files are followed by name, reopened when replaced, and read from the start when truncated (the same semantics as `tail -F`).
- SSH: the stream reconnects with backoff, capped at 60 s. Each drop and reconnect is recorded on the watched log, so a silent gap is never mistaken for a quiet system. Lines lost while the link was down are not invented.
- One watcher per log: a lease ensures that two Metaform processes never count the same log twice. The lease is a lock on a file of its own in the home; a process that wants the log waits on the lock and takes the log over the moment its holder ends, a crash included, from the last position written. The project store records who holds it, for `autoticket logs`. Why: the system lets go of a dead process's lock at once, so takeover needs neither a heartbeat nor anyone looking at one. A holder that hangs keeps its logs. (Change, 2026-10-15, dispatched ticket 2ede3067 (code.system.management.knowledge#32), the no-polling rule: before, the holder wrote a beat every second and other processes looked every 2 s for one older than 15 s.)
- Counts are written in batches, at most once a second per group, so a flood of errors costs one write a second, not one per line. Nothing is written while nothing is read. (Change, 2026-10-15, dispatched ticket 2ede3067 (code.system.management.knowledge#32), the no-polling rule: before, counts, positions and the beat were written every second whether or not anything was read.)

## Where a group sits on the map

- When the line or its stack trace names a file and function, the code index maps them to an Address, and the group sits there, like a ticket or a note at that part.
- Otherwise it sits at the project's top node.

## Telling the orchestrator

- Every interval (15 min by default), the orchestrating agent gets a ranked list of groups: count, the change since the last list, example line, Address, first seen and last seen.
- The first list sets the baseline. After it, any group never seen before is reported at once, together with the agents and tickets that were working when it first appeared.
- An agent or the person can reset the baseline whenever they want a clean start, for example at the start of a refactor.
- Groups are not Kanban tickets. The orchestrator, or the person, promotes a group to a ticket when it is worth work. The ticket links back to its group, so the counter shows whether the fix held.

## Intake and the connect notice

- When the module is on, intake has a step that asks which logs to tail, local or over SSH.
- On a greenfield project, intake records that the project is not built yet and only intent exists, so there are no logs to watch.
- While the module is on and no log is configured, agents receive a notice at connect, as with intake's first-run notice. It tells them to configure autoticket against the project's logs, and to ignore the message if there are no logs to capture yet. The exact wording is Rich's to approve; the orchestrator will propose it in prompts.xml form.

## Proof it works (acceptance)

- Feeding 1,000 lines made from 3 error templates with random values produces 3 groups whose counts sum to 1,000, and leaves the log uncopied.
- A 30-line Python traceback is read as one entry, so it counts once.
- Rotating the log file, truncating it, and dropping the SSH link mid-stream lose no lines that remain readable, count none twice, and record the drop.
- Two Metaform processes watching one project count each line once.
- A line holding an API key stores its example with the key masked.
- After the first list, a line of a new template is reported at once, and a line of a known template is not.
- An error whose trace names a mapped file sits at that file's Address.
- An SSH source works through `ssh` with an alias from `~/.ssh/config`, and Metaform's stores hold no key material.

## Amendment, 2026-10-18, ticket code.scheduler.task#8 (bf47336a): errors file themselves

Draft for the owner. It supersedes the sections "Telling the orchestrator" (the timed list, the baseline, reset and promote) and the module's "off until enabled" line, as built on 2026-10-18.

- Why: a project heals itself. When something breaks, the system files a ticket and an agent fixes it, with no one reading logs or approving the work (the owner's decision, 2026-10-18; tickets agents write are no longer held).
- Every fault reaches the grouping as an event, `fault.raised`, never a timer: the web server's faults, the page's errors (sent once a second in one request), a failed MCP tool call, metaform_feedback, and an agent run that crashed or whose agent exited with its ticket open. Each says what failed and where: source, message, detail, file, how to reproduce it, and the ticket of the agent whose call failed.
- Faults group with those raised at the same place (source, file, function) whose message matches by onhold's Dice method, so one kind of error is one group however often it repeats.
- A group never seen before becomes one ticket at once, kind broken, at the element that owns the failing file: the element whose path ref names it, else the one citing a file in the deepest shared folder, else the top node. Its task holds the evidence (message, first and last seen, count, a sample), how to reproduce it, and that the fix comes with a check proving the error no longer happens. Under Autostart an agent starts it like any ticket.
- One open ticket per group: a recurrence while its ticket is open rewrites its count and last seen in that ticket's note. A recurrence after its ticket is done files a new ticket.
- Guardrails: at most `autoticket_open_most` (default 5) tickets it filed are open at once, the rest waiting as groups and filed oldest first as one is done; an error raised by an agent working an autoticket ticket is counted on that ticket; feedback (a design choice) and an error naming deleting or removing data are filed held for the person, with why.
- Revision, 2026-10-18, functional assessment of ticket code.scheduler.task#8 (FQC, assignment 2c4e0348): the cap counts only the open tickets autoticket filed that an agent may work, those not held. A held ticket waits in Backlog for the person and takes no slot, so faults keep being filed while the person has not yet read the held ones; once the person releases a held ticket it counts toward the cap. Why: the cap bounds how much agent work autoticket starts at once, and a held ticket starts none; counted, five held feedback tickets stopped every later fault from being filed.
- Revision, same assessment: a failed MCP tool call whose fault was published tells the agent the failure is filed for a fix, naming the ticket when the pass filed it or counted it on one, and asks for metaform_feedback only for what the error does not say. Why: the fault already carries the message, the traceback and the call that reproduces it, so asking for feedback on it files the same failure again, as a held ticket.
- Removed: the timed ranked list, `autoticket_interval_minutes`, the baseline, `reset`, `promote`, and the `autoticket-list` and `autoticket-new` signals. autoticket is on by default on Linux and macOS.