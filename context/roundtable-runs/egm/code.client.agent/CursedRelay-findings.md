# CursedRelay: GF9 counterexample and evidence limits

The assertion that “last non-empty segment” implements “text after the last tool call” is false
for a turn ending with a tool call. This follows directly from the supplied source; no live agent
or SDK assumption is needed.

| Step | Source operation | Transcript state |
| --- | --- | --- |
| Agent emits `Checking` | `append(None, "Checking")`, harness.rs:124–137 | One segment containing `Checking`; split is false |
| Agent starts a tool | v1 `ToolCall` invokes `split()`, 746–748 | Same segment; split becomes true (140–142) |
| Turn ends without later text | `take_turn`, 682–690 | Calls `final_message()` without creating another segment |
| Final extraction | `final_message`, 166–170 | Returns `Checking`; there is no text after the tool |

Even if later text consists only of whitespace, the reverse scan skips that blank segment and
can return the earlier `Checking`. A gate comment above the function does not alter either path.

V2 provides a second reason to avoid equivalence: `segment(id)` retains first-seen order
(144–153), snapshots replace contents in that order (155–163), and v2 tool updates only publish
activity, without splitting text (819–831). Updating an earlier message after a later one does
not move it to the end.

The two-output observation from the other participants is valid and independent:
`reply()` joins all nonblank text segments, `final_message()` selects the last nonblank one, and
both are published in `PromptCompleted`. The supplied manager consumer is missing, so naming
`final_message` as the group's field is a recommended contract, not a verified current fact.

The consolidated resolution must therefore either recommend amending RT-G09 to the current
last-nonblank-segment behavior, or recommend changing extraction to honor the strict last-tool
boundary. A prose claim that the two are already equivalent is not a resolution.

Chronology likewise cannot resolve GF8: the explicit permission decision is a requirement,
whereas a later build report describes implementation. Date labels clarify GF3/GF7, but do not
authorize silently changing a requirement to match implementation. GF1/GF4 caller claims remain
conditional on checking files absent from this snapshot.
