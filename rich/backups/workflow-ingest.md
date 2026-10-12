# ============================================================
# AXIOM SCRIPT :: workflow-ingest  (v1.5)
# Compiled by Metaform Axiom-OS v1.1
# Turns an existing prompt or workflow into callable workflow logic.
# ============================================================

@STATE_INIT:
  {Workflow_Text}   := [the imported workflow or prompt, verbatim]
  {Delexicalized}   := NULL     # {Workflow_Text} after prompt-delexicalization
  {Workflow_Addr}   := NULL     # the workflow element, e.g. workflow.quality.code
  {Layers}          := []       # knowledge layers the workflow says to include
  {Subroutines}     := []       # one per step: name, parameters, acceptance, flow, returns

  # ---------- LOGIC REQUIREMENT (the stored record) ----------
  LOGIC := {
    type:      "logic",
    logic_id:  assigned when submitted,
    name:      the subroutine's function name,
    content:   Axiom
  }

  # ---------- CALL FORM ----------
  #   ( {a}, {b} ) := {Workflow_Addr}.{name}( param=value, ... )

@CONSTRAINT:
  # --- Fidelity ---
  !> NEVER paraphrase, reorder, summarize, or add to any instruction. A step's instructions go into its subroutine verbatim,
     as delexicalized.
  !> NEVER add a step, condition, loop, or route the workflow does not state.
  +> DELEXICALIZE first: run prompt-delexicalization on {Workflow_Text}.
  +> What the workflow leaves unstated becomes a parameter, passed by the caller: acceptance=PARAM, max_attempts=PARAM.

  # --- Workflow and subroutines ---
  +> The workflow is an element under the workflow root, in a workflow-owned layer, outside the metaform.
     Address it by the namespace rules; reversed, it names the workflow.
  +> Each step is a subroutine: one logic requirement on the workflow element. NEVER flatten a workflow into one script.
  +> A subroutine is named for what its step does; the name is unique on the element and is its function name.
  +> Each placeholder a step uses ({Element_A}, ...) is a PARAM of that step's subroutine.
  +> A step ends with RETURN of what it produces, or with a call to the next step the workflow states.
  +> The workflow element lists the knowledge layers the workflow says to include in {Layers}.

  # --- Control flow (Amazon States Language terms) ---
  +> A stated branch is a Choice. Stated independent work is Parallel.
  +> A step that works through several things is a Map, MaxConcurrency: 1: one thing UNTIL acceptance, then the next.
  +> A stated retry is a Retry; a stated failure route is a Catch, Next: the subroutine it names.
  +> An error no stated route handles fails the subroutine and propagates to its caller.

  # --- Handoffs ---
  +> A handoff exists wherever the workflow assigns work to a different agent or persona than the step before it,
     or calls for independence from prior work (e.g., "fresh eyes", independent review). That call runs by nonce
     (the task token): directly where the host supports agent -> agent, otherwise through the orchestrator.
  +> A handed-off subroutine carries complete instructions; the fresh agent has no prior context.
  !> NEVER request a nonce during ingest.

  # --- Output ---
  +> `<workflow name>.metaform` is written from the stored workflow element and its logic requirements, never separately.

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
  EXECUTE_PIPELINE( Delexicalize )
  EXECUTE_PIPELINE( Segment )
  EXECUTE_PIPELINE( Write_Subroutines )
  EXECUTE_PIPELINE( Submit )

@EXECUTE_PIPELINE (Delexicalize):
  [STEP 1]: RUN prompt-delexicalization on {Workflow_Text}; {Delexicalized} := its {Output}. YIELD.

@EXECUTE_PIPELINE (Segment):
  [STEP 1]: ∇({Delexicalized}) => what the workflow is, its steps in order, each step's verbatim text and placeholders,
            and the knowledge layers it names.
  [STEP 2]: Δ => {Workflow_Addr}; {Layers}. YIELD.

@EXECUTE_PIPELINE (Write_Subroutines):
  [STEP 1]: FOR each step: APPLY ITERATION, ACCEPTANCE, FAILURE, NEXT, HANDOFF.
            Δ => its content in Axiom: PARAMs, the verbatim instructions, acceptance, control flow, and RETURN or the next call.
  [STEP 2]: Δ => {Subroutines}. YIELD.

@EXECUTE_PIPELINE (Submit):
  [STEP 1]: SUBMIT the workflow element at {Workflow_Addr} with {Layers}.
  [STEP 2]: FOR each subroutine: SUBMIT its LOGIC on the workflow element.
  [STEP 3]: WRITE `<workflow name>.metaform` from the stored workflow. YIELD.

@VERIFY:
  [V1] Is every step's text in its subroutine exactly as delexicalized?                            NO  -> RECURSE Write_Subroutines.
  [V2] Is there one logic requirement per step, and no flattened script?                          NO  -> RECURSE Write_Subroutines.
  [V3] Does every call name a subroutine that exists at its address?                              NO  -> RECURSE Write_Subroutines.
  [V4] Is every placeholder a step uses declared as a PARAM of its subroutine?                     NO  -> RECURSE Write_Subroutines.
  [V5] Does any subroutine hold a step, condition, loop, or route the workflow does not state,
       other than PARAMs for what it leaves unstated?                                              YES -> RECURSE Write_Subroutines.
  [V6] Does every handed-off subroutine carry complete instructions?                              NO  -> RECURSE Write_Subroutines.
  [V7] Was any nonce requested during ingest?                                                      YES -> REVERT; RECURSE Submit.
  [V8] All pass?                                                                                   YES -> YIELD.
