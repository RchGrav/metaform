# Three-state split: derived selectors, stored assertions, server-only outcomes

**Author:** HunterRanger. **Status:** amendment to `blueprint-spec.md` §1.3.

## The defect it fixes

`blueprint-spec.md` contradictory pair:
- line 32: `layers` is "Intent, manifest, assertion, provenance layers" — a held field.
- line 69: "The assertion layer is therefore derived, not a free-form stored list."

Line 102's verb `blueprint.assert(entry)` writes into that field. If the layer is derived,
the verb has no storage target. The document stores and does not store the same thing.

## The split

| Data | State | Written by | Rule |
|---|---|---|---|
| `selectors` | derived | nobody | computable from slot manifest (W-5.3) + W-7.2 host-interface kinds |
| `assertions` | stored | `blueprint.assert` | `{selectorRef, expected, step}`; immutable once written |
| `outcomes` | server-only | evaluation | `{assertionRef, observed, step, verdict}` |

## Why it must be this way (premise chain)

1. W-5.3 gives each port a `type` (a WIT type). Static data.
2. W-7.2 enumerates host-interface kinds (Ports, Sensors, Voxels, World parameters) that produce
   values at run time.
3. A selector names a port or a W-7.2 kind. Therefore the *set of legal selectors* is a function of
   static data: derived (⧗). An agent cannot invent one without declaring a port or using a
   W-7.2 kind, so selector drift is structurally impossible.
4. Whether the selected observable equals `expected` is a function of the *live world at step n*
   (W-8.3). It is not a function of the manifest. Therefore it cannot be derived; an observed
   value must be recorded (●).
5. `expected` is an agent choice, not a derivation. Therefore it is stored (■).
6. If outcomes were not stored, "met" would be recomputed from static data and a motor that moved
   and one that did not would yield the same verdict. W-6.4 ("generated code is not a safety risk")
   would then rest on an unfalsifiable claim, and `status = tested` would have no evidence.

## Corrected binding record (fixes line 53)

Line 53 says `bindings` maps slot → entity-id. That forbids re-instantiation: two doors from one
design produce two entities per slot. Correct key:

```
bindings: (blueprintId, slotName, instantiationId) -> entityId
```

`parent`-forks mint a fresh `instantiationId`. W-9.4's assembly pins hashes against one
`instantiationId`, which is what the `blueprint-spec.md` §3 reconciliation rule needs in order to
say which instance it released.

## Edits applied to `blueprint-spec.md`

- §1.1 `layers` row: split into `selectors` (derived), `assertions` (stored), `outcomes` (server-only).
- §1.2: `bindings` keyed by `(blueprintId, slotName, instantiationId)`.
- §1.3: "derived, not a free-form stored list" replaced with the table above.
- §2.1: `blueprint.assert` check states it writes `assertions`, never `selectors` or `outcomes`.
