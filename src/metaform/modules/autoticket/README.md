# autoticket

Watches a project's logs while work goes on and ranks the errors in them by how often they happen, for the orchestrating agent. Design: `artifacts/specs-draft/autoticket.md`.

## Purpose

Agents otherwise see only the code and the map. autoticket shows them what the running system does wrong, ranked by how often, without anyone reading logs. A new kind of error is reported as soon as it appears, while the change that caused it is still small, and a group whose counter stops rising after a fix is evidence that the fix held; a counter that rises again later is a regression.

## Template version

The template changelog version this module started from: 0.2.0.

## Declaration

`SUPPORTED_OS` is Linux and macOS: logs are followed as `tail -F` follows them, and a remote log is reached through the system's own `ssh` and a POSIX shell on the host. `DEPENDENCIES` is empty. `SHIPS_DISABLED` is true: the module is off until `metaform enable autoticket`. `MODULE` declares the verbs below, the status hook, the tables, `item_read`, `items_at` with the item kind `error group`, and `work_read`.

### Toolbar items and panes

None.

## Common base used

`metaform.settings` declares the three settings. `metaform.data` gives the module's own tables, `Store.number` for each group's item number at its Address, `Store.work` for the tickets at work when a group is first seen, and `Store.add_work` for `promote`. `metaform.module` gives `Context`, `Stop`, `Status`, `titled` and `held_role`, and `surface` with `context` and `call` to run map's `code-context` verb, which maps a file and function to an Address. `metaform.prompt_files` reads `resources/prompts.xml`. Nothing else of Metaform is imported.

### Provides

Nothing.

## Prompts

`resources/prompts.xml` holds `instructions`, and an empty `connect`, `counts` and `rules`. The status hook reads two more prompts that are not in the file yet: `intake_step`, sent at connect to an intake agent while no log is configured, and `connect_notice`, sent at connect to the person's own agent in that state. Their wording is the person's to approve; the drafts are in `artifacts/specs-draft/autoticket-prompts.md`. While a prompt is absent or empty nothing is sent.

## Verbs

- `add <log>`, write: watch a log. A local file is recorded with its identity and size now, so it is read from its end at this moment even before a watch runs; `ssh://<host>/<absolute path>` is read from its end at its first connect.
- `remove <log>`, write: stop watching a log; its groups stay.
- `logs`, read: the watched logs, which process reads each, where it has reached, its drops and reconnects, and the capture rules.
- `no-logs`, write: record that the project has no logs to watch yet, being only intent; it silences the connect notice until a log is added.
- `add-rule <pattern>` and `remove-rule <pattern>`, write: a capture rule, a regular expression; the entries it matches are grouped exactly as errors are.
- `watch [seconds=<n>]`, write, open world, task: read every watched log whose lease this process can take, until stopped or for `seconds`. It returns how many lines it read, entries it captured, groups it made, groups it reported, lists it sent and drops it saw.
- `list [limit=<n>]`, read, the default: every group, most counted first, with its change since the last list, its example's first line, its Address and item, and first and last seen.
- `reset`, write: send the list now as the new baseline, for a clean start such as the start of a refactor.
- `promote <group> [title=<t>]`, write: make a group a ticket of kind broken at its Address, the group linked to the ticket, so `map work id=<id>` shows the group's counter. A role held back by `roles_without_authority` is refused.

## Settings

- `autoticket_interval_minutes`, 15: how often the orchestrator is sent the ranked list. The first list sets the baseline.
- `autoticket_similarity`, `0.45`: the Dice coefficient at which two entries are the same kind, onhold's value. A text setting, since number settings are whole numbers, checked to be above 0 and at most 1.
- `autoticket_capture`, `errors`: `errors` counts the entries holding a level word, ERROR, FATAL, CRITICAL, SEVERE or PANIC, `level=error`, a Python traceback's start or a word ending in Exception, and those a capture rule matches; `rules` counts only those a capture rule matches.

The watched logs and the capture rules are records, kept with `add`, `remove`, `add-rule` and `remove-rule`, not list settings, as the template's settings rule says.

## Events

It publishes `signal.raised` with `module` `autoticket`, BASE-057, which dispatch keeps as a signal the orchestrator reads with `dispatch signals`:

- `autoticket-list`, every interval, from whichever watch process claims it first: `baseline` (true for the list that set it), `at`, `groups` (the first 20, each with `group`, `count`, `change`, `example`, `address`, `item`, `first_seen`, `last_seen`), `more`, and `logs` with drops.
- `autoticket-new`, at once, for a group first seen after the baseline: the same fields as a group in the list, and `working`, the agents and tickets at work when it was first seen.

It publishes `map.changed` after it makes groups, so an open page shows them. It subscribes to nothing.

## Sync and async

`watch` is a coroutine: the watch runs in a worker thread, so in the MCP server it never blocks other calls, and a cancel stops it at once, giving its leases back. Each log is read by a thread of its own, and each lease is waited on by a thread of its own. Nothing wakes on a timer to look for a change, QUAL-015: the watch sleeps on its queue until a reader hands it a line, a lease is handed over, a `map.changed` from another process names `autoticket.logs`, `autoticket.rules` or `autoticket.state` (heard through the base's listener, BASE-053), or a real deadline comes: an open entry's 2 s of quiet, the one-second write batch, the interval's list, or the end of `seconds`. A local reader at its file's end sleeps until the system says the file changed: inotify on Linux, on the open file and on its name in its folder; kqueue on macOS, on the open file and its folder. Every other verb is synchronous.

## Layers

It writes no layer. Its tables, version 1, are all in the project's store, `place='project'`, so a clear of the project's metaforms keeps the error history:

- `groups`, keyed by `group_id`: `fingerprint`, `example` (masked), `count`, `first_seen`, `last_seen`, `active` (JSON, agents and tickets at first-seen), `address` and `number` (its item at its Address), `listed` (its count at the last list), `known` (1 once in a list or reported), `work_id` (the ticket it was promoted to). Indexes on `(address, number)` for `item_read` and `items_at`, and on `work_id` for `work_read`. Written by `watch`, `reset` and `promote`.
- `logs`, keyed by `source`: `holder` (who holds the lease, shown by `autoticket logs`) and `beat` (when it last wrote), `identity` and `offset` (where its reader has reached), `drops`, `reconnects`, `last_drop`, `added`. Written by `add`, `remove` and `watch`.
- `rules`, keyed by `pattern`, with `added`. Written by `add-rule` and `remove-rule`.
- `state`, keyed by `name`: `baseline`, `listed_at`, `no_logs`. Written by `watch`, `reset`, `no-logs` and `add`.

## Lifecycle and cleanup

No `start` or `stop`. A log's lease is a lock on a file of its own under the home's `run/autoticket`, held by the watch reading it. A watch gives back its leases when it ends, its position written, and stops its reader threads and any `ssh` it started. A watch that dies holding a lease, by a crash too, has its lock let go by the system, and a watch waiting on that lock takes the log over at that moment, from the last position written. A holder that hangs keeps its logs, since its process still holds the locks.

## Modules relied on

map, through its `code-context` verb, to place a group at the Address of the file and function its trace names; with map off or no code index, a group sits at the project's top node. dispatch, through the `signal.raised` event, keeps the reports for the orchestrator; with dispatch off, `autoticket list` still gives the ranked list.

## Systems supported

Linux and macOS.

## Resources owned

A reader thread for each log the watch holds, an open file and an inotify or kqueue handle for a local log, and an `ssh` process for a remote one; a lease thread and its lock file's handle for each watched log. All released when the watch ends; the lock files stay, empty, so a lock is never taken on a file another holder has removed.

## Installed and direct wheel

The same in both: it needs `ssh` on PATH only for a remote log, and on the host `sh`, `ls`, `awk`, `wc` and a `tail` with `-F` and `-c`.

## Demonstration

```bash
metaform enable autoticket
metaform autoticket add /var/log/shop/app.log
metaform autoticket add ssh://web1/var/log/shop/app.log
metaform autoticket watch            # until stopped; run it under hold to keep it running
metaform autoticket list
metaform autoticket promote 3
```
