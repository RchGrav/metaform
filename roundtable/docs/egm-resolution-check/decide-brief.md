# Brief: decide the "No owner source" proposals

## Background

Roundtable is the owner's multi-agent discussion tool. Its code is at `/home/rich/topogee-roundtable/roundtable`. Tables of AI agents wrote resolutions for each part of Roundtable, and a check then sorted every proposed change against the owner's sources. The rows marked **No owner source** were handed back to the owner to decide. The owner's expectations say that is wrong by default: gaps are for the engineer to work out.

Read `/home/rich/topogee/EXPECTATIONS.md` first and follow it.

## Your job

Your file is given below. For every row in it marked **No owner source**:

1. Read the proposal in the resolution it came from: `/home/rich/topogee-roundtable/roundtable/docs/egm-resolutions/<address>.md`.
2. Where the proposal claims something about the code, check the claim in the code. The code is under `/home/rich/topogee-roundtable/roundtable/crates` and `/home/rich/topogee-roundtable/roundtable/adapters`. Say whether you checked it.
3. Decide on one of these:
   - **Adopt:** the proposal is right. Give the exact change: the description text for the map, or the code change in one or two sentences.
   - **Adopt changed:** the idea is right but the proposal is wrong in detail. Give your version.
   - **Reject:** say why, with evidence.
   - **Owner-dependent:** only if the answer truly depends on information or priorities only the owner has. Name the exact dependency, give the options and their consequences, recommend one, and say when another option would be better.

The decision must respect the owner's sources and must not redesign anything. The owner's sources are the same as in the first check:

- `/tmp/claude-1000/-home-rich-topogee/7f8c0a01-1644-4aa9-aa2e-d4020129a980/scratchpad/owner-session-decisions.md` (newest; governs)
- `/tmp/claude-1000/-home-rich-topogee/7f8c0a01-1644-4aa9-aa2e-d4020129a980/scratchpad/owner-map-decisions.md` (only `"by": "owner"` entries or entries with an `owner_statement` are the owner's)
- `/home/rich/topogee-roundtable/roundtable/Roundtable_ACP_Integration_Design.md`
- `/tmp/claude-1000/-home-rich-topogee/7f8c0a01-1644-4aa9-aa2e-d4020129a980/scratchpad/evalspec/roundtable_spec/SPECIFICATION.md` (the text is the owner's; the API address in it is only where JEV's documentation is, not a route choice; Roundtable uses OpenRouter)
- `/home/rich/topogee-roundtable/roundtable/docs/gate-burden.md` (inference gates only; only the owner removes a gate)

Owner texts (prompts, JEV questions, feedback text) are never changed without the owner. A proposal that rewrites one is owner-dependent.

Do not change any file except your output file.

## Output

Write one markdown file to the output path given. For each resolution that has such rows:

```
## <address>

| Row | Proposal (plain words) | Decision | The change, or the reason | Checked in code |
|---|---|---|---|---|
```

End the file with:
- the list of **Owner-dependent** rows, each with its dependency, options, and recommendation;
- any safety-relevant items you found, first.

Write in plain English with full sentences. Do not invent terms or abbreviations. Spell out what a finding says instead of only giving its number. When you finish, reply with only the output path and the count of each decision.
