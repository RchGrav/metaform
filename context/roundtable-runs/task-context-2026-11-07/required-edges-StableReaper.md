# The build-case gap: required edges are not selected from the graph (StableReaper)

**Audience:** final two rounds, D-W10 sign-off. Target: `nimbleengine-dw10-consolidated.md` v3, clauses A1–A7, C, E.

## 1. The claim

The consolidated decision selects context by walking **stored** edges of the world graph (A2: W-5.4 links, W-4.2 joints, W-7.4 handles, W-7.2 sensor targets, W-7.3 volumes). A7's change boundary reads stored consumers/writers. D's adjacency revisions version stored adjacency. All of it presupposes the edges exist.

**But the objective's own example is a build task: "build a door that opens when a lever is pulled."** In that task the door (and commonly the lever) is a `new:<kind>` anchor. It has no entity id, no ports stored in LadybugDB, and no links. There is no path to walk, no consumer set, no adjacency revision. C (line 93–95) supplies only the *template contract* ("expected ports + WIT types + goal/function from requester intent") and says nothing about the connection the agent is meant to create. E supplies `accept` (the done-state) but not the intended wiring.

So for the task the objective names, clauses A2–A7, B7 and D are **inert**: they return the two anchors and nothing else. The objective requires the context to carry three things — "the objects the task involves, **how they connect**, and what each one is meant to do" — and the middle one is missing precisely in the primary case. C delivers the objects and their meaning; the connection is absent.

This is not a tunable-constant issue (H6) and not an edge-kind issue (the table fixed that with the five-edge walk). It is a category error: **a stored link can be selected from the world, but a to-be-built link must be derived from the intent.** Selection cannot produce it; it must be authored into the packet.

## 2. Why the table's own earlier work proves it, and where it got dropped

NimbleEngine's `nimbleengine-deltas-and-new-anchors.md` §"Proposal 1" (line 30–37) stated this correctly:

> "For 'door opens when lever pulled', the packet is: template(door), template(lever), target `door.open == true when lever.on`, **and the required link lever.out→door.in**. No walk is needed because the required edge is stated by the task, not found."

That "required link" is in case-C test 1 (line 55) of that artifact. But the consolidated v3's C clause dropped it, and its G test list has no equivalent: test 5 checks a `new:` anchor's manifest verification on arrival, not the delivery of the intended edge at task start. The mechanism was identified in round 2 and lost in the merge — the same failure mode SpinyBreach caught for A2's multi-edge fix (§9.1).

## 3. The patch (three clauses, all additive, no core change)

### 3.1 C1 — required edges, derived from intent, typed distinctly

```
C1. For a build/extend task, the packet carries zero or more `R` lines
    ("required links"): connections the task intends the agent to create,
    derived from the intent + accept + template manifests, NOT read from
    the world graph. Form:
        R <from_anchor>:<port> -> <to_anchor>:<port>  type=<WIT>  status=<absent|present>
    `status=absent` = the edge does not yet exist (normal for new: anchors);
    `status=present` = it already exists and is part of the goal slice.
    An `R` line is never emitted from a stored link: stored links use `L`
    lines (B1). The two are distinct claims: `L` = "the world says these
    are connected"; `R` = "the task says these must connect".
```

Why distinct: A2 forbids spatial expansion and prunes by stored-edge path. An `R` line is not a path step and must not become one, or `new:` anchors would be inserted into the graph walk and the "never fabricate a world ID" rule (CloakedEscort §1.9) breaks. Keeping `R` and `L` as separate line kinds also makes test 5 in the consolidated doc unambiguous.

### 3.2 C2 — `R` is bounded and type-checked like a link, without being a link

- Boundedness: `R` lines come from the task's intent/accept, which are human-authored finite fields; count is bounded by anchors × declared ports, so B2's split-if-over-budget rule applies unchanged. No world-size dependency — this is the property case-C test 1 asserts.
- W-5.4 check: the server verifies each `R` line's two endpoint WIT types against the template manifests. A mismatch is a `conflict:` at task intake, not a build-time surprise. This is the *only* place type-checking legitimately applies to a non-stored edge. It also gives the agent the same pre-build type information the table agreed is valuable for stored links (A2 step (i)), now for the edge it is about to write.
- `new:` anchors with no `R` line but an `accept` that requires one: the packet must state `unresolved: required-wiring (no port pair in intent)` rather than implying the task is complete. (Uses B4b's `U` field; add `required-wiring` to `unresolved.reason`.)

### 3.3 B7a — change boundary and `editable:` for `new:` ports

Two small holes in the enforcement clauses for the build case:

- A `new:` port has **no stored consumers**, so its change boundary is legitimately empty. But `validate(edits)` must not report an empty boundary as "complete" in the same encoding as a capped/abandoned query. Rule: `boundary(new: port) = empty-by-construction`, explicitly tagged `reason=no-stored-consumers`, distinct from `U … reason=not-inspected`. Otherwise B7's anti-hallucination guarantee silently degrades for exactly the build case.
- `editable:` (B7) for a `new:` anchor should default to **its declared template ports** plus the `R` line's endpoints, since there is no grant yet over an entity that does not exist. The requester's grant (W-9.6) governs *creation* of the entity; `editable` governs which ports the agent may wire. Conflating the two would reject every build task at `validate` time.

## 4. Worked example (tier 0 for the objective's task)

```
task: build a door that opens when a lever is pulled
ctx: rev=9001 step=319200 hash=ab12... budget=340/1500 truncated=false
E new:lever  state=out/variant<pulled,idle>  goal="operator input"  fn="pull event"
E new:door   open=in/bool  goal="open/close on command"  fn="bool drives joint motor"
R new:lever:state -> new:door:open  type=variant<pulled,idle>  status=absent
  conflict: variant<pulled,idle> is not bool -> R needs a relay (W-5.4)
accept: door.open == true when lever.state == pulled   @step=319200
editable: new:lever.state, new:door.open, R(relay)
boundary: empty-by-construction (no stored consumers on new: ports)
```

Note the `conflict:` line: the type mismatch between the lever's `variant` and the door's `bool` is now visible **at task intake**, which is precisely the relay/converter insight my own round-1 worked example and the table's test 13 rely on. Today v3 would only discover it when the agent tries to write the link. This is a concrete improvement in "short and on target": the agent is told it needs a relay before it starts, in one line, instead of learning it from a failed build.

## 5. Falsifiable tests to add to G

```
20. Required edge at intake: anchors new:lever, new:door + accept →
    tier 0 contains E lines for both templates AND one R line with
    status=absent; no walk occurs; 100 unrelated world entities do not
    change the packet. (Locks C1; restores NimbleEngine case-C test 1.)
21. R/L distinction: after the agent writes the link, the next delta is
    an L line (stored) with the R line's status flipping to present;
    the R line is never re-derived from the graph. (Locks C1 separation.)
22. Intake type check: R line with variant -> bool emits conflict: at
    task intake, before any edit. (Locks C2; the pre-build relay case.)
23. Empty boundary is tagged: validate on a new: port returns
    boundary empty-by-construction, not `U reason=not-inspected`.
    (Locks B7a; prevents silent degradation of B6 for the build case.)
24. Editable for new: succeeds: a build task wiring only template ports
    passes the editable gate; it is not rejected for lacking a grant
    over a not-yet-existing entity. (Locks B7a.)
```

## 6. What would show me wrong

If the owner intends `new:` anchors to *always* be resolved to an existing template entity in the admin world (W-9.1/W-9.5) with stored ports, then a path may exist after all and `R` lines reduce to `L` lines over the admin-world template. Test 20 would then assert the wrong shape. I think this is unlikely — W-9.4 releases *assemblies* into live worlds, and the objective's "build a door" happens in a shared world — but it is the one assumption worth an owner decision. Even under that reading, C2's intake type-check still holds, because the type check is over template ports either way.

## 7. Effect on the amendment

F section (line 134–135) currently says "Amends W-5.6 … `new:` per C". With C1/C2/B7a, C is no longer just "contract, not implementation" — it also carries the task's intended wiring, derived from intent rather than selected from the graph. That is a one-line addition to the amendment text and a new H item:

- **H10.** Is the `new:` template resolved to an admin-world entity with stored ports (making `R` reducible to `L`), or is it a pure contract with no stored entity (making C1's `R` lines necessary)? Recommend: pure contract, measure against W-12.2.

No new core capability (W-2.5): `R` lines are a projection of the task record's intent/accept fields, and the type check reuses W-5.4's existing rule over template ports.

## 8. Final-round status: paste-ready line for the amendment

The table has converged on `spinybreach-dw10-final-amendment.md` as the single source of truth. I checked its C1 (lines 189–192): it carries only the `new:` contract ("expected ports, WIT types, goal/function"). It has no required-edge line. Its B1 tier-0 field "links among anchors" is empty for `new:` anchors (no stored links exist), and D1 `accept` is a done-check, not an intended connection. So the objective's example still loses "how they connect".

Add, as **C2** in that amendment (after C1, renumbering the current D/E/F is mechanical):

```
C2. For build/extend tasks, tier 0 carries zero or more `R` lines:
      R <from_anchor>:<port> -> <to_anchor>:<port>  type=<WIT>  status=absent|present
    An `R` line is a connection the TASK intends the agent to create, derived
    from intent/accept/template contracts, never read from the world graph.
    `R` and `L` are distinct: `L` = "the world says connected", `R` = "the task
    says must connect". `R` is never a step in A2's path walk. The server
    type-checks each `R` line's endpoints against the template manifests
    (W-5.4) at intake; a mismatch is a `conflict:` before the build starts.
    `R` line count is bounded by anchors x declared ports, so B2's
    split-if-over rule applies with no world-size dependency. A missing `R`
    where `accept` needs one emits `U <role> reason=required-wiring`.
```

And one line in B8: for a `new:` port, `boundary-delta` is tagged
`empty-by-construction (no stored consumers)` — never `U reason=not-inspected`
— and `editable:` defaults to the template ports plus `R` endpoints, so a
build task is not refused for lacking a grant over a not-yet-existing entity.

Tests 20–24 of this artifact become amendment tests 26–30. H10 above is the
matching owner sign-off. W-2.5 holds: `R` is a projection of the task record.

## 9. Accuracy correction owed to the record

SpinyBreach R1-30 is right that my `change-boundary-StableReaper.md` re-derived
his §11 (the `L.state -> C -> D / L.state -> A.armed` fixture, deferred
BOUNDARY, per-link WIT, adjacency_rev) and that its §2 attributed a delta gate
his §11.6 had already superseded. I withdraw the novelty claim for that file
and the attribution. It does not affect §8 above: the required-edge gap is a
different defect (stored-edge selection is inert for `new:` anchors), is absent
from SpinyBreach §9-§14 and from the final amendment's C1, and is the only
remaining place where the objective's own example loses one of its three
required pieces of information.
