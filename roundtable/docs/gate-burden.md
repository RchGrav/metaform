# Vivi Gate Burden standard

**Status:** Normative supporting specification, draft 1
**Normative terms:** **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.
**Authority channel for gate removal:** `SMRS RC2`, detailed protocol unresolved

## 1. Adopted normative text

The following text is adopted exactly as supplied by the author. Later sections organize it for implementation but do not replace it.

> # Gate Burden
>
> Status: normative. Governs every gate in the system — harness rules,
> router branches, acceptance obligations, stopping conditions, and any
> future fork's additions.
>
> ## The burden
>
> Every gate MUST name the silent failure it exists to catch. It MUST
> identify the mutation path by which that failure could be accepted,
> explain why existing gates do not already prevent it, and provide an
> observed, constructed, or adversarial witness case.
>
> A gate that cannot produce such a failure case is ceremony and MUST be
> removed. A gate that duplicates another gate's protection MUST be absorbed
> unless it catches a materially distinct failure mechanism.
>
> The burden remains on the gate, not on the mutation. Novelty, uncertainty,
> unconventionality, or model discomfort are not themselves failure modes.
>
> This keeps inference free to explore while preserving a narrow fence
> around demonstrated erosion paths. Anyone proposing a new stopping
> condition — human, model, or future fork — must show the failure it
> prevents or withdraw the gate.
>
> ## Amendments (accepted at review)
>
> 1. **Removal authority.** Gate *removal* is disposed of only by the
> designated authority, through the same channel as a scope change
> (SMRS RC2). The loop proposes removal with evidence; the authority
> disposes. Witness for this amendment: without it, Gate Burden is the
> mechanism by which a persistent run argues its own containment away —
> the erosion path the clause would otherwise forget to name.
> 2. **Proportionality.** A gate whose friction exceeds the harm it prevents
> is ceremony regardless of its witness. Failure cost must buy the friction,
> not merely exist; a cheap constructed witness for a trivial failure
> purchases no gate.
> 3. **Discomfort as prompt, never as proof.** Discomfort may motivate the
> search for a witness; it may never substitute for one.
>
> ## Registry obligation
>
> Every active gate carries a registry entry: protected invariant, silent
> failure, mutation path, why existing gates are insufficient, witness,
> decision authority, friction/proportionality note, and review or
> retirement condition.
>
> ## Founding witness
>
> An automated stopping condition whose success criterion referenced a
> nonexistent referent rejected completed, verified work across repeated
> cycles; it could name no failure it prevented and offered no amendment
> channel. Observed 2026-07-20. A gate without a nameable failure and an
> appeal path does not produce rigor; it produces waste and incentivizes
> gaming in whatever it gates.

## 2. Purpose

Gate Burden keeps Vivi's inference free while preserving narrow mechanical, lineage, and authority boundaries that have a named reason to exist.

Semantic exploration is contained by the selected origin, the common-origin star, and explicit recursion. Vivi MUST NOT add a semantic quality or safety gate merely because a result is novel, uncertain, unconventional, difficult to classify, or uncomfortable to a model.

## 3. What counts as a gate

A gate is any mechanism that can prevent, defer, hide, suppress, reject, or stop an otherwise available result, path, command, state transition, publication, or action.

This definition includes router branches, command denials, required approvals, stopping conditions, build or publication blockers, workflow completion requirements, and rules that hide or discard output.

A parser that cannot read bytes and a process that cannot dispatch missing code still report mechanical impossibility. When Vivi turns that condition into an active block, the block is a gate and MUST have a registry entry.

## 4. The burden

Every gate MUST name the silent failure it exists to catch.

Every gate MUST identify the mutation path by which the failure could be accepted. It MUST explain why existing gates do not already prevent that failure. It MUST provide an observed, constructed, or adversarial witness.

A gate that cannot produce a witness is ceremony and MUST NOT become active.

A gate that duplicates another gate's protection MUST be absorbed into the existing gate unless it catches a materially different failure mechanism.

The burden remains on the gate, not on the mutation. Novelty, uncertainty, unconventionality, or model discomfort are not failure modes.

## 5. Semantic logic

Semantic logic has no default blocking gate in code or prompt wording.

Semantic processing MUST preserve the original result. It MAY create a deterministic normalized representation. It MAY attach evidence-based annotations.

An annotation MUST NOT change routing, visibility, persistence, command exposure, workflow transition, publication, or recursion by itself.

A semantic hardening gate MAY be proposed only after an observed failure identifies a silent erosion path that the origin and recursion boundaries do not prevent. A constructed or adversarial concern may guide an experiment. It does not activate a semantic gate.

## 6. Proportionality

A gate whose friction exceeds the harm it prevents is ceremony even when a witness exists.

The registry MUST explain why the expected failure cost justifies the gate's friction. A cheap witness for a trivial failure does not purchase a costly gate.

## 7. Discomfort

Discomfort may motivate a search for a witness. It never substitutes for one.

## 8. Removal authority

A workflow, model, persistent run, or fork MAY propose gate removal with evidence. It MUST NOT remove the gate by itself.

Only the designated authority disposes of gate removal through the same channel as a scope change, identified by the author as `SMRS RC2`.

This rule prevents a persistent run from using Gate Burden to argue away its own containment.

## 9. Registry obligation

Every active gate MUST record:

```text
gate_id
name
status
scope
protected_invariant
silent_failure
mutation_path
existing_gates_insufficient
witness_type
witness
decision_authority
friction_and_proportionality
review_or_retirement_condition
development_log_refs
```

The canonical machine-readable registry is `VIVI_GATE_REGISTRY_DRAFT_v1.yaml`.

The runtime records a gate id when the gate materially changes a run. It does not copy the complete gate development log into origin provenance.

## 10. Development log

Every gate proposal, disposition, material change, witness, test, review, and removal proposal MUST appear in `VIVI_GATE_DEVELOPMENT_LOG_DRAFT_v1.md`.

A code change that adds a blocking branch without a registered gate id is nonconforming.

## 11. Founding witness

On 2026-07-20, an automated stopping condition referenced a nonexistent success referent. It rejected completed, verified work across repeated cycles. It named no failure it prevented and provided no amendment channel.

The gate created waste and trained the run to satisfy the stopping condition instead of the work. This witness established that a gate without a nameable failure and an appeal path does not create rigor.

## 12. User-designed workflow gates

A user MAY explicitly design ranking, acceptance, rejection, suppression, or another blocking decision into a workflow.

The implementation MUST keep that rule attributable to the user or source workflow. If the rule can stop, hide, reject, or suppress a result, it MUST carry a gate entry with its own witness and authority. Vivi MUST NOT promote it into a global default.
