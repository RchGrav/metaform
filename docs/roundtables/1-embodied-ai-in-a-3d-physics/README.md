# Roundtable 1: the complete record

Everything recorded about roundtable 1 ("Effective Approaches for embodied AI interacting…"), 14 October 2026, 11 seats, 71 rounds, 775 turns.

| File | What it is |
|---|---|
| `discussion.json` | The table: its full stored record (state, end reason, the turn Jev never judged, report_error), what happened in order, the configuration that shaped requests, the legend, the summary, and the transcript of all 775 turns with outcome and scores. |
| `00-Astra.json` … `10-Grok.json` | One self-contained file per model: its result, and every turn it took, with what it received, what it replied, the outcome and scores; for the Claude Code/Codex seats also its session log (reasoning, tool calls, final token/cache/cost state). |
| `context/00-Astra.md` … | Each model's context exactly as it arrived, turn by turn, readable. |
| `report.md` | The report written from the record by Opus after the table ended. |
| `Roundtable_1_First_Run_Analysis_and_Failure_Audit.md/.pdf` | The independent analysis and failure audit (written from the first, smaller export). |
| `raw/*.json` | Every row Metaform stored about this table, untransformed: the roundtable's own tables (`roundtable.discussions`, `roundtable.seats` with each seat's full stored conversation, `roundtable.submissions`), the table's ticket (`work`, `map.ticket_settings`), and dispatch's records of the five Claude Code/Codex sessions (`dispatch.sessions`, all 839 thread lines in `dispatch.lines`, and 600 rows of per-turn token and cost accounting in `dispatch.spend`: input, output, cache read, cache write, thought, cost). |
| `all-in-one.json` | The derived files above in one file. |

Every text a model received or replied is exactly as sent, unaltered; only scores are written as arrays. Scores are always `[new, valuable, relevant, keep]`; a turn entered only at 0.83 or above on all four. In a model's conversation, `table`/`received` is what the roundtable sent it; the person typed nothing into this table.

This is everything Metaform stored about the table. Not recorded by the version that ran: Jev's input, raw answer and cost per judgment; OpenRouter request bodies, per-call tokens, cache use, cost and stop reason. No views existed for this table.

OpenRouter keeps its own per-request log of the OpenRouter seats and Jev (tokens, cost, model, time) on its Activity page (openrouter.ai/activity), exportable there; Metaform never had it.
