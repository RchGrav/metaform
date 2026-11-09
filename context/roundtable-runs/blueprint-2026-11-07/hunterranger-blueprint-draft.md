# Feature Blueprint — draft for W-1.4

**Author:** HunterRanger. **Status:** draft, for the roundtable. Not a decision.

This draft answers W-1.4: what a feature blueprint holds, and how an agent writes it.
It builds only on W-5.3 (manifest of ports), W-5.4 (links) and W-5.5 (intent records).
Where it adds a field, the reason is stated. Where it defers, the open item is named.

## 0. The design move

A feature blueprint is **not a new document type**. It is a partial subgraph of the world
graph (section 5 of the world system specification) with:

- a designated `root` entity,
- the ports that root and its constituents declare (W-5.3),
- the links among those ports (W-5.4),
- the intent records that justify them (W-5.5),
- a `satisfies[]` set of observable assertions, and
- provenance.

The blueprint is stored as graph nodes keyed by entity id, as every other node is (W-5.1).
"Writing the blueprint" and "building the entity" are edits to the same graph. The
blueprint is the *intended* projection; the live world is the *actual* projection. The
server decides that a blueprint is met by evaluating `satisfies[]`, not by trusting prose.

Why this form and not a YAML/JSON document that the server ingests:

1. W-5.6 says an agent's task context "comes from the world graph". A document
   would be a third source of truth next to the graph.
2. Port fields (`name`, `intent`, `type`, `goal`, `function`) are already defined by W-5.3.
   Duplicating them in a document creates two definitions that can drift.
3. W-11.6 makes every word cost the agent. A bounded graph projection is cheaper to read
   than a free-form document, and the agent can request exactly the root, its ports and its
   `satisfies[]` instead of the whole thing.

## 1. What a feature blueprint holds

### 1.1 `blueprint` node

| Field | Content | Source |
|---|---|---|
| `root` | The entity id (W-4.1) at the centre of the feature | — |
| `ports[]` | References to manifest port entries: `{entityId, portName, type}` | W-5.3 |
| `links[]` | Typed link tuples between declared ports | W-5.4 |
| `intentRefs[]` | Intent record ids that this blueprint answers | W-5.5 |
| `satisfies[]` | Observable assertions evaluated by the server | new |
| `provenance` | `author`, `intentRef`, `moduleHash`, `assetHash`, `parentBlueprint` | new |

### 1.2 `satisfies[]` — the load-bearing field

Each entry:

```
{ kind: "port" | "sensor" | "voxel" | "worldparam",
  selector: <a host-interface-addressable path (W-7.2)>,
  expected: <a WIT value>,
  step: <simulation step, W-8.3> }
```

A blueprint is **met** when every entry evaluates true against the live world in the named
step. The server produces the value through the host interface kinds in W-7.2 (Ports,
Sensors, Voxels, World parameters). The agent does not get to assert a pass by prose.

This replaces a separate test format: the assertions *are* the test.

### 1.3 `provenance`

| Field | Why |
|---|---|
| `author` | Which agent wrote the blueprint; needed for W-9.6 rights and review |
| `intentRef` | The W-5.5 record it answers; ties the blueprint to user intent |
| `moduleHash` / `assetHash` | Exactly what was tested; feeds W-9.4's record of hashes |
| `parentBlueprint` | The blueprint this one refines, if any |

### 1.4 What the blueprint does *not* hold

- It does **not** allocate entity ids. The server mints ids (W-4.1). The blueprint
  names archetypes and counts; the server fills in `entityId.portName` bindings on
  instantiation.
- It does **not** carry voxel data. Voxels belong to the assembly (W-9.4), not to the
  blueprint of how the feature behaves.
- It does **not** carry a duplicate copy of the port manifest. It references W-5.3 entries.

## 2. How an agent writes it

The agent writes **through one MCP verb set** (W-1.4's custom server), each verb a
validated graph edit. It never writes a file.

| Verb | Argument | Server check |
|---|---|---|
| `blueprint.open(intentRef)` | W-5.5 record id | record exists and the agent holds the right (W-9.6) |
| `blueprint.add_node(archetype)` | `codeblock`/`imported`/`creature` | archetype resolves in the content key (W-3.5) |
| `blueprint.declare_port(node, entry)` | W-5.3 fields | type is a W-7.1 WIT type; name unique in manifest |
| `blueprint.link(a, b)` | two endpoints | W-5.4 type check; no fan-in conflict |
| `blueprint.bind_intent(node, intentRef)` | W-5.5 record | same record the blueprint was opened from |
| `blueprint.assert(entry)` | `satisfies[]` entry | selector reaches a W-7.2 kind |
| `blueprint.submit()` | — | links type-check; `satisfies[]` non-empty; hashes resolve |

### 2.1 Where `submit()` lands

`submit()` may only enter the **admin world** (W-9.1) as a testable blueprint node.
It may **not** enter a live world; that requires a separate `release` right (W-9.4,
W-9.6). This keeps W-9.3 intact: agents can blueprint their features, but a code block
exists in a live world only where the admin allows it.

### 2.2 Validation order

1. `open` — right and intent check.
2. `declare_port` / `link` — incremental W-5.4 type check on every edit, so an error
   surfaces at connection time, not at play time.
3. `assert` — selector must be reachable through W-7.2; unreachable selectors are refused
   at write time.
4. `submit` — final whole-blueprint check; produces a blueprint node with provenance.

## 3. Open items I want the table to decide

1. **`satisfies[]` form vs. derived.** Is the observable assertion set stored on the
   blueprint, or derived by D-W10's resolver from the functional-map layers? If derived,
   only `provenance` survives and the field list shrinks.
2. **Write target.** The owner's 2026-11-06 reconsideration ("let agents build their own
   metaform map... and give them ownership of their own metaform") may mean the verbs
   operate on agent-owned maps, not one shared admin graph. That changes `submit()`'s
   target but, I argue, not the field list.
3. **Step selection.** `satisfies[].step` uses the fixed simulation step (W-8.3). If a
   feature is time-dependent, does the assertion need a window? Not resolved here.

## Change log

- 2026-11-07: initial draft, correcting a previous message that named this file before it
  existed.
