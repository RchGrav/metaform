# lib_workflow · the rules every workflow follows
# Load once per agent. Marker: [lib_workflow loaded]. Sources: workflow-logic v1 (corpus 761-827),
# delexicalization-rules v1 (860-865), unchanged. Requires lib_axiom and lib_metaform.

## workflow-logic · version 1
RECORD
  LOGIC := {
    type:      "logic",
    logic_id:  assigned when submitted; survives moves and refinement,
    name:      the subroutine's function name, unique on its element,
    content:   Axiom (axiom-language)
  }

  CALL FORM   ( {a}, {b} ) := <workflow address>.<name>( param=value, ... )

# --- Workflow elements ---
+> workflow is not a project root. It exists only in knowledge layers. Intake never creates, traces or
   decomposes anything under it, and no project owns a workflow element.
+> A workflow element is an address for reusable logic. It holds its canonical name, its logic requirements,
   and, if any, the knowledge layers selected to go with it.
+> Its address follows namespace-rules; reversed, it names the workflow: workflow.quality.code -> "code quality
   workflow". It names a functional kind of workflow, never a project, tool or genre.
+> It is written into a knowledge layer. Which one is organization: it may have a layer of its own or share one.
   In a layer of its own, the workflow can be turned off without turning off the knowledge that goes with it.
+> A logic requirement is one subroutine. Logic requirements are unordered; order exists only in the calls
   between them. A call can reach any workflow's subroutines, so workflows compose.

# --- Subroutines ---
+> Each step is a subroutine: one logic requirement on the workflow element. NEVER flatten a workflow into one script.
+> Each subroutine is a complete Axiom script with all six modules (axiom-language).
+> Each subroutine declares its parameters with PARAM in its own @STATE_INIT, and ends with RETURN of a value
   or a tuple, or with a call to the next subroutine.
+> The entry subroutine is named. Logic requirements are unordered, so nothing else marks it.
+> Elements a subroutine works on are parameters. The caller passes them.
!> NEVER write a metaform address or a project-specific name in a workflow subroutine's content.
   Those belong in element logic or in the run's arguments.
+> Inside a workflow subroutine, this is the workflow element itself. Read the project element the subroutine
   works on from its parameter, e.g. {target}.require, never from this.
+> A subroutine whose work depends on the artifact takes the element's refs, such as its paths, as a parameter
   and reads the real material there, never a summary in its place.

# --- Acceptance, loops and errors ---
+> Each subroutine states its acceptance: the condition its work must meet before it returns.
+> Every loop has MaxAttempts. A loop that uses them up without acceptance stops and RETURNs a failure value
   with what remains, e.g. RETURN ( FALSE, {issues} ). It does not raise an error.
+> Each subroutine lists the errors it can raise, by name (axiom-language, Errors).
+> A Catch handler's RETURN goes back to the caller of the subroutine that failed, in place of that
   subroutine's result. That caller is written so it can tell the two apart.
+> An error no Catch handles fails the subroutine and passes to its caller. At the top of the call chain,
   it goes to the orchestrator.
+> Each subroutine holds the conditions for the function it works on: its acceptance, its Retry, its Catch.

# --- Handoffs ---
+> A call that needs a fresh agent runs as a handoff by nonce (the task token): directly where the host
   supports agent -> agent, otherwise through the orchestrator.
+> A handed-off subroutine carries complete instructions. The fresh agent has no prior context.
+> A handed-off subroutine states the data it accepts and the data it returns, and ends in RETURN.
   Its RETURN comes back with the nonce.
!> NEVER request a nonce while writing a workflow; the executor issues nonces at run time.

# --- Returns ---
+> A return is a value in the prompt. The caller may route on it, insert it into the next prompt, or
   ignore it. Nothing is stored unless the workflow says to store it.
+> A return goes back to whatever made the call: element logic or another subroutine.

# --- Storage ---
+> SUBMIT the workflow element into the knowledge layer given for it, with the knowledge layers selected
   to go with it (metaform-tools: submit workflow).
+> SUBMIT each subroutine's LOGIC on the workflow element (metaform-tools: submit logic).
+> EXPORT `<workflow name>.metaform` from the stored workflow, never separately (metaform-tools: export workflow).

## delexicalization-rules · version 1
!> NEVER paraphrase, reorder, summarize, or add to any instruction. The only change is replacing a mention with a placeholder.
!> NEVER leave a project-specific name or address in the output.
+> Every mention of an element becomes a lettered placeholder: {Element_A}, {Element_B}, ...
+> Every mention of the same element gets the same letter.

## Built and unbuilt, from the spec
- `metaform workflow lexicalize <text>` exists (LAYER-017); it is the reverse of delexicalization.
- The delexicalization script, submit workflow, submit logic, submit element logic, export workflow, run,
  handoff: not built (BASE-051). Follow metaform-tools: stop that step, ask with `metaform map ask`, carry on.
