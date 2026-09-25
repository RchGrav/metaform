# Trace from source requirements to the spec

This table maps every requirement in REQUIREMENTS.md, read with REQUIREMENTS-corrections.md applied, and every entry in SETTLED.md to the spec records that carry it. The corrections file says none of its entries apply until Rich approves them; this trace reads them as proposed, and a row whose disposition rests on an unapproved correction stands only once that correction is approved.
Dispositions: covered; deferred, meaning nonces, assignment context or remote hosting; removed, with the reason from the corrections file; NOT COVERED, explained in the notes below the tables.

## REQUIREMENTS.md

| Source | Subject | Spec ids | Disposition |
|---|---|---|---|
| REQ-001 | The requirements are the product contract; older material is evidence | 00-index Authority | covered |
| REQ-002 | Requirements describe outcomes and invariants | 00-index Authority | covered |
| REQ-003 | Open choices do not block unrelated work; no invented semantics | 00-index Authority | covered |
| REQ-004 | No implementation self-ratification | QUAL-006, QUAL-012 | covered |
| REQ-010 | Project understanding is reusable working context | MAP-001 | covered |
| REQ-011 | Artifact independence, software and non-software | MAP-041, MAP-021 | covered |
| REQ-012 | Types and artifact realizations stay distinct | MAP-010, MAP-015 | covered |
| REQ-013 | An address names a Type; element identity survives retyping | MAP-010, MAP-012, MAP-015, STORE-007 | covered |
| REQ-014 | Elements and Entities are distinct concepts | MAP-042 | covered |
| REQ-015 | Encounter meaning belongs to the join; a join runs one way | MAP-003, MAP-020 | covered |
| REQ-016 | Joins are owned by their receiver and directly addressable | MAP-003, STORE-007, STORE-010 | covered |
| REQ-017 | Everything is a layer; one variable per layer; declared behavior; unknown content survives | LAYER-001, LAYER-002, LAYER-003, LAYER-004, STORE-021 | covered |
| REQ-018 | Root Types: media or asset, stakeholder or entity | MAP-014 | covered; record open |
| REQ-020 | Intake is an authored workflow | MCP-009, BASE-003 | covered; owning module open |
| REQ-021 | Canonical Intake semantics are preserved | MAP-013, MAP-040 | covered |
| REQ-022 | Intake begins coarse and remains extensible | MAP-030, MAP-040 | covered |
| REQ-023 | Annealed subtypes live inside their shared join | MAP-030, MAP-031, MAP-032, STORE-011 | covered |
| REQ-024 | Reasoning receives actual artifact evidence | MAP-043 | covered |
| REQ-025 | Native and latent reasoning are separate layers with their own provenance | LAYER-014 | covered |
| REQ-026 | Structural corrections are explicit revisions | LAYER-011, STORE-017 | covered |
| REQ-030 | The chassis is independently operable | BASE-001 | covered |
| REQ-031 | The chassis is the smallest shared base; no nonces; per-layer provenance | BASE-002, BASE-004 | covered |
| REQ-032 | Every feature is implemented in a module | BASE-003, BASE-004 | covered |
| REQ-033 | Every module follows the template contract | BASE-019 | covered |
| REQ-034 | Modules are self-contained, one file or one package | BASE-014 | covered |
| REQ-035 | Modules load from system, user and entry-point places | BASE-014 | covered; per-project place open |
| REQ-036 | Shipped and community modules use the same contract | BASE-004, BASE-014 | covered |
| REQ-037 | Discovery and activation are distinct | BASE-015 | covered |
| REQ-038 | Module lifecycle is owned and reversible | BASE-018, QUAL-010 | covered |
| REQ-039 | Module failures are isolated | BASE-018 | covered |
| REQ-040 | Modules interact through public contracts | BASE-004, BASE-010, STORE-023 | covered |
| REQ-041 | Public module-to-module invocation exists | none | NOT COVERED |
| REQ-042 | Platform limits belong to modules | BASE-015, BASE-016, QUAL-002 | covered |
| REQ-050 | Stable public services | BASE-004, STORE-023 | covered |
| REQ-051 | Public imports do not create competing runtimes | STORE-003, STORE-002 | covered |
| REQ-052 | Context follows operations | BASE-028 | covered |
| REQ-053 | Sync and async access are both supported | BASE-009 | covered |
| REQ-054 | Feature logic has one owning operation | BASE-006, MCP-003 | covered |
| REQ-060 | Modules declare their settings in code | BASE-008, CLI-010 | covered |
| REQ-061 | Configuration has one authoritative root | STORE-001, STORE-002 | covered |
| REQ-062 | Zero configuration; defaults are the working settings | CLI-020 | covered |
| REQ-063 | Hydration is additive and non-destructive | CLI-023 | covered |
| REQ-064 | Configuration survives module absence | CLI-024 | covered |
| REQ-065 | Glue; unset all skips glued; select from list or module data | CLI-013, CLI-016, CLI-017, CLI-019 | covered |
| REQ-066 | Installed and portable execution share configuration | BASE-023, BASE-025, STORE-030 | NOT COVERED |
| REQ-070 | Surface economy | CLI-005, CLI-006 | covered |
| REQ-071 | Command grammar and two kinds of help; progressive disclosure | CLI-001, CLI-005, CLI-006, CLI-007, CLI-008, CLI-009 | covered |
| REQ-072 | Module ownership remains visible | BASE-029 | covered |
| REQ-073 | Complete CLI | BASE-006, MCP-003 | covered |
| REQ-074 | Working context is folder settings; narrowing states the way back | CLI-021, CLI-022 | covered |
| REQ-075 | Assignment context | MCP-012 | deferred |
| REQ-076 | Navigation exit and work finalization stay distinct | CLI-022 | deferred |
| REQ-077 | Help is generated from live contributions | CLI-010, MCP-007 | covered |
| REQ-078 | Interactive and non-interactive use are equivalent | CLI-025, MCP-014 | covered |
| REQ-079 | Concise settings screen | CLI-026 | covered |
| REQ-080 | Work identity by nonce | MCP-012 | deferred |
| REQ-081 | Assignment delivery is exact | MCP-012 | deferred |
| REQ-082 | Submission uses the assignment header | MCP-012 | deferred |
| REQ-083 | The working-folder table lives in the home; nothing marks project folders | STORE-002 | covered |
| REQ-084 | MCP uses the same work identity | MCP-012 | deferred |
| REQ-085 | One MCP process serves many assignments | MCP-012 | deferred |
| REQ-086 | MCP serves the folder's command surface from the CLI declaration | MCP-003, MCP-004 | covered |
| REQ-087 | Harness participation is vendor-independent | MCP-009, MCP-016 | NOT COVERED |
| REQ-090 | Modules may be sync, async or both | BASE-009 | covered |
| REQ-091 | Long-running work returns a trackable receipt | BASE-030 | covered |
| REQ-092 | Work survives the initiating client's exit | BASE-030 | covered |
| REQ-093 | Background work has explicit ownership | BASE-018 | covered |
| REQ-094 | Cancellation state is truthful | BASE-031 | covered |
| REQ-095 | The event bus is shared infrastructure | BASE-010 | covered |
| REQ-096 | Event request and response reach a terminal outcome | BASE-032 | covered |
| REQ-097 | Events do not become a second workflow engine | BASE-033 | covered |
| REQ-100 | One common object and reference model | STORE-007, STORE-023 | covered |
| REQ-101 | Exact read revisions recorded | LAYER-010, STORE-016 | removed: provenance is one record per layer, nothing per item or per read |
| REQ-102 | Mandatory detailed inference provenance | LAYER-010, STORE-016 | removed: replaced by the per-layer provenance record |
| REQ-103 | Non-inference provenance is truthful | LAYER-010, STORE-016 | removed: replaced by the per-layer record; a person-written layer's record is open |
| REQ-104 | Producing occurrence and content identity are distinct | LAYER-010 | removed: replaced by the per-layer provenance record |
| REQ-105 | One-reference provenance inspection | LAYER-010, STORE-016 | removed: replaced by the per-layer provenance record |
| REQ-106 | Immutable layers change by revision; mutable layers in place | LAYER-011, LAYER-012, STORE-017, STORE-018 | covered |
| REQ-107 | Identity survives relocation | STORE-007, STORE-027 | covered |
| REQ-108 | All data is global under the home | STORE-001 | covered |
| REQ-109 | Durable writes are recoverable | STORE-006, STORE-027 | covered |
| REQ-110 | Existing data is preserved | STORE-029 | covered; migration of chassis-branch stores open |
| New | Direct indexed access; a whole layer or all layers at a node is one read | STORE-005, STORE-025, LAYER-008 | covered |
| REQ-120 | Knowledge attaches locally | LAYER-003, STORE-015 | covered |
| REQ-121 | Select and mask rule | LAYER-007, STORE-019 | covered |
| REQ-122 | Selection applies on every context path | LAYER-007, STORE-028 | covered |
| REQ-123 | Unsupported selection stays explicit | LAYER-007 | covered |
| REQ-124 | Hiding follows dependencies between layers | LAYER-006 | covered; record open |
| REQ-125 | Generated knowledge records its sources | LAYER-010 | removed: covered by the per-layer provenance record |
| REQ-126 | Memory follows the reference memory server over the map's nodes | LAYER-013, STORE-020 | covered |
| REQ-127 | Memory is mutable in place with no provenance | LAYER-012, STORE-018 | covered |
| REQ-128 | Memory uses the normal CLI and MCP surfaces | LAYER-013, MCP-003 | covered |
| REQ-130 | Rules belong to operations | none | NOT COVERED |
| REQ-131 | Rule content remains authored content | none | NOT COVERED |
| REQ-132 | Rules are inspectable and editable | none | NOT COVERED |
| REQ-133 | Operations apply their rules | none | NOT COVERED |
| REQ-134 | Issued rule revisions are retained | none | NOT COVERED |
| REQ-140 | Workflows preserve authored intent | none | NOT COVERED |
| REQ-141 | Serialization and semantic conversion are distinct | none | NOT COVERED |
| REQ-142 | Canonical workflow representation preserves meaning | none | NOT COVERED |
| REQ-143 | Workflow context stays object-bound | none | NOT COVERED |
| REQ-144 | Lexicalization is explicit | none | NOT COVERED |
| REQ-145 | Issued prompts are exact snapshots | none | NOT COVERED |
| REQ-146 | Workflow revisions and runs are independent | none | NOT COVERED |
| REQ-147 | Replay may reuse prior work | none | NOT COVERED |
| REQ-148 | Human waits remain human waits | none | NOT COVERED |
| REQ-149 | Workflow execution is CLI-complete | none | NOT COVERED |
| REQ-150 | Workflow upload preparation is module-owned | none | NOT COVERED |
| REQ-160 | Artifact boundaries are consistent | none | NOT COVERED |
| REQ-161 | Navigation markers are not artifact edits | STORE-001 | covered |
| REQ-162 | Origins and variants stay distinct | none | NOT COVERED |
| REQ-163 | Reconstruction works without the original repository | none | NOT COVERED |
| REQ-164 | Portable continuation includes pending physical work | none | NOT COVERED |
| REQ-165 | Import preserves divergent history | STORE-027 | covered; conflict handling open |
| REQ-170 | The wheel is directly executable | BASE-023 | covered |
| REQ-171 | Direct wheel use needs no permanent installation | BASE-023 | covered |
| REQ-172 | Cold offline execution | BASE-024 | covered |
| REQ-173 | Hosted-agent execution is a primary case | BASE-024 | covered |
| REQ-174 | Runtime preparation is isolated from durable state | BASE-023, STORE-030 | covered |
| REQ-175 | Selected modules mean selected implementations | BASE-022 | covered |
| REQ-176 | Packaging derives dependencies from module ownership | BASE-022, BASE-026 | covered |
| REQ-177 | Native dependencies produce accurate compatibility tags | BASE-024 | covered |
| REQ-180 | Before 1.0 free; from 1.0 lowest chassis version plus capabilities | BASE-020 | covered |
| REQ-181 | Compatibility is behavioral | BASE-020 | covered |
| REQ-182 | Older writers preserve unknown data | STORE-021 | covered |
| REQ-183 | Minor and patch evolution is non-destructive | BASE-020, STORE-029 | covered |
| REQ-184 | Wheel execution does not corrupt the installation | BASE-023 | covered |
| REQ-185 | Runtime code origin is deliberate | BASE-023 | covered |
| REQ-190 | Web is optional | none | NOT COVERED |
| REQ-191 | Web uses the same operations | none | NOT COVERED |
| REQ-192 | Web presentation is polished | none | NOT COVERED |
| REQ-193 | Web technology is not an invariant | none | NOT COVERED |
| REQ-194 | One global web instance | none | NOT COVERED |
| REQ-195 | Web authentication belongs to the web module | none | NOT COVERED |
| REQ-196 | Browser terminal is a separate optional module | none | NOT COVERED |
| REQ-200 | Every shipped module has a developer README | BASE-034 | covered |
| REQ-201 | The template demonstrates the current contract | BASE-019 | covered |
| REQ-202 | One template module with README and tests | BASE-019 | covered |
| REQ-203 | Documentation exposes actual ownership | QUAL-013 | covered |
| REQ-210 | Verify externally observable behavior | QUAL-006 | covered |
| REQ-211 | Semantic and mechanical correctness are distinct | QUAL-006, QUAL-008 | covered |
| REQ-212 | Fixtures and real providers are labeled accurately | QUAL-014 | covered |
| REQ-213 | Zero-module acceptance | BASE-001 | covered |
| REQ-214 | Module removal acceptance | BASE-017, BASE-018 | covered |
| REQ-215 | Offline wheel acceptance is end to end | BASE-024 | covered |
| REQ-216 | Same-major compatibility tested in both orders | BASE-020 | covered |
| REQ-217 | User-facing polish is acceptance-relevant | CLI-005, CLI-006, MCP-013, MCP-018 | covered |
| Section 20 | Remediation instructions from the old audit | none | removed: recommended removal, awaiting confirmation |

## SETTLED.md

| Source | Subject | Spec ids | Disposition |
|---|---|---|---|
| S-01 | The chassis runs completely on its own as a CLI | BASE-001, BASE-002 | covered |
| S-02 | The chassis does not run workflows; MCP is a module | BASE-003, MCP-001 | covered |
| S-03 | Modules may use everything the chassis offers | BASE-004 | covered |
| S-04 | Every module starts from the template, with a changelog | BASE-019 | covered |
| S-05 | Template and demo modules ship disabled | BASE-017 | covered |
| S-06 | Module data goes through the data access object as a layer | BASE-005, STORE-022, STORE-023 | covered |
| S-07 | Repo wheel carries every module; local build carries enabled ones | BASE-022 | covered |
| S-08 | A wheel runs directly from its own subfolder | BASE-023, STORE-030 | covered; per build or per name open |
| S-09 | A directly run wheel works in hosted code execution | BASE-024 | covered |
| S-10 | Installing a wheel merges its data | BASE-025 | covered; meaning of merge open |
| S-11 | Metaform offers to maintain a user's fork, CI and wheel | BASE-027 | covered |
| S-12 | pyproject.toml, uv, and uvx launch | BASE-021, MCP-010 | covered |
| S-13 | Distribution name undecided | BASE-021, MCP-010 | covered; open |
| S-14 | The chassis depends only on stdlib and pure-Python packages | BASE-026 | covered |
| S-15 | MCP uses the official SDK's server | MCP-002 | covered |
| S-16 | Remote hosting later | MCP-012 | deferred |
| S-17 | Linux, macOS and Windows by default | QUAL-002, MCP-023 | covered |
| S-18 | Modules state compatibility; a verb may narrow its own | BASE-015, BASE-016 | covered |
| S-19 | CI on all three systems, template CI the same | QUAL-003 | covered |
| S-20 | Polished setup | MCP-013 to MCP-020 | covered; first-test subset open |
| S-21 | The installer asks by default; named tools or all set up without asking | MCP-014, CLI-002 | covered |
| S-22 | One fixed skill copied to each chosen tool's global folder | MCP-021 | covered |
| S-23 | Each skill path is proven by a loading test | MCP-022 | covered |
| S-24 | Project selection when the host starts outside the folder | MCP-011 | covered; open |
| S-25 | Each module adds concise instructions deferring to help | BASE-012, MCP-008 | covered |
| S-26 | No intake: delegate to a subagent that reads its instructions by name | MCP-009 | covered |
| S-27 | `--` ends switch parsing | CLI-003 | covered |
| S-28 | Every long switch is a setting | CLI-011 | covered |
| S-29 | `--confirm` is never a setting | CLI-018, BASE-013 | covered |
| S-30 | The schema lists every setting with its system default | CLI-010 | covered |
| S-31 | Booleans have two forms and never toggle | CLI-015, CLI-016 | covered |
| S-32 | Module switches are settings | CLI-012, BASE-007 | covered |
| S-33 | code_quality_standards.md is the bar | QUAL-001 | covered |
| S-34 | Tests exist only to protect the design | QUAL-006 | covered |
| S-35 | Type checking, lint, three-system runs, critic review | QUAL-003, QUAL-004, QUAL-005, QUAL-008 | covered |
| S-36 | The first working test | MCP-024 | covered |
| S-37 | Open: REQ-018 roots | MAP-014 | covered; open |
| S-38 | Open: REQ-035 per-project module place | BASE-014 | covered; open |
| S-39 | Open: REQ-124 hiding by dependency | LAYER-006 | covered; open |
| S-40 | Open: Section 20 removal | none | removed: recommended, awaiting confirmation |

## What the spec lacks for each NOT COVERED row

- REQ-001, REQ-002, REQ-003: carried by the Authority section of 00-index.md.
- REQ-041: whether a module can call another module's public operation beyond events is open question 7 in 04-chassis-modules.
- REQ-066: confirmed design gives a directly run wheel its own data subfolder, BASE-023 and STORE-030, which contradicts sharing one configuration. Whether REQ-066 is retired, or reconciled through merge on install, BASE-025, needs Rich's answer.
- REQ-087: MCP-009 covers operation from inside any host. Launching a configured harness conflicts with the confirmed rule that Metaform never launches a model, and no correction retires it. The deterministic local fixture is not specified.
- REQ-130 to REQ-134: the rulebook is not in the spec.
- REQ-140 to REQ-150: the workflow module is not in the spec. BASE-003 places workflows in modules and MCP-009 delivers intake instructions by name, but workflow execution, representation, snapshots, revisions, replay, human waits and CLI completeness are unspecified.
- REQ-160, REQ-162, REQ-163, REQ-164: artifact history, origins and variants, reconstruction and portable continuation are not in the spec.
- REQ-190 to REQ-196: the web and browser terminal modules are not in the spec.

## Records that carry build detail for other records

These records were added to close gaps a builder would otherwise guess at. Each serves the records named, not a source requirement of its own.

| Record | Serves |
|---|---|
| STORE-031 | MAP-041, STORE-002, CLI-001 |
| STORE-032 | MAP-040, LAYER-001, MCP-009 |
| STORE-033 | STORE-017, STORE-024 |
| STORE-034 | STORE-017, MAP-015 |
| STORE-035 | LAYER-005, LAYER-007 |
| STORE-036 | LAYER-011 |
| STORE-037 | STORE-006 |
| BASE-035, BASE-036, BASE-037 | BASE-004, BASE-006, BASE-014, CLI-001, MCP-003 |
| BASE-038 | STORE-024, STORE-025, MCP-003 |
| BASE-039 | MCP-009, MAP-040 |
| BASE-040 | LAYER-013 |
| BASE-041, BASE-042 | BASE-022, BASE-023, BASE-024 |
| BASE-043 | CLI-001, CLI-011 |
| CLI-027, CLI-028, CLI-029, CLI-030 | CLI-005, CLI-007, CLI-021, MCP-005 |
