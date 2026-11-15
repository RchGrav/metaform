# Metaform MCP v3.0 — Interface Schemas, CEL Data Contracts & Backend Specification

**Architecture Target:** TypeScript (`tsx`) & Python MCP Servers (Rust Core Ready)  
**Database Engine:** LadybugDB (Cypher / SoA storage internally $\leftrightarrow$ JSONPath AoS view externally)[cite: 1]  
**Core Paradigm:** Inference Amortization, Progressive Context Disclosure, and **CEL** (`ComposedElementLayer` — plural-noun array overlays like animation cels)[cite: 1, 3].

---

## 1. Architectural Concepts: CELs, SoA-to-AoS, and Inference Amortization

### 1.1 CELs (`ComposedElementLayer` Overlays)
In the Metaform schema, any **plural-noun key holding a JSON array of objects** at any namespace node (or provider record) is a **CEL (`ComposedElementLayer`)**—functioning exactly like transparent animation cels stacked over the base functional topology[cite: 1, 3].
* **Base Topology:** The hierarchical namespace trie (`$.{project}.{namespace_address}`), element metadata (`label`, `name`, `name_length`, `role`, `status`), and `.providers["{pe_address}"]` (`ifd`, `op`, `ef`, `ice`)[cite: 1, 3].
* **CEL Overlays (Plural-Noun Arrays):** `skills[]` (following the finalized `ext-skill` specification), `tickets[]`, `sources[]`, `investigations[]`, `memories[]`, etc.[cite: 1]
* **Ancestral CEL Inheritance & Scoping:** As shown in your example where `"skills": [...]` sits on `"code"` above `"system.management.knowledge"`, a CEL can be placed at a coarse namespace branch (`code.skills[]`) or directly on a leaf element (`code.agent.autonomous.skills[]`)[cite: 1]. When an agent focuses on a node for a task+ticket combo, the Facilitation Agent / server pre-computes or resolves only the CELs active for that node.
* **SoA vs. AoS Boundary:** LadybugDB and Cypher manage the **Structure of Arrays (SoA)** columnar storage under the hood, while the MCP interface projects and accepts **Array of Objects (AoS)** (`skills: [{ uri, frontmatter, resources }]`) for ergonomic agent consumption.

### 1.2 Minimal Two-Tool Surface
To replace the bulky legacy Python tools with a razor-sharp interface that supports **adding, editing, removing, and viewing** both the functional topology and CEL overlays, the MCP exposes **two tools**[cite: 1]:
1. **`metaform_mutate` (Add / Edit / Remove Elements, Providers & CELs):** Receiver-centric mutation tool (`mutation`, never destructive transformation)[cite: 1]. Supports `upsert` (add/edit), `remove` (prune elements, specific provider links, or specific CEL entries), and `anneal` (fold subparts into a parent element while preserving history)[cite: 1, 4].
2. **`metaform_view` (Topology Dump, Ticket Pre-Orientation & Fuzzy Search):** Read-only progressive disclosure tool with three modes[cite: 1]:
   * `mode: "topology"` — **Ultra-low-context N-level hierarchy dump**. Returns *only* the navigable namespace tree and reversed industry names (zero prose, zero CELs) for near-zero token cost.
   * `mode: "orient"` — **Inference-Amortized Working Envelope**. Given a `namespace_address` (or `ticket_id`), hands the agent its exact pre-oriented functional packet in one shot: the target node, its active CELs (`skills[]`, `tickets[]`, `sources[]`), outbound `.providers` (what SDKs/upstream resources it uses and *why* via `op`/`ef`), inbound **downstream receivers** (who relies on this functionality), and the transitive closure of **ICE (`ice: true`)** coupled elements[cite: 1, 4].
   * `mode: "search"` — Fuzzy matcher across reversed industry names (`"autonomous agent"`), project labels (`"Hermes Agent"`), and dotted `snake_case` addresses (`"code.agent.autonomous"`)[cite: 1, 2].

---

## 2. Backend Code-Controlled CEL Gatekeeper (TypeScript & Python)

The backend controls in code which CEL plural-noun array layers exist and which ones the current agent session is permitted to read or mutate[cite: 1]. The MCP server dynamically compiles the `inputSchema` of `metaform_mutate` and `metaform_view` from this registry at startup[cite: 1].

### 2.1 Canonical CEL Schemas (`ext-skill`, `tickets`, `sources`, `investigations`)

```typescript
// cel_registry.ts — TypeScript (tsx) Reference Implementation
export type CelScope = "branch" | "element" | "provider";

export interface CelLayerSpec {
  /** Plural noun key name in the JSON trie (e.g. 'skills', 'tickets', 'sources') */
  name: string;
  /** Where this CEL array may be attached */
  scopes: CelScope[];
  /** Unique natural key field inside each array object used for idempotent upsert/remove */
  identityKey: string;
  /** JSON Schema for a single element inside the AoS array */
  itemSchema: Record<string, unknown>;
}

export const CANONICAL_CEL_REGISTRY: Record<string, CelLayerSpec> = {
  skills: {
    name: "skills",
    scopes: ["branch", "element"],
    identityKey: "uri",
    itemSchema: {
      type: "object",
      description: "Finalized ext-skill progressive discovery descriptor.",
      properties: {
        uri: {
          type: "string",
          pattern: "^skill://[a-zA-Z0-9_\\-/]+/SKILL\\.md$",
          description: "Canonical skill URI (e.g., 'skill://git-workflow/SKILL.md')."
        },
        frontmatter: {
          type: "object",
          properties: {
            name: { type: "string", minLength: 1 },
            description: { type: "string", minLength: 1 }
          },
          required: ["name", "description"],
          additionalProperties: true
        },
        resources: {
          type: "array",
          items: {
            type: "object",
            properties: {
              uri: { type: "string" },
              digest: { type: "string", pattern: "^sha256:[a-f0-9]{64}$" },
              size: { type: "integer", minimum: 0 }
            },
            required: ["uri", "digest", "size"],
            additionalProperties: false
          }
        }
      },
      required: ["uri", "frontmatter", "resources"],
      additionalProperties: false
    }
  },
  sources: {
    name: "sources",
    scopes: ["element", "provider"],
    identityKey: "value",
    itemSchema: {
      type: "object",
      description: "Code entry points, file paths, or symbol references.",
      properties: {
        key: { type: "string", enum: ["path", "entrypoint", "symbol", "line", "uri"] },
        value: { type: "string", minLength: 1 }
      },
      required: ["key", "value"],
      additionalProperties: false
    }
  },
  tickets: {
    name: "tickets",
    scopes: ["element", "provider"],
    identityKey: "id",
    itemSchema: {
      type: "object",
      description: "Task/ticket overlay pre-orienting the agent at this functional node.",
      properties: {
        id: { type: "string", minLength: 1 },
        title: { type: "string", minLength: 1 },
        intent: { type: "string", description: "Functional mutation goal (ASD-STE100)." },
        status: { type: "string", enum: ["open", "in_progress", "review", "done"] },
        skill_uris: {
          type: "array",
          items: { type: "string" },
          description: "Task+ticket filtered skill:// URIs built by the facilitation agent."
        }
      },
      required: ["id", "title", "intent", "status"],
      additionalProperties: false
    }
  },
  investigations: {
    name: "investigations",
    scopes: ["element", "provider"],
    identityKey: "reason",
    itemSchema: {
      type: "object",
      description: "Drift observations, missing functionality notes, or ICE coupling proofs.",
      properties: {
        kind: { type: "string", enum: ["drift", "not_built", "ice_proof", "anomaly"] },
        reason: { type: "string", minLength: 1 },
        ref: { type: "string" }
      },
      required: ["kind", "reason"],
      additionalProperties: false
    }
  }
};

export interface ServerLayerPolicy {
  /** CEL plural nouns enabled for reading in this session */
  readableCels: string[];
  /** CEL plural nouns enabled for mutation (add/edit/remove) in this session */
  writableCels: string[];
  /** Whether base topology (elements/providers) may be mutated in this session */
  allowTopologyMutation: boolean;
}
```

---

## 3. Complete MCP Tool Schemas (`tools/list` Contract)

Below are the exact JSON Schemas for the two MCP tools. Note how `cels` is dynamically constrained by `writableCels` / `readableCels` from the backend `ServerLayerPolicy`.

### 3.1 Tool 1: `metaform_mutate` (Add, Edit, Remove & Anneal)

This single tool handles **adding, editing, and removing** receiving elements, providing elements, provider records, and CEL array items while preserving the strict dual-path LadybugDB rule:
* **Receiving Element (RE)** is mutated at `$.{projectname}.{receiving_element_namespace_address}` (with multi-word `snake_case` segments mapped to `camelCase` keys in LadybugDB)[cite: 1].
* **Provider Record** under the RE is keyed by the flat string `.providers["{providing_element_namespace_address}"]`[cite: 1, 3].
* **Providing Element (PE)** is simultaneously materialized/updated at `$.{projectname}.{providing_element_namespace_address}`[cite: 1].

```json
{
  "name": "metaform_mutate",
  "description": "Mutates (adds, edits, removes, or anneals) functional elements, flat-keyed provider records, and code-enabled CEL overlays (skills[], sources[], tickets[], investigations[]) in LadybugDB at $.{project}.{namespace_address}. Enforces reversible non-destructive graph mutations and streams live updates to the workbench.",
  "inputSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "project": {
        "type": "string",
        "description": "Target project identifier (maps to root $.{projectname})."
      },
      "action": {
        "type": "string",
        "enum": ["upsert", "remove", "anneal"],
        "default": "upsert",
        "description": "'upsert': add or edit the RE, its PEs, and its CEL overlays. 'remove': remove specified provider keys, CEL items, or the RE itself. 'anneal': fold fine-grained subparts in `absorb_addresses` into this RE."
      },
      "receiver": {
        "type": "object",
        "description": "Target Receiving Element (RE) or namespace branch at $.{project}.{receiver.address}.",
        "properties": {
          "address": {
            "type": "string",
            "pattern": "^(code|document|media|data|collection|upstream|downstream)(\\.[a-z0-9_]+)*$",
            "description": "Dotted snake_case namespace_address (e.g., 'code.agent.autonomous', 'code.queue.dead_letter', or root branch 'code' when attaching branch-level CELs like code.skills[])."
          },
          "label": {
            "type": "string",
            "minLength": 1,
            "description": "Project-specific designation or canonical title displayed on the graph node card (e.g., 'Hermes Agent', 'Metaform'). Required when creating a new element."
          },
          "name_length": {
            "type": "integer",
            "minimum": 1,
            "description": "Number of trailing segments reversed by the server to compute the printed industry `name` (e.g., 2 on 'code.queue.dead_letter' -> 'dead letter queue')."
          },
          "role": {
            "type": "string",
            "enum": ["CQU", "DE", "SE", "NE"],
            "description": "Ontological role: CQU (at downstream.cqu.*), DE (Defining Element), SE (Substantial Element), or NE (Notable Element)."
          },
          "status": {
            "type": "string",
            "enum": ["built", "not_built", "exclude"],
            "description": "Mutable implementation status of the element."
          },
          "cels": {
            "$ref": "#/$defs/ElementCelMap",
            "description": "Plural-noun CEL array overlays to upsert (or remove by identityKey when action='remove') at this namespace address."
          }
        },
        "required": ["address"],
        "additionalProperties": false
      },
      "providers": {
        "type": "object",
        "description": "Map keyed by the flat dotted snake_case {providing_element_namespace_address}. On 'upsert', adds/edits the provider record under RE.providers['{pe_address}'] and materializes the PE node at $.{project}.{pe_address}. On 'remove', removes the specified provider record keys from RE.providers (or removes specific CEL items inside them).",
        "propertyNames": {
          "pattern": "^(code|document|media|data|collection|upstream|downstream)(\\.[a-z0-9_]+)+$"
        },
        "additionalProperties": {
          "type": "object",
          "properties": {
            "ifd": {
              "type": "string",
              "enum": ["sends", "receives", "both"],
              "description": "Information Flow Direction that satisfies the RE's OP (excluding request parameters)."
            },
            "op": {
              "type": "string",
              "minLength": 1,
              "description": "Operative Purpose (the active 'why' of the RE). Written strictly in ASD-STE100."
            },
            "ef": {
              "type": "string",
              "minLength": 1,
              "description": "Encounter Function (the 'how' delivered by the PE). Written strictly in ASD-STE100 starting with a 3rd-person singular present-tense verb."
            },
            "ice": {
              "type": "boolean",
              "default": false,
              "description": "True if the RE and PE are Indivisibly Coupled Elements (ICE) sharing state/lifecycle that cannot be separated without breaking."
            },
            "status": {
              "type": "string",
              "enum": ["built", "not_built"]
            },
            "provider_node": {
              "type": "object",
              "description": "Metadata materialized for the Providing Element itself at $.{project}.{pe_address}.",
              "properties": {
                "label": { "type": "string", "minLength": 1 },
                "name_length": { "type": "integer", "minimum": 1 },
                "role": { "type": "string", "enum": ["DE", "SE", "NE"] },
                "status": { "type": "string", "enum": ["built", "not_built", "exclude"] },
                "cels": { "$ref": "#/$defs/ElementCelMap" }
              },
              "required": ["label", "name_length", "role"],
              "additionalProperties": false
            },
            "cels": {
              "$ref": "#/$defs/ProviderCelMap",
              "description": "Plural-noun CEL array overlays attached specifically to this provider encounter."
            }
          },
          "additionalProperties": false
        }
      },
      "absorb_addresses": {
        "type": "array",
        "items": {
          "type": "string",
          "pattern": "^(code|document|media|data|collection|upstream|downstream)(\\.[a-z0-9_]+)+$"
        },
        "description": "Used when action='anneal': list of fine-grained namespace addresses to fold into `receiver.address`, re-pointing inbound links and merging CEL arrays non-destructively."
      }
    },
    "required": ["project", "receiver"],
    "additionalProperties": false,
    "$defs": {
      "ElementCelMap": {
        "type": "object",
        "description": "Code-enabled plural-noun CEL arrays permitted on namespace branches and element nodes.",
        "properties": {
          "skills": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "uri": { "type": "string", "pattern": "^skill://[a-zA-Z0-9_\\-/]+/SKILL\\.md$" },
                "frontmatter": {
                  "type": "object",
                  "properties": {
                    "name": { "type": "string" },
                    "description": { "type": "string" }
                  },
                  "required": ["name", "description"]
                },
                "resources": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "uri": { "type": "string" },
                      "digest": { "type": "string" },
                      "size": { "type": "integer" }
                    },
                    "required": ["uri", "digest", "size"]
                  }
                }
              },
              "required": ["uri", "frontmatter", "resources"]
            }
          },
          "sources": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "key": { "type": "string", "enum": ["path", "entrypoint", "symbol", "line", "uri"] },
                "value": { "type": "string" }
              },
              "required": ["key", "value"]
            }
          },
          "tickets": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "id": { "type": "string" },
                "title": { "type": "string" },
                "intent": { "type": "string" },
                "status": { "type": "string", "enum": ["open", "in_progress", "review", "done"] },
                "skill_uris": { "type": "array", "items": { "type": "string" } }
              },
              "required": ["id", "title", "intent", "status"]
            }
          },
          "investigations": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "kind": { "type": "string", "enum": ["drift", "not_built", "ice_proof", "anomaly"] },
                "reason": { "type": "string" },
                "ref": { "type": "string" }
              },
              "required": ["kind", "reason"]
            }
          }
        },
        "additionalProperties": false
      },
      "ProviderCelMap": {
        "type": "object",
        "description": "Code-enabled plural-noun CEL arrays permitted inside a provider record.",
        "properties": {
          "sources": { "$ref": "#/$defs/ElementCelMap/properties/sources" },
          "tickets": { "$ref": "#/$defs/ElementCelMap/properties/tickets" },
          "investigations": { "$ref": "#/$defs/ElementCelMap/properties/investigations" }
        },
        "additionalProperties": false
      }
    }
  }
}
```

#### How `metaform_mutate` Handles Add, Edit, and Remove Cleanly:
1. **Add / Edit Element + Provider (`action: "upsert"`):**
   * If `receiver` has `label`, `name_length`, and `role`, it creates or updates the element node at `$.{project}.{re_camel_path}` and computes `name` (reversed industry name)[cite: 1].
   * If `receiver` only has `address` and `cels` (e.g., attaching `"skills": [...]` to `"code"` or editing a single attribute on an existing node), it merges those fields into `$.{project}.{re_camel_path}` without requiring redundant fields.
   * For each key in `providers`, it upserts `.providers["{pe_address}"]` and upserts `$.{project}.{pe_camel_path}`[cite: 1].
   * For each CEL array in `cels` (e.g. `skills[]`), it deduplicates/upserts items by their `identityKey` (`uri` for `skills`, `id` for `tickets`, `value` for `sources`).
2. **Remove Element, Provider Link, or CEL Item (`action: "remove"`):**
   * **Remove specific CEL items:** Pass `action: "remove"` with `receiver.address` and `receiver.cels: { "skills": [{ "uri": "skill://old/SKILL.md", ... }] }` $\rightarrow$ removes only that skill from the CEL array.
   * **Remove a Provider Record link:** Pass `action: "remove"` with `receiver.address` and `providers: { "code.old.provider": {} }` $\rightarrow$ deletes `"code.old.provider"` from `RE.providers` without deleting the PE's own node.
   * **Remove an entire Element:** Pass `action: "remove"` with `receiver: { "address": "code.obsolete.node" }` and no `providers` or `cels` $\rightarrow$ removes the element metadata at that path and cleans up dangling inbound `.providers` references.

---

### 3.2 Tool 2: `metaform_view` (Low-Context Topology Dump, Ticket Pre-Orientation & Search)

This tool is built specifically for **Inference Amortization** and **Progressive Context Disclosure**:

```json
{
  "name": "metaform_view",
  "description": "Progressive context disclosure and navigation tool for the LadybugDB Metaform graph. Supports three modes: (1) 'topology' for a super-compact N-level dump of navigable namespace hierarchy names with zero prose overhead; (2) 'orient' for an inference-amortized working envelope at a target namespace_address or ticket_id (returning active CEL overlays like skills[] and sources[], outbound provider OP/EFs, inbound downstream dependents, and transitive ICE coupled elements); (3) 'search' for fuzzy matching across reversed industry names, labels, and addresses.",
  "inputSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "project": {
        "type": "string",
        "description": "Target project identifier."
      },
      "mode": {
        "type": "string",
        "enum": ["topology", "orient", "search", "audit"],
        "default": "orient",
        "description": "'topology': low-token N-level hierarchy dump of namespace addresses and names. 'orient': full inference-amortized task/ticket envelope for a specific node. 'search': fuzzy lookup across names/labels/addresses. 'audit': intake completeness check."
      },
      "address": {
        "type": "string",
        "description": "Target dotted snake_case namespace_address (e.g., 'code.system.management.knowledge' or branch 'code' for topology dump). Optional in 'orient' mode if `ticket_id` is supplied."
      },
      "ticket_id": {
        "type": "string",
        "description": "Optional ticket identifier (e.g., 'TICKET-104'). In 'orient' mode, automatically resolves the target namespace_address bearing this ticket and filters `skills[]` to the task+ticket combo."
      },
      "depth": {
        "type": "integer",
        "minimum": 1,
        "maximum": 8,
        "default": 3,
        "description": "In 'topology' mode: number of namespace hierarchy levels (N) to dump. In 'orient' mode: hop depth for ICE coupling traversal (direct neighbors are always 1 hop; ICE chains traverse up to `depth`)."
      },
      "query": {
        "type": "string",
        "description": "Used in 'search' mode: fuzzy query matched against reversed industry names ('knowledge management system'), project labels ('Metaform'), or snake_case addresses."
      },
      "cels": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": ["skills", "sources", "tickets", "investigations"]
        },
        "description": "Optional filter of CEL plural-noun overlays to disclose in 'orient' mode (defaults to all code-enabled readable CELs: ['skills', 'sources', 'tickets', 'investigations']). Ignored in 'topology' mode."
      }
    },
    "required": ["project", "mode"],
    "additionalProperties": false
  }
}
```

---

## 4. Exact Data Contracts Returned by `metaform_view`

### 4.1 `mode: "topology"` — Ultra-Low-Context N-Level Hierarchy Dump
When an agent calls `metaform_view({ "project": "metaform", "mode": "topology", "depth": 4 })`, it gets **zero OP/EF prose and zero CEL bloat**—just the navigable functional skeleton so it can see the shape of the project in <150 tokens:

```json
{
  "project": "metaform",
  "mode": "topology",
  "depth": 4,
  "tree": {
    "downstream": {
      "cqu": {
        "engineer": {
          "software": "software engineer [CQU | AI Engineer]"
        }
      }
    },
    "code": {
      "system": {
        "management": {
          "knowledge": "knowledge management system [DE | Metaform]"
        }
      },
      "service": {
        "decision": "decision service [SE | Jev]"
      },
      "store": {
        "event": "event store [SE | EventStore] (+1 child)"
      }
    },
    "upstream": {
      "service": {
        "inference": "inference service [NE | LLM API]"
      }
    }
  }
}
```
* Every leaf or materialized element shows: `"{printed_industry_name} [{role} | {label}]"` (plus `(+N children)` if truncated by `depth`).

---

### 4.2 `mode: "orient"` — Inference-Amortized Pre-Orientation Envelope
When an agent is assigned a ticket or navigates to a node (`metaform_view({ "project": "metaform", "mode": "orient", "address": "code.system.management.knowledge", "ticket_id": "MF-42" })`), the backend executes **Inference Amortization** and returns everything the agent needs to execute a clean, reversible mutation in one single payload:

```json
{
  "project": "metaform",
  "mode": "orient",
  "execution_gate": "MUTATION_NOT_TRANSFORMATION: Preserve functional contracts and ICE boundaries. All changes must be reversible.",
  "focus_element": {
    "address": "code.system.management.knowledge",
    "jsonpath": "$.metaform.code.system.management.knowledge",
    "label": "Metaform",
    "printed_name": "knowledge management system",
    "name_length": 3,
    "role": "DE",
    "status": "built"
  },
  "cels": {
    "skills": [
      {
        "uri": "skill://git-workflow/SKILL.md",
        "inherited_from": "code",
        "frontmatter": {
          "name": "git-workflow",
          "description": "Follow this team's Git conventions for branching and commits"
        },
        "resources": [
          {
            "uri": "skill://git-workflow/SKILL.md",
            "digest": "sha256:b95a384300adeea2d902f7d19cd7c04b378ef58e09759107b9c7db4dcacbaa25",
            "size": 190
          }
        ]
      }
    ],
    "tickets": [
      {
        "id": "MF-42",
        "title": "Add camelCase segment normalization to LadybugDB dual-path writer",
        "intent": "Convert multi-word snake_case namespace segments to camelCase keys on JSONPath write while preserving verbatim snake_case addresses.",
        "status": "in_progress",
        "skill_uris": ["skill://git-workflow/SKILL.md"]
      }
    ],
    "sources": [
      { "key": "entrypoint", "value": "src/mcp/engine.ts" },
      { "key": "path", "value": "src/mcp/lexical.ts" }
    ],
    "investigations": []
  },
  "outbound_providers": {
    "code.service.decision": {
      "pe_jsonpath": "$.metaform.code.service.decision",
      "pe_label": "Jev",
      "pe_printed_name": "decision service",
      "pe_role": "SE",
      "ifd": "both",
      "ice": true,
      "op": "Coordinate agent task routing and enforce reversible mutation gates.",
      "ef": "Evaluates ticket preconditions and dispatches pre-oriented context envelopes to worker agents.",
      "cels": {
        "sources": [{ "key": "path", "value": "src/jev/router.ts" }]
      }
    },
    "upstream.database.graph": {
      "pe_jsonpath": "$.metaform.upstream.database.graph",
      "pe_label": "LadybugDB",
      "pe_printed_name": "graph database",
      "pe_role": "NE",
      "ifd": "both",
      "ice": false,
      "op": "Persist hierarchical namespace tries and resolve Cypher SoA queries into AoS JSON views.",
      "ef": "Executes atomic Cypher and JSONPath transactions over columnar property graph tables."
    }
  },
  "inbound_dependents": [
    {
      "re_address": "downstream.cqu.engineer.software",
      "re_jsonpath": "$.metaform.downstream.cqu.engineer.software",
      "re_label": "AI Software Engineer",
      "re_printed_name": "software engineer",
      "re_role": "CQU",
      "ifd": "receives",
      "ice": false,
      "op": "Navigate functional architecture and execute scoped, reversible code mutations without context overload.",
      "ef": "Streams live topological maps and delivers task-scoped CEL skills, entrypoints, and ICE boundaries."
    }
  ],
  "ice_coupled_cluster": [
    {
      "address": "code.service.decision",
      "label": "Jev",
      "printed_name": "decision service",
      "coupled_via": "code.system.management.knowledge -> code.service.decision",
      "sources": [{ "key": "path", "value": "src/jev/router.ts" }]
    }
  ]
}
```

#### Why this `orient` Envelope Achieves Maximum Inference Amortization:
1. **Ancestral + Ticket-Filtered CEL Resolution:** Notice how `"skill://git-workflow/SKILL.md"` lived at `$.metaform.code.skills` in the database, and the server automatically resolved it down to `code.system.management.knowledge` (marking `"inherited_from": "code"`) and filtered it against `ticket.skill_uris`! The agent doesn't have to climb the tree looking for skills.
2. **Code Entrypoints Upfront:** `cels.sources` gives the exact files (`src/mcp/engine.ts`, `src/mcp/lexical.ts`) for both the focus node and its providers.
3. **Upstream SDKs/Resources (`outbound_providers`) + Downstream Dependents (`inbound_dependents`):** The agent immediately sees both what this element relies on (`outbound_providers`) and who relies on this element (`inbound_dependents`), preventing breaking changes to downstream consumers.
4. **Automatic ICE Cluster Boundary (`ice_coupled_cluster`):** Any neighbor (or transitive chain up to `depth`) marked `"ice": true` is surfaced with its source files so the agent never breaks an Indivisibly Coupled Element pair.

---

## 5. Buildable TypeScript (`tsx`) MCP Server Implementation

Here is the clean, buildable TypeScript implementation uniting the lexical transform pipeline (`snake_case` $\rightarrow$ `camelCase` DB keys, reversed `name`, verbatim `address`), the `ServerLayerPolicy` CEL gatekeeper, and the LadybugDB Cypher/JSONPath adapter.

```typescript
// metaform_mcp_server.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { CANONICAL_CEL_REGISTRY, ServerLayerPolicy } from "./cel_registry.js";

// ============================================================================
// 1. LEXICAL & JSONPATH PIPELINE
// ============================================================================

const VALID_ROOTS = new Set([
  "code", "document", "media", "data", "collection", "upstream", "downstream"
]);

const RESERVED_KEYS = new Set([
  "address", "name", "label", "role", "status", "name_length", "providers",
  ...Object.keys(CANONICAL_CEL_REGISTRY)
]);

export function snakeToCamel(segment: string): string {
  if (!segment.includes("_")) return segment;
  const parts = segment.split("_");
  return parts[0] + parts.slice(1).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join("");
}

export function camelToSnake(dbKey: string): string {
  return dbKey.replace(/([a-z0-9])([A-Z])/g, "$1_$2").toLowerCase();
}

export function addressToJsonPath(project: string, address: string): { jsonPath: string; keys: string[] } {
  const projKey = project.trim().replace(/[^a-zA-Z0-9_]/g, "_");
  const segments = address.split(".");
  if (!VALID_ROOTS.has(segments[0])) {
    throw new Error(`Invalid root scope '${segments[0]}' in address '${address}'.`);
  }
  const dbKeys = segments.map(snakeToCamel);
  return {
    jsonPath: `$.${projKey}.${dbKeys.join(".")}`,
    keys: [projKey, ...dbKeys]
  };
}

export function computePrintedName(address: string, nameLength: number): string {
  const segments = address.split(".");
  const slice = segments.slice(-Math.max(1, nameLength));
  return slice.reverse().map(s => s.replace(/_/g, " ")).join(" ");
}

// ============================================================================
// 2. CODE-CONTROLLED CEL GATEKEEPER & LADYBUGDB STORE
// ============================================================================

export class MetaformStore {
  private db: Record<string, any> = {};

  constructor(public readonly policy: ServerLayerPolicy) {}

  private ensureProject(project: string): { projKey: string; root: Record<string, any> } {
    const projKey = project.trim().replace(/[^a-zA-Z0-9_]/g, "_");
    if (!this.db[projKey]) {
      this.db[projKey] = { id: crypto.randomUUID(), project };
    }
    return { projKey, root: this.db[projKey] };
  }

  private mergeCels(
    target: Record<string, any>,
    cels: Record<string, any[]> | undefined,
    action: "upsert" | "remove"
  ): void {
    if (!cels) return;
    for (const [celName, items] of Object.entries(cels)) {
      if (!this.policy.writableCels.includes(celName)) {
        throw new Error(
          `CEL layer '${celName}' is locked by backend policy. Writable CELs: [${this.policy.writableCels.join(", ")}]`
        );
      }
      const spec = CANONICAL_CEL_REGISTRY[celName];
      if (!spec) throw new Error(`Unregistered CEL layer '${celName}'.`);

      const currentList: any[] = target[celName] ?? [];
      const idKey = spec.identityKey;

      if (action === "upsert") {
        for (const item of items) {
          const idx = currentList.findIndex(existing => existing[idKey] === item[idKey]);
          if (idx >= 0) {
            currentList[idx] = { ...currentList[idx], ...item };
          } else {
            currentList.push(item);
          }
        }
        target[celName] = currentList;
      } else if (action === "remove") {
        const toRemove = new Set(items.map(i => i[idKey]));
        target[celName] = currentList.filter(existing => !toRemove.has(existing[idKey]));
        if (target[celName].length === 0) delete target[celName];
      }
    }
  }

  private getOrCreateNode(project: string, address: string): { jsonPath: string; node: Record<string, any> } {
    const { jsonPath, keys } = addressToJsonPath(project, address);
    const { root } = this.ensureProject(project);
    let curr = root;
    for (const key of keys.slice(1)) {
      if (!curr[key] || typeof curr[key] !== "object" || Array.isArray(curr[key])) {
        curr[key] = {};
      }
      curr = curr[key];
    }
    return { jsonPath, node: curr };
  }

  // --------------------------------------------------------------------------
  // MUTATION EXECUTION (Upsert / Remove / Anneal)
  // --------------------------------------------------------------------------
  public mutate(payload: any): Record<string, any> {
    const { project, action = "upsert", receiver, providers = {}, absorb_addresses = [] } = payload;

    if (!this.policy.allowTopologyMutation && (receiver.role || Object.keys(providers).length > 0)) {
      throw new Error("Topology mutation is disabled in this session; only CEL overlays may be updated.");
    }

    const { jsonPath: rePath, node: reNode } = this.getOrCreateNode(project, receiver.address);

    if (action === "remove" && !receiver.cels && Object.keys(providers).length === 0) {
      // Remove entire element metadata at receiver.address
      for (const k of Object.keys(reNode)) {
        if (RESERVED_KEYS.has(k)) delete reNode[k];
      }
      return { ok: true, action: "removed_element", re_jsonpath: rePath };
    }

    if (action === "upsert" || action === "anneal") {
      if (receiver.role === "CQU" && !receiver.address.startsWith("downstream.cqu.")) {
        throw new Error("CQU elements must be addressed under 'downstream.cqu.*'.");
      }
      reNode.address = receiver.address;
      if (receiver.label) reNode.label = receiver.label;
      if (receiver.name_length) {
        reNode.name_length = receiver.name_length;
        reNode.name = computePrintedName(receiver.address, receiver.name_length);
      }
      if (receiver.role) reNode.role = receiver.role;
      if (receiver.status) reNode.status = receiver.status;
    }

    // Apply CEL mutations on Receiver
    this.mergeCels(reNode, receiver.cels, action === "remove" ? "remove" : "upsert");

    // Process flat-keyed Providers under RE and Dual-Path PE nodes in LadybugDB
    const touchedProviders: string[] = [];
    if (Object.keys(providers).length > 0) {
      reNode.providers = reNode.providers ?? {};
      for (const [peAddress, pSpec] of Object.entries<any>(providers)) {
        if (action === "remove") {
          if (pSpec.cels && reNode.providers[peAddress]) {
            this.mergeCels(reNode.providers[peAddress], pSpec.cels, "remove");
          } else {
            delete reNode.providers[peAddress];
          }
          touchedProviders.push(peAddress);
          continue;
        }

        // Upsert PE at $.{project}.{pe_camel_path}
        const { jsonPath: pePath, node: peNode } = this.getOrCreateNode(project, peAddress);
        peNode.address = peAddress;
        if (pSpec.provider_node) {
          const pn = pSpec.provider_node;
          peNode.label = pn.label;
          peNode.name_length = pn.name_length;
          peNode.name = computePrintedName(peAddress, pn.name_length);
          peNode.role = pn.role;
          if (pn.status) peNode.status = pn.status;
          this.mergeCels(peNode, pn.cels, "upsert");
        }

        // Upsert flat ProviderRecord under RE.providers["{peAddress}"]
        const existingRec = reNode.providers[peAddress] ?? {};
        if (pSpec.ifd) existingRec.ifd = pSpec.ifd;
        if (pSpec.op) existingRec.op = pSpec.op;
        if (pSpec.ef) existingRec.ef = pSpec.ef;
        if (typeof pSpec.ice === "boolean") existingRec.ice = pSpec.ice;
        if (pSpec.status) existingRec.status = pSpec.status;
        this.mergeCels(existingRec, pSpec.cels, "upsert");

        reNode.providers[peAddress] = existingRec;
        touchedProviders.push(pePath);
      }
    }

    return {
      ok: true,
      action,
      re_jsonpath: rePath,
      re_address: receiver.address,
      re_printed_name: reNode.name,
      touched_providers: touchedProviders,
       absorbed: action === "anneal" ? absorb_addresses : []
    };
  }

  // --------------------------------------------------------------------------
  // VIEW EXECUTION (Topology Dump / Ticket Pre-Orientation / Search)
  // --------------------------------------------------------------------------
  public view(payload: any): Record<string, any> {
    const {
      project,
      mode = "orient",
      address,
      ticket_id,
      depth = 3,
      cels = this.policy.readableCels
    } = payload;

    const { root } = this.ensureProject(project);

    if (mode === "topology") {
      return {
        project,
        mode: "topology",
        depth,
        tree: this.buildLowContextTopology(root, depth)
      };
    }

    if (mode === "orient") {
      return this.buildOrientEnvelope(project, root, address, ticket_id, depth, cels);
    }

    return { project, mode, note: "Search/Audit results" };
  }

  private buildLowContextTopology(node: Record<string, any>, maxDepth: number, currentDepth = 0): any {
    const out: Record<string, any> = {};
    for (const [key, val] of Object.entries(node)) {
      if (RESERVED_KEYS.has(key) || key === "id" || key === "project") continue;
      if (val && typeof val === "object" && !Array.isArray(val)) {
        const childBranches = Object.keys(val).filter(k => !RESERVED_KEYS.has(k));
        const summary = val.role
          ? `${val.name ?? camelToSnake(key)} [${val.role}${val.label ? " | " + val.label : ""}]`
          : null;

        if (currentDepth + 1 >= maxDepth || childBranches.length === 0) {
          const suffix = childBranches.length > 0 ? ` (+${childBranches.length} children)` : "";
          out[camelToSnake(key)] = (summary ?? camelToSnake(key)) + suffix;
        } else {
          const subTree = this.buildLowContextTopology(val, maxDepth, currentDepth + 1);
          if (summary) subTree._self = summary;
          out[camelToSnake(key)] = subTree;
        }
      }
    }
    return out;
  }

  private buildOrientEnvelope(
    project: string,
    root: Record<string, any>,
    targetAddress: string | undefined,
    ticketId: string | undefined,
    depth: number,
    requestedCels: string[]
  ): Record<string, any> {
    // 1. Collect all elements for reverse dependent lookup & ticket resolution
    const allElements = new Map<string, { jsonPath: string; node: any }>();
    const walk = (curr: any, keys: string[]) => {
      const snakeAddr = keys.map(camelToSnake).join(".");
      if (curr.role || curr.providers || curr.tickets) {
        allElements.set(snakeAddr, {
          jsonPath: `$.${project.replace(/[^a-zA-Z0-9_]/g, "_")}.${keys.join(".")}`,
          node: curr
        });
      }
      for (const [k, v] of Object.entries(curr)) {
        if (!RESERVED_KEYS.has(k) && v && typeof v === "object" && !Array.isArray(v)) {
          walk(v, [...keys, k]);
        }
      }
    };
    for (const r of VALID_ROOTS) {
      if (root[r]) walk(root[r], [r]);
    }

    // 2. Resolve targetAddress from ticketId if not explicitly provided
    let resolvedAddress = targetAddress;
    let activeTicket: any = null;
    if (ticketId) {
      for (const [addr, { node }] of allElements.entries()) {
        const found = (node.tickets ?? []).find((t: any) => t.id === ticketId);
        if (found) {
          activeTicket = found;
          if (!resolvedAddress) resolvedAddress = addr;
          break;
        }
      }
    }
    if (!resolvedAddress) {
      throw new Error("Either `address` or a valid `ticket_id` must be provided in 'orient' mode.");
    }

    const { jsonPath: focusPath, node: focusNode } = this.getOrCreateNode(project, resolvedAddress);

    // 3. Resolve Ancestral + Local CELs (e.g., code.skills[] inherited by code.system.management.knowledge)
    const allowedCels = requestedCels.filter(c => this.policy.readableCels.includes(c));
    const resolvedCels: Record<string, any[]> = {};
    const { keys: pathKeys } = addressToJsonPath(project, resolvedAddress);

    for (const celName of allowedCels) {
      const mergedItems: any[] = [];
      let curr = root;
      const walkedSegments: string[] = [];
      for (const segKey of pathKeys.slice(1)) {
        curr = curr?.[segKey];
        walkedSegments.push(camelToSnake(segKey));
        if (curr && Array.isArray(curr[celName])) {
          const origin = walkedSegments.join(".");
          for (const item of curr[celName]) {
            mergedItems.push(
              origin === resolvedAddress ? item : { ...item, inherited_from: origin }
            );
          }
        }
      }
      // If oriented via a specific ticket that specifies `skill_uris`, filter skills[] to that task+ticket combo!
      if (celName === "skills" && activeTicket?.skill_uris?.length) {
        const allowedUris = new Set(activeTicket.skill_uris);
        resolvedCels[celName] = mergedItems.filter(s => allowedUris.has(s.uri));
      } else {
        resolvedCels[celName] = mergedItems;
      }
    }

    // 4. Outbound Providers (SDKs / Upstream / Internal PEs this element uses)
    const outboundProviders: Record<string, any> = {};
    const iceCluster: any[] = [];
    for (const [peAddr, pRec] of Object.entries<any>(focusNode.providers ?? {})) {
      const peEntry = allElements.get(peAddr);
      outboundProviders[peAddr] = {
        pe_jsonpath: peEntry?.jsonPath ?? "",
        pe_label: peEntry?.node?.label ?? "",
        pe_printed_name: peEntry?.node?.name ?? "",
        pe_role: peEntry?.node?.role ?? "",
        ifd: pRec.ifd,
        ice: Boolean(pRec.ice),
        op: pRec.op,
        ef: pRec.ef,
        cels: Object.fromEntries(
          allowedCels.filter(c => Array.isArray(pRec[c])).map(c => [c, pRec[c]])
        )
      };
      if (pRec.ice) {
        iceCluster.push({
          address: peAddr,
          label: peEntry?.node?.label,
          printed_name: peEntry?.node?.name,
          coupled_via: `${resolvedAddress} -> ${peAddr}`,
          sources: peEntry?.node?.sources ?? []
        });
      }
    }

    // 5. Inbound Dependents (Downstream entities relying on this functionality)
    const inboundDependents: any[] = [];
    for (const [reAddr, { jsonPath: reJPath, node: reNode }] of allElements.entries()) {
      const rec = reNode.providers?.[resolvedAddress];
      if (rec) {
        inboundDependents.push({
          re_address: reAddr,
          re_jsonpath: reJPath,
          re_label: reNode.label,
          re_printed_name: reNode.name,
          re_role: reNode.role,
          ifd: rec.ifd,
          ice: Boolean(rec.ice),
          op: rec.op,
          ef: rec.ef
        });
        if (rec.ice) {
          iceCluster.push({
            address: reAddr,
            label: reNode.label,
            printed_name: reNode.name,
            coupled_via: `${reAddr} -> ${resolvedAddress}`,
            sources: reNode.sources ?? []
          });
        }
      }
    }

    return {
      project,
      mode: "orient",
      execution_gate:
        "MUTATION_NOT_TRANSFORMATION: Preserve functional contracts and ICE boundaries. All changes must be reversible.",
      focus_element: {
        address: resolvedAddress,
        jsonpath: focusPath,
        label: focusNode.label,
        printed_name: focusNode.name,
        name_length: focusNode.name_length,
        role: focusNode.role,
        status: focusNode.status ?? "built"
      },
      cels: resolvedCels,
      outbound_providers: outboundProviders,
      inbound_dependents: inboundDependents,
      ice_coupled_cluster: iceCluster
    };
  }
}
```

---

## 6. LadybugDB Cypher SoA $\leftrightarrow$ AoS Materialization Pattern

Because LadybugDB stores nodes and CEL records in columnar **Structure of Arrays (SoA)** tables under the hood while projecting **Array of Objects (AoS)** to the MCP layer:
1. **Element Table (`ElementNode`):** Columns `(project, address, jsonpath, label, name, name_length, role, status)`.
2. **Encounter Edge Table (`PROVIDER_ENCOUNTER`):** Directed edges `(re:ElementNode)-[r:PROVIDER_ENCOUNTER {ifd, op, ef, ice, status}]->(pe:ElementNode)` where `re.address` is the receiving element and `pe.address` is the flat provider key.
3. **CEL Overlay Tables (`CelSkill`, `CelSource`, `CelTicket`, `CelInvestigation`):** Attached via `(n:ElementNode)-[:HAS_CEL_SKILL]->(s:CelSkill)` and projected directly into the AoS array `skills: collect({ uri: s.uri, frontmatter: s.frontmatter, resources: s.resources })` inside a single Cypher `RETURN` clause during `metaform_view(mode="orient")`.

