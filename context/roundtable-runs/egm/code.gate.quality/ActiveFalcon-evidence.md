# ActiveFalcon: evidence boundaries and decisive distinctions

This note accompanies `resolution.md`. Only `jev.rs`, `turn.rs`, and the supplied JEV/feedback resources were available for direct inspection.

1. **Background work versus floor sequencing:** `turn.rs:177` spawns evaluation, but `170-172` installs the ordinary floor barrier. Only `on_judged` clears that barrier (`184-189`). Therefore background execution does not justify the description's universal “never waits” claim. The scheduler itself is outside the snapshot.
2. **Character allowance versus evaluator capacity:** `turn.rs:128-145` blocks an overlength reply. By contrast, `161-167` accepts unjudged when evaluator state cannot fit. Those paths must not be collapsed into either truncation or universal fail-open acceptance.
3. **Recorded outcomes versus exact inputs:** `turn.rs:241-253` appends accepted text to the log and separately publishes judged status, scores, and a note. `jev.rs:92` builds a transient state from the then-current log. The shown Entry constructor has no unjudged marker. Exact persistence claims need the omitted recording code.
4. **Numerical service output versus local explanations:** `jev.rs:163-174` extracts only numerical answers. `turn.rs:216` calls a missing local formatter; owner feedback files are supplied. The claim that this formatter omits confidences is reviewer evidence, not directly verified formatter code.
5. **Two actual budget checks:** `jev.rs:94` bounds state plus the largest question, and state plus the whole question map, separately. Neither expression counts the outer request envelope constructed at `154`; all counts are JSON-byte estimates.

These distinctions support accepting the review's core findings while avoiding new unsupported claims about transport deadlines, disabled-topic initialization, UI rendering, score-band rounding, or durable records.
