# Separate decision sheet — use High/Extra High, not Pro iteration

This file is intentionally separate from the specification assignment. These are genuine design choices or measurements that the conversation did not fully settle, NOT permissions for Pro to invent requirements.

1. **Reputation aggregation:** simple arithmetic mean, weighted mean by longevity, or another specific formula? Conversation called for a history-respecting mean; no exact statistical formula was selected. Define what counts as an assessment cycle and how tied lowest scores behave.
2. **Lowest-score retirement:** two consecutive bottom rankings was a suggested grace rule, not a fully specified eviction policy. Determine whether retirement is automatic, opportunistic when capacity is needed, or configurable; define interaction with current work without interrupting it inadvertently.
3. **Cache economics:** actual model/harness cache preservation and price curves must be measured. No universal five-minute expiry or 40% utilization cutoff was finalized.
4. **Inbox semantics:** exact distinction between delivered, read and acknowledged; whether a node's notice is consumed by one first recipient or any appropriate recipient; retention/visibility of read receipts.
5. **Compaction boundary:** exact semantics of once-only context delivery across compaction/handoff and when newly changed versions become eligible; historic intended 50%-65% handoff figures require code/spec reconciliation.
6. **Intake payload shape:** final concrete public schema of batched semantic fields, permitted revisions and relationships, plus whether a single apply operation covers all current structural mutations.
7. **Prompt disposition:** review the legacy prompt inventory and decide keep/rework/discard. The current repository may contain useful canonical semantic text that requires exact preservation; evaluate it explicitly rather than adopting every old prompt.
8. **Agent compatibility:** which harnesses support MCP events today and what the local message fallback actually offers. A2A remote collaboration is not part of the immediate local requirement.
9. **Architecture partitioning:** exact new backend persistence technology/schema and transaction boundaries must follow the final semantic contracts and measured needs; existing SQLite/Cypher mechanics are informative, not inherently binding.

Do not turn these items into speculative default gates. Where the specification must refer to an undecided item, mark the small affected portion and proceed on settled parts.
