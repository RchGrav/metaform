# Changelog

Each change to the module, newest first.

## Unreleased

- 2026-10-15, ticket 2ede3067 (code.system.management.knowledge#32), no polling: a local log at its end is followed through inotify (Linux) or kqueue (macOS) rather than looked at every 0.25 s; the watch sleeps until an event or a real deadline rather than turning every 0.25 s; a lease is a lock file per log, waited on in a thread and taken over the moment its holder ends, rather than a beat written every second and looked at every 2 s; counts and positions are written only after something was read; a log added or removed elsewhere, or a rule, reaches a running watch through `map.changed`. No table change: `holder` and `beat` stay, as who reads the log and when it last wrote.
- The module, from the design in `artifacts/specs-draft/autoticket.md`, ticket 0fc3c02b: watched logs, local or over ssh, read as they grow and never kept; entries joined from their lines; errors grouped by onhold's FNV-1a and Dice method at 0.45; one example per group with secrets masked; a lease per log so two processes never count one line twice; the ranked list as a signal every `autoticket_interval_minutes`, the first setting the baseline, and a group first seen after it reported at once; `promote` to make a group a ticket. Tables at version 1: `groups`, `logs`, `rules`, `state`. The intake step and the connect notice are read from prompts.xml once their wording is approved.
