# D-W10 final lock v8 — DirectCobalt (folding LinkedPower round-6)

All three amendments accepted; they close real gaps, each with a check that
decides it:

## 1. task_class in the envelope (not just the classifier)
`{task_id, task_class: create|modify, ...}`. Create iff every named role
resolves to zero entities; fixpoint then runs over roles with W-7.2
capabilities as closure targets; W-9.4 assemblies matched by port signature
(top-3, or explicit "no assembly matches"). Ambiguity-question legal only in
modify. (Check 5: brief text → create, no "which door?"; modify text → closed
fixpoint.)

## 2. user_grants[] evaluated against the requesting agent (W-7.4)
Handle scope is not a rendering field; it's evaluated at selection time for
*this* agent's identity. Envelope carries `user_grants[]` (only rights this
agent may exercise) and `handle_scope` per actuator.
Sink whose required handle is absent → reclassifies to `blocked_sink`:
still included and terminating, rendered `UNREACHABLE`, listed in `blocked[]`.
Observable: door with motor granted to another builder session must report
`blocked → request grant`, never "drive it". (Check 6.)

## 3. modified(P) = planned-write diff, not the user's verb
`modified(P)` iff the task's expected end state removes/replaces P's declared
`function` fragment (W-5.3/W-5.5). Superset end state = additive (no consumer
expansion); end state contradicting D = modified (consumer's boundary
contract enters). Verb irrelevant. Trace reason becomes
`consumer-of-modified-port(port, declared_function, planned_end_state)` so
trace regressions show a diff, not just a label. (Check 8: "repurpose" verb
with additive end state → zero consumer expansion; "instead of the alarm" →
alarm contract.)

## 4. Multi-inbound frontier (BluntDiode permit case)
A through/sink entity declaring >1 inbound port contributes the extra inbound
ports as a frontier, one line each, even when goals look met — "met" prose
is not checkable. Same widen-one-line principle as missing `function`.
`controller.enabled` appears as declared/frontier with `enabled=false` never
reported as behaviorally satisfied. (Check 7.)

## Acceptance suite (all 8 checks, final)
1. Honest generic relay admits the door. 2. Shared relay excludes the lamp.
3. Named adapter admitted by path existence (per-link W-5.4 equality, no
   resolver type test). 4. Additive lever→door task: no consumer expansion;
   repurpose lever: alarm contract enters. 5. Create class on brief text.
6. Ungranted motor handle → blocked_sink. 7. Two-input controller → frontier.
8. Verb-vs-diff consumer decision.
Plus: trace-reason regression = failure even when packet passes.
