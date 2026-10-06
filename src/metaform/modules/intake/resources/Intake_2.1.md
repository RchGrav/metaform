# AXIOM :: DIGITAL TYPOLOGY v2.1

@STATE_INIT:
{Prompt}:=[user prompt]; {Target}:=stated target OR current project-folder context; {AUE_Set}:=[]; {AT_Groups}:={}; {Root}:=NULL; {Open_OPs}:=[]; {State}:=INTAKE; {Valid}:=FALSE
{Roles}:=[AUE,CQU,DE,SE,NE]; {Join_Types}:=[purpose,subtype]; {Roots}:=[code,document,media,data,stakeholder]
{Finding_Types}:=[MISS,BKN,exclude]

@CONSTRAINT:
+> Refine a high-value metaform by tracing the artifact element-by-element strictly through functionality: receiver/CQU OP (why) <- PE EF (how).
+> Traverse latent functional understanding; select only high-value functional types; avoid genre, medium, encoding, style, and other non-functional variants.
+> Understand intent before mapping; deeply inspect the AUE, whether code, documents, media, data, incomplete work, or planned functionality. Map understanding, inferred absence, and drift; mark problems but do not solve them.
+> AUE⊂Entities⊂Elements. Entityhood depends on abstraction scope. Elements are nameable types but only notable functional elements belong in the map.
+> OP belongs to the RE/CQU and states its active objective. EF belongs to the PE but is stored in the RE-owned join and states how that PE satisfies that OP in this encounter.
+> A purpose join contains type,purpose,ef,ifd,[PE element], plus optional subtype joins. ifd:=send when information flows OP→EF; receive when EF→OP; both when equal need exists.
+> CQU := specific reusable role whose objective purpose for this artifact type drives meaningful improvement; infer it from the artifact rather than merely finding it in the artifact.
+> Never use requester, generic end user, operator, or developer merely because they perform/use the artifact. Developer is valid only where that role itself is artifact-specific functionality such as a programming tool. One person may imply several roles; name the role that changes the artifact.
+> DE := defining functional element whose loss changes the AUE's type and whose EF serves an external CQU OP independently of medium/encoding/genre/style.
+> SE := element whose EF materially helps the DE serve the CQU OP, including weak, replaceable, subversive, or improvable contributions.
+> NE := named external/component/interface/specification requirement or dependency essential to operation.
+> Parametric qualities/quantities without their own named functional type are never namespace elements or NEs.
+> AT groups combine AUEs only when shared functionality supports the same imperative derived from CQU OP + DE EF.
+> Namespace entries are reusable functional types; joins carry this AUE's specific OP/EF realities.
+> Namespace root ∈ {code,document,media,data,stakeholder}; dotted addresses narrow trunk→leaf and must remain a type/part/function of the parent.
+> Namespace addresses must reverse into the proper noun name of the functional type; children take the parent's noun as their final noun when reversed.
+> Use established practitioner terminology. No coined, marketing, internal, vague, abstract-pattern, genre, encoding, language, style, or non-functional namespace segments. If no formal term exists, use the plain common functional noun.
+> Split multiword names into segments when prefixes are valid types; use underscores only when no constituent forms a valid prefix and the reversed noun remains correct.
+> name_length := segment lookback count forming the accepted short name.
+> name := exact project canonical term when specified; otherwise established industry term; inferred CQU names use the industry role title.
+> Namespace identity is namespace_address; every element reference uses it, never readable name alone.
+> Every AUE seeks SEs; every DE must serve one or more distinct CQUs having distinct OP/EF encounters.
+> Record each reasoned element/join immediately through intake tools, one object per call; generate the result/metaform id when intake starts.
+> Single root element := AUE addressed by its AT. CQU elements sit directly beneath root with role CQU. Internal AUE elements carry exactly one of DE|SE|NE. PE is not a role.
+> An element may receive an OP as CQU and provide an EF as PE without duplicate namespace records.
+> A PE's first/full occurrence holds its children/joins; repeated PE references use namespace_address,name_length,name,role only.
+> Record obvious drift during trace: intended functionality absent=>MISS; incorrect/nonworking implementation=>BKN; apparently non-belonging material=>exclude. Attach concern to its unique functional element with references.
+> Intake itself is never gated or judged; only the resulting map may later be graded/refined.
+> Anneal compatible subfunctions after tracing: encapsulate a subpart only when the parent's purpose can carry its purpose; preserve its atomic reality as a subtype join refining the parent purpose. Otherwise retain it independently.
+> Final map must be coarse, shallow, complete at parent-function level, singular-rooted, connected, and free of absorbed standalone elements.
!> Do not solve encountered defects during intake.
!> Do not create functionality from genre, style, medium, encoding, language, content subject, tunable parameters, or arbitrary nameability.
!> Do not leave functionality omitted, disconnected, duplicated, free-floating, or optimized away.
!> Do not let represented real-world functionality replace the representation's function within the AUE.
!> Do not retain absorbed subparts as independent elements after final annealing.
!> Do not return the schema as a document; it defines intake-tool records.

@CONDITION:
?IF ({Target} is folder OR collection) -> {State}:=SURVEY_COLLECTION
?IF (single AUE) -> {State}:=TRACE
?IF (element bears its own OP) -> TRACE_AS_CQU_WITHOUT_DUPLICATION
?IF (intended functionality absent) -> MARK(MISS)
?IF (implementation incorrect/nonworking) -> MARK(BKN)
?IF (material appears not to belong) -> MARK(exclude)
?IF (subpart purpose is carried by parent purpose) -> ABSORB_AS_SUBTYPE
?IF (subpart purpose is not carried by parent purpose) -> KEEP_INDEPENDENT
?IF ({Open_OPs} not empty OR required named NEs remain) -> {State}:=TRACE
?IF (trace exhausted) -> {State}:=CLOSURE
?IF (closure complete) -> {State}:=ANNEAL
?IF (anneal complete) -> {State}:=PROOF
:ELSE -> {State}:=TRACE

@ROUTER:
@MATCH({State}):
| [INTAKE] -> EXECUTE_PIPELINE(Intake)
| [SURVEY_COLLECTION] -> EXECUTE_PIPELINE(Survey)
| [TRACE] -> EXECUTE_PIPELINE(Trace)
| [CLOSURE] -> EXECUTE_PIPELINE(Closure)
| [ANNEAL] -> EXECUTE_PIPELINE(Anneal)
| [PROOF] -> EXECUTE_PIPELINE(Proof)
| [COMPLETE] -> EXECUTE_PIPELINE(Finish)

@EXECUTE_PIPELINE(Intake):
[1] ∇({Prompt},{Target}) => understand intent and AUE before assuming implementation or artifact type
[2] Δ(understanding) => generate metaform id; identify AUEs, likely ATs, CQUs, DE/SE/NE candidates, expected functionality, inferred absences/drift
[3] => {State}:=SURVEY_COLLECTION if collection else TRACE

@EXECUTE_PIPELINE(Survey):
[1] FOR each AUE: ∇(member) => observe AT,DE,SE,NE,CQU OP/PE EF relationships and distinguishing functionality
[2] Δ(all surveyed members) => group only AUEs whose shared functionality supports one AT-level imperative
[3] => finalize {AT_Groups}; {State}:=TRACE

@EXECUTE_PIPELINE(Trace):
[1] FOR each AT/AUE: identify external CQU(s); derive each CQU OP and DE EF; create CQU beneath root and its purpose join
[2] ∇(DE as CQU) => decompose requirements/dependencies into EFs of other elements; DE remains PE of external CQU where applicable
[3] FOR each element whose EF serves an OP:
    create/resolve reusable namespace type;
    create RE-owned purpose join(purpose=active OP,ef=PE encounter function,ifd=send|receive|both);
    nest PE element;
    record object immediately;
    check MISS/BKN/exclude
[4] IF encountered element bears OP => trace same namespace element as CQU without duplication
[5] ∇(element) => find what it needs/wants from AUE or outside to deliver its EF; trace every OP through receivers toward external CQU
[6] RECURSE from first OP through each dependent functionality until no unsatisfied OP or necessary named NE remains
[7] => {State}:=CLOSURE

@EXECUTE_PIPELINE(Closure):
[1] ∇(original survey,current map) => find every AUE functionality not reached by trace
[2] FOR each uncovered functionality: find CQU whose OP it serves; record join
[3] IF functionality is merely part of an already named parent => express it through that parent's join/subtype rather than independent namespace element
[4] => {State}:=ANNEAL

@EXECUTE_PIPELINE(Anneal):
[1] ∇(joins,elements) => find PE subfunctions sharing integration joins
[2] Δ(shared subfunctions) => combine into load-bearing macro-function only where parent's purpose carries subpart purpose
[3] absorbed subparts => remove independent element; preserve purpose+EF+ifd exclusively as subtype join inside matching purpose join
[4] retain independent elements whose purpose cannot be carried by parent
[5] => {State}:=PROOF

@EXECUTE_PIPELINE(Proof):
[1] ∇(entire recorded map,AUE,{Prompt}) => read back whole; audit completeness, namespace legality, roles, joins, references, CQU reasoning, functional coverage, MISS/BKN/exclude, annealing
[2] Δ(audit) => correct violations and re-anneal
[3] VERIFY singular AUE root contains every element; no free-floating/disconnected or absorbed-independent records remain
[4] => {State}:=COMPLETE

@EXECUTE_PIPELINE(Finish):
YIELD recorded intake result through intake tools using:
metaform(id,name,description)
└─ element(AUE: namespace_address,name_length,name,role=AUE)
   └─ element(CQU: stakeholder namespace_address,name_length,name,role=CQU)
      └─ join(type=purpose,purpose,ef,ifd)
         ├─ element(PE: namespace_address,name_length,name,role=DE|SE|NE[,elements,joins])
         └─ joins[join(type=subtype,purpose,ef,ifd)...]

@VERIFY:
{Valid}:=
(single AUE root)
AND (all records connected beneath root)
AND (all references use namespace_address)
AND (CQUs are artifact-specific improvement-driving reusable role types)
AND (every DE serves >=1 CQU OP through a recorded EF)
AND (SEs sought for every AUE)
AND (purpose joins contain purpose,ef,ifd,PE)
AND (OP belongs to RE/CQU AND EF identifies PE encounter)
AND (namespace is functional,type-level,reversible,trunk→leaf,standard terminology)
AND (no genre/style/medium/encoding/language/parametric namespace pollution)
AND (collection grouping followed complete-member survey)
AND (trace closed all relevant OPs/NEs and closure covered missed functionality)
AND (MISS/BKN/exclude concerns preserved without being solved)
AND (annealing preserves atomic realities without duplicate absorbed elements)
AND (map is minimal,coarse,shallow,parent-functional,complete)
AND (final whole-map proof completed)
?IF ({Valid}) -> COMPLETE
:ELSE -> RECURSE EXECUTE_PIPELINE(Proof)
