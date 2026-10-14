---
name: external-service-sync-watcher
description: Use when a module syncs external tickets on a timer.
category: development
---

# Modules that keep a ticket in step with an external service

A ticket follows its external issue only through the module's `sync` verb; a watcher repeats `sync` on a timer, so no one has to run it by hand.

- On every sync, while the ticket is open, read the issue's new comments and write each one that is not a system notice or the module's own write-back as a message at the Address.
- Do not bridge the module's own cancel or status comment back in, or it returns as a message.
- When the issue is done, resolve the ticket with the assignee's last comment, cut to 2,000 characters; if there is none, keep the placeholder text.
- A CLI-only `watch` verb runs `sync`, then waits the check-minutes setting, read fresh each round. It writes a beat every 20 seconds to a record for its own project in the Metaform home, treats a beat older than three intervals as gone, and on SIGTERM ends like Ctrl-C and removes the record only if the pid is its own.
- Subscribe to `web.started` and start `watch` detached (Popen, as twilio and cloud do) when a linked ticket is open and no watcher beats.
- Use one record per project, not one shared file: two projects' web starts would overwrite each other.
- A verb that reaches the network declares open_world, and a new one needs a reasoned entry in the registry (see verify-guard-test-by-mutation).
- Verify the periodic path end to end with a stub service (see scripted-check-spawned-servers). Update the module README and CHANGELOG Unreleased in the same change.
