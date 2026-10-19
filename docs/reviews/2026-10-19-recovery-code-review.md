# Recovery code review — 2026-10-19

Reviewed the control, automation, project routing, memory delivery, and scoped knowledge paths on
`c4f449fc33f3dcf2268b44b44cb500d338e47f2b`. The fixes below include the previously reproduced memory busywork bug.

## Findings and fixes

1. **Memory authors received notices about their own writes.** A worker that recorded its findings took a second
   turn asking it to read those same findings. Successful mutations now record the exact content the author knows
   in its context receipts. An edit acknowledges its resulting body only when the prior body was already known;
   an intervening unread change from another agent remains unread. Creation, observation edits, relations,
   deletion, and index withdrawal are covered. No storage schema changes are required.
2. **Queued memory notices became stale and accumulated during repeated edits.** A notice queued during a running
   turn was delivered even after that turn read its memory. Notices now coalesce by functional entry and resolve
   their current contents at delivery. Obsolete notices do not start an ACP turn. Interrupt releases the discarded
   notice state so later changes remain deliverable; human message order is preserved.
3. **Watcher cleanup failure disabled recovery.** If the final log-position write raised during `release()`, the
   listener remained open and the bounded retry was skipped. Cleanup now attempts both resource releases, retains
   the retry budget, and schedules recovery even when fault reporting uses the same unavailable database.
4. **Cross-project messages could be labelled as outgoing.** Two adapters may use identical session IDs in different
   projects. Direction now includes project identity, and note/reply summaries retain project and base provenance.
5. **Replies returned by a waiting tool left a stale receipt in the sender's project.** The local copy was marked
   read, but the remote copy remained queued. Consumption now propagates the read receipt to the recorded sender
   project, as ordinary turn delivery already does.

The own-write, queued-notice, watcher-cleanup, and cross-project direction regressions failed before their fixes.
The live cross-project scenario also verifies a waiting tool's reply and its remote read receipt while the other
project has changed its active base. Tests use fake ACP adapters and isolated project stores.

## Validation

- Memory suite: 63 passed before the additional relation/index case; final delivery regressions and the real
  dispatch own-write regression: 14 passed. This includes unseen peer revisions and multiple edits in one batch.
- Cross-project delivery: 3 passed. Watcher lifecycle and recovery: 4 passed.
- Final interrupt/coalescing regression: passed; later memory changes remain deliverable after Interrupt.
- Broader recovery suite: 180 passed, 1 skipped (the opt-in idle measurement). This covers orchestration,
  autoticket, direct specialist execution, user control, peer teams, liveness, worker capacity, server events,
  and scoped knowledge.
- Final memory-delivery, user-control, and cross-project run: 21 passed. Final transport run: 4 passed, including
  the opt-in idle measurement and the unrelated-event burst with zero storage reads or scheduled work.
- Separate 60-second idle samples at the review base and final source used 0.02 and 0.04 CPU seconds respectively
  in the runner (0.033% and 0.067% of one core). The fake adapter used 0.00 CPU seconds in both. No polling was added.
- Repository CI lint scope (`ruff check src tests conftest.py`) and Pyright on the changed modules passed.
- Source distribution and wheel builds passed.

This is a focused recovery review, not a claim that the entire repository test suite is green. Existing broader
test failures and optional voice typing errors are described in
[the phase-one implementation report](2026-10-19-phase-one-implementation.md). An exploratory lint run outside the
CI scope also found existing issues in archived skills, documentation scripts, `rich/`, and `scripts/calver.py`;
these are outside this change. No user project packets, databases, or live agent state were modified.
