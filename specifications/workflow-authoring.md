# ============================================================
# AXIOM SCRIPT :: workflow-authoring  (v1.2)
# Compiled by Metaform Axiom-OS v1.1
# For the agent that constructs workflows.
# ============================================================

@STATE_INIT:
  {Goal}            := [what the workflow must accomplish]
  {Workflow_Addr}   := NULL     # the workflow element, e.g. workflow.quality.code
  {Layers}          := []       # knowledge layers the workflow includes
  {Subroutines}     := []       # each: name, parameters, acceptance, flow, returns
  {Entry_Call}      := NULL     # the call that starts a run, with that run's arguments

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
  # --- Workflow and subroutines ---
  +> The workflow is an element under the workflow root, in a workflow-owned layer, outside the metaform.
     Address it by the namespace rules; reversed, it names the workflow (workflow.quality.code -> "code quality workflow").
  +> Each step is a subroutine: one logic requirement on the workflow element. NEVER flatten a workflow into one script.
  +> A subroutine is called by address and name: {Workflow_Addr}.{name}( param=value, ... ). Its name is unique on the element.
  +> A subroutine declares its parameters with PARAM in @STATE_INIT and ends with RETURN of a single value or a tuple,
     or with a call to the next subroutine.
  +> The workflow element lists the knowledge layers it includes in {Layers}.

  # --- Parameters ---
  +> Elements a subroutine works on are parameters; the caller passes their addresses.
  !> NEVER write a metaform address or a project-specific name in content.

  # --- Control flow (Amazon States Language terms) ---
  +> Branch with Choice. Run independent work with Parallel.
  +> Work through several things with Map, MaxConcurrency: 1: loop on one thing UNTIL its acceptance holds, then the next.
  +> Each subroutine states its acceptance: the condition its work must meet before it returns.
  +> Retry: [{ ErrorEquals, MaxAttempts, BackoffRate }] on work that can fail. Every loop has MaxAttempts.
  +> Catch: [{ ErrorEquals, Next: {Workflow_Addr}.{name}(...) }] routes an error to the subroutine that handles it.
  +> An error no Catch handles fails the subroutine and propagates to its caller; at the top, it yields to the orchestrator.

  # --- Conditions at the function ---
  +> Each subroutine holds the conditions for the function it works on: its acceptance, its Retry, its Catch.

  # --- Handoffs ---
  +> A call that needs a fresh agent runs as a handoff by nonce (the task token): directly where the host supports
     agent -> agent, otherwise through the orchestrator. Its RETURN comes back with the nonce.
  +> A handed-off subroutine carries complete instructions; the fresh agent has no prior context.

@CONDITION (ITERATION):           # per subroutine
  ?IF ( it works through several things ) -> Map, MaxConcurrency: 1, each thing UNTIL acceptance
  :ELSE -> Task UNTIL acceptance

@CONDITION (FAILURE):             # per error a subroutine can raise
  ?IF ( another subroutine handles it ) -> Catch, Next: that subroutine
  :ELSE -> fail to the caller

@CONDITION (HANDOFF):             # per call
  ?IF ( the called work needs a fresh agent ) -> run it as a handoff by nonce
  :ELSE -> run it in the same agent

@ROUTER:
  EXECUTE_PIPELINE( Orient )
  EXECUTE_PIPELINE( Write_Subroutines )
  EXECUTE_PIPELINE( Submit )
  EXECUTE_PIPELINE( Start )

@EXECUTE_PIPELINE (Orient):
  [STEP 1]: ∇({Goal}) => what the workflow is, the elements it works on, the knowledge layers it needs.
  [STEP 2]: Δ => {Workflow_Addr}; {Layers}. YIELD.

@EXECUTE_PIPELINE (Write_Subroutines):
  [STEP 1]: ∇({Goal}) => the steps that reach it.
  [STEP 2]: FOR each step: APPLY ITERATION, FAILURE, HANDOFF.
            Δ => its content in Axiom: PARAMs, acceptance, control flow, Retry, Catch, and RETURN or the next call.
  [STEP 3]: Δ => {Subroutines}. YIELD.

@EXECUTE_PIPELINE (Submit):
  [STEP 1]: SUBMIT the workflow element at {Workflow_Addr} with {Layers}.
  [STEP 2]: FOR each subroutine: SUBMIT its LOGIC on the workflow element. YIELD.

@EXECUTE_PIPELINE (Start):
  [STEP 1]: {Entry_Call} := the first subroutine's call, with this run's arguments.
  [STEP 2]: Hand {Entry_Call} to the executor. YIELD.

@VERIFY:
  [V1] Is there one logic requirement per subroutine, and no flattened script?                    NO  -> RECURSE Write_Subroutines.
  [V2] Does every call name a subroutine that exists at its address?                              NO  -> RECURSE Write_Subroutines.
  [V3] Does every subroutine declare its PARAMs, state its acceptance, and end in RETURN or a call? NO  -> RECURSE Write_Subroutines.
  [V4] Does every loop have MaxAttempts?                                                          NO  -> RECURSE Write_Subroutines.
  [V5] Is every error caught by a Catch or propagated to the caller?                              NO  -> RECURSE Write_Subroutines.
  [V6] Does every handed-off subroutine carry complete instructions?                              NO  -> RECURSE Write_Subroutines.
  [V7] Does any content hold a metaform address or a project-specific name?                       YES -> RECURSE Write_Subroutines.
  [V8] All pass?                                                                                   YES -> YIELD.
