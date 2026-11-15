# Roundtable 12: 120b9fed-in-topogee-taking-a-ticket

This report was written from the table's record alone, by no model. The table ended because ended by its chair.

Opening: A person brings you a question. It is the whole frame of this discussion: it is not about one part of anything unless it says so, and it may be about something that does not exist yet.

The question: In Topogee, taking a ticket should do for an agent what goto does for an address: hand it a file folder, in sections, holding everything its task needs and nothing else. How should that folder be assembled from the map and its modules, and what should the first version leave out?

Two decisions are still open, and the table should give a recommendation on each:
1. Does a ticket name one address or several?
2. Does the folder hold summary sheets (counts and skill frontmatter) or full content?

Grounding, on GitHub at RchGrav/topogee, branch intake-3.1. Read it with `gh api repos/RchGrav/topogee/contents/<path>?ref=intake-3.1 -H "Accept: application/vnd.github.raw"`:
- TOPOGEE-SPEC.md: R-5.31 (tickets select context), R-5.30 (goto, the summary sheet), R-2.11 (presence and the data controller), R-5.29 (memory). Only items marked Decided are firm.
- docs/designs/topogee-map-server-design.md: the sections "Reads", "Modules and the data controller" and "The memory module".

Evidence from Metaform, the earlier system:
- Ticket writes were 36% of all agent calls (map_work, 3,877 of 10,878).
- A pushed "N unread memories" notice drove 1,884 memory reads.
- Context delivered once per context never reliably knew what the agent still held after compaction.

Topogee's rules: every token is counted; an order of steps lives in a prompt, not in the tool (R-5.18, Proposed); no more than about 30 selectable things in an agent's range.

You are in the folder of the person's project, and you can read its files when the question touches it. You cannot change anything, and nothing you say changes the project; the person reads the table's report and decides. Build on what the others contribute, add what only you can add, and keep going until the question is answered.

## Seats

- Fable (acp:claude/fable): 2 slots, 2 submissions, 2 kept, active
- Astra (acp:codex/gpt-6-astra): 1 slots, 1 submissions, 0 kept, active
- Opus (acp:claude/opus): 1 slots, 1 submissions, 1 kept, active
- Sol (acp:codex/gpt-6.1-sol): 1 slots, 1 submissions, 0 kept, active

## Topic 1: In Topogee, taking a ticket should do for an agent what goto does for an address: hand it a file folder, in sections, holding everything its task needs and nothing else. How should that folder be asse

### Ideas

The topic has no synthesis.
