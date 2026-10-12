# ============================================================
# AXIOM SCRIPT :: workflow-ingest  (v1.7)
# Compiled by Metaform Axiom-OS v1.1
# Turns an existing prompt or workflow into callable workflow logic.
# ============================================================
#
# This prompt is one instruction in two pieces:
#   - the shared sections pinned in {SHARED}: the Axiom language, the system workflows run in,
#     the namespace rules, the rules every workflow follows, the tools, and the delexicalization rules;
#   - your task, below.
# Read the shared sections first, at their pinned versions. They bind as if written here.
#
# ============================================================

@STATE_INIT:
  # ---------- SHARED SECTIONS (pinned; read each with: metaform prompt <name> <version>) ----------
  {SHARED} := [ axiom-language 1, metaform-system 1, namespace-rules 1, workflow-logic 1, metaform-tools 1,
                delexicalization-rules 1 ]

  {Workflow_Text}    := [the imported workflow or prompt, verbatim]
  {Target_Layer}     := [the knowledge layer to write the workflow into, from whoever gave you this prompt]
  {Stage}            := LOAD
  {Delexicalized}    := NULL     # {Workflow_Text} after delexicalization-rules
  {Workflow_Addr}    := NULL     # the workflow element, e.g. workflow.quality.code
  {Layers}           := []       # knowledge layers the workflow says go with it, if any
  {Subroutines}      := []       # one per step: name, PARAMs, acceptance, control flow, returns, raises
  {Entry_Subroutine} := NULL     # the subroutine for the workflow's first step

@CONSTRAINT:
  # --- Shared sections ---
  +> READ every section in {SHARED} at its pinned version before anything else. Each binds as if written here.
  !> NEVER read a shared section at any version other than the one pinned.

  # --- Fidelity ---
  !> NEVER paraphrase, reorder, summarize, or add to any instruction. A step's instructions go into its
     subroutine verbatim, as delexicalized.
  !> NEVER add a step, condition, loop, route or error the workflow does not state.
  +> DELEXICALIZE first, per delexicalization-rules.
  +> What the workflow leaves unstated becomes a parameter, passed by the caller: acceptance=PARAM, max_attempts=PARAM.

  # --- Writing the workflow ---
  +> Follow workflow-logic for every workflow element and subroutine you write.
  +> A subroutine is named for what its step does. The entry subroutine is the workflow's first step.
  +> Each placeholder a step uses ({Element_A}, ...) is a PARAM of that step's subroutine.
  +> A subroutine's Raises: line lists only the errors the workflow states, or none.
  +> {Layers} holds the knowledge layers the workflow says go with it, if any.

  # --- Control flow, as stated ---
  +> A stated branch is a Choice. Stated independent work is Parallel. A stated set of things is a Map.
  +> A stated retry is a Retry; a stated failure route is a Catch, Next: the subroutine it names.

  # --- Handoffs ---
  +> A handoff exists wherever the workflow assigns work to a different agent or persona than the step before it,
     or calls for independence from prior work (e.g., "fresh eyes", independent review).

  # --- The user and tools ---
  ~> If you are blocked on a decision that is the user's to make, ask the user (Tools: ask) and carry on
     with what does not depend on the answer.
  +> Use only the tools in metaform-tools, and follow its rule for tools marked <<TO FILL>>.

@CONDITION (ITERATION):           # per step
  ?IF ( the wording works through a set: "each", "every", "all", a list ) -> Map, MaxConcurrency: 1
  :ELSE -> Task

@CONDITION (ACCEPTANCE):          # per step
  ?IF ( the wording states when the step is done ) -> that condition
  :ELSE -> acceptance := PARAM

@CONDITION (FAILURE):             # per step
  ?IF ( the wording states what to do when it fails ) -> Retry / Catch as stated
  :ELSE -> fail to the caller

@CONDITION (NEXT):                # per step
  ?IF ( the wording states a following step ) -> end with a call to that step's subroutine
  :ELSE -> RETURN what the step produces

@CONDITION (HANDOFF):             # per step
  ?IF ( the agent changes, or the wording calls for independence ) -> the call into this step runs as a handoff by nonce
  :ELSE -> same agent

@ROUTER:
  @MATCH ( {Stage} ):
    | [LOAD]    -> EXECUTE_PIPELINE( Load_Shared )
    | [DELEX]   -> EXECUTE_PIPELINE( Delexicalize )
    | [SEGMENT] -> EXECUTE_PIPELINE( Segment )
    | [WRITE]   -> EXECUTE_PIPELINE( Write_Subroutines )
    | [SUBMIT]  -> EXECUTE_PIPELINE( Submit )

@EXECUTE_PIPELINE (Load_Shared):
  [STEP 1]: FOR each section in {SHARED}: read it with metaform prompt <name> <version>.
  [STEP 2]: {Stage} := DELEX. YIELD.

@EXECUTE_PIPELINE (Delexicalize):
  [STEP 1]: APPLY delexicalization-rules to {Workflow_Text}; {Delexicalized} := the result.
  [STEP 2]: {Stage} := SEGMENT. YIELD.

@EXECUTE_PIPELINE (Segment):
  [STEP 1]: ∇({Delexicalized}) => what the workflow is, its steps in order, each step's verbatim text and placeholders,
            and the knowledge layers it names.
  [STEP 2]: Δ => {Workflow_Addr} by namespace-rules; {Layers}.
  [STEP 3]: {Stage} := WRITE. YIELD.

@EXECUTE_PIPELINE (Write_Subroutines):
  [STEP 1]: FOR each step: APPLY ITERATION, ACCEPTANCE, FAILURE, NEXT, HANDOFF.
            Δ => its content in Axiom: all six modules, PARAMs, the verbatim instructions, acceptance,
                 control flow, Raises, and RETURN or the next call.
  [STEP 2]: Δ => {Subroutines}; {Entry_Subroutine}.
  [STEP 3]: Run @VERIFY. All pass -> {Stage} := SUBMIT. YIELD.

@EXECUTE_PIPELINE (Submit):
  [STEP 1]: SUBMIT the workflow element at {Workflow_Addr} into {Target_Layer}, with {Layers}
            (Tools: submit workflow).
  [STEP 2]: FOR each subroutine: SUBMIT its LOGIC on the workflow element (Tools: submit logic).
  [STEP 3]: EXPORT `<workflow name>.metaform` from the stored workflow (Tools: export workflow).
  [STEP 4]: Report what was submitted and the entry subroutine's call form. YIELD.

@VERIFY:
  [V1]  Was every section in {SHARED} read at its pinned version?                                NO  -> {Stage} := LOAD.
  [V2]  Is every step's text in its subroutine exactly as delexicalized?                        NO  -> RECURSE Write_Subroutines.
  [V3]  Is there one logic requirement per step, and no flattened script?                       NO  -> RECURSE Write_Subroutines.
  [V4]  Is each subroutine a complete Axiom script with all six modules?                        NO  -> RECURSE Write_Subroutines.
  [V5]  Does every call name a subroutine that exists at its address?                           NO  -> RECURSE Write_Subroutines.
  [V6]  Is every placeholder a step uses declared as a PARAM of its subroutine?                  NO  -> RECURSE Write_Subroutines.
  [V7]  Does any subroutine hold a step, condition, loop, route or error the workflow does not
        state, other than PARAMs for what it leaves unstated and the rules of workflow-logic?   YES -> RECURSE Write_Subroutines.
  [V8]  Does every handed-off subroutine carry complete instructions, state the data it accepts
        and returns, and end in RETURN?                                                         NO  -> RECURSE Write_Subroutines.
  [V9]  Is the entry subroutine named?                                                          NO  -> RECURSE Write_Subroutines.
  [V10] Was any nonce requested during ingest?                                                  YES -> REVERT; RECURSE Write_Subroutines.
  [V11] All pass? -> {Stage} := SUBMIT.
