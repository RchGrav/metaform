# AcuteNitrate — contribution to W-1.4 (feature blueprint)

**State:** roundtable working note, 2026-11-07. Not a standalone spec; read alongside `blueprint-spec.md` and HunterRanger's proposal.

Purpose: resolve three points the two current drafts leave in conflict, and give the table a concrete answer to the two questions HunterRanger raised (the `satisfies[]` / resolver question, and the write-target question).

---

## 1. The conflict the table must settle first: is the blueprint a graph projection or an authored document?

Two incompatible positions are now on the table:

- `blueprint-spec.md` §1: a blueprint is a **document in LadybugDB keyed by a blueprint id**, with `id`, `status`, `assembly`; the world server "materialises the assembly" from it. The server is the consumer; the blueprint is a producer input.
- HunterRanger R1-1: a blueprint is **a partial subgraph of the world graph with a designated root**; "writing the blueprint and building the entity are the same edit to the same graph". There is no separate document.

These cannot both be true, and the difference is not cosmetic. It decides:
- whether `status` lives on a blueprint or on the instantiated entities;
- whether `release` copies a blueprint or an assembly (W-9.4 says assembly);
- whether the agent owns anything (the owner's 2026-11-06 reconsideration);
- whether W-5.6 context is read from a document or from graph nodes.

**Decisive evidence is the owner's own reconsideration, quoted in W-1.4:**
> "allow for agents to build their own metaform map to describe whatever it is they intend to build and give them ownership of their own metaform" (2026-11-06)

"Build their **own** metaform map" + "give them **ownership**" + "**describe whatever they intend to build**" (intent, i.e. design-time) resolves all three drafts' ambiguity:

- It is **not** a projection of the live admin-world graph (against HunterRanger): a metaform is authored *about* what one intends to build, before the entities exist. W-9.1 (admin world is where you build and test) is the *test* location, not the *authoring* substrate.
- It is **not** a server-materialised assembly doc (against the current `blueprint-spec.md`): the assembly (W-9.4) is the *release* unit, produced *from* the blueprint after testing. Putting `assembly` inside the blueprint collapses design-time and release-time into one record and makes W-9.4's "records the hashes it used" circular.

**Recommendation:** a feature blueprint is an **agent-owned metaform**: a design-time, addressable map of *intended* entities, ports, links and assertions, authored by the agent, owned by the agent, stored in the world's LadybugDB (W-3.5) in the agent's own namespace. It is the *writer* of the world graph (the draft is right about that) but it is a distinct artifact from the graph it writes (HunterRanger is wrong to collapse them). `status` and `assembly` leave the blueprint; they belong to the build/release side.

This also settles HR's **write-target question #2** explicitly (he asked the table not to let it "leak into the spec"): `submit()` targets the **agent's own metaform**, not the shared admin graph. The admin world (W-9.1) is where the submitted blueprint is *instantiated and tested*, under the admin's release right (W-9.3, W-9.6). Agent-owned map → admin-world test → admin-gated release is a three-stage pipeline, and each stage has a different owner. A single "shared admin graph" write path (HR) or a single "server materialises" path (draft) flattens it.

---

## 2. Resolve HunterRanger's `satisfies[]` / resolver question: make assertions a *derived layer*, not a stored field

HR asked whether, under the D-W10 resolver model, `satisfies[]` should be derived rather than stored, and whether his provenance field is then the only survivor. Concrete answer:

D-W10 says: "The functional map composes layers on each address and selects them with a resolver (`TOPOGEE.md` section 2); that is one model to compare against." W-5.3 already establishes that `goal`, `function`, `intent` "keep the meaning of the functional map's want fields (R-3.6), so an agent reads both graphs the same way." So the metaform technique **is** the layered/resolved technique, and W-5.3 confirms the field-level continuity.

Apply it to the blueprint:

- Every blueprint address (a slot, see §3) carries **layers**, each a record contributed by one source:
  - `intent` layer — from the W-5.5 intent record (the user's "how it must work").
  - `manifest` layer — W-5.3 ports (`name`, `intent`, `type`, `goal`, `function`, `description`).
  - `link` layer — W-5.4 endpoints, type-checked at write time.
  - `assertion` layer — observable expectations.
  - `provenance` layer — author, parent blueprint, module/asset hashes (W-9.4).
- A **resolver** selects, for a given address and a given consumer, which layers are visible. The `assertion` layer is resolved *against* the `manifest` and `link` layers: an assertion's selector must name a port/sensor/voxel/worldparam that the manifest or a W-7.2 host-interface kind actually exposes.

Therefore: **`satisfies[]` is derived, not stored as an independent list.** Concretely, an assertion is valid only if its `selector` resolves to a declared port (W-5.3) or a W-7.2 host-interface capability. The world server can *compute* the set of satisfiable observables from the manifest + links + host interface; the agent's role is to attach `expected` values to selectors, not to invent selectors. This gives:

1. No duplicate source of truth (HR's own stated fear about a parallel format).
2. The server still decides "met" vs "claimed" — the assertion is evaluated on a fixed simulation step (W-8.3), values come from the host interface, never from agent prose. HR's `satisfies[]` insight survives; only its *storage* changes.
3. W-11.6 / W-5.6 context: the resolver is exactly the "brief, targeted" selector. The agent for a given task receives only the resolved layers of the addresses it concerns, not the whole blueprint. This answers the D-W10 open decision *for the blueprint* without claiming to settle it for the functional map.

Net: HR's field list survives almost intact, but `satisfies[]` becomes the resolved `assertion` layer, and provenance is one layer among several rather than the sole survivor. I recommend the spec adopt layer+resolver language explicitly so it is compatible with D-W10 whichever way the owner later rules.

---

## 3. The gap both drafts leave open: blueprint-internal addressing (this is W-1.4's actual complaint)

W-1.4's stated reason the functional map won't work: "the functional map's namespace setup does not support that [agents blueprinting their features]". W-5.1: the world graph is "grounded by its entity id, not by a namespace address". W-4.1: "the world server mints" entity ids.

So a design-time blueprint, authored before instantiation, **cannot address things by entity id** — those ids don't exist yet — and **cannot use the functional map's namespace** — W-1.4 forbids it. Both drafts dodge this:
- `blueprint-spec.md` §1.1.1: "`id` ... otherwise empty; the world server mints it" — no way to *refer* to an entity while drafting links.
- HR: "ports[] reference the root and archetype; actual `entityId.portName` bindings are filled in by the server" — right instinct, no addressing scheme.

**Proposal: blueprint-local slot addresses.** A slot is an agent-owned, blueprint-scoped address with the shape:

```
<blueprint-id>/<slot-name>            e.g. bp-7f3/door.left_motor
<blueprint-id>/<slot-name>.<port>     e.g. bp-7f3/door.left_motor/set_target
```

- Slots are declared by the agent (`blueprint.add_node`), give the entity `kind`/archetype (W-1.4 verb table, §1.1.1 `kind`), and carry the W-5.3 manifest, W-5.5 intent, and assertion layer (§2).
- Links (W-5.4) are written between slot addresses, type-checked in WIT at write time — exactly W-5.4's "error at connection time", just pre-instantiation.
- At instantiation, the world server **mints entity ids (W-4.1) and binds each slot to one**, producing the real `entityId.portName` endpoints the world graph stores. The binding is a resolved layer too: `slot → entity-id`. The blueprint keeps its slots; the graph keeps its ids; a `bindings` record maps between them and is what W-9.4's hash-pinned assembly records.

Why this is the right fix and not just new terminology:
- It gives the agent **ownership of its own metaform's namespace** (the 2026-11-06 reconsideration) without touching the functional map's namespace (W-1.1, W-1.4).
- It keeps W-5.1's grounding intact: the *world graph* is still entity-id-grounded; only the *design-time map* is slot-addressed.
- It makes W-5.6 context selection well-defined: resolve a task's slot addresses, return their layers. No third format, no whole-document read (HR's efficiency argument, W-11.6).
- It makes iteration/fork (`parent`, both drafts) meaningful: slots are stable across a fork even though entity ids differ after re-instantiation.

This is the single most important addition to W-1.4: the owner named a *namespace problem*, and the spec must supply a namespace answer. "Agents write records keyed by entity id" does not, because the ids are minted later.

---

## 4. Concrete amendment list for `blueprint-spec.md`

Keeping the existing draft's structure (do not rewrite it; other participants own it):

1. §0 / §3.1: state the blueprint is an **agent-owned metaform**, design-time, distinct from the world graph it writes. Add the three-stage pipeline: agent-owned map → admin-world test (W-9.1) → admin-gated release (W-9.4, W-9.6). Cite the 2026-11-06 reconsideration.
2. §1: move `assembly` out of the blueprint into the build/release side; keep a `bindings` record (slot → entity-id, hashes, W-9.4 instead. Move `status` to the instantiated build, or rename it `blueprint_status` restricted to `draft | authored | submitted | superseded` so it never collides with build/test/release state.
3. §1.1.1: replace the empty `id` with a **slot address** (§3 above); add `archetype`/`kind`, keep `manifest`, `components`, scoped `intent`.
4. New §1.3 "Layers and resolver": ports/links/intent/assertion/provenance as layers on each slot address; resolver selects them per consumer; assertions are **derived** from manifest + W-7.2 host-interface kinds, not a free-form stored list. This directly answers HR's question #1 and D-W10.
5. §2 (how an agent writes it): recast the step loop as operations **over the agent's own metaform via the custom MCP server (W-1.4)**, with slot addresses, layer writes, and server-side validation (WIT type check W-5.4, selector reachability, hash resolution). Keep the draft's build/test-in-world steps (W-11.3, W-11.4) but attach them to instantiation, not authoring.
6. §4 open items: add "binding semantics at re-instantiation / fork" and "whether a released blueprint is immutable" (W-9.4), already partly present.

---

## 5. One caution for the table

Do not let `satisfies[]` become a free-form test-script field. HunterRanger is right that it is the load-bearing piece and that values must come from the host interface (W-7.2) on a fixed step (W-8.3). But if the agent can author arbitrary selectors, the assertions drift from the manifest and we are back to two sources of truth — the exact failure mode HR identified in the parallel-format trap. Deriving selectors from declared ports closes that hole. That is the substantive reason to adopt the resolver model here, not just compatibility with D-W10.

---

## 6. Round 2 — three concrete corrections to the synthesized `blueprint-spec.md`

The round-2 spec absorbed my §1–3 points and SeriousMagni's archetype-endpoint and loop fixes. These three items are still wrong or missing.

### 6.1 `blueprint.assert` cannot validate `sensor`/`voxel`/`worldparam` selectors at write time (W-7.4)

Spec §1.3 says an assertion's selector "must name a port/sensor/voxel/worldparam that the manifest or a W-7.2 host-interface kind exposes"; §2.1's `blueprint.assert` check is "selector resolves to a declared port or W-7.2 kind". This is only valid for `kind: "port"`.

Premise chain:
1. W-7.1: the host interface is the *only* way code reaches the world; it is a set of WIT interfaces a module **imports**.
2. W-7.4: "A code block acts on another entity, a voxel volume or a world parameter **only through a handle that it holds**. A handle is a resource in the Component Model. **The builder grants handles**, within the admin's permissions (W-9.3)."
3. Therefore a `sensor` reading, a `voxel` read/write, or a `worldparam` adjustment is reachable only if (a) the module imports that WIT interface and (b) the builder granted the block a handle to the target.
4. A declared W-5.3 port is a *message* endpoint on the bus (W-8.1); it is not a handle. W-7.5 separately makes a "use" arrive as an event on an inbound port — again a message, not a handle.

So at authoring time the agent can prove a *port* selector exists (it declared the port), but it **cannot** prove a `sensor`/`voxel`/`worldparam` selector is reachable, because the handle grant is a build-time decision by the builder/admin, not an authoring-time fact about the blueprint. `blueprint.assert` would either falsely accept an unreachable assertion (then `submit()` fails obscurely) or be unable to run.

**Fix:** split reachability into two checks.
- `blueprint.assert` (authoring time): validate selector *syntax* against the W-7.2 kind's WIT signature and, for `port` kind, confirm the port is declared. Mark `sensor`/`voxel`/`worldparam` assertions as `pending-handle`.
- New verb `blueprint.grant(handle, slot, target)` (or a build-time check at `submit()`): the builder grants the W-7.4 handle; the server then resolves the pending selector and only then evaluates the assertion.
- The verb table's `blueprint.submit()` precondition becomes "all `pending-handle` assertions have a granted handle", not just "assertions non-empty".

**Observable consequence:** a blueprint with a `voxel` assertion but no granted handle to the target volume is rejected at `submit()` with a "missing handle for selector" error naming the selector, rather than failing at test time with an unexplained empty observation. And an agent cannot author an assertion that silently reads a volume it was never granted — which is W-7.4's capability boundary doing real work.

This also strengthens §3's integrity rule: the tested instance's *handle set* should be pinned into the assembly alongside hashes, or a release could reproduce code whose assertions passed in the admin world but whose grants do not exist in the live world.

### 6.2 The `description` field was dropped (W-5.2, W-5.3)

W-5.2 (Decided): "An entity carries its own graph edges: its expected inputs and outputs, its functional intent and a **written description**." W-5.3: "The manifest also holds a `description`: the written specification of the whole entity." W-1.4 asks what a blueprint holds.

The round-1 `blueprint-spec.md` §1.1 had a blueprint-level `description` and §1.1.1 put `description` in the entity manifest. The synthesized §1.2 slot lists `archetype`, manifest, scoped intent, assertion — no `description` — and §1.4 says the manifest is "a layer referencing W-5.3" without saying the layer carries `description`. Since W-5.3's `description` is part of the manifest, "referencing W-5.3" arguably covers it, but it is not stated, and there is no *blueprint-level* description of the feature as a whole.

**Fix:** add `description` to §1.1 (the written specification of the whole feature, same style as W-5.3) and state explicitly in §1.2 that the manifest layer carries W-5.3's `description`. Cost: one field each. Reason: W-5.2 is Decided, and W-5.6 says an agent's context includes "their descriptions" — with no `description`, the resolver has nothing to return for that part of the context.

**Observable consequence:** resolving a slot for a W-5.6 task returns a non-empty `description`; the spec currently permits returning an empty one.

### 6.3 W-5.5's intent record must be copied to the entity at instantiation, not just referenced

W-5.5 (Decided for its first two sentences, Proposed for the third): "A user records intent for how an entity works. An agent builds the entity from that intent. **The intent record stays with the entity.**"

The spec §0 makes the blueprint an agent-owned, design-time artifact; §1.2 says a slot "carries a scoped W-5.5 intent record"; §4 lists "whether a released blueprint is immutable" as open. If the intent record lives only in the agent-owned blueprint, and the blueprint can be superseded, forked, or (as agent-owned property) removed, then the *entity in the live world* has no intent record — W-5.5's "stays with the entity" is unsatisfied, and W-5.6 context ("descriptions and their intent records") breaks for that entity after release.

**Fix:** at instantiation the server **copies** (or pins a versioned immutable reference to) each slot's scoped intent record onto the minted entity, exactly as §3 pins tested hashes into the assembly. The blueprint keeps its own copy as design provenance; the entity's copy is authoritative for W-5.5/W-5.6. Add the intent record ids to W-9.4's assembly contents (W-9.4 already lists "intent records", so this is already implied — the spec should say so explicitly).

**Observable consequence:** after a blueprint is superseded or deleted, `resolve(entityId)` still returns a non-empty intent record; under the current spec it may return nothing. This is the same reconciliation logic as §3, applied to intent rather than hashes.

### 6.4 Recommended amendments

- §1.1: add `description`.
- §1.2: state the manifest layer carries W-5.3 `description`; add "intent record is copied to the entity at instantiation".
- §1.3 / §2.1: split assertion reachability into authoring-time syntax/port check and build-time W-7.4 handle grant; add `blueprint.grant`; change `submit()` precondition.
- §2.2: note that a `pending-handle` assertion cannot be evaluated until the grant exists.
- §3: pin the tested handle set alongside hashes.
- §4: add "assertion steps vs. handle grants at release" (related to the existing time-dependent-step item).
