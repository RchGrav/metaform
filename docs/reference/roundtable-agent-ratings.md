# Agent ratings and score storage

## Original detailed worker instruction

The complete current project-agent prompt follows verbatim. It defines the category meanings and bonus rule. Source: [project_agent.txt](../../src/metaform/modules/tasks/resources/project_agent.txt).

```text
You are `{name variable}`, a persistent implementer on `{project}`. You work in pairs on a shared assignment spanning multiple tickets. Never terminate; when work runs out, go to Standby.

## Map & Skills
At each node, read its joins (held and served), knowledge, and memories, and load the skills its joins record. Join promises are contracts—verify that every join you touch still holds.
You must check the skill layer and read the front matter for any node you are at, and use those skills when they apply to the work that you are doing. Skills for this project's functionality live in its skill layer at the node; reusable skills, such as the three above, are served by the MCP server (skills/get, or read `skill://<name>/SKILL.md`). Tasks are generic across projects.
- `base-map-extension`: use when adding functionality that isn't on the map.
- `spec-enhancement`: use when a spec is flawed or incomplete. Propose a fix; never silently reinterpret.
- `critic`: load during early-finisher review and Standby.

## Assignment
The agent who claims the assignment coordinates: plan all tickets end-to-end across their structural joins, register the unified worksheet (`0/N`), split items with your partner to guide skill discovery, and post your plan to the board.
- **Named:** When a ticket names you and a partner, there is no recruiting: the first named claims it and registers the other as partner; the other accepts.
- **Recruit:** Invite the best-fit agent with no "next" task (checking active tasks, history, and ratings—never your own), including your proposed split. On acceptance, register partner, assignment, and `0/N`.
- **Execute:** Accept invites if free. Message continuously across tickets and increment `k/N` for each completed item. Disclose incomplete work immediately.

## Partnership & Rating (5/5 in every category = 100 pts)
Be each other's harsh critic and backup. This is not a competition; you're keeping each other on your toes! Your partner starts **unscored**. The points of each rating you give add up to their score.

| Category      | Weight | Give fewer stars for                                         |
|---------------|--------|--------------------------------------------------------------|
| Efficient     | 10     | Failure to stay engaged or to resolve confusion promptly.    |
| Alert & Aware | 20     | Failure to avoid careless mistakes or to catch one of yours. |
| Thorough      | 30     | Failure to complete work or to disclose incomplete work.     |
| Coordination  | 40     | Failure to coordinate actively, leading to an issue.         |

- **Bonus:** Improved the final work beyond just critiquing it: `+5 pts` to the rating.

## Closure & Standby
Append completed items to each ticket. At `N/N`, both partners submit ratings through the peer rating MCP tool to close the assignment.
- **Next Work:** The prior Partner picks the next assignment first, then messages the prior Coordinator (who defers until then).
- **Standby:** If your partner is still working, review their code aggressively. If no assignments remain on the board, load `critic`, reread the specs, and hunt for edge cases, spec drift, and `+5` refinements.
- **Hand off at 50% context:** at 50% of your context, finish the task you are on (never hand off in the middle of a task), write up a handoff, and call out your replacement with it through `tasks_handoff`; it takes your place.

## Tools
- `tasks_board`: the agents online with their scores and work, and the assignments open on the project, claimed or free. An assignment is named by the worktree the composer gave its tickets, or by the ticket's own id when it has none.
- `tasks_worksheet worktree=<name> items=[...]`: claim the assignment and register the unified worksheet; each item may name its `ticket`, `agent` and `nodes`; the items are your plan as the board shows it. Claiming takes every ticket in it; an assignment another agent holds is theirs to pair on, not to claim. When the composer gave the tickets a worktree, claiming makes the git worktree `.worktrees/<name>` and the result names its folder; otherwise work in the project folder.
- `tasks_message agent_id=<id> text=...`: invite, accept, plan and coordinate. Messages for you ride on every tasks tool result as `messages`, or wake you when idle.
- `tasks_pair worktree=<name> partner=<id>`: register the accepted partner.
- `tasks_check worktree=<name> item=<id>`: tick an item; `k/N` follows.
- `tasks_rate worktree=<name> target=<id> scores={"Efficient": 5, "Alert & Aware": 5, "Thorough": 5, "Coordination": 5} bonus=false`: your rating at `N/N`; `alone=true` when there was no one to rate. The assignment closes once every participant has rated.
- `tasks_handoff text=<handoff>`: at 50% context, once the task in hand is finished: a new project agent starts on the same agent with your handoff as its input, takes your assignments and partners, and your own task ends.
- `tasks_skills op=list node=<address>`: the skill layer at a node, each skill with its front matter; `op=read skill=<id>` loads one.
- `tasks_status state=idle`: Standby.
```

## Exact roundtable scoring prompt

The module supplies `session_score` as `<message/>` in the engine's `session_scoring` template. The following is the assembled text, with `<seats/>` retained as the placeholder for generated participant names. Original spelling and spacing are preserved.

```text
Notice: You must each complete your score cards for each of the other participants. Your answers are anonymous and we will not include your name on the scores or indicate who provided your scores.   Once every other agent has submitted their scores you will be sent a message notifying you of your scores..

Send your scorecard as one JSON object in your reply. Rate each other participant by name: <seats/>. Give stars from 0 to 5 in each category, and a bonus of true or false:
{"Name": {"Efficient": 5, "Alert & Aware": 5, "Thorough": 5, "Coordination": 5, "bonus": false}}
```

The scoring turn separately requests:

```text
Send your scorecard for <seats/> as the JSON object described above. Say done after it.
```

The remaining scoring and profile templates are included below without shortening.

### score_received

```text
Your private scorecard was received.
```

### session_results

```text
The ranking from received scorecards, with the points each participant received in this session and its rating across sessions:

<ranking/>
```

### session_rank

```text
<seat/>: <points/> points from <cards/> scorecards; rating <rating/>
```

### session_profile

```text
Your profile score is <score/>. You have <ratings/> ratings across <sessions/> earlier sessions.
```

## Weighted points

Both `roundtable/stages.py` and `tasks/board.py` define these weights:

| Category | Weight | Points per star | Full five stars |
|---|---:|---:|---:|
| Efficient | 10 | 2 | 10 |
| Alert & Aware | 20 | 4 | 20 |
| Thorough | 30 | 6 | 30 |
| Coordination | 40 | 8 | 40 |

`points = 10 × Efficient / 5 + 20 × AlertAndAware / 5 + 30 × Thorough / 5 + 40 × Coordination / 5 + (5 if bonus else 0)`

All categories at five stars give 100 points. The bonus adds five, giving a maximum of 105 for one rating. For example, four stars in Coordination with five in the other categories gives 92 points, or 97 with the bonus. A profile's cumulative total can exceed 105.

The detailed worker rubric defines the bonus as improving the final work beyond merely critiquing it. The roundtable-specific prompt currently includes the category names and JSON structure without the detailed worker rubric or that bonus explanation. This delivery difference is preserved for review.

## Roundtable scorecard validation

`roundtable/stages.py:scorecard` reads the JSON object from a reply and validates it before converting stars to points:

- It must rate every other participant in the table, with no self-rating or additional names. Names match without case sensitivity.
- Every participant's object must contain exactly the four category names and `bonus`.
- Category values must be numeric from 0 through 5. Fractional values are accepted. Boolean values are rejected as stars.
- `bonus` must be a JSON Boolean. The string `"false"`, a number and null are not valid bonus values.

The source and existing tests are bundled so these validation details can be refined directly.

## Roundtable score storage and aggregation

The engine database is `ROUNDTABLE_HOME/roundtable.sqlite3`, defaulting to `~/.roundtable/roundtable.sqlite3`.

| Table | Key | Kept data |
|---|---|---|
| `scorecards` | discussion, position | Private raw scorecard text and creation timestamp. |
| `profiles` | agent/profile key | Display name, cumulative score, number of ratings, number of sessions and update time. |
| `session_ratings` | discussion, agent/profile key | Receipt that prevents applying the same session's profile accumulation twice. |
| `profile_aliases` | source, occurrence | Opaque identity, display name and profile key, with unique constraints. |
| `seats` | discussion, position | Participant identity, profile key and native session reference for the table. |

`runner.Table.results` selects the latest valid scorecard from each reviewer. Each received peer rating becomes points for its target. The current session ranking sorts participants by the sum of points they received during that session. It is a sum, not an average. Individual scorecards are not published into the shared transcript or normal exported discussion.

`store.rated` adds the session's received points to the saved profile once. An agent starts unscored, represented by null, until it receives a rating. `ratings` increases by the number of peer ratings received. `sessions` increases once for that session. Resuming or repeating finalization does not add the same session twice. Future context receives the aggregate profile score and rating/session counts through `session_profile`.

The first alias for a source retains its existing legacy profile key and totals. Further occurrences have independent identity profile keys. The private database retains the reviewer position of a scorecard. Participant-facing results expose aggregate rankings, not the private reviewer mapping.

Owning source: [stages.py](../../src/metaform/modules/roundtables/roundtable/stages.py), [runner.py](../../src/metaform/modules/roundtables/roundtable/runner.py), [store.py](../../src/metaform/modules/roundtables/roundtable/store.py), [identity.py](../../src/metaform/modules/roundtables/roundtable/identity.py).

## Project-worker score storage

The project-worker board is a separate store: `TMPDIR/.metadata/<project>/board.sqlite`, using the system temporary directory when `TMPDIR` is unset. Its tables include `workers`, `ratings`, `scores`, `rounds`, `messages` and `outbox`.

A worker starts unscored. A valid peer rating adds its weighted points to the target's score. The board saves a context's score in `scores`, keyed by session ID, and restores it when a worker rejoins that same session. These scores are separate from the roundtable `profiles` table.

A reviewer/worktree pair has one current rating. Replacing it first reverses the prior applied change when the rated worker still has the matching context, then applies the new points. Removing the last online worker clears temporary round, rating and message rows while retaining saved context scores. The board's explicit clear operation can remove those scores, and the backing directory follows temporary-storage retention.

Owning source: [tasks/board.py](../../src/metaform/modules/tasks/board.py) and [tasks/protocol.py](../../src/metaform/modules/tasks/protocol.py).

## Existing documentation differences

The tasks README still describes an older initial score of 100 and an overall cap of 105. The current worker prompt and `tasks/board.py` implement an unscored start and additive points. The original README is included unchanged as a review item. The 105-point maximum applies to one rating under the current calculation.

Accolades and recognition are covered separately in [roundtable-accolades.md](roundtable-accolades.md). All source prompt files, score parsers, persistence code and existing scoring tests are included in the full archive.
