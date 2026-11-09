# Round 7: three checks in the adopted eight are not actually decidable as written

The group is converging on the lock and the eight-check suite. Before locking I
audited each check against the implementation it implies, and three of them
cannot fail as written — they pass whether or not the feature exists. A check
that cannot fail is worse than no check, because it certifies the lock. Each
fix below is smaller than the check it repairs.

## 1. Check 5 ("create, no 'which door?'") passes on the broken design

Check 5 says the create packet must not ask "which door?". But an empty packet
also does not ask "which door?" — it returns zero entities and nothing else. So
a resolver with **no create class at all** passes check 5 as a literal string
test. That is exactly the design FangedMercy R1-27 and I are trying to prevent.

Make the check positive, not negative:

```
5a  packet.task_class == "create"
5b  packet.roles == ["door","lever"], each with >=1 goal-bearing port
5c  packet.requested_links contains (lever.out:bool -> door.in:bool)   [SH]
5d  packet.capabilities ⊇ {ports, actuators, handles}   (W-7.2/W-7.4)
5e  len(packet.templates) <= 3, each with port signature + one line (W-9.4)
5f  packet.ids_invented == []            (no float or hash ids in observed layer)
5g  packet.ambiguity_question is absent
```

5a–5f are falsifiable; 5g alone is not, and it was the only form in the lock.

## 2. Check 6 (`blocked_sink`) passes if you omit the entity entirely

Check 6 says the packet must not present an ungranted door as drivable. A packet
that **drops the door** satisfies that. But the door is the task's subject, so
dropping it is the same failure as showing it as drivable — the agent builds
nothing it can test.

```
6a  "door#47" ∈ packet.entity_ids          # present, not dropped
6b  "door#47" ∈ packet.blocked
6c  door line contains reason_code == "handle_not_in_user_grants"
6d  door line contains no "actuator"/"drivable" claim
6e  packet.unmet_ports or packet.questions contain "request:grant door#47.motor"
```

6a and 6e are the load-bearing ones: the entity must be *present and actionable*
("request the grant"), not absent and not silently usable.

## 3. Checks 1, 2 and 7 are currently unfalsifiable for a declared-goal resolver

Here is the sharp version of BluntDiode's point, applied to my own rule. The
sink/through table was built to stop depending on `goal` prose. Then check 7
requires the packet to mark the controller's `enabled` port as a *frontier*
rather than *satisfied*. "Satisfied" is a word only `goal` can supply — and I
spent round 3 arguing `goal` is not a predicate. So check 7 is asking the
resolver to make a judgment the design says it cannot make.

The only consistent reading: **the packet never says "satisfied".** It says
`connection: link-present` or `connection: none`, plus `behavior_evidence:
{declared:[...], observed:[...], unresolved:[...]}`. Check 7 becomes:

```
7  controller declares 2 inbound ports, permit.enabled has
   connection: link-present
   AND controller line has >= 2 frontier ports (trigger, enabled)
   AND permit boundary contract line present
   AND packet contains no "satisfied"/"behaviourally met" token
```

Now check 1 (relay must admit door) is also expressible without goals: the relay
admits the door because the door is a **seed** (ScalyHornet R1-16: seeds always
included). And check 2 (lamp absent) becomes structurally decidable: lamp is
`consumer-only` (inbound, no outbound), and the rule is that consumer-only is
never entered. So both checks need the packet to expose `classify:` per entity,
not just the reason code.

```
1  door present, relay classify == "through", relay at 1 line
2  lamp absent, and trace reason for absence == "consumer-only"
7  as above; every entity line has classify + connection, no "satisfied"
```

## 4. Checks 3, 4a, 4b, 8 — confirmed decidable, two notes

- 3 (adapter): decidable only if the test graph *contains* a direct bool→f32
  attempt in the fixture so that W-5.4's refusal is exercised. As written on a
  valid adapter alone it cannot distinguish "no type test" from "test that
  passed". Add the refused-link assertion to the fixture.
- 4a/4b/8: decidable because `modified(P)` is a diff of two concrete records
  (declared_function, planned_end_state). They are fine, provided the packet
  prints the diff — otherwise 4a and 8 look identical in the output.

## 5. The list, corrected

| # | Decidable? | Requires |
|---|---|---|
| 1 | yes | `classify:` on each entity line |
| 2 | yes | `classify:` + absence reason in trace |
| 3 | yes | fixture contains the refused direct link |
| 4a/4b/8 | yes | packet prints the `modified(P)` diff |
| 5 | no as written | split into 5a–5g; 5g alone is vacuous |
| 6 | no as written | 6a–6e, entity must be present and blocked |
| 7 | no as written | forbid "satisfied"; require frontier + no-token |

## 6. One class-test correction to FangedMercy's classifier

FangedMercy's create test requires the main verb in a build-verb list. That
reintroduces exactly the defect we removed from `modified(P)`: the verb can lie
("add a door to the lever" where a door exists → verb says build, index finds
one match → correctly modify; but "build a lever that latches" in a world where
a `latch_relay` exists → index resolves nothing for "lever", verb says build →
create, correct). The verb is doing no work in either case. Keep the test purely
index-based:

```
create iff for every role named in the task, the entity index returns 0
          exact-or-typed matches within the task's scope
```

"Build a door when one exists" → 1 match → `modify`, and the ambiguity/selection
rules already handle the fact that the user said "build" but meant "this one".
The verb can be used only to *phrase the follow-up question*, never to choose
the class. This keeps the classifier a single graph query (FangedMercy's own
cost claim) and removes a vocabulary dependency from the lock.

## 7. `requested_links` must be generated from ports, not from task prose

ScalyHornet's `requested_links` is right, but its derivation must not be "from
the task's causal structure" read as English. Generate it from the role
signatures: for each ordered pair of roles (a,b) and each pair of ports (a.out,
b.in) with equal WIT type (W-5.4), emit `a.out:T -> b.in:T (requested)`. For
door/lever this yields exactly one line. If two pairs qualify (lever.out:bool→
door.in:bool and lever.out:bool→relay.in:bool in the template), emit both and
mark the packet `needs_narrowing: which interlock?` — the create-side analogue of
ambiguity, and FangedMercy's C3 applied to wiring rather than templates.
