# Brief: check Roundtable resolutions against the owner's sources

## Background

Roundtable is the owner's multi-agent discussion tool. Its code is at `/home/rich/topogee-roundtable/roundtable`. For each part of Roundtable, a table of AI agents was given only the part's map entry, some review findings, and the code. Each table wrote a resolution: a list of proposed changes. The tables never saw the owner's design documents or decisions. The owner suspects the proposals drift from the design, for example by treating the code as the truth when the owner's design says otherwise.

Your job is to check each proposal in your assigned resolutions against the owner's sources. Do not change any file except your output file.

## The owner's sources

Read all of these first:

1. `/tmp/claude-1000/-home-rich-topogee/7f8c0a01-1644-4aa9-aa2e-d4020129a980/scratchpad/owner-session-decisions.md`: the owner's newest decisions. These govern over everything else.
2. `/tmp/claude-1000/-home-rich-topogee/7f8c0a01-1644-4aa9-aa2e-d4020129a980/scratchpad/owner-map-decisions.md`: decisions recorded in the map. Only entries with `"by": "owner"` or with an `owner_statement` are the owner's. Entries with `"by": "Claude"` are builder choices. They are not owner authority.
3. `/home/rich/topogee-roundtable/roundtable/Roundtable_ACP_Integration_Design.md`: the owner's ACP design.
4. `/tmp/claude-1000/-home-rich-topogee/7f8c0a01-1644-4aa9-aa2e-d4020129a980/scratchpad/evalspec/roundtable_spec/SPECIFICATION.md`: the owner's evaluation spec. The text is the owner's. The JSON and Python examples in that folder were added by another agent and are not the owner's design.
5. `/home/rich/topogee-roundtable/roundtable/docs/gate-burden.md`: the owner's Gate Burden standard. It applies only to inference gates.
6. `/home/rich/topogee-roundtable/roundtable/README.md`: the owner said "that was never my spec". Treat it as a disputed source. Cite it only to show that a proposal leans on it.

Where sources conflict, the newer owner decision wins.

## What to check

For every proposed change in each resolution (each change to code, to the description, or to the map), put it in exactly one group:

- **Already answered:** the owner already decided this question. Quote the owner's words and give the source. Say whether the proposal agrees or disagrees with that answer.
- **Against the owner:** the proposal contradicts an owner source. Quote the source. This includes proposals that keep a builder choice the owner has since overruled.
- **Changes the foundation:** the proposal would change how Roundtable fundamentally works or is unsafe, for example timers, killing agents, truncation, adding gates, changing owner texts, or changing the event or permission model. Say why in one or two sentences.
- **Consistent:** it fits the owner's sources and changes nothing fundamental. Name the source it fits.
- **No owner source:** nothing the owner wrote covers it, so the owner should decide. Usually these are wording fixes to the description or fixes for real code bugs. Say which.

Also note, for each resolution:
- whether it treats the code as the truth over the owner's design;
- whether it compared options and explained why the chosen one is best for the project.

Do not judge whether the code works. Judge only against the owner's sources. If you are unsure, say so and give the reason. Do not guess.

## Output

Write one markdown file to the output path you are given. For each resolution:

```
## <address>

Treats code as the truth: yes / no / partly (one sentence)
Compares options: yes / no / partly (one sentence)

| # | Proposed change (short, plain words) | Group | Owner source and quote, or reason |
|---|---|---|---|
```

End the file with a short list of the proposals in **Against the owner** and **Changes the foundation**, with their resolution address and row number.

## How to write

Use plain English with full sentences. Do not invent terms or abbreviations. Spell out each review finding instead of only writing "GF3". Quote the owner exactly and do not paraphrase a quote.

When you finish, reply with only the output path and the number of rows in each group.
