# Metaform MCP Server — Buildable Engineering Specification

**Document ID:** `SPEC-METAFORM-MCP-BUILD-3.0`  
**Target Architecture:** Model Context Protocol (MCP) Server + LadybugDB Dual-Path Graph Engine + Live WebSocket UI Broadcaster  
**Domain:** Universal Ontological Linguistic Typonomy (`code`, `document`, `media`, `data`, `collection`, `upstream`, `downstream`)[cite: 1, 4]

---

## 1. System Architecture & Data Flow

The Metaform MCP Server eliminates the legacy 9-tool micro-CRUD pattern (`intake.element`, `intake.join`, `intake.remove`, etc.) and replaces it with a **two-tool receiver-centric streaming architecture** (`metaform_encounter` and `metaform_context`)[cite: 1]. 

Every call to `metaform_encounter` executes an **Atomic Dual-Path Upsert** into LadybugDB while simultaneously streaming real-time graph deltas to the browser workbench canvas (`hermes-agent` live view) so the user sees nodes and edges materialize as the agent reasons[cite: 1, 2].

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                             LLM AGENT (MCP CLIENT)                                  │
│  Reads:  metaform://intake/procedure  |  metaform://intake/schema                   │
│  Calls:  1. metaform_encounter (Write) |  2. metaform_context (Read/Fuzzy/Audit)    │
└───────────────────┬─────────────────────────────────────────────┬───────────────────┘
                    │ JSON-RPC 2.0 (MCP Tool Call)                │ JSON-RPC 2.0
                    ▼                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        METAFORM MCP SERVER (Python / TypeScript)                    │
│  ┌────────────────────────────────────┐   ┌──────────────────────────────────────┐  │
│  │ Lexical Transform Pipeline         │   │ Code-Controlled Layer Gatekeeper     │  │
│  │ • Input: dotted snake_case         │   │ • Server-side LayerPolicyEngine      │  │
│  │ • DB Key: snake_case -> camelCase  │   │ • Dynamically injects allowed layer  │  │
│  │ • Printed Name: reverse last       │   │   enums into MCP inputSchema         │  │
│  │   `name_length` segs, '_' -> ' '   │   │ • Rejects unauthorized array writes  │  │
│  │ • Address: preserved verbatim      │   └──────────────────────────────────────┘  │
│  └────────────────────────────────────┘                                             │
└───────────────────┬─────────────────────────────────────────────┬───────────────────┘
                    │ Atomic Dual-Path Transaction                │ WebSocket Delta
                    ▼                                             ▼
┌──────────────────────────────────────────┐ ┌────────────────────────────────────────┐
│              LADYBUGDB                   │ │       METAFORM WEB WORKBENCH UI        │
│ • Path 1 (RE):                           │ │ • Animates node cards (`label`)        │
│   $.{project}.{re_camel_path}            │ │ • Inspector shows:                     │
│   └─ .providers["{flat_pe_snake_addr}"]  │ │   - Label: "Hermes Agent"              │
│ • Path 2 (PE):                           │ │   - Printed name: "autonomous agent"   │
│   $.{project}.{pe_camel_path}            │ │   - Address: "code.agent.autonomous"   │
└──────────────────────────────────────────┘ └────────────────────────────────────────┘
```

---

## 2. Deterministic Lexical & Addressing Pipeline

To satisfy the exact UI inspector requirements (as seen in the `hermes-agent` workbench trace[cite: 2]), the database storage conventions, and the Reversible Noun Phrase rules of Digital Typology[cite: 1, 4], the server implements five strict representations for every element:

| Representation | Field / Location | Format Rule | Single-Word Example | Multi-Word Segment Example |
| :--- | :--- | :--- | :--- | :--- |
| **1. Input & Display Address** | `address` (UI `Address:`) | Dotted `snake_case` exactly as entered by the agent[cite: 1]. Never mutated when displayed. | `code.agent.autonomous`[cite: 1, 2] | `code.queue.dead_letter`[cite: 1, 4] |
| **2. LadybugDB JSONPath** | Storage path in LadybugDB | Rooted at `$.{projectname}`[cite: 1]. Dots become nested object keys[cite: 1]. Any multi-word segment containing `_` is converted from `snake_case` to `camelCase`[cite: 1]. | `$.hermes_agent.code.agent.autonomous`[cite: 1] | `$.hermes_agent.code.queue.deadLetter`[cite: 1] |
| **3. Provider Map Key** | Key inside RE's `.providers` object | Flat dotted `snake_case` string (`{providing_element_namespace_address}`)[cite: 1]. Never expanded into nested objects inside `.providers`[cite: 1]. | `"code.agent.autonomous"`[cite: 1] | `"code.queue.dead_letter"`[cite: 1] |
| **4. Printed Industry Name** | `name` (UI `Printed name:`) | Take the final `name_length` segments of `address`, **reverse their order**, and replace all `.` and `_` with spaces[cite: 1, 4]. | `name_length: 2` $\rightarrow$ `"autonomous agent"`[cite: 1, 2] | `name_length: 2` $\rightarrow$ `"dead letter queue"`[cite: 1] |
| **5. Project Official Label** | `label` (Card title & UI header) | Stored on every element node[cite: 1, 3]. Contains the project-specific title, class name, or brand designation[cite: 1, 3]. | `"Hermes Agent"`[cite: 1, 2] | `"DeadLetterQueue"`[cite: 1] |

### 2.1 Reference Implementation (`lexical.py`)

```python
import re
from typing import List, Tuple

VALID_ROOT_SCOPES = frozenset({
    "code", "document", "media", "data", "collection", "upstream", "downstream"
})

ADDRESS_REGEX = re.compile(
    r"^(code|document|media|data|collection|upstream|downstream)(\.[a-z0-9_]+)+$"
)

def normalize_project_key(project_name: str) -> str:
    """Normalizes a project name for the root JSONPath key $.{projectname}."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", project_name.strip())

def snake_to_camel(segment: str) -> str:
    """Converts a snake_case segment to camelCase for LadybugDB JSONPath keys."""
    if "_" not in segment:
        return segment
    parts = segment.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])

def camel_to_snake(db_key: str) -> str:
    """Reverses a camelCase LadybugDB key back to canonical snake_case."""
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", db_key).lower()

def address_to_jsonpath(project_name: str, namespace_address: str) -> Tuple[str, List[str]]:
    """
    Converts (project_name, dotted_snake_address) into:
      1. The canonical LadybugDB JSONPath string: $.{projectname}.{camelCaseSegments...}
      2. The list of object keys to traverse from the document root.
    """
    if not ADDRESS_REGEX.match(namespace_address):
        raise ValueError(
            f"Invalid namespace_address '{namespace_address}'. Must start with one of "
            f"{sorted(VALID_ROOT_SCOPES)} and use lowercase snake_case segments."
        )
    proj_key = normalize_project_key(project_name)
    db_segments = [snake_to_camel(seg) for seg in namespace_address.split(".")]
    json_path = f"$.{proj_key}." + ".".join(db_segments)
    return json_path, [proj_key] + db_segments

def compute_printed_name(namespace_address: str, name_length: int) -> str:
    """
    Computes the industry-standard canonical 'name' by taking the last `name_length`
    segments of `namespace_address`, reversing their order, and replacing '_' with ' '.
    """
    segments = namespace_address.split(".")
    if name_length < 1:
        raise ValueError("name_length must be >= 1")
    tail = segments[-name_length:] if name_length <= len(segments) else segments
    return " ".join(seg.replace("_", " ") for seg in reversed(tail))
```

---

## 3. Code-Controlled Layer Governance (`layers.py`)

In `metaform_schema.json`, any JSON array at a namespace address or inside a provider record is a **`ComposedElementLayer`**[cite: 1, 3]. Which layers may be written is strictly controlled in server code via `LayerController` and injected dynamically into the MCP tool schema at server initialization[cite: 1].

```python
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Set
import jsonschema

LayerScope = Literal["element", "provider"]

@dataclass(frozen=True)
class LayerDefinition:
    name: str
    allowed_scopes: Set[LayerScope]
    description: str
    item_schema: Dict[str, Any]

# Canonical Registry of all ComposedElementLayers known to the system
LAYER_REGISTRY: Dict[str, LayerDefinition] = {
    "sources": LayerDefinition(
        name="sources",
        allowed_scopes={"element", "provider"},
        description="Source file paths, line ranges, or artifact URIs grounding this element or encounter.",
        item_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "enum": ["path", "symbol", "line", "uri"]},
                "value": {"type": "string", "minLength": 1}
            },
            "required": ["key", "value"],
            "additionalProperties": False
        }
    ),
    "investigation": LayerDefinition(
        name="investigation",
        allowed_scopes={"element", "provider"},
        description="Drift observations, missing functionality notes, or code-vs-spec discrepancies.",
        item_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["drift", "not_built", "anomaly", "omission"]},
                "reason": {"type": "string", "minLength": 1},
                "ref": {"type": "string"}
            },
            "required": ["kind", "reason"],
            "additionalProperties": False
        }
    ),
    "ice_evidence": LayerDefinition(
        name="ice_evidence",
        allowed_scopes={"provider"},
        description="Implementation evidence (shared state, lifecycle coupling, internal contracts) proving Indivisibly Coupled Elements (ICE).",
        item_schema={
            "type": "object",
            "properties": {
                "block": {"type": "string"},
                "shared_state": {"type": "string", "minLength": 1},
                "ref": {"type": "string"}
            },
            "required": ["shared_state"],
            "additionalProperties": False
        }
    ),
    "corrections": LayerDefinition(
        name="corrections",
        allowed_scopes={"element", "provider"},
        description="Remediation records filed during Step 10/12 auditing.",
        item_schema={
            "type": "object",
            "properties": {
                "issue": {"type": "string"},
                "remediation": {"type": "string"}
            },
            "required": ["issue", "remediation"],
            "additionalProperties": False
        }
    )
}

class LayerController:
    """
    Code-level policy engine controlling which ComposedElementLayers can be added
    by an agent during the current MCP server execution context.
    """
    def __init__(self, enabled_layers: List[str]):
        unknown = set(enabled_layers) - set(LAYER_REGISTRY.keys())
        if unknown:
            raise ValueError(f"Unknown layer(s) configured in code: {unknown}")
        self.enabled_layers: Set[str] = set(enabled_layers)

    def build_layers_json_schema(self, scope: LayerScope) -> Dict[str, Any]:
        """Generates the exact JSON Schema `properties` block for permitted layers at `scope`."""
        props = {}
        for layer_name in sorted(self.enabled_layers):
            defn = LAYER_REGISTRY[layer_name]
            if scope in defn.allowed_scopes:
                props[layer_name] = {
                    "type": "array",
                    "description": defn.description,
                    "items": defn.item_schema
                }
        return {
            "type": "object",
            "description": f"Code-controlled ComposedElementLayers permitted on {scope} records.",
            "properties": props,
            "additionalProperties": False
        }

    def validate_and_merge(
        self, target_node: Dict[str, Any], incoming_layers: Dict[str, List[Any]], scope: LayerScope
    ) -> None:
        """Validates incoming layer items against code policy and deduplicates/appends them."""
        if not incoming_layers:
            return
        for layer_name, items in incoming_layers.items():
            if layer_name not in self.enabled_layers:
                raise PermissionError(
                    f"Layer '{layer_name}' is disabled by server code policy. "
                    f"Allowed layers: {sorted(self.enabled_layers)}"
                )
            defn = LAYER_REGISTRY[layer_name]
            if scope not in defn.allowed_scopes:
                raise PermissionError(f"Layer '{layer_name}' is not allowed on scope '{scope}'.")
            for item in items:
                jsonschema.validate(instance=item, schema=defn.item_schema)
            existing = target_node.setdefault(layer_name, [])
            for item in items:
                if item not in existing:
                    existing.append(item)
```

---

## 4. Complete MCP Interface Schemas (JSON-RPC / MCP Protocol)

### 4.1 MCP Tools (`tools/list` Payload)

#### Tool 1: `metaform_encounter` (Receiver-Centric Dual-Path Mutation Tool)

```json
{
  "name": "metaform_encounter",
  "description": "Atomically records or updates a Receiving Element (RE) at $.{project}.{receiving_element_namespace_address} and upserts its flat-keyed Provider Records under .providers['{providing_element_namespace_address}'] while simultaneously materializing each Providing Element (PE) at $.{project}.{providing_element_namespace_address} in LadybugDB. Streams live topology updates to the UI canvas.",
  "inputSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "project": {
        "type": "string",
        "description": "Project identifier (used as root key $.{projectname} in LadybugDB)."
      },
      "receiver": {
        "type": "object",
        "description": "The Receiving Element (RE) bearing the Operative Purpose (OP). Inserted as a nested JSONPath at $.{project}.{receiver.address}.",
        "properties": {
          "address": {
            "type": "string",
            "pattern": "^(code|document|media|data|collection|upstream|downstream)(\\.[a-z0-9_]+)+$",
            "description": "Dotted snake_case namespace_address of the Receiving Element (e.g., 'downstream.cqu.worker.knowledge', 'code.agent.autonomous', 'code.queue.dead_letter')."
          },
          "label": {
            "type": "string",
            "minLength": 1,
            "description": "Project-specific official designation or title displayed on the graph node card (e.g., 'Hermes Agent', 'Knowledge worker', 'SessionDB')."
          },
          "name_length": {
            "type": "integer",
            "minimum": 1,
            "description": "Lookback count of trailing segments reversed by the server to form the industry-standard printed name (e.g., 2 on 'code.agent.autonomous' -> 'autonomous agent')."
          },
          "role": {
            "type": "string",
            "enum": ["CQU", "DE", "SE", "NE"],
            "description": "Ontological role: CQU (external beneficiary at downstream.cqu.*), DE (Defining Element), SE (Substantial Element), or NE (Notable Element)."
          },
          "status": {
            "type": "string",
            "enum": ["built", "not_built", "exclude"],
            "description": "Optional implementation status (set to 'not_built' when intended functionality is missing from the artifact)."
          },
          "layers": {
            "type": "object",
            "description": "Code-controlled ComposedElementLayers attached to the Receiving Element.",
            "properties": {
              "sources": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "key": { "type": "string", "enum": ["path", "symbol", "line", "uri"] },
                    "value": { "type": "string", "minLength": 1 }
                  },
                  "required": ["key", "value"],
                  "additionalProperties": false
                }
              },
              "investigation": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "kind": { "type": "string", "enum": ["drift", "not_built", "anomaly", "omission"] },
                    "reason": { "type": "string", "minLength": 1 },
                    "ref": { "type": "string" }
                  },
                  "required": ["kind", "reason"],
                  "additionalProperties": false
                }
              }
            },
            "additionalProperties": false
          }
        },
        "required": ["address", "label", "name_length", "role"],
        "additionalProperties": false
      },
      "providers": {
        "type": "object",
        "description": "Dictionary keyed by the flat dotted snake_case {providing_element_namespace_address}. Each entry records the encounter under the RE and upserts the PE node at $.{project}.{providing_element_namespace_address}.",
        "propertyNames": {
          "pattern": "^(code|document|media|data|collection|upstream|downstream)(\\.[a-z0-9_]+)+$"
        },
        "additionalProperties": {
          "type": "object",
          "properties": {
            "ifd": {
              "type": "string",
              "enum": ["sends", "receives", "both"],
              "description": "Direction [sends|receives|both] of the substance/information flow that satisfies the RE's OP (excluding request parameters)."
            },
            "op": {
              "type": "string",
              "minLength": 1,
              "description": "Operative Purpose (the active 'why' of the RE). Written strictly in ASD-STE100 Simplified Technical English."
            },
            "ef": {
              "type": "string",
              "minLength": 1,
              "description": "Encounter Function (the 'how' delivered by the PE in this encounter). Written strictly in ASD-STE100 starting with a 3rd-person singular present-tense verb."
            },
            "ice": {
              "type": "boolean",
              "default": false,
              "description": "True if the RE and PE are Indivisibly Coupled Elements (ICE) sharing state/lifecycle that cannot be separated without breaking."
            },
            "status": {
              "type": "string",
              "enum": ["built", "not_built"],
              "description": "Optional status for this specific encounter."
            },
            "provider_node": {
              "type": "object",
              "description": "Metadata materialized at $.{project}.{providing_element_namespace_address} in LadybugDB.",
              "properties": {
                "label": {
                  "type": "string",
                  "minLength": 1,
                  "description": "Project-specific designation or title for the Providing Element (e.g., 'Context Engine')."
                },
                "name_length": {
                  "type": "integer",
                  "minimum": 1,
                  "description": "Lookback segment count for the PE's reversed industry name."
                },
                "role": {
                  "type": "string",
                  "enum": ["DE", "SE", "NE"],
                  "description": "Ontological role of the Providing Element (DE, SE, or NE)."
                },
                "status": {
                  "type": "string",
                  "enum": ["built", "not_built", "exclude"]
                },
                "layers": {
                  "type": "object",
                  "properties": {
                    "sources": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "key": { "type": "string", "enum": ["path", "symbol", "line", "uri"] },
                          "value": { "type": "string", "minLength": 1 }
                        },
                        "required": ["key", "value"],
                        "additionalProperties": false
                      }
                    },
                    "investigation": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "kind": { "type": "string", "enum": ["drift", "not_built", "anomaly", "omission"] },
                          "reason": { "type": "string", "minLength": 1 },
                          "ref": { "type": "string" }
                        },
                        "required": ["kind", "reason"],
                        "additionalProperties": false
                      }
                    }
                  },
                  "additionalProperties": false
                }
              },
              "required": ["label", "name_length", "role"],
              "additionalProperties": false
            },
            "layers": {
              "type": "object",
              "description": "Code-controlled ComposedElementLayers attached to this specific provider record.",
              "properties": {
                "sources": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "key": { "type": "string", "enum": ["path", "symbol", "line", "uri"] },
                      "value": { "type": "string", "minLength": 1 }
                    },
                    "required": ["key", "value"],
                    "additionalProperties": false
                  }
                },
                "investigation": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "kind": { "type": "string", "enum": ["drift", "not_built", "anomaly", "omission"] },
                      "reason": { "type": "string", "minLength": 1 },
                      "ref": { "type": "string" }
                    },
                    "required": ["kind", "reason"],
                    "additionalProperties": false
                  }
                },
                "ice_evidence": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "block": { "type": "string" },
                      "shared_state": { "type": "string", "minLength": 1 },
                      "ref": { "type": "string" }
                    },
                    "required": ["shared_state"],
                    "additionalProperties": false
                  }
                }
              },
              "additionalProperties": false
            }
          },
          "required": ["ifd", "op", "ef", "provider_node"],
          "additionalProperties": false
        }
      },
      "anneal_absorb": {
        "type": "array",
        "items": {
          "type": "string",
          "pattern": "^(code|document|media|data|collection|upstream|downstream)(\\.[a-z0-9_]+)+$"
        },
        "description": "Optional list of fine-grained namespace addresses to absorb into this RE during Step 11 annealing. Re-points inbound provider references and removes their standalone nodes."
      }
    },
    "required": ["project", "receiver"],
    "additionalProperties": false
  }
}
```

#### Tool 2: `metaform_context` (Tree Traversal, Fuzzy Namespace Matcher & Audit Tool)

```json
{
  "name": "metaform_context",
  "description": "Queries the LadybugDB Metaform graph to extract purposeful context. Supports fuzzy matching across reversed industry names, project labels, and dotted snake_case namespace addresses, plus directional graph/tree traversal and Step 10/12 completion auditing.",
  "inputSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "project": {
        "type": "string",
        "description": "Project identifier (root key $.{projectname} in LadybugDB)."
      },
      "query": {
        "type": "string",
        "description": "Fuzzy search query matched against reversed industry names ('autonomous agent'), project labels ('Hermes Agent'), dotted snake_case addresses ('code.agent.autonomous'), or OP/EF prose."
      },
      "address": {
        "type": "string",
        "description": "Exact dotted snake_case namespace address (or prefix branch like 'code' or 'downstream.cqu') to anchor traversal."
      },
      "direction": {
        "type": "string",
        "enum": ["providers", "receivers", "both", "namespace_tree"],
        "default": "both",
        "description": "Traversal mode: 'providers' (outbound dependencies of this RE), 'receivers' (inbound REs served by this PE), 'both' (bidirectional functional neighborhood), or 'namespace_tree' (JSONPath hierarchical children)."
      },
      "depth": {
        "type": "integer",
        "minimum": 1,
        "maximum": 6,
        "default": 2,
        "description": "Maximum hop depth to traverse from the anchor or matched element(s)."
      },
      "include_layers": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Optional list of ComposedElementLayer names (e.g., ['sources', 'investigation', 'ice_evidence']) to include in the returned payload."
      },
      "audit": {
        "type": "boolean",
        "default": false,
        "description": "If true, returns a diagnostic audit of unexamined SE leaf nodes, disconnected elements, CQU reachability, and ICE coupling symmetry."
      }
    },
    "required": ["project"],
    "additionalProperties": false
  }
}
```

### 4.2 MCP Resources (`resources/list`) & Prompts (`prompts/list`)

To support MCP hosts that read context via Resources or slash-command Prompts[cite: 1]:

```json
{
  "resources": [
    {
      "uri": "metaform://intake/procedure",
      "name": "Digital Typology Universal Intake Procedure (v2.0)",
      "description": "Canonical 12-step ontological linguistic typonomy procedure, CQU rules, reversible namespace rules, and ASD-STE100 constraints.",
      "mimeType": "text/markdown"
    },
    {
      "uri": "metaform://intake/schema",
      "name": "Metaform LadybugDB Graph JSON Schema",
      "description": "Canonical JSON Schema for $.{projectname} hierarchical namespace tries and flat-keyed provider records.",
      "mimeType": "application/schema+json"
    }
  ],
  "prompts": [
    {
      "name": "metaform_intake",
      "description": "Run a live-streaming Digital Typology functional intake on a target folder or artifact.",
      "arguments": [
        {
          "name": "project",
          "description": "Target project name (e.g., 'hermes-agent').",
          "required": true
        },
        {
          "name": "target_prompt",
          "description": "Optional task focus (e.g., 'initial intake', 'drift investigation', 'feature enhancement').",
          "required": false
        }
      ]
    }
  ]
}
```

---

## 5. Buildable Core Engine Implementation (`engine.py`)

Below is the complete, self-contained reference implementation of the LadybugDB Dual-Path Graph Engine, the Fuzzy Lexicon/Address Matcher, and the Live WebSocket Event Broadcaster.

```python
import difflib
import re
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from lexical import (
    address_to_jsonpath,
    camel_to_snake,
    compute_printed_name,
    normalize_project_key,
    VALID_ROOT_SCOPES,
)
from layers import LayerController, LAYER_REGISTRY

RESERVED_ELEMENT_KEYS = frozenset({
    "address", "name", "label", "role", "status", "name_length", "providers"
}) | frozenset(LAYER_REGISTRY.keys())


class LadybugMetaformEngine:
    """
    Buildable LadybugDB JSONPath Graph Engine implementing:
      1. Dual-Path insertion:
         - RE inserted at $.{projectname}.{re_camel_path}
         - ProviderRecord inserted at $.{projectname}.{re_camel_path}.providers["{flat_pe_snake_address}"]
         - PE inserted at $.{projectname}.{pe_camel_path}
      2. Deterministic snake_case -> camelCase DB keys, reversed printed `name`, and verbatim `address`.
      3. Multi-dimensional fuzzy query & tree/graph traversal.
    """

    def __init__(
        self,
        layer_controller: LayerController,
        ws_broadcaster: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.db: Dict[str, Dict[str, Any]] = {}
        self.layer_controller = layer_controller
        self.ws_broadcaster = ws_broadcaster or (lambda event: None)

    def _ensure_project_root(self, project: str) -> Tuple[str, Dict[str, Any]]:
        proj_key = normalize_project_key(project)
        if proj_key not in self.db:
            self.db[proj_key] = {
                "id": uuid.uuid4().hex,
                "project": project,
                "label": project
            }
        return proj_key, self.db[proj_key]

    def _upsert_trie_node(
        self,
        project: str,
        address: str,
        label: str,
        name_length: int,
        role: str,
        status: Optional[str] = None,
        layers: Optional[Dict[str, List[Any]]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Materializes a node at $.{projectname}.{camel_case_path} without clobbering
        any existing child namespace branches or existing `.providers` map.
        """
        # Ontological guardrail: CQUs must reside under downstream.cqu.*
        if role == "CQU" and not address.startswith("downstream.cqu."):
            raise ValueError(
                f"Element '{address}' has role='CQU' but is not under 'downstream.cqu.*'."
            )
        if address.startswith("downstream.cqu.") and role != "CQU":
            raise ValueError(
                f"Element '{address}' under 'downstream.cqu.*' must have role='CQU'."
            )

        json_path, path_keys = address_to_jsonpath(project, address)
        _, proj_root = self._ensure_project_root(project)

        curr = proj_root
        for seg_key in path_keys[1:]:
            if seg_key not in curr or not isinstance(curr[seg_key], dict):
                curr[seg_key] = {}
            curr = curr[seg_key]

        printed_name = compute_printed_name(address, name_length)

        curr["address"] = address
        curr["label"] = label
        curr["name_length"] = name_length
        curr["name"] = printed_name
        curr["role"] = role
        if status is not None:
            curr["status"] = status

        if layers:
            self.layer_controller.validate_and_merge(curr, layers, scope="element")

        return json_path, curr

    def execute_encounter(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the atomic `metaform_encounter` tool operation.
        """
        project = payload["project"]
        re_spec = payload["receiver"]
        providers_spec = payload.get("providers", {})
        anneal_absorb = payload.get("anneal_absorb", [])

        # 1. Upsert Receiving Element (RE) at $.{project}.{re_camel_path}
        re_jsonpath, re_node = self._upsert_trie_node(
            project=project,
            address=re_spec["address"],
            label=re_spec["label"],
            name_length=re_spec["name_length"],
            role=re_spec["role"],
            status=re_spec.get("status"),
            layers=re_spec.get("layers")
        )

        upserted_providers = []
        if providers_spec:
            re_providers_map = re_node.setdefault("providers", {})

            for pe_flat_address, p_rec in providers_spec.items():
                pe_node_spec = p_rec["provider_node"]
                if pe_node_spec["role"] == "CQU":
                    raise ValueError(
                        f"Providing Element '{pe_flat_address}' cannot have role 'CQU'. "
                        "CQUs are exclusively external Receiving Elements."
                    )

                # 2. Upsert Providing Element (PE) at $.{project}.{pe_camel_path}
                pe_jsonpath, _ = self._upsert_trie_node(
                    project=project,
                    address=pe_flat_address,
                    label=pe_node_spec["label"],
                    name_length=pe_node_spec["name_length"],
                    role=pe_node_spec["role"],
                    status=pe_node_spec.get("status"),
                    layers=pe_node_spec.get("layers")
                )

                # 3. Upsert flat-keyed ProviderRecord under RE.providers["{pe_flat_address}"]
                existing_rec = re_providers_map.get(pe_flat_address, {})
                existing_rec["ifd"] = p_rec["ifd"]
                existing_rec["op"] = p_rec["op"]
                existing_rec["ef"] = p_rec["ef"]
                existing_rec["ice"] = bool(p_rec.get("ice", False))
                if "status" in p_rec:
                    existing_rec["status"] = p_rec["status"]

                if "layers" in p_rec:
                    self.layer_controller.validate_and_merge(
                        existing_rec, p_rec["layers"], scope="provider"
                    )

                re_providers_map[pe_flat_address] = existing_rec
                upserted_providers.append({
                    "pe_address": pe_flat_address,
                    "pe_jsonpath": pe_jsonpath,
                    "pe_name": compute_printed_name(pe_flat_address, pe_node_spec["name_length"]),
                    "pe_label": pe_node_spec["label"],
                    "ifd": existing_rec["ifd"],
                    "ice": existing_rec["ice"]
                })

        # 4. Handle Step 11 Annealing (`anneal_absorb`)
        absorbed_count = 0
        for old_addr in anneal_absorb:
            if old_addr != re_spec["address"]:
                if self._absorb_element(project, old_addr, re_spec["address"], re_node):
                    absorbed_count += 1

        # 5. Compute live progress metrics & broadcast WebSocket delta
        audit_summary = self._compute_audit_summary(project)
        ws_event = {
            "event": "metaform.encounter.recorded",
            "project": project,
            "receiver": {
                "address": re_spec["address"],
                "jsonpath": re_jsonpath,
                "label": re_node["label"],
                "name": re_node["name"],
                "role": re_node["role"]
            },
            "providers": upserted_providers,
            "absorbed": anneal_absorb,
            "totals": audit_summary["totals"]
        }
        self.ws_broadcaster(ws_event)

        return {
            "ok": True,
            "re_jsonpath": re_jsonpath,
            "re_address": re_spec["address"],
            "re_printed_name": re_node["name"],
            "re_label": re_node["label"],
            "upserted_providers": upserted_providers,
            "absorbed_elements": absorbed_count,
            "graph_status": audit_summary["totals"]
        }

    def _iter_all_elements(self, project: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """
        Traverses the LadybugDB JSONPath trie for `project` and yields
        (dotted_snake_address, jsonpath, node_dict) for every materialized element.
        """
        proj_key, proj_root = self._ensure_project_root(project)
        results: List[Tuple[str, str, Dict[str, Any]]] = []

        def _walk(node: Dict[str, Any], db_keys: List[str]):
            if "role" in node and "label" in node:
                snake_addr = node.get("address") or ".".join(camel_to_snake(k) for k in db_keys)
                jpath = f"$.{proj_key}." + ".".join(db_keys)
                results.append((snake_addr, jpath, node))

            for k, v in node.items():
                if k not in RESERVED_ELEMENT_KEYS and isinstance(v, dict):
                    _walk(v, db_keys + [k])

        for root_scope in VALID_ROOT_SCOPES:
            if root_scope in proj_root and isinstance(proj_root[root_scope], dict):
                _walk(proj_root[root_scope], [root_scope])

        return results

    def _absorb_element(
        self, project: str, old_addr: str, target_re_addr: str, target_re_node: Dict[str, Any]
    ) -> bool:
        """Folds `old_addr` into `target_re_addr` during Step 11 annealing."""
        _, path_keys = address_to_jsonpath(project, old_addr)
        _, proj_root = self._ensure_project_root(project)

        parent = proj_root
        for k in path_keys[1:-1]:
            if k not in parent or not isinstance(parent[k], dict):
                return False
            parent = parent[k]

        leaf_key = path_keys[-1]
        old_node = parent.get(leaf_key)
        if not isinstance(old_node, dict):
            return False

        # Merge permitted element-level layers (e.g., sources) into target_re_node
        for layer_name in self.layer_controller.enabled_layers:
            if layer_name in old_node and isinstance(old_node[layer_name], list):
                existing = target_re_node.setdefault(layer_name, [])
                for item in old_node[layer_name]:
                    if item not in existing:
                        existing.append(item)

        # Re-point any provider references across the graph from old_addr -> target_re_addr
        for _, _, elem_node in self._iter_all_elements(project):
            prov_map = elem_node.get("providers", {})
            if old_addr in prov_map:
                old_rec = prov_map.pop(old_addr)
                if elem_node.get("address") != target_re_addr:
                    prov_map.setdefault(target_re_addr, old_rec)

        # Remove element metadata from old_node; delete key if it has no child namespace branches
        for meta_key in list(old_node.keys()):
            if meta_key in RESERVED_ELEMENT_KEYS:
                del old_node[meta_key]
        if not old_node:
            del parent[leaf_key]

        return True

    def execute_context_query(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the `metaform_context` tool operation:
          - Fuzzy matching across `name` (reversed industry name), `label`, `address`, and OP/EF
          - Directional graph/tree traversal (`providers`, `receivers`, `both`, `namespace_tree`)
          - Optional Step 10/12 completeness audit
        """
        project = payload["project"]
        query = (payload.get("query") or "").strip()
        anchor_address = (payload.get("address") or "").strip()
        direction = payload.get("direction", "both")
        depth = int(payload.get("depth", 2))
        include_layers = set(payload.get("include_layers") or [])
        run_audit = bool(payload.get("audit", False))

        all_elements = self._iter_all_elements(project)
        by_address: Dict[str, Tuple[str, Dict[str, Any]]] = {
            addr: (jpath, node) for addr, jpath, node in all_elements
        }

        # Build reverse index: PE address -> list of (RE address, ProviderRecord)
        inbound_receivers: Dict[str, List[Dict[str, Any]]] = {}
        for re_addr, _, re_node in all_elements:
            for pe_addr, p_rec in re_node.get("providers", {}).items():
                inbound_receivers.setdefault(pe_addr, []).append({
                    "re_address": re_addr,
                    "re_label": re_node.get("label"),
                    "re_name": re_node.get("name"),
                    "ifd": p_rec.get("ifd"),
                    "ice": p_rec.get("ice", False),
                    "op": p_rec.get("op"),
                    "ef": p_rec.get("ef")
                })

        matched_addresses: List[Tuple[str, float]] = []
        if anchor_address:
            for addr in by_address:
                if addr == anchor_address or addr.startswith(anchor_address + "."):
                    matched_addresses.append((addr, 1.0))
        elif query:
            matched_addresses = self._fuzzy_rank(query, all_elements)
        else:
            # Default to CQU and DE roots if neither query nor address is specified
            for addr, _, node in all_elements:
                if node.get("role") in ("CQU", "DE"):
                    matched_addresses.append((addr, 1.0))

        # Format matched nodes and traverse neighborhood up to `depth`
        matches_out = []
        for addr, score in matched_addresses[:15]:
            if addr not in by_address:
                continue
            jpath, node = by_address[addr]
            matches_out.append(
                self._serialize_context_slice(
                    addr, jpath, node, score, direction, depth,
                    by_address, inbound_receivers, include_layers
                )
            )

        response: Dict[str, Any] = {
            "project": project,
            "match_count": len(matches_out),
            "matches": matches_out
        }
        if run_audit:
            response["audit"] = self._compute_audit_summary(project)
        return response

    def _fuzzy_rank(
        self, query: str, all_elements: List[Tuple[str, str, Dict[str, Any]]]
    ) -> List[Tuple[str, float]]:
        """
        Scores elements across reversed industry `name`, project `label`,
        dotted `address` (both snake_case and camelCase), and OP/EF prose.
        """
        q_lower = query.lower()
        q_tokens = set(re.split(r"[\s._]+", camel_to_snake(query))) - {""}
        scored: List[Tuple[str, float]] = []

        for addr, _, node in all_elements:
            name_lower = (node.get("name") or "").lower()
            label_lower = (node.get("label") or "").lower()
            addr_lower = addr.lower()

            # 1. Exact match on address, reversed printed name, or project label
            if q_lower in (addr_lower, name_lower, label_lower):
                scored.append((addr, 1.0))
                continue

            # 2. Substring or token-set overlap against reversed industry name & address
            cand_tokens = (
                set(re.split(r"[\s._]+", addr_lower))
                | set(re.split(r"[\s._]+", name_lower))
                | set(re.split(r"[\s._]+", camel_to_snake(node.get("label", ""))))
            ) - {""}

            token_overlap = len(q_tokens & cand_tokens) / max(len(q_tokens), 1)
            seq_ratio = max(
                difflib.SequenceMatcher(None, q_lower, name_lower).ratio(),
                difflib.SequenceMatcher(None, q_lower, label_lower).ratio(),
                difflib.SequenceMatcher(None, q_lower, addr_lower).ratio()
            )
            best_score = max(token_overlap * 0.92, seq_ratio * 0.88)

            # 3. Check OP/EF text if lexical score is low
            if best_score < 0.55:
                for p_rec in node.get("providers", {}).values():
                    op_ef = f"{p_rec.get('op', '')} {p_rec.get('ef', '')}".lower()
                    if q_lower in op_ef:
                        best_score = max(best_score, 0.65)
                        break

            if best_score >= 0.45:
                scored.append((addr, round(best_score, 3)))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored

    def _serialize_context_slice(
        self,
        addr: str,
        jpath: str,
        node: Dict[str, Any],
        score: float,
        direction: str,
        depth: int,
        by_address: Dict[str, Tuple[str, Dict[str, Any]]],
        inbound_receivers: Dict[str, List[Dict[str, Any]]],
        include_layers: Set[str]
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "address": addr,
            "jsonpath": jpath,
            "label": node.get("label"),
            "printed_name": node.get("name"),
            "name_length": node.get("name_length"),
            "role": node.get("role"),
            "match_score": score
        }
        if "status" in node:
            out["status"] = node["status"]

        for layer_name in include_layers:
            if layer_name in node:
                out[layer_name] = node[layer_name]

        if direction in ("providers", "both") and depth >= 1:
            prov_out = {}
            for pe_addr, p_rec in node.get("providers", {}).items():
                pe_jpath, pe_node = by_address.get(pe_addr, ("", {}))
                entry = {
                    "pe_jsonpath": pe_jpath,
                    "pe_label": pe_node.get("label"),
                    "pe_printed_name": pe_node.get("name"),
                    "pe_role": pe_node.get("role"),
                    "ifd": p_rec.get("ifd"),
                    "ice": p_rec.get("ice", False),
                    "op": p_rec.get("op"),
                    "ef": p_rec.get("ef")
                }
                for layer_name in include_layers:
                    if layer_name in p_rec:
                        entry[layer_name] = p_rec[layer_name]
                prov_out[pe_addr] = entry
            out["providers"] = prov_out

        if direction in ("receivers", "both") and depth >= 1:
            out["receivers_of_this_pe"] = inbound_receivers.get(addr, [])

        if direction == "namespace_tree":
            children = [
                other_addr for other_addr in by_address
                if other_addr.startswith(addr + ".")
            ]
            out["namespace_descendants"] = sorted(children)

        return out

    def _compute_audit_summary(self, project: str) -> Dict[str, Any]:
        """Computes real-time Step 7/9/10/12 completion diagnostics."""
        all_elements = self._iter_all_elements(project)
        by_addr = {addr: node for addr, _, node in all_elements}

        total_encounters = 0
        referenced_pes: Set[str] = set()
        cqu_roots: List[str] = []

        for addr, _, node in all_elements:
            if node.get("role") == "CQU":
                cqu_roots.append(addr)
            for pe_addr in node.get("providers", {}):
                total_encounters += 1
                referenced_pes.add(pe_addr)

        # Unexamined SEs: elements with role == 'SE' that have no outbound `.providers` yet
        unexamined_se_leaves = [
            addr for addr, node in by_addr.items()
            if node.get("role") == "SE" and not node.get("providers")
        ]

        # Disconnected elements: non-CQU nodes that are neither referenced as a PE nor have providers
        disconnected = [
            addr for addr, node in by_addr.items()
            if node.get("role") != "CQU" and addr not in referenced_pes and not node.get("providers")
        ]

        return {
            "totals": {
                "elements": len(all_elements),
                "encounters": total_encounters,
                "cqu_roots": len(cqu_roots),
                "unexamined_se_leaves": len(unexamined_se_leaves)
            },
            "unexamined_se_addresses": sorted(unexamined_se_leaves),
            "disconnected_addresses": sorted(disconnected)
        }
```

---

## 6. MCP Server Wiring (`server.py`)

This module connects the `LadybugMetaformEngine` and `LayerController` to the standard Model Context Protocol (MCP) server lifecycle over stdio or SSE/StreamableHTTP.

```python
import asyncio
import json
from typing import Any, Dict, List
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from layers import LayerController
from engine import LadybugMetaformEngine

# 1. Configure permitted ComposedElementLayers in code (never exposed for LLM override)
ACTIVE_LAYER_POLICY = LayerController(
    enabled_layers=["sources", "investigation", "ice_evidence"]
)

# 2. Initialize LadybugDB Engine
engine = LadybugMetaformEngine(layer_controller=ACTIVE_LAYER_POLICY)
app = Server("metaform-mcp-server")


@app.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """Dynamically injects the code-controlled layer schemas into `metaform_encounter`."""
    element_layers_schema = ACTIVE_LAYER_POLICY.build_layers_json_schema("element")
    provider_layers_schema = ACTIVE_LAYER_POLICY.build_layers_json_schema("provider")

    return [
        types.Tool(
            name="metaform_encounter",
            description=(
                "Records or updates a Receiving Element (RE) at $.{project}.{receiving_element_namespace_address} "
                "and upserts its flat-keyed Provider Records under .providers['{providing_element_namespace_address}'] "
                "while simultaneously materializing each Providing Element (PE) at "
                "$.{project}.{providing_element_namespace_address} in LadybugDB."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "receiver": {
                        "type": "object",
                        "properties": {
                            "address": {
                                "type": "string",
                                "pattern": "^(code|document|media|data|collection|upstream|downstream)(\\.[a-z0-9_]+)+$"
                            },
                            "label": {"type": "string", "minLength": 1},
                            "name_length": {"type": "integer", "minimum": 1},
                            "role": {"type": "string", "enum": ["CQU", "DE", "SE", "NE"]},
                            "status": {"type": "string", "enum": ["built", "not_built", "exclude"]},
                            "layers": element_layers_schema
                        },
                        "required": ["address", "label", "name_length", "role"],
                        "additionalProperties": False
                    },
                    "providers": {
                        "type": "object",
                        "propertyNames": {
                            "pattern": "^(code|document|media|data|collection|upstream|downstream)(\\.[a-z0-9_]+)+$"
                        },
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "ifd": {"type": "string", "enum": ["sends", "receives", "both"]},
                                "op": {"type": "string", "minLength": 1},
                                "ef": {"type": "string", "minLength": 1},
                                "ice": {"type": "boolean", "default": False},
                                "status": {"type": "string", "enum": ["built", "not_built"]},
                                "provider_node": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string", "minLength": 1},
                                        "name_length": {"type": "integer", "minimum": 1},
                                        "role": {"type": "string", "enum": ["DE", "SE", "NE"]},
                                        "status": {"type": "string", "enum": ["built", "not_built", "exclude"]},
                                        "layers": element_layers_schema
                                    },
                                    "required": ["label", "name_length", "role"],
                                    "additionalProperties": False
                                },
                                "layers": provider_layers_schema
                            },
                            "required": ["ifd", "op", "ef", "provider_node"],
                            "additionalProperties": False
                        }
                    },
                    "anneal_absorb": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["project", "receiver"],
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="metaform_context",
            description=(
                "Extracts purposeful functional context from the LadybugDB Metaform graph via "
                "fuzzy matching on reversed industry names, project labels, and dotted snake_case "
                "addresses, or via directional tree/provider traversal and completion auditing."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "query": {"type": "string"},
                    "address": {"type": "string"},
                    "direction": {
                        "type": "string",
                        "enum": ["providers", "receivers", "both", "namespace_tree"],
                        "default": "both"
                    },
                    "depth": {"type": "integer", "minimum": 1, "maximum": 6, "default": 2},
                    "include_layers": {"type": "array", "items": {"type": "string"}},
                    "audit": {"type": "boolean", "default": False}
                },
                "required": ["project"],
                "additionalProperties": False
            }
        )
    ]


@app.call_tool()
async def handle_call_tool(
    name: str, arguments: Dict[str, Any]
) -> List[types.TextContent]:
    try:
        if name == "metaform_encounter":
            result = engine.execute_encounter(arguments)
        elif name == "metaform_context":
            result = engine.execute_context_query(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as exc:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"ok": False, "error": str(exc)}, indent=2)
            )
        ]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Canonical LadybugDB Storage Schema (`metaform_schema.json`)

This is the finalized, production-ready JSON Schema for the stored LadybugDB document (`metaform://intake/schema`)[cite: 1, 3]. It enforces the `$.{projectname}` root, nested `camelCase` namespace branches, `address`/`name`/`label`/`name_length`/`role` attributes on every element, and flat `{providing_element_namespace_address}` keys inside `.providers`[cite: 1, 3].

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Metaform LadybugDB Graph Model",
  "description": "A Metaform is a namespace-addressed JSON document rooted at $.{projectname}. Object keys establish hierarchical namespace addresses (with snake_case compound segments stored as camelCase keys in LadybugDB). Receiving Elements (RE) hold flat-keyed provider records under .providers['{providing_element_namespace_address}'], while every Providing Element (PE) is simultaneously materialized at $.{projectname}.{providing_element_namespace_address}.",
  "type": "object",
  "additionalProperties": {
    "$ref": "#/$defs/ProjectRoot"
  },
  "$defs": {
    "ProjectRoot": {
      "title": "Project Root Node ($.{projectname})",
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "description": "Unique intake/metaform identifier."
        },
        "project": {
          "type": "string",
          "description": "Canonical project identifier."
        },
        "label": {
          "type": "string",
          "description": "Human-readable project title."
        },
        "code": { "$ref": "#/$defs/NamespaceNode" },
        "document": { "$ref": "#/$defs/NamespaceNode" },
        "media": { "$ref": "#/$defs/NamespaceNode" },
        "data": { "$ref": "#/$defs/NamespaceNode" },
        "collection": { "$ref": "#/$defs/NamespaceNode" },
        "upstream": { "$ref": "#/$defs/NamespaceNode" },
        "downstream": { "$ref": "#/$defs/NamespaceNode" }
      },
      "additionalProperties": false
    },
    "NamespaceValue": {
      "title": "Value at a namespace address",
      "oneOf": [
        { "$ref": "#/$defs/NamespaceNode" },
        { "$ref": "#/$defs/ComposedElementLayer" },
        { "type": ["string", "number", "boolean", "null"] }
      ]
    },
    "NamespaceNode": {
      "title": "Namespace branch or functional element (RE / PE)",
      "type": "object",
      "properties": {
        "address": {
          "type": "string",
          "pattern": "^(code|document|media|data|collection|upstream|downstream)(\\.[a-z0-9_]+)+$",
          "description": "Canonical dotted snake_case namespace_address exactly as entered (e.g., 'code.queue.dead_letter')."
        },
        "name": {
          "type": "string",
          "description": "Industry-standard canonical printed name computed by reversing the final name_length segments and replacing underscores with spaces (e.g., 'dead letter queue')."
        },
        "label": {
          "type": "string",
          "description": "Company-specific corporate designation or project official terminology displayed on the graph card (e.g., 'Hermes Agent')."
        },
        "role": {
          "type": "string",
          "enum": ["CQU", "DE", "SE", "NE"],
          "description": "The ontological role of this element within the digital typology (CQU | DE | SE | NE)."
        },
        "status": {
          "type": "string",
          "enum": ["built", "not_built", "exclude"],
          "description": "Mutable value indicating the present implementation state of the element."
        },
        "name_length": {
          "type": "integer",
          "minimum": 1,
          "description": "The number of trailing segments reversed upward to construct the industry-standard printed name."
        },
        "providers": {
          "$ref": "#/$defs/Providers"
        },
        "sources": {
          "$ref": "#/$defs/ComposedElementLayer"
        },
        "investigation": {
          "$ref": "#/$defs/ComposedElementLayer"
        },
        "corrections": {
          "$ref": "#/$defs/ComposedElementLayer"
        }
      },
      "additionalProperties": {
        "$ref": "#/$defs/NamespaceValue"
      }
    },
    "ComposedElementLayer": {
      "title": "Array-valued composed element layer",
      "description": "Code-governed JSON array attached at a namespace address or provider record. Retains native item structure without synthetic integer IDs.",
      "type": "array",
      "items": true
    },
    "Providers": {
      "title": "Receiving element's providers map",
      "description": "An object whose keys are the flat dotted snake_case namespace addresses of Providing Elements ({providing_element_namespace_address}).",
      "type": "object",
      "propertyNames": {
        "pattern": "^(code|document|media|data|collection|upstream|downstream)(\\.[a-z0-9_]+)+$"
      },
      "additionalProperties": {
        "$ref": "#/$defs/ProviderRecord"
      }
    },
    "ProviderRecord": {
      "title": "Provider record",
      "description": "A receiver-owned statement of an operational relationship mapping a flat provider namespace address key to its context-specific IFD, OP, EF, and ICE state.",
      "type": "object",
      "properties": {
        "ifd": {
          "type": "string",
          "enum": ["sends", "receives", "both"],
          "description": "Direction [sends|receives|both] of the information flow that satisfies the active goal (OP) of the Receiving Element (RE), excluding request parameters."
        },
        "op": {
          "type": "string",
          "description": "The active goal (why) of the Receiving Element (RE) that the provider's EF must satisfy. Formatted strictly in ASD-STE100."
        },
        "ef": {
          "type": "string",
          "description": "The mechanism, interface, relationship, or method of the Providing Element (PE) that satisfies the OP. Formatted strictly in ASD-STE100 starting with a 3rd-person singular verb."
        },
        "ice": {
          "type": "boolean",
          "default": false,
          "description": "True when the RE and PE are Indivisibly Coupled Elements (ICE) that cannot be separated without breaking."
        },
        "status": {
          "type": "string",
          "enum": ["built", "not_built"]
        },
        "sources": {
          "$ref": "#/$defs/ComposedElementLayer"
        },
        "investigation": {
          "$ref": "#/$defs/ComposedElementLayer"
        },
        "ice_evidence": {
          "$ref": "#/$defs/ComposedElementLayer"
        },
        "corrections": {
          "$ref": "#/$defs/ComposedElementLayer"
        }
      },
      "required": ["ifd", "op", "ef"],
      "additionalProperties": false
    }
  }
}
```

---

## 8. End-to-End Trace Verification (`hermes-agent`)

To verify how a single `metaform_encounter` call populates LadybugDB and drives the exact UI state shown in the `hermes-agent` workbench recording[cite: 2]:

### 8.1 Agent Tool Call (`metaform_encounter`)
```json
{
  "project": "hermes-agent",
  "receiver": {
    "address": "code.agent.autonomous",
    "label": "Hermes Agent",
    "name_length": 2,
    "role": "DE",
    "layers": {
      "sources": [{ "key": "path", "value": "run_agent.py" }]
    }
  },
  "providers": {
    "code.search.session_history": {
      "ifd": "receives",
      "ice": false,
      "op": "Recall relevant prior user conversations across past sessions.",
      "ef": "Indexes past session transcripts in SQLite FTS5 and returns ranked conversation snippets.",
      "provider_node": {
        "label": "session_search",
        "name_length": 2,
        "role": "SE"
      }
    }
  }
}
```

### 8.2 Resulting LadybugDB State (`$.hermes_agent`)
```json
{
  "hermes_agent": {
    "id": "9c8b1a2f4e3d4c5b8a7f6e5d4c3b2a10",
    "project": "hermes-agent",
    "label": "hermes-agent",
    "code": {
      "agent": {
        "autonomous": {
          "address": "code.agent.autonomous",
          "label": "Hermes Agent",
          "name": "autonomous agent",
          "name_length": 2,
          "role": "DE",
          "sources": [
            { "key": "path", "value": "run_agent.py" }
          ],
          "providers": {
            "code.search.session_history": {
              "ifd": "receives",
              "ice": false,
              "op": "Recall relevant prior user conversations across past sessions.",
              "ef": "Indexes past session transcripts in SQLite FTS5 and returns ranked conversation snippets."
            }
          }
        }
      },
      "search": {
        "sessionHistory": {
          "address": "code.search.session_history",
          "label": "session_search",
          "name": "session history search",
          "name_length": 2,
          "role": "SE"
        }
      }
    }
  }
}
```
* **RE Path:** `$.hermes_agent.code.agent.autonomous`[cite: 1, 2]
* **Flat Provider Key under RE:** `.providers["code.search.session_history"]`[cite: 1]
* **PE Path (with `snake_case` $\rightarrow$ `camelCase` conversion):** `$.hermes_agent.code.search.sessionHistory`[cite: 1]
* **Printed Name (`name`):** `"session history search"` (`name_length: 2` reversed with `_` dropped for a space)[cite: 1]
* **Verbatim Address (`address`):** `"code.search.session_history"`[cite: 1]
