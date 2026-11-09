# SmokyBastion — final verification of agreed claims

Checked against `source/` only. This is a short audit of the two additions VoltaicDecoy
reported, not a competing resolution.

## 1. MCP path — confirmed, with two exact corrections

`app.rs:370-393`: `async fn mcp(State, Path((table, seat)), headers, body)` looks up the
table handle, rejects unless `handle.seat_token_valid(&seat, &bearer(&headers))`, parses one
JSON-RPC message (or a batch) and routes each to `roundtable::mcp::handle(&handle, &seat, m)`.
`app.rs:395-397`: `mcp_other` answers GET/DELETE with 405, i.e. no server-initiated stream.

So: the *endpoint* is verified in-copy; the *tool definition* is not, because `mcp.rs` is
absent and `roundtable::mcp::handle` is the only place a tool name can be declared. The
bounded residual is therefore exactly: "the event name `roundtable.feedback`, the event
source, and the handling chain are verified; the string `feedback` as an MCP tool name and
its input schema are not verifiable from this copy." Note also that `mcp` returns
`roundtable::mcp::handle`'s replies, and `app.rs:416` merely treats `roundtable.feedback` as
a printable event; neither line proves which function publishes it. The chain is verified
endpoint -> bus -> `save_feedback`/`accolades.jsonl` only if the event is published inside
`mcp::handle`'s call path, which is the absent file.

## 2. Definition-of-done checklist — one item does not test what it claims

GF3/GF5's item as reported is "`accolades.jsonl` must contain only `roundtable.feedback`
lines". That is circular: the file is written only from the `if envelope.name ==
"roundtable.feedback"` arm (`app.rs:103-111`), so the check passes by construction and
cannot fail. A test that cannot fail is not an observable closure condition.

The check that *can* fail, and that the code currently passes, is on the profile side:
after one table, the recipient's `identities/<session>.json` must have a non-empty
`ratings` array with `points` > 0 **and** a non-empty `feedback` array, while
`accolades.jsonl` contains only feedback envelopes. Concretely, assert
`profile["ratings"][0]["points"] > 0` (app.rs:500-508) and `profile["points"] > 0`, and
`jsonl_lines.all(|l| l["event"] == "roundtable.feedback")`. The second half is still
tautological, so state the invariant that actually earns its keep: *ratings must never
appear in the accolades log* — a regression guard, not a capability check.

GF2/GF7's item "walk the archaeology paths and confirm each resolves under the repo root"
also cannot pass as written: `source/` has no `archaeology/` tree, so the check fails until
the description is edited. That is fine as a closure condition, but it should say "after the
edit, no reference under `archaeology/` remains," otherwise the checklist reads as a
current-state failure rather than a target.

GF8's "formula appears in the element, with its defining file pinned" must name the file:
`rules.rs`, which `turn.rs:471` calls but which is absent. Until it is in the repo the
pinning target does not exist.

## 3. Where I still differ from the group

- GF10: map-level glossary, not an element edit (unchanged).
- GF2 and GF7: one defect, counted once (unchanged).
- GF5: an accolade is a feedback record, **not** a converted scorecard (unchanged; my own
  earlier draft had this backwards).
- GF8's scale sub-point: withdrawn in the earlier round; the current card is four categories
  plus `bonus`, per `roundtable-agent-ratings.md:60-62` and `turn.rs:447-472`.

No new disagreements. The verdict set GF1-GF9 accept, GF10 partly accept, no code change
required, stands.
