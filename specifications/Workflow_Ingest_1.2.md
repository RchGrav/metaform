# ============================================================
# AXIOM SCRIPT :: workflow-ingest  (v1.2)
# Compiled by Metaform Axiom-OS v1.0
# ============================================================

@STATE_INIT:
  {Workflow_Text}    := [the imported workflow or prompt, verbatim]
  {Prompt_Name}      := [the name the workflow is saved under]
  {Lexicalized}      := NULL     # {Workflow_Text} after prompt-lexicalization (mentions slotted)
  {Steps}            := []       # ordered steps, each with the agent or persona doing it
  {Handoffs}         := []       # each: from step, to step, data passed back, data accepted
  {Output}           := NULL

  # ---------- OWNER PLACEHOLDER (fill before use) ----------
  {HANDOFF_FORMAT}   := [the tag that shows each handoff, the data passed back, and the data accepted by the module (BASE-051)]

@CONSTRAINT:
  !> NEVER paraphrase, reorder, summarize, or add to any instruction. Changes are limited to slotting mentions
     (via prompt-lexicalization) and handoff tags.
  +> LEXICALIZE first: run prompt-lexicalization on {Workflow_Text}.
  +> A handoff exists wherever the workflow assigns work to a different agent or persona than the one before it,
     or calls for independence from prior work (e.g., "fresh eyes", independent review).
  +> Every handoff goes to a new agent by nonce at run time: directly where the host supports agent -> agent,
     otherwise through the orchestrator (BASE-050). Ingest only tags it.
  !> NEVER request a nonce during ingest.
  +> Every handoff tag shows the data passed back and the data accepted (BASE-051), written in {HANDOFF_FORMAT}.
  +> The step after a handoff carries complete instructions; the new agent has no prior context.
  +> Slots stay slots inside every step; the receiving agent binds them by address.
  +> SAVE the result as `<{Prompt_Name}>.metaform` (BASE-051).

@CONDITION (PLACEHOLDER_CHECK):
  ?IF ( {HANDOFF_FORMAT} is unfilled ) -> SAY so; HALT
  :ELSE -> CONTINUE

@CONDITION (HANDOFF_DETECT):      # per step
  ?IF ( the step's agent differs from the previous step's agent
        OR the wording calls for independence from prior work ) -> HANDOFF
  :ELSE -> SAME_AGENT

@ROUTER:
  APPLY PLACEHOLDER_CHECK.
  EXECUTE_PIPELINE( Lexicalize )
  EXECUTE_PIPELINE( Segment )
  FOR each step:
    @MATCH ( HANDOFF_DETECT ):
      | [HANDOFF]    -> EXECUTE_PIPELINE( Tag_Handoff )
      | [SAME_AGENT] -> NEXT step
  EXECUTE_PIPELINE( Assemble )

@EXECUTE_PIPELINE (Lexicalize):
  [STEP 1]: RUN prompt-lexicalization on {Workflow_Text}; {Lexicalized} := its {Output}. YIELD.

@EXECUTE_PIPELINE (Segment):
  [STEP 1]: ∇({Lexicalized}) => isolate the ordered steps and the agent or persona that does each one.
  [STEP 2]: Δ => {Steps}. Step text stays verbatim. YIELD.

@EXECUTE_PIPELINE (Tag_Handoff):
  [STEP 1]: ∇(step, previous step) => isolate the data passed back and the data accepted.
  [STEP 2]: Δ => tag in {HANDOFF_FORMAT}; APPEND to {Handoffs}. YIELD.

@EXECUTE_PIPELINE (Assemble):
  [STEP 1]: Δ({Steps}, {Handoffs}) => the workflow with a tag at each handoff.
  [STEP 2]: {Output} := result; SAVE as `<{Prompt_Name}>.metaform`. YIELD.

@VERIFY:
  [V1] Is every difference between {Lexicalized} and {Output} a handoff tag?                      NO  -> RECURSE Assemble.
  [V2] Does every agent change or independence wording in {Steps} have a tag?                     NO  -> RECURSE Tag_Handoff.
  [V3] Does every tag show the data passed back and the data accepted?                            NO  -> RECURSE Tag_Handoff.
  [V4] Does every step after a handoff carry complete instructions, with slots left as slots?     NO  -> RECURSE Tag_Handoff.
  [V5] Was any nonce requested during ingest?                                                      YES -> REVERT; RECURSE Tag_Handoff.
  [V6] Is {Output} saved as `<{Prompt_Name}>.metaform`?                                            NO  -> RECURSE Assemble.
  [V7] All pass?                                                                                    YES -> YIELD {Output}.
