# autoticket

Files every fault Metaform raises, and every error in a project's watched logs, as a ticket to fix: each new kind becomes one ticket at once, at the element that owns the failing file, and its repeats are counted on that ticket. Design: `artifacts/specs-draft/autoticket.md`.

## Purpose

A project heals itself: when something breaks, the system files a ticket and an agent fixes it, with no one reading logs or approving the work. A new kind of error is filed as soon as it appears, while the change that caused it is still small, and a group whose counter stops rising after a fix is evidence that the fix held; a counter that rises again after completion reopens the same canonical ticket, retaining prior repair evidence. Cancelled tickets remain cancelled.

## Template version

The template changelog version this module started from: 0.2.0.

## Declaration

`SUPPORTED_OS` is Linux and macOS: logs are followed as `tail -F` follows them, and a remote log is reached through the system's own `ssh` and a POSIX shell on the host. `DEPENDENCIES` is empty. `SHIPS_DISABLED` is false: every project files its faults. `MODULE` declares the verbs below, the subscriptions to `fault.raised` and `map.changed`, the status hook, the tables, `item_read`, `items_at` with the item kind `error group`, and `work_read`.

### Toolbar items and panes

None.

## Common base used

`metaform.settings` declares the three settings. `metaform.data` gives the module's own tables, `Store.number` for each group's item number at its Address, `Store.work` for the tickets at work when a group is first seen and for whether a ticket it filed is open, `Store.add_work` to file a ticket and `Store.edit_work` to count on its note, `Store.citing` to find the element whose file ref, `path=` in the sources layer, names a file, and `Store.refs` for the nearest one. `metaform.module` gives `Context`, `Stop`, `Status`, `Subscription` and `Verb`. `metaform.events.announced` announces each ticket it writes, so the agent starter and open pages hear of it. `metaform.prompt_files` reads `resources/prompts.xml`. Nothing else of Metaform is imported.

### Provides

Nothing.

## Prompts

`resources/prompts.xml` holds `instructions`; `ticket`, the task of a ticket it files, with its fills `message`, `source`, `count`, `first`, `last`, `sample` and `reproduce`; `held_design` and `held_data`, why a ticket waits for the person; and an empty `connect`, `counts` and `rules`. The wording of `ticket`, `held_design` and `held_data` awaits the person's approval. The status hook reads two more prompts that are not in the file yet: `intake_step`, sent at connect to an intake agent while no log is configured, and `connect_notice`, sent at connect to the person's own agent in that state. Their wording is the person's to approve; the drafts are in `artifacts/specs-draft/autoticket-prompts.md`. While a prompt is absent or empty nothing is sent.

## Verbs

- `add <log>`, write: watch a log. A local file is recorded with its identity and size now, so it is read from its end at this moment even before a watch runs; `ssh://<host>/<absolute path>` is read from its end at its first connect.
- `remove <log>`, write: stop watching a log; its groups stay.
- `logs`, read: the watched logs, which process reads each, where it has reached, its drops and reconnects, and the capture rules.
- `no-logs`, write: record that the project has no logs to watch yet, being only intent; it silences the connect notice until a log is added.
- `add-rule <pattern>` and `remove-rule <pattern>`, write: a capture rule, a regular expression; the entries it matches are grouped exactly as errors are.
- `watch [seconds=<n>]`, write, open world, task: read every watched log whose lease this process can take, until stopped or for `seconds`. It returns how many lines it read, entries it captured, groups it made, groups it reported, lists it sent and drops it saw.
- `list [limit=<n>]`, read, the default: every group, most counted first, with its example's first line, its Address and item, first and last seen, and its ticket once filed.

A ticket is filed by the module itself, never by a verb: see Filing below.

## Settings

- `autoticket_open_most`, 5: how many tickets autoticket filed may be open and not held at once; each further kind of error waits as a group and is filed, oldest first, when one of them is done. A held ticket waits for the person and takes no place; released, it takes one.
- `autoticket_similarity`, `0.45`: the Dice coefficient at which two entries are the same kind, onhold's value. A text setting, since number settings are whole numbers, checked to be above 0 and at most 1.
- `autoticket_capture`, `errors`: `errors` counts the entries holding a level word, ERROR, FATAL, CRITICAL, SEVERE or PANIC, `level=error`, a Python traceback's start or a word ending in Exception, and those a capture rule matches; `rules` counts only those a capture rule matches.

The watched logs and the capture rules are records, kept with `add`, `remove`, `add-rule` and `remove-rule`, not list settings, as the template's settings rule says.

## Events

It subscribes to two topics:

- `fault.raised`, published where Metaform fails in a way no one expected: the web server's `Handler.fault` (a 500, with its traceback), the page's errors through `/api/page-faults` (`core/errors.js` `pageFailed`, and `readFailed` for reads that did not fail with the server's own 500), the MCP server when a module's verb raises, and on every `metaform_feedback`, and dispatch's runner when a run failed, did not start, or its agent ended by itself with the ticket open. Its payload says what failed and where: `source`, `message`, `detail`, `file`, `reproduce`, `work_id` (the ticket of the agent whose call failed) and `count`. The page's errors of one request come as one event whose `faults` lists them, so they cost one pass. A pass the event ran returns `tickets`, the tickets its faults were filed as or counted on, so the MCP server answers a failed verb with the ticket that will fix it rather than asking for feedback on it.
- `map.changed`, to file a waiting group when a ticket it filed is done. It acts only on a change naming the `work` table, of kind `ticket`, and of a ticket it filed; one that does not say what it concerns may have closed any, and is looked at once.

It publishes `map.changed` after it makes groups from a log, so an open page shows them, and announces each ticket it files or counts on.

## Filing

Faults and log entries are grouped by onhold's method. A fault's fingerprint is its place, the source, file and function hashed as one term, then its message's words: faults group only with those raised at the same place, so the words a source puts around every error never make two errors one. Then:

- A group never seen before is filed at once as a ticket of kind broken, at the element that owns its file: the one whose `path=` ref names it, else one whose ref ends with the path named (the page names `page/app/...`), else the element citing a file in the deepest folder the two share, else the project's top node. Its task, the `ticket` prompt, holds the message, what raised it, the count, first and last seen, a sample with secrets masked, how to reproduce it, and that the fix must come with a check proving the error no longer happens.
- A group that recurs while its ticket is open has its line in that ticket's note rewritten: `autoticket group <n>: seen <count> times, first <t>, last <t>: <message>`.
- A fault raised by an agent working a ticket autoticket filed (`work_id`) is counted on that ticket, never filed anew.
- At most `autoticket_open_most` tickets it filed are open and not held at once; the rest wait as groups. A held ticket starts no agent work, so it takes no place, and faults keep being filed while the person has not read the held ones.
- Feedback, whose answer is a design choice, and an error whose message names deleting or removing data, are filed held in Backlog, the why at the start of the note. The task also tells the agent to stop and leave the choice to the person when the fix turns out to be one.
- A group seen again after its ticket is done waits to be filed anew.

Faults that arrive while a pass for the same project runs in the process merge into its next pass, so a burst costs one pass, CLAUDE.md section 2; the page sends the errors of one second in one request. A group is claimed before it is filed, so two processes never file one group twice.

## Sync and async

`watch` is a coroutine: the watch runs in a worker thread, so in the MCP server it never blocks other calls, and a cancel stops it at once, giving its leases back. Each log is read by a thread of its own, and each lease is waited on by a thread of its own. Nothing wakes on a timer to look for a change, QUAL-015: the watch sleeps on its queue until a reader hands it a line, a lease is handed over, a `map.changed` from another process names `autoticket.logs`, `autoticket.rules` or `autoticket.state` (heard through the base's listener, BASE-053), or a real deadline comes: an open entry's 2 s of quiet, the one-second write batch, or the end of `seconds`. The subscribers run in the publisher's thread, a worker thread under an event loop. A local reader at its file's end sleeps until the system says the file changed: inotify on Linux, on the open file and on its name in its folder; kqueue on macOS, on the open file and its folder. Every other verb is synchronous.

## Layers

It writes no layer. Its tables, version 2, are all in the project's store, `place='project'`, so a clear of the project's metaforms keeps the error history:

- `groups`, keyed by `group_id`: `fingerprint`, `example` (masked), `count`, `first_seen`, `last_seen`, `active` (JSON, agents and tickets at first-seen), `source` (what raised it, `log` for a watched log), `reproduce` (masked), `address` and `number` (its item at its Address), `work_id` (its ticket; empty while it waits, `filing <time>` while one process files it). Indexes on `(address, number)` for `item_read` and `items_at`, and on `work_id` for `work_read` and the map.changed subscriber. Written by `watch` and the `fault.raised` subscriber. Version 2 added `source` and `reproduce` and dropped `listed` and `known`, which served the timed list.
- `logs`, keyed by `source`: `holder` (who holds the lease, shown by `autoticket logs`) and `beat` (when it last wrote), `identity` and `offset` (where its reader has reached), `drops`, `reconnects`, `last_drop`, `added`. Written by `add`, `remove` and `watch`.
- `rules`, keyed by `pattern`, with `added`. Written by `add-rule` and `remove-rule`.
- `state`, keyed by `name`: `no_logs`. Written by `no-logs` and `add`.

## Lifecycle and cleanup

No `start` or `stop`. A log's lease is a lock on a file of its own under the home's `run/autoticket`, held by the watch reading it. A watch gives back its leases when it ends, its position written, and stops its reader threads and any `ssh` it started. A watch that dies holding a lease, by a crash too, has its lock let go by the system, and a watch waiting on that lock takes the log over at that moment, from the last position written. A holder that hangs keeps its logs, since its process still holds the locks.

## Modules relied on

None to place a group: it sits at the element that owns its file, read from the map's sources layer, and with none at the project's top node. The tickets it files are started by dispatch's Autostart like any ticket; with dispatch off they wait on the board.

## Systems supported

Linux and macOS.

## Resources owned

A reader thread for each log the watch holds, an open file and an inotify or kqueue handle for a local log, and an `ssh` process for a remote one; a lease thread and its lock file's handle for each watched log. All released when the watch ends; the lock files stay, empty, so a lock is never taken on a file another holder has removed.

## Installed and direct wheel

The same in both: it needs `ssh` on PATH only for a remote log, and on the host `sh`, `ls`, `awk`, `wc` and a `tail` with `-F` and `-c`.

## Demonstration

```bash
metaform autoticket add /var/log/shop/app.log
metaform autoticket add ssh://web1/var/log/shop/app.log
metaform autoticket watch            # until stopped; run it under hold to keep it running
metaform autoticket list               # each group with its ticket
metaform map work kind=broken          # the tickets it filed
```


The web supervisor owns a watcher for every registered project, even with no browser page open. `autoticket_watch`, `autoticket_file`, `autoticket_reopen` and `autoticket_hold_feedback` are independent Full Auto policy controls. Register actual logs with `metaform autoticket add log=<path>`; the watcher never invents paths. Local file rotation and recorded offsets survive reconnects through the existing watch leases. Watcher failures publish an actionable fault and retry with bounded backoff. Error text mentioning removal or deletion does not create an approval gate.
