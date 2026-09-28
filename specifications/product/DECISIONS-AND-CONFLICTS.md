# Historical decisions, source conflicts and implementation choices

> **Superseded ledger.** [REQUIREMENTS.md](../REQUIREMENTS.md) is the sole
> governing product contract. The decisions and conflicts below preserve the
> September 16 review; their old open questions do not add obligations or stop
> current remediation. Use [section 20](../REQUIREMENTS.md#20-remediation-instructions)
> and the [live matrix](../REMEDIATION-MATRIX.md) for active work.

This ledger accompanies the historical [product consolidation](PRODUCT-SPECIFICATION.md).
Source keys resolve in [SOURCES.md](SOURCES.md). Retained quotations are evidence
of the earlier discussion, not a parallel current requirements register.

## 1. Settled corrections from the supplied conversation

The quotations below are short verbatim anchors from the conversation provided for
this task. The descriptions consolidate the surrounding clarification. They are
not a complete transcript, and no message timestamps are invented.

| ID | Settled meaning | Conversation anchor and supersession |
| --- | --- | --- |
| D01 | Current base `asset` replaces `media`; preserve historical source references. | “the base object called media is going to be renamed asset” — supersedes old base lists. |
| D02 | Joins live inside their Receiving Entity's namespace-addressed record; other system objects remain addressable. | “actually I take that back joins live in a namespace_address record.. joins need to be with the receiving entity always” — supersedes the preceding suggestion of independent join records. |
| D03 | Chassis owns concrete shared services; executable external modules contribute features. Build the fresh object-based chassis against this direction. | “none of the old code is aligned to the current spec … its all object based tracking now”; public import example `from metaform import settings, event, cli`, followed by `data`. |
| D04 | Initial storage is all-global, one user-folder root/database with project ownership; sources stay in place. | “how about all global initially” / “we can evolve from there” — supersedes requiring repo-local state in the initial design. |
| D05 | Project selector starts all ones; each object's selector starts zero and mask all ones. | “its project level … layer_select is all 0 and layer mask is all 1's in every object project level has a layer select … all 1's”. |
| D06 | Selection travels trunk toward leaves; mask filters incoming selection before local selection. Workflows observe the same masks. | “layer_select flows up and the mask is under it” plus “for a workflow it has a workflow layer select and observes the masks in the objects”. The earlier base-level and reversed-order explanations are superseded. |
| D07 | Hiding a contributing object hides derived inference; each layer also has a general-graph default visibility flag. | “if you hide an object from the graph … any layers that were derived from that would also be hidden”; “each layer has a flag for the general knowledge graph”. S09 records a later clarification about any directly used prompt source; see C07. |
| D08 | Inference can add knowledge at objects **and their owned joins**; memory is a basic layer indexed by the Metaform. | “for each object individually and its set of joins”; “agent can make a memory layer indexed by the metaform”. Supersedes treating a particular older Knowledge Tool's question policy as a platform-wide limit. |
| D09 | Hooks support sync and async; agents/harness responses must be nonblocking; request and response use the same event system. | “chassis should expose a way for modules to participate async or sync or both, agents should be async”; “have the response come back when its done.. but not block”. |
| D10 | Three demonstration modules: standalone all-service hello-world template plus two derived event participants. Real harness examples support both Codex and Claude. | “3 modules, 2 that show the event system working and then a template … hello world … all the different hooks”; “codex or claude both”. Supersedes intermediate two-module/template interpretations. |
| D11 | Modules are a single Python file or folder copied into plugins. Disabled policy is a text file named exactly `disabled`. | “a module can be a single file or a folder copied into the plugins folder”; “make the file disabled” — supersedes `disable`. |
| D12 | Module Python declares help and settings, dynamic settings sections hide on removal but values survive. BIOS-style menu and CLI share set/unset; glue preserves a user-owned baseline. | “removing the modules hides the settings but keeps them incase the module comes back”; “the python embeds help into its module”; “reset to a baseline you own”. |
| D13 | Module entry replaces the base surface, hidden working-folder binding persists it, exit restores the main surface. Assignment nonce/header identifies work. | “activate the module have it make a hidden file in your working folder … when you exit it returns you to main”; “reject submissions without [the header]”. Exact lifecycle mapping is C10. |
| D14 | Web remains a removable global plugin, one instance/port; commands `web`, `web stop`; bind hostname/IP and port are plugin settings. | “the web plugin has two commands web, web stop”; “bind to localhost or 0.0.0.0 and port”; “or a specific ip”. |
| D15 | Complete CLI access and executable-wheel upload operation are required. Workflow preparation/execution is workflow-module owned. | “support 100% cli … running the wheel by its entrypoint … uploading to web based systems”; “this would be part of the workflow module”. |
| D16 | The sample architecture and generated Metaform are guidance, not a complete or verified contract. Consolidate all sources before relying on them. | “use my suggestion loosely it wasnt checked”; “its probably incomplete … this was just guidance”; latest request for “the combined thing that your understanding will be built from”. |

Additional exact recovery decisions are preserved in S15: Click; XML → dictionary
using ElementTree and XML/JSON round trips; context as referenced objects in the
workflow editor; intake as a real workflow; object-oriented provenance from the
outset. The historical withholding of Native joins/OPs from Latent is superseded
by the complete-Native-account rule in S02/S04 and the supplied conversation.

## 2. Genuine source conflicts and incomplete mappings

These items retain the alternatives actually found. They do not ask Rich to repeat
settled decisions or invent approval gates. Resolve them in the combined record
before implementing behavior that depends on the disputed meaning.

### C01 — Element roles, join roles and Notable

**Sources:** S02 §2 uses `property`/`requirement`, open classification and `is_soft`;
older semantic definitions use hard dependency/property/supportive. S05 intake
explicitly emits DE/SE/NE and TARGET, while older semantic clarification retires
Notable as a separate category.

**Known:** Preserve the authored intake and distinguish Element classification,
relationship role and typed executable join entry. **Unresolved:** which vocabulary
is current at each layer and the lossless mapping between these sources. Do not
rename NE to another term or force TARGET into a dependency enum. A schema-only
rename would alter operative meaning without settling it.

### C02 — Shallow intake scope and actual artifact detail

**Sources:** S02 §2/capability 16 calls for the exterior receiver of the DE and the
actual Native functional account; §10 explicitly excludes that receiver and
Encounters from shallow shape. S05 constrains artifact-specific instance data to
OP and begins with DE as initial RE. S04 says actual artifact understanding is
recorded separately from universal Type Description.

**Known:** Base shape is coarse, Type-focused; deeper inference is possible; Latent
receives everything Native actually recorded. **Unresolved:** exactly which record
contains the actual account, whether exterior receiving purpose belongs to shallow
or a later pass, and whether current XML restrictions apply to base construction
or the whole namespace. The current linked-property use of `code.cpp.cxx23` is
settled; the XML statement that `code.cpp` is invalid cannot be applied as a global
prohibition. Do not merge these sources into an invented mandatory sequence.

### C03 — Type, Element and namespace record envelope

**Sources:** S02 §5 uses distinct Type/Element/binding records; S05 RE schema stores
EF/name length/aliases/joins in an RE shape; D02 places owned joins in their
namespace object. S05's RE schema lacks the outer `namespace_address` envelope.

**Known:** Universal Type meaning and actual artifact facts remain distinguishable;
each namespace object has a record; joins remain owned. **Unresolved:** new canonical
record kinds and Type-to-artifact binding representation. Existing legacy tables
or the generic chassis Record class do not settle that schema.

### C04 — Names, joins, combined entities and reference encoding

**Sources:** Name rule and S02 use `length`; XML, current conversation and RE schema
use `name_length`. Intake prose describes `re`/`pe`; its nested final XML implies
RE by ownership. XML examples omit schema-required aliases.

**Known:** Name length is a leaf-backward lookback count, including reused
components. Combined/inactive entities must remain addressable. **Unresolved:**
canonical field name, source-preserving adapters, owned-join paths, combined-entity
references and executable typed-entry envelope. Do not invent aliases or semantic
values just to pass a validator.

### C05 — Final XML versus incremental object submissions

**Sources:** S05 requests a final XML response; later material in S10's original
account proposes live object puts via MCP/CLI.

**Known:** Preserve the actual answer and source provenance; accept the required
header for assignment attribution. **Unresolved:** how an authored final XML
workflow relates to incremental updates, their provenance/transaction boundary and
the event at which its foundation is complete. Both could be supported, but that
is not yet a selected execution contract.

### C06 — Parametric representation

**Sources:** S02 and semantic sources define a Type tunables array and reserved
names; S05 shallow intake says never to enumerate Parametric elements.

**Known:** Tuning alone does not constitute the relevant semantic transformation
acceptance. **Unresolved:** whether the array is later/deep metadata, belongs to a
different source format, or needs an explicit revision. Do not add it to current
shallow output merely to satisfy an older schema.

### C07 — Layer visibility, dependencies and selector contexts

**Sources:** D05–D07; S06 D04/D05; S09 `/knowledge_layer/basis` and guidance
E03.03/J09.01–03.

**Settled:** project/object defaults; mask-before-local-select; workflow observes
object masks; hiding an inference source hides dependent inference. The generated
guidance explicitly attributes a later clarification to the user: hiding **any**
node directly used in a generation prompt hides the generated knowledge, cascading
to dependents. Preserve that attribution; it is not an independently available
verbatim message in this consolidation.

**Unresolved:** saved project versus nonce-specific hiding scope; visibility flag
versus explicit selection precedence; selector bit allocation/versioning; per-step
versus workflow selection; and the stored unit of a multi-output generation when
only some inputs or subjects are hidden. The source dependency and attachment
target must be distinct whichever unit is selected. A selected bit is not evidence
that hidden-source knowledge is visible. S09 implementation/cache recipes remain
guidance until adopted.

### C08 — Knowledge Tool recipe versus general inference

**Sources:** S02 §8 specifies Type-base/whole-composite questions, no separate join
targets and no property powerset. D08 and S09 explicitly target objects and joins.

**Known:** The platform supports object-and-join inference; unrestricted powerset
enumeration was an observed defect, not a requirement. **Unresolved:** retain the
older recipe as one named operation, revise it, or replace it with another
explicitly authored recipe. Its preview/answer-array shape must not become a
universal restriction on other modules' inference output.

### C09 — Native XML grammar and context tags

**Sources:** S15 XML/ElementTree correction; S05 and S14 variants; S11 historical
JSON-native grammar.

**Known:** XML/dictionary/JSON round trip, authored behavior preservation, referenced
context, mixed/ordered/repeated XML structures and embedded schemas. **Unresolved:**
canonical workflow tags/schema, reference and automation-entry encoding, and
whitespace/comment fidelity. Old executable operations (prompt/user/branch/foreach/
call/parallel/tool) describe necessary behavior; they do not automatically settle
new XML fields. The sample files are alternatives, not mutually mandatory grammars.

### C10 — Nonces, context boundaries and completion

**Sources:** S02 §9 and §13; S06 D02/D03/D08; S07/S08 current implementation; D13.

**Settled:** explicit nonce/header attribution; `.agentid/nonce` restored; module
navigation marker; contextual surface replaces the base; completion/abort retain
history and clear the active binding; process IDs do not identify logical agents.

**Outstanding source details:** workflow-definition revisions mint workflow nonces;
eight-character hashed/random agent nonces; 24-hour inactivity behavior; per-step
versus per-run nonce lifetime; original `done` (delegated assignment) versus
`complete` (admin-context exit); project-main-folder-only orchestration and
self-assigned admin; whether CLI finalization is compulsory after MCP writes.

The implemented generic chassis uses submit to record an answer, complete/abort to
settle assignment work, and exit to detach navigation. This is documented evidence,
not an implicit cancellation of the older workflow-specific requirements. Compare
one single-step and one multi-step interaction to settle the mapping, including
when selection/header changes and when markers disappear. S02's 24-hour/read-only
help rules also require explicit comparison with the persistent host.

### C11 — Provisioning and built-in guidance state

**Sources:** S02 §§12–14; S07/S08; global-data S10.

**Known:** usable point-of-use guidance, dynamic module/workflow catalog, a functional
Metaform teaching the chassis interfaces, and unfamiliar-harness provisioning.
The SPEC says that built-in account is omitted from the selected-project viewer
and cannot be removed through user operations.

**Unresolved:** how `provisioning.json` and harness-binary-parent familiarity map to
the global settings/data contract, and which older startup routes remain exposed
in the fresh contextual CLI. The chassis's retained administrative guidance and
removable feature modules are different responsibilities.

### C12 — Global web surface

**Sources:** S02 §13 describes `web`, `web stop`, `web status`, default 8642, opening
the current/last project and `/projects`; D14 requests the two-command plugin and
basic bind/port settings. S07/S08 implement the initial plugin.

**Known:** one global web instance/public port, web-owned commands/settings and
removability. **Unresolved:** whether a dedicated `web status` remains or status
appears through the general chassis surface, exact default port and when changing
bind/port affects a running listener. Workbench capabilities remain required even
though the initial web plugin is smaller. Historical random per-project endpoints
are not the current deployment model.

### C13 — Portable representation and version compatibility

**Sources:** S12 describes JSON knowledge/local SQLite execution and relationship
closure; S02 §14 describes shared installed/wheel data and refusing an out-of-date
installed copy; D04 selects one global initial store and D15 executable uploads.

**Known:** independent selected-project export, complete needed assets and pending
work, Python operation without original home/service/Git, retained provenance,
continued work and re-export. **Unresolved:** exact portable representation and
schema compatibility checks, coexistence with an installed copy, executable closure
for embedded joins, and eventual connected reconciliation. A hypothetical merge
protocol or automatic upgrade is not a requirement already agreed here.

### C14 — Artifact history details

**Sources:** S10 current global pattern and original data-folder account.

**Known:** full origin identities; both derived lineage IDs; common-origin variants;
changed binaries whole; Python reconstruction; preserved divergent imports.
**Unresolved:** exact 3 MB threshold calculation/units, concrete on-disk payload
layout, suffix allocation details and mapping old parent-chain archives into the
common-origin model. Preserve old histories during that mapping. Artifact source
boundaries must be consistent across capture, diff, application and export; the
hidden discovery markers must not become project edits.

## 3. Engineering choices, proposals and historical evidence

| Topic | How this consolidation treats it |
| --- | --- |
| `Plugin` dataclass; typed `Record`, `RecordRef`, `Producer`, Assignment and Job; service signatures | Current engineering contract in S08; no claim that generic records complete the semantic schema. |
| Background host, local authenticated RPC, SQLite implementation, context variables | Current chassis mechanisms supporting async/persistence; not requirements for a distributed message broker or untrusted-code sandbox. |
| Click | Explicitly selected. The pasted `MultiCommand` snippet, shortened UUID and two-table schema were unchecked guidance. |
| ASGI/Uvicorn/Starlette | Recommended then used in the web slice; not an immutable product constraint. |
| attrs/cattrs, Pydantic, jsonschema | Discussed choices; no universal schema-library mandate established. Current dataclasses are implementation evidence. Pandas is not required. |
| Generated specs Metaform and 94-directive layer | Functional map and attributed engineering guidance, explicitly incomplete; no blanket promotion of every directive into the PRD. |
| Workbench colors, exact old route/command names, legacy tables/JSON layouts | Historical implementations; preserve user outcomes and explicit constraints, reconcile exact current interfaces. |
| Ladybug/Cypher | Explicitly retired in subsequent docs; do not restore from older plans. |
| Remote command-and-control work packets | Future external module; first chassis delivery does not require it. |
| Image generation | Retained optional capability in earlier feature inventory; expanded presets and particular photo workflows remain proposals. |
| Automatic improvement of Metaform workflows from accumulated provenance | Expressed opportunity; adoption/evaluation mechanism not settled. |
| Actual fixture, harness, wheel and historical workbench checks | Evidence for their precise source/scenario only. Not whole-product semantic acceptance. |

## 4. Review discipline

This ledger records why sources differ; it is not an additional runtime validator.
When a decision is made, record its wording/source here and update the corresponding
requirement. Keep original source text available. Do not change authored prompts,
rewrite deleted drafts into place, or alter source data merely to make this ledger
look resolved.
