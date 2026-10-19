# VIEW-018 amendment draft, ticket 09b62d16afa843e5a8853b5ce9801d0b (code.interface.graphical#98)

Draft for the owner's approval. It goes in `specifications/09-viewer.md`, record VIEW-018, after its last amendment.

It replaces one sentence in the 2026-10-15 amendment for ticket c9a65cda (code.processor.intake#8): "on each event the
page reads the intakes building, the query `intake-building`". It also narrows one clause in the 2026-10-15 amendment
for ticket 993b0a27: "the tickets are read only when the change names their tables". Both earlier bullets stay as they
are written.

Ticket 09b62d16 asked for the change to go into the record itself. Under the draft-and-approve rule, it is drafted here
instead.

- Amendment, 2026-10-15, ticket 09b62d16afa843e5a8853b5ce9801d0b (code.interface.graphical#98), built by a Claude agent
  on that ticket, supersedes the clause "on each event the page reads the intakes building" in the 2026-10-15
  amendment for ticket c9a65cda: the page decides from each `map.changed` alone what it reads, and then reads only that.
  (1) The merges, the Review notice of VIEW-044, are read again only when a change names `dispatch.merges` or the kind
  `merge`, or names neither its tables nor its kinds, as the server's `merge_change` decides. They are also read on the
  stream's reopen. A session, permission, spending or progress write reads none.
  (2) The page gathers the `work_ids` its changes name over a batch. It reads those tickets alone, through the `work`
  read's new `ids` argument (`ids=a,b`), and merges them into the tickets it holds. When a ticket reads as it was held,
  nothing is drawn again. The selected node's Work box is read again only when a changed ticket is at that node. All
  the tickets are read only when a change names no `work_ids`. The open messages are read only when a change's kinds
  name `message` or `question`, or, with no kinds, its tables name `messages` or `map.question_work` or it names none.
  (3) A change to the ops of the metaform shown whose `seq` the page has drawn already is dropped before any read. The
  project's metaforms, the `bases` read, are read only when a change in the batch names no `base_id`, which is how
  `changes.note` announces a metaform added, removed or made active. What is building, the `intake-building` read, is
  read in these cases: when a change names `intake.recorder` or no tables, while an intake is followed, while this
  project's intake agent runs, and beside every whole reload of the map. Taking the recording hold now names
  `intake.recorder`, with the kind `intake`, in the change of the command that took it (data/recorder.py `hold`). So
  a page learns that an agent began recording from the event. An intake begun from the command line takes no hold. It
  makes a layer, and a new layer falls back to a whole reload, so the page still finds it there.
  Why: the polling check of 2026-10-15 (artifacts/perf/2026-10-15-polling-check/find-page.txt) found that a runner's
  session write read every merge, at about 0.5 s of server CPU in a dispatch subprocess. It found that one ticket's step
  read every ticket (1.3 MB) and every open message. It found that an ops change with nothing new still made six reads.
  The before and after figures are in artifacts/perf/2026-10-15-graphical-98/RESULTS.md.
