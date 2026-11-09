# Check of the 26 Roundtable resolutions against the owner's sources (2026-11-07)

The tables that wrote the resolutions saw only each part's map entry, the review findings, and the code. This check holds every proposed change against the owner's sources: the decisions in `owner-decisions-used.md`, the owner's decisions in the map, the ACP design, the evaluation spec, and the Gate Burden standard. The README was treated as disputed, because the owner said "that was never my spec". The brief is in `brief.md`. The detail is in `group1.md` to `group4.md`.

Claude read every item in "Against the owner" and "Changes the foundation" in the resolution text, and checked the code claims below in the code.

## Totals

| Group | Proposals |
|---|---|
| Already answered by the owner | 74 |
| Against the owner | 35 |
| Changes the foundation | 5 |
| Consistent with the owner's sources | 95 |
| No owner source (owner decides) | 145 |
| **Total** | **354** |

- No resolution is free of code-as-truth reasoning. Two say it outright: `code.adapter.agent` ("The code is the ground truth for this review") and `upstream.registry.agent`.
- Most resolutions compare options for one or two findings only.
- No resolution cites one of the owner's dated decisions by date, because the tables did not have them.

## Changes the foundation (5)

1. `code.gate.quality`: put a timer on the JEV call. The owner said timeouts were "never meant to be the design".
2. `code.bus.event`: make the event-name check crash the program in release builds, in the bus every part depends on. The owner said "This roundtable must do everything it can not to get stuck."
3. `code.server.tool`: record the wait for the floor as a new gate and settle gate RT-G11 without the owner. Only the owner removes gates.
4. `code.rating.peer`: key scorecards by seat ID instead of name. This changes the scoring prompt agents receive, which may be owner text.
5. `data.log.discussion`: add a table-wide turn number to every outcome event, which changes the event model next to the owner's "[R1-2]" message ID.

## Against the owner (35), by kind

- **Rewrites the owner's words or terms to match the code.**
  - `code.adapter.agent` removes "not ori .. we said opencode" and calls it "the author's account".
  - `upstream.system.reputation` softens the owner's statement about return weighting, and defines "accolade" as a record with no points.
  - `code.launcher.agent` renames the owner's "ACP autoselection" and drops "catalog aliases".
  - `code.selector.topic` marks the owner's poll decision "revised-by-implementation".
  - `code.client.agent` drops "rejected at once with the reason" from a safety-relevant decision.
  - `code.gate.quality` rewrites the "never holds the table" comment and the "reasons" decision to match the code.
- **Records a wait as the design, against "the table never waits on JEV" and "the table never waits on independent work":** `code.manager.chat.group` (JEV wait, topic poll wait).
- **Keeps truncation,** against "we arent going to be truncating":
  - `code.selector.topic`, `code.builder.prompt`, `document.prompt.system` and `code.quota.character` keep the 512-character cut of topic proposals;
  - `data.log.discussion` keeps truncation counts.
- **Imposes or announces a limit:** `code.quota.character` applies 1,024 characters when no limit is set, and tells agents their limit in every prompt.
- **Accepts a gap as the design:**
  - `code.roster.participant` records a one-seat minimum, against "at least two are available to debate".
  - `upstream.sdk.agent` accepts that OpenRouter seats have no MCP tools.
  - `upstream.tracer.agent` and `code.monitor.activity` narrow what the ACP design says monitoring must observe.
  - `upstream.judge.llm` keeps "same underlying intent", against "{{foo}} is the same as {{bar}}".
- **Lets builder layers outrank the owner:** `code.manager.chat.group` proposes that `rules`, `gates` and `elephant.built` win over earlier owner statements. It also marks the rounds decision superseded, although topics are only off by default.
- **Leans on the disputed README:** several resolutions cite it as the source of definitions.
- **Timeout as future work:** `code.adapter.agent` (`run_command`).

## Gaps in the code that the check found (verified in the code)

These are not resolution problems. The code does not match the owner's sources.

1. The rejection notice leaves out the numbers. The evaluation spec says: "Labels include the dimension and returned numeric result so the author can connect the guidance to the result." `prompts.rs:44` prints only the label and the feedback. This was Claude's error in building the owner's spec. Fixed: each label now shows the result, for example "- Relevance (0.42): …".
2. Topic proposals are cut to 512 characters (`turn.rs:323`), against "we arent going to be truncating". Topics are off by default.
3. A table can start with one seat (`config.rs:110`), against "at least two are available to debate".
4. A rejected permission request gives the agent no reason. The reason goes only to the event bus. ACP's permission answer has no field for a reason, so meeting the owner's decision needs another route, for example the next prompt.

## Open questions the check raised for the owner

- Whether the "block, never truncate" rule covers topic proposals.
- Whether root-only AgentSight capture is acceptable.
