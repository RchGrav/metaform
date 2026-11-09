## Module 1: Architectural Philosophy & Core Principles

### 1.1 Durable vs. Ephemeral Knowledge

The system map exists exclusively to record durable, long-lasting structural and functional reality.

\


- **Durable Knowledge (In-Map):** Element identities, functional dependencies (`wants`), operational entry points (`sources`), system-provided procedural capabilities (`skills`), durable engineering invariants, and verified architectural review gates.

- **Ephemeral Knowledge (Out-of-Map):** Transient investigation notes, drift observations, temporary debugging flags, or speculative coupling theories. Ephemeral findings must be routed to an external issue or ticket tracker and are strictly prohibited from residing in the map database.

### 1.2 Storage Topology & Multi-Project Isolation

The database architecture separates global chassis administration from isolated project graphs:

\


- **Chassis Database (**`~/.metaform/metaform.lbug`**):** Tracks registered project nodes, source path pointers, and global system settings.

- **Project Databases (**`~/.metaform/projects/<encoded-path-id>/project.lbug`**):** Stores the functional graph for a single project. A project database never stores its own project name or project attribute on elements; provenance is resolved externally through `source.txt` and the chassis database.

- **Settings Inheritance (CLI-023):** System defaults are declared in code and never written to storage. Only explicit global or project-level overrides are persisted, ensuring upstream default updates propagate automatically to unconfigured nodes.

## Module 2: Typological Ontology & Namespace Rules

### 2.1 Root Functional Types

Every element address in the map must descend from one of six root functional domains:

\


- `code` — Executable logic, algorithms, pipelines, and software components.

- `document` — Specifications, narratives, contracts, and structured text elements.

- `media` — Visual, audio, and scenic functional assets.

- `data` — Schemas, tables, queues, payloads, and persistent structures.

- `upstream` — External providers, third-party APIs, and inbound dependencies outside the project tree.

- `downstream` — External consumers and outbound integration targets outside the project tree.

### 2.2 Ontological Construction Rules

1. **Reversible Noun Phrase Rule:** Splitting an address on periods (`.`), reversing the segments, and replacing underscores (`_`) with spaces must yield a grammatically sound, industry-standard noun phrase where child segments inherit their parent segment as their trailing noun (e.g., `code.buffer.ring.packet` reverses to *"packet ring buffer code"*).

2. **Containment Hierarchy:** All artifacts are entities, and all entities are elements ($\text{Artifacts} \subset \text{Entities} \subset \text{Elements}$).

3. **Functional Narrowing:** Namespaces must narrow strictly from trunk to leaf. Every child segment must represent a functional subtype or constituent part of its parent scope—never an encoding (`.jpg`, `.cpp`, `.word`) or non-functional genre (`.platformer`).

4. **Segment Prefix Independence & Underscore Joining:** Any multi-word concept whose prefix forms a valid standalone functional type must be split by periods (`code.engine.game`, `code.engine.physics`). Words may be joined by underscores only when individual words do not form valid functional prefixes on their own (`code.queue.dead_letter`, `data.bill_of_materials`).

5. **Industry-Standard Lexicon (Non-Coinage):** All segments must use standard practitioner terminology. Coined words, internal slang, marketing labels, and arbitrary abbreviations are strictly prohibited.

## Module 3: Element Base Values & Systemic Role Taxonomy

### 3.1 Core Element Scalar Fields (intake)

Every element registered in the map supports five validated scalar properties declared in the root `intake` dictionary:

\


| Field Name | Requirement | Definition & Validation Rule |
| - | - | - |
| `technical_name` | Mandatory | The well-understood practitioner short name derived from the leaf segments. Must exactly match the same number of leading words of the reversed, space-separated namespace address. |
| `name` | Mandatory | The canonical project title, brand identifier, or industry acronym (e.g., `"RX Ring Buffer"`, `"WAN"`). Must be non-empty and must **not** match `technical_name`. |
| `role` | Mandatory | Systemic functional classification from the controlled role taxonomy. |
| `uri` | Optional | Primary relative path or locator for the element. |
| `status` | Optional | Current lifecycle state of the element. |

### 3.2 Systemic Role Taxonomy

Each element must be assigned one of four systemic roles:

\


- **Definitive:** The element of the artifact under examination whose loss causes a mutation, meaning it no longer allows the artifact to remain what it is.

- **Supportive:** An indivisibly coupled element whose function is meant to assist the definitive element.

- **Notable:** A discrete, structurally independent feature or specialized exception case that possesses unique systemic significance.

- **Divergent:** An unaligned, weak, or redundant element captured during intake that deviates from the core architecture. This role must be investigated on the purpose it is serving, and either be realigned as repaired or improved, or ejected.

## Module 4: Root Intake and Layer Definitions

### 4.1 Root Registries

The project root (`.`) uses `intake` to identify the fields included in the base intake view. `system` and `layers` identify system entries and contextual layers.

\


- `intake`: A dictionary keyed by reserved field name. A key’s presence includes that field in the base intake view. Each value holds the field’s optional definition.

2. `system`: System-provided capabilities shared across projects: `skills`, `memory`, and `sources`. Agents maintain project memory through CRUD as described in its definition.

3. `layers`**:** Project-specific layers available for agent creation and population through instructions. A prompted layer acts as a metaprompt: the instruction defines the work and its scope, which can be a branch, a set of elements, or each element meeting a stated condition. The layer is registered by name in `layers`; additional fields describe its instructions, schema, or report template as needed.

### 4.2 Registry Entry Shapes and Optional Fields

The `intake` dictionary maps each field name to an object containing its optional definition:

| Form | Dictionary member | Meaning |
| - | - | - |
| Minimal | `"name": {}` | Presence establishes membership in intake. |
| Expanded | `"wants": {"description": "Direct functional dependencies between an originating element and a fulfilling provider element."}` | Additional fields describe the entry as needed. |

Each field name appears directly as a key in `intake`. An empty definition object is sufficient. Definitions describe the fields; element data retains its own types, including strings for scalar values and an array for `wants`.

Include definition fields according to need. Section 4.6 documents their purpose, value types, and interpretation.

\


- **Field Rules:** Apply grammatical constraints declared in an entry’s `fields` to the corresponding data fields. The `wants` definition below declares its rules for `why`, `how`, and `intent`.

- **Report Compilation:** Where a `template` is provided, the engine interpolates the entry’s field values into it to structure the human-readable report.

### 4.3 Root Registry JSON

A root with minimal intake definitions:

```json
{
  ".": {
    "intake": {
      "technical_name": {},
      "name": {},
      "role": {},
      "uri": {},
      "status": {},
      "wants": {}
    },
    "system": {
      "skills": {},
      "memory": {},
      "sources": {}
    },
    "layers": {}
  }
}
```

The following root expands `wants` with its description, sentence template, and field guidance. The other intake definitions remain empty.

```json
{
  ".": {
    "intake": {
      "technical_name": {},
      "name": {},
      "role": {},
      "uri": {},
      "status": {},
      "wants": {
        "description": "Direct functional dependencies between an originating element and a fulfilling provider element.",
        "template": "{originator.address} ({originator.name}) requires {provider.address} ({provider.name}) in order to {why}, which {how}.",
        "fields": {
          "why": {
            "part_of_speech": "Bare infinitive verb phrase",
            "rule": "State the active goal as a sentence fragment beginning with a base action verb. Do not include a leading 'to', subject nouns, or any words ending in -ing.",
            "example": "drain raw frames from the network interface card"
          },
          "how": {
            "part_of_speech": "Third-person singular present indicative verb phrase",
            "rule": "State how the provider satisfies the goal beginning with a present-tense verb ending in -s or -es that agrees with 'which'. Do not include subject nouns, 'by', or any words ending in -ing.",
            "example": "holds descriptor pointers across contiguous memory segments"
          },
          "intent": {
            "part_of_speech": "Controlled base verb",
            "rule": "Single lowercase base verb classifying the interaction transfer mode.",
            "example": "receive"
          }
        }
      }
    },
    "system": {
      "skills": {
        "description": "Skills Entries as defined by SEP-2640",
        "ref": "https://modelcontextprotocol.io/seps/2640-skills-extension"
      },
      "memory": {
        "description": "An adaptation of the sample memory graph provided by modelcontextprotocol.io, with prompts tailored to durable, atomic facts about the project. Agents maintain the relevance of these facts through create, read, update, and delete (CRUD) operations.",
        "ref": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory"
      },
      "sources": {}
    },
    "layers": {
      "{{prompted_layer_name}}": {
        "description": "{{description of prompted layer}}",
        "prompt": "{{instructions used to infer and create the layer, then run against the addressed elements to populate it}}"
      },
      "{{plugin_name}}": {
        "description": "{{description of plugin and when to use it}}",
        "ref": "{{plugin repository URL}}",
        "instruction": "{{instruction delivered once inline when the plugin or skill is triggered through ACP while the layer is active}}",
        "artifacts": [
          {
            "summary": "{{summary of artifact}}",
            "uri": "{{artifact uri in filesystem}}"
          }
        ]
      }
    }
  }
}
```

### 4.4 Prompted Layers and Namespace Inference

A prompted layer is a project-defined layer whose instruction acts as a metaprompt over addressed elements. The instruction specifies the work and its scope: a branch, a set of elements, or each element meeting a stated condition. The namespace supplies the functional context for inference.

Execution occurs in this order:

1. Infer the layer from the prompted instructions.

2. Create the layer and register its name in the root `layers` dictionary.

3. Run the prompt against the addressed elements and add the resulting data to the created layer.

The layer must be created before data is added by running the prompt against the elements.

### 4.5 Plugin Layer Example

A plugin layer associates artifacts produced by a plugin with the functionalities they refer to. The `egm` layer links review artifacts produced by Google Elephant Goldfish Model to every functionality referenced by each artifact, making the artifacts discoverable when an agent works at that functionality.

```json
{
  "egm": {
    "description": "Google Elephant Goldfish Model: Use it when a feature needs design decisions before implementation.",
    "ref": "https://github.com/google/elephant-goldfish-model",
    "instruction": "EGM artifact layer: egm",
    "artifacts": [
      {
        "summary": "{{summary of artifact}}",
        "uri": "{{artifact uri in filesystem}}"
      },
      {}
    ]
  }
}
```

The empty object in the example is a placeholder for another artifact entry. Each populated entry supplies an artifact summary and its filesystem URI.

When this layer is active and the plugin or skill is triggered through Agent Client Protocol (ACP), the layer’s `instruction` is delivered once inline to the agent. Here, “EGM artifact layer: egm” tells the agent to associate the produced artifacts with the relevant functionalities through the `egm` layer.

### 4.6 Special Field Types and Interpretation

Definition fields are included according to need. Their meanings are:

| Field | Value type | Purpose and interpretation |
| - | - | - |
| `description` | String | Informational description of the entry and its intended use. |
| `ref` | String | Informational reference to a specification, repository, or other supporting documentation. |
| `prompt` | String | Instructions used to infer and create a prompted layer, then run against the addressed elements to populate it, as described in Section 4.4. |
| `instruction` | String | Extra instructions delivered once inline to the agent when the plugin or skill is triggered through ACP while the layer is active. In the plugin-layer example, these direct the association of produced artifacts with functionalities in the map. |
| `fields` | Object | Definitions of the entry’s data fields, with the type or language guidance needed for each field. |
| `template` | String | Report format whose placeholders are filled from the corresponding data to produce readable output. |
| `artifacts` | Array of objects | References to produced artifacts associated with the functionality. Each entry contains `summary` and `uri`. |

Within a field definition, `type` describes the data type; `part_of_speech` supplies grammatical guidance for language content. `rule` describes the field’s stated requirements, and `example` illustrates its content. In an artifact entry, `summary` describes the artifact and `uri` identifies its filesystem location.

## Module 5: Storage vs. Agent Views & Protocol Operations

### 5.1 Nested Storage View (Internal Database State)

In storage, the tree is represented hierarchically. Root-level skills apply to the entire project, while element properties sit at their respective leaf nodes:

\


```json
{
  ".": {
    "intake": {
      "technical_name": {},
      "name": {},
      "role": {},
      "uri": {},
      "status": {},
      "wants": {}
    },
    "system": {
      "skills": {},
      "memory": {},
      "sources": {}
    },
    "layers": {
      "comprehension_reviewer": {},
      "design_critic": {},
      "zoom_out_review": {},
      "implementation_readiness": {}
    },
    "skills": 
      {
        "uri": "skill://git-workflow/SKILL.md",
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

  },
  "code": {
    "buffer": {
      "ring": {
        "packet": {
          "technical_name": "packet ring buffer",
          "name": "RX Ring Buffer",
          "role": "Supportive",
          "uri": "./src/buffers/rx_ring.c"
        }
      }
    },
    "pipeline": {
      "ingest": {
        "network": {
          "technical_name": "network ingest pipeline",
          "name": "Packet Intake Engine",
          "role": "Definitive",
          "uri": "./src/network/pipeline.c",
          "wants": [
            {
              "code.buffer.ring.packet": {
                "why": "drain raw frames from the network interface card",
                "how": "holds descriptor pointers across contiguous memory segments",
                "intent": "receive"
              }
            }
          ],
          "memory": [
            {
              "fact": "isolates receive descriptors from transmit completion queues"
            }
          ],
          "sources": [
            {
              "uri": "./src/network/pipeline.c"
            }
          ]
        }
      }
    }
  }
}
```

### 5.2 Flat Agent View & Query Protocol

Agents never interact with deep nested trees. Omitting the top-level command verb executes a **Read** query. The command `{"orphaned": {}}` executes an orphan scan and returns a bare JSON array of result objects.

\


- **Base Map Dump (`{".": {}}`):** Returns only fields named in `intake` across all elements.

- **Selective Layer Discovery (**`{".": {"layers": []}}`**):** Returns the registered layer definitions on root without loading the element map.

### Orphan Scan Results

The `orphaned` command detects unreferenced elements and returns a bare JSON array of single-key objects, each mapping an element address to its values. Each result is a separate array entry.

Run the scan with `{"orphaned": {}}`. The engine returns the array directly:

```json
[
  {
    "code.buffer.ring.packet": {
      "technical_name": "packet ring buffer",
      "name": "RX Ring Buffer",
      "role": "Supportive",
      "uri": "./src/buffers/rx_ring.c"
    }
  },
  {
    "code.buffer.ring": {
      "technical_name": "ring buffer",
      "name": "Base Ring Structure",
      "role": "Supportive",
      "uri": "./src/buffers/ring.c"
    }
  }
]
```

### 5.3 Orphan-Safe Deletion Lifecycle

An element cannot be deleted while any other element references it in `wants`.

\


1. **Attempt Direct Delete (Blocked):**

   \

```json
{ "delete": { "code.buffer.ring.packet": {} } }
```

2. **Execute Remediation (Sever Dependency / Orphan the Target):**

   \

```json
{
  "delete": {
    "code.pipeline.ingest.network": {
      "wants": ["code.buffer.ring.packet"]
    }
  }
}
```

3. **Verify Unreferenced Status via Orphan Scan:**

   \

```json
{ "orphaned": {} }
```

4. **Delete Orphaned Element:**

   \

```json
{ "delete": { "code.buffer.ring.packet": {} } }
```

## Module 6: Validation Engine & Error Remediation Reference

Every validation failure returns a deterministic error code, the violated rule, the broken compiled test sentence (where applicable), and the exact `remediation` payload required to fix it.

\


### 6.1 TECHNICAL_NAME_ALIGNMENT_FAILURE

- **Rule:** `technical_name` must match the same number of leading words of the reversed, space-separated namespace address (`"packet ring buffer code"`).

```json
{
  "update": {
    "code.buffer.ring.packet": {
      "technical_name": "ring packet buffer"
    }
  },
  "status": "error",
  "code": "TECHNICAL_NAME_ALIGNMENT_FAILURE",
  "message": "Invalid technical_name 'ring packet buffer' for address 'code.buffer.ring.packet'.",
  "expected_prefix": "packet ring buffer",
  "remediation": {
    "update": {
      "code.buffer.ring.packet": {
        "technical_name": "packet ring buffer"
      }
    }
  }
}
```

### 6.2 CANONICAL_NAME_COLLISION_FAILURE

- **Rule:** `name` is mandatory and must not equal `technical_name`.

```json
{
  "update": {
    "code.buffer.ring.packet": {
      "name": "packet ring buffer"
    }
  },
  "status": "error",
  "code": "CANONICAL_NAME_COLLISION_FAILURE",
  "message": "Mandatory field 'name' must differ from 'technical_name' ('packet ring buffer').",
  "remediation": {
    "update": {
      "code.buffer.ring.packet": {
        "name": "RX Ring Buffer"
      }
    }
  }
}
```

### 6.3 ROLE_TAXONOMY_FAILURE

- **Rule:** `role` must be one of `Definitive`, `Supportive`, `Notable`, or `Divergent`.

```json
{
  "update": {
    "code.buffer.ring.packet": {
      "role": "SE"
    }
  },
  "status": "error",
  "code": "ROLE_TAXONOMY_FAILURE",
  "message": "Invalid role 'SE'. Must be one of: Definitive, Supportive, Notable, Divergent.",
  "remediation": {
    "update": {
      "code.buffer.ring.packet": {
        "role": "Supportive"
      }
    }
  }
}
```

### 6.4 GRAMMAR_CONSTRAINT_VIOLATION (wants.why / wants.how)

- **Rule:** `why` must be a bare infinitive verb phrase; `how` must be a 3rd-person singular present verb phrase (`-s`/`-es`); neither may contain `-ing` words.

```json
{
    "update": {
        "code.pipeline.ingest.network": {
            "wants": {
                "code.buffer.ring.packet": {
                    "why": "to draining raw frames from the network interface card",
                    "how": "holding descriptor pointers across contiguous memory segments"
                }
            }
        }
    },
    "status": "error",
    "code": "GRAMMAR_CONSTRAINT_VIOLATION",
    "message": "Fields 'why' and 'how' violate part-of-speech constraints (no leading 'to', no '-ing' verbs).",
    "tested_sentence": "code.pipeline.ingest.network (Packet Intake Engine) requires code.buffer.ring.packet (RX Ring Buffer) in order to to draining raw frames from the network interface card, which holding descriptor pointers across contiguous memory segments.",
    "remediation": {
        "update": {
            "code.pipeline.ingest.network": {
                "wants": {
                    "code.buffer.ring.packet": {
                        "why": "drain raw frames from the network interface card",
                        "how": "holds descriptor pointers across contiguous memory segments"
                    }
                }
            }
        }
    }
}

```

### 6.5 LAYER_NOT_REGISTERED

- **Rule:** Agents cannot write to undeclared layers.

```json
{
  "update": {
    "code.pipeline.ingest.network": {
      "couplings": [{ "remote": "code.buffer.ring.packet" }]
    }
  },
  "status": "error",
  "code": "LAYER_NOT_REGISTERED",
  "message": "Cannot write to 'couplings': layer is not registered in project root 'layers'.",
  "remediation": {
    "delete": {
      "code.pipeline.ingest.network": {
        "couplings": []
      }
    }
  }
}
```

### 6.6 DEPENDENCY_LOCK

- **Rule:** Elements with inbound `wants` references cannot be deleted until orphaned.

```json
{
  "delete": {
    "code.buffer.ring.packet": {}
  },
  "status": "error",
  "code": "DEPENDENCY_LOCK",
  "message": "Cannot delete 'code.buffer.ring.packet' (RX Ring Buffer): required by 1 active dependent.",
  "reason": "code.pipeline.ingest.network (Packet Intake Engine) requires code.buffer.ring.packet (RX Ring Buffer) in order to drain raw frames from the network interface card, which holds descriptor pointers across contiguous memory segments.",
  "remediation": {
    "delete": {
      "code.pipeline.ingest.network": {
        "wants": [
          "code.buffer.ring.packet"
        ]
      }
    }
  }
}
```

## Module 7: Formatted Human-Readable Export Report

When a layer includes a report `template`, the engine uses it to render the layer’s data as formatted text:

\


> ### 1. Global Project Skills (system.skills)
>
> - Scope `.` exposes skill 'git-workflow': Follow this team's Git conventions for branching and commits (Resource: `skill://git-workflow/SKILL.md`).
>
>
>
> ### 2. Functional Dependencies (intake.wants)
>
> - `code.pipeline.ingest.network` (Packet Intake Engine) requires `code.buffer.ring.packet` (RX Ring Buffer) in order to drain raw frames from the network interface card, which holds descriptor pointers across contiguous memory segments.
>
>
>
> ### 3. Implementation Entry Points (system.sources)
>
> - Entry-point source for `code.pipeline.ingest.network` (Packet Intake Engine) resides at `./src/network/pipeline.c`.
>
> - Entry-point source for `code.buffer.ring.packet` (RX Ring Buffer) resides at `./src/buffers/rx_ring.c`.
>
>
>
> ### 4. Regional Durable Memory (system.memory)
>
> - Durable memory for `code.pipeline.ingest.network` (Packet Intake Engine): isolates receive descriptors from transmit completion queues.
>
>
>
> ### 5. Unbiased Architecture & Readiness Gates
>
> - **Comprehension Reviewer:** Comprehension review for `code.pipeline.ingest.network` (Packet Intake Engine) records status Clear, because the specification defines every packet boundary and byte offset explicitly.
>
> - **Design Critic:** Hostile design critique for `code.pipeline.ingest.network` (Packet Intake Engine) flags High risk, noting that the design drops tail frames silently when producer indices wrap before consumer locks release.
>
> - **Zoom-Out Review:** Macro architectural review for `code.pipeline.ingest.network` (Packet Intake Engine) rates alignment as Aligned, observing that the element transfers frames directly to kernel ring buffers without intermediate serialization layers.
>
> - **Implementation Readiness:** Implementation readiness check for `code.pipeline.ingest.network` (Packet Intake Engine) issues decision Go, verifying that the specification locks down struct layouts, error return codes, and memory barrier semantics.
