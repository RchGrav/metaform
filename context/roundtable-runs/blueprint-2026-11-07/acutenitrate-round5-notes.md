# AcuteNitrate — Round 5: two remaining items in `blueprint-spec.md`

Everything I raised in Rounds 1–3 is now absorbed into the spec, so I am not restating it. Two items remain: one concrete flaw in "what a blueprint holds", and one open decision the table has asked to settle three times (R1-5, R1-8, R1-9).

## 1. Flaw: the slot-level `limits` field lets content grant itself its own safety budget

B-2.2 lists, per slot, "`limits` (W-6.3 budgets, W-7.3 physics needs)". No verb writes it (B-3.1), no `submit()` check reads it (B-3.1), and no clause says who sets its values. Read the requirements it cites:

- W-6.3: "Each invocation has a fuel budget, a memory limit and a limit on messages sent. A module that exceeds a limit fails that invocation only, and the world server disables its binding and records the fault." Its **Reason**: "the owner requires that content not harm the core (W-2.5)". Its limit **values are Open (D-W6)**, with the recommendation "Measure first; set values from the Minecraft-like content of W-12.1".
- W-2.5 (Decided): "Content never requires an adjustment to the core." The core supplies the systems; content is built on it.
- W-7.3: physics precision (continuous collision detection, substep count) "can be set for each entity" — this part is legitimately per-entity.

Causal chain: W-6.3's limits exist *to stop content harming the core*. If a blueprint — which is agent-authored content — carries `limits` as a writable field with no cap, then content chooses its own fuel, memory and message budget. A generated module that declares a huge fuel budget has effectively disabled W-6.3 for itself. That inverts W-6.3's Reason and contradicts W-2.5. W-6.4's "generated code is not a safety risk" is argued (in its own Reason) precisely by "runs only as a WASM module, under the limits of W-6.3" — so a self-set limit removes the premise of the safety claim the spec's B-4.1/B-3.5 work so hard to make inspectable.

Note D-W6 says limits are *measured* and set from W-12.1 content, not authored per blueprint. W-7.3's per-entity precision is different: it is a physics setting, not a resource budget, so it can stay per-slot.

**Fix (recommended action):** split the field.
- Rename the W-6.3 part to `limit_request` — a declaration of *need* (minimum fuel/memory/messages the module requires), which the server **clamps to the world's W-6.3 limits** at `submit()`. The effective (clamped) values are recorded in the MS-1 build receipt alongside hashes and the handle set. The agent cannot raise the cap; only the admin can change it, under W-9.6, and D-W6 remains the place that decides the values.
- Keep W-7.3 physics precision as a genuine per-slot setting (`precision`), since W-7.3 explicitly permits per-entity setting.
- Add a `submit()` rejection: `limit_request` exceeding the world cap → error `{field:"limit_request", reason:"exceeds W-6.3 world cap", offending value}` (B-3.4 error shape).

**Observable consequence:** a blueprint declaring `fuel: 18446744073709551615` is accepted as a *request* but instantiated with the world's capped fuel; the receipt shows the cap, not the request. Under the current B-2.2 an implementation has no rule and may either honour the request (safety hole) or ignore the field silently (dead field). Either outcome is checkable, which is what makes this a spec defect rather than a preference.

**What would show this mistaken:** if W-6.3's limits were intended to be per-module and author-set — but its Reason ("content not harm the core") and D-W6 ("Measure first; set values from ... W-12.1") both point to world-level, measured values. Or if `limits` were meant to be W-7.3 precision only; B-2.2 explicitly says "W-6.3 budgets", so it includes the resource limits.

## 2. Settle D-B4 / D-W10: a shared resolver is prohibited by W-1.1, so "blueprint-only" is forced

HunterRanger (R1-5, R1-9) and LogicalImpala (R1-8) each say they have no argument that settles whether the resolver applies blueprint-only or to the whole world graph. D-B4 currently recommends "Blueprint-only for now" with no reason, and the spec's B-3.2 is titled "concrete W-5.6/D-W10 answer" while only describing the blueprint's context slice — so D-W10 is in fact still open.

Premises, from `world-system-spec.md`:
- W-1.1 (Decided, with owner source): "The functional map is an engineering tool for building the system. It has no role inside a world. **The world system never reads or writes the functional map**, and players never extend it."
- W-5.1 (Decided): the world graph uses "its own graph technique, **modeled on** the metaform technique" — a separate instance, not the same graph.
- W-5.3's Reason: `goal`/`function`/`intent` "keep the meaning of the functional map's want fields (R-3.6), **so an agent reads both graphs the same way**" — a shared *field vocabulary* for a reader, not a shared resolver.
- D-W10's recommendation: "The functional map composes layers on each address and selects them with a resolver (`TOPOGEE.md` section 2); **that is one model to compare against**."

Causal step: a resolver that spans both graphs must compose layers across both, which requires the world system to read the functional map's layers. W-1.1 forbids exactly that read. Therefore a single shared resolver **cannot be built**; only the *technique* is shared — each graph implements layer composition independently, with the same layer field shapes, so one agent reader parses both. That is consistent with W-5.1's "modeled on" and with W-5.3's Reason, and it does not violate W-1.1. It also corrects D-W10's recommendation: the functional-map resolver is a **design-time model to copy, not a runtime service to call**.

**Recommended spec change:** rewrite D-B4 as "**Blueprint resolver is a separate instance. The world system never calls the functional map's resolver (W-1.1). Both graphs use W-5.3's layer field shapes so a single agent reader serves both.**" Add to D-W10's recommendation a note that comparing against `TOPOGEE.md` section 2 is a specification-time comparison only. Remove "for now" — the constraint is Decided, not provisional.

**Observable consequence:** no released world-server build contains a code path that resolves a functional-map address; an agent's reader parses `goal`/`function`/`intent` from both graphs with one parser. If a future participant proposes a unified resolver, W-1.1 is the cited blocker, so the decision is inspectable rather than a preference. This is the difference between "leave Open" and "settled on grounds the table can check".

**What would show this mistaken:** if W-1.1 were Proposed rather than Decided (it is Decided), or if "the world system never reads" were scoped to players only (the text names the world system itself). Neither holds, so the shared-resolver option is closed.

## 3. Note on the broader state

The spec is now complete on W-1.4's two questions (B-2 "what it holds", B-3 "how an agent writes it"), and the MS-1..6 additions cover receipts, dependency fingerprints, external roles and retryability. The two items above are the last substantive ones I can find. I have deliberately not edited `blueprint-spec.md` this turn, to avoid colliding with the concurrent edits by HunterRanger, LogicalImpala and ModularShift; both changes above are narrow enough to paste into B-2.2, B-3.1/B-3.4 and §6.
