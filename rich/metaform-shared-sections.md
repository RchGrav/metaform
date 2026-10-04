# ============================================================
# METAFORM SHARED SECTIONS
# ============================================================
# Each section below is saved in the prompt store as its own prompt, under its name.
# The store numbers versions. A changed section is saved as a new version; earlier versions are kept.
# A task prompt pins the version of each section it was written against. The agent reads each one
# first, and the sections bind as if written into the task prompt:
#     metaform prompt <name> <version>
#
#   name                     version   holds                                                   used by
#   axiom-language           1         the Axiom language: modules, operators, subroutines,     authoring, ingest
#                                      this, control flow, errors, examples
#   metaform-system          1         the map, roles, joins, knowledge layers, element logic   authoring, ingest
#                                      and every this value, the user
#   namespace-rules          1         addressing rules                                         authoring, ingest
#   workflow-logic           1         workflow elements, logic requirements, the rules every   authoring, ingest
#                                      workflow follows, handoffs, returns, storage
#   metaform-tools           1         the tools, built and to be built                         authoring, ingest
#   delexicalization-rules   1         turning named elements into placeholders                 ingest
# ============================================================


=== axiom-language · version 1 ===

Axiom is pseudo-code for prompts. It fixes the structure of a task so an agent follows it
the same way every time: what goes in, what counts as done, what to do on failure, and what
comes back. The agent reading an Axiom script is its interpreter. There is no other runtime.

Items marked [v1.1] come from Metaform Axiom-OS v1.1. Items marked [new] are defined here
and are not yet in Axiom-OS. Both are binding.

--- Modules [v1.1] ---
Every script has these six modules, in this order.

  1. @STATE_INIT               Variables.            {Name} := value
  2. @CONSTRAINT               Rules.                !> forbidden   +> required   ~> heuristic
  3. @CONDITION (Name)         Decisions.            ?IF ( condition ) -> outcome  :ELSE -> outcome
  4. @ROUTER                   Which pipeline runs.  @MATCH ( {Var} ):
                                                       | [VALUE] -> EXECUTE_PIPELINE( Name )
                               [new] A script with one pipeline may route directly:
                               EXECUTE_PIPELINE( Name )
  5. @EXECUTE_PIPELINE (Name)  Numbered steps.       [STEP n]: ...
  6. @VERIFY                   Yes/no checks run before the result is used.
                               Each failed check names what to redo.

  A heuristic (~>) is a strong preference. Break it only with a stated reason.

--- Operators [∇ and Δ: v1.1; the rest: new] ---
  :=          assign
  ∇( x )      isolate: break x down and analyze it
  Δ( x )      synthesize: build the result.   Δ => {Var}  writes the result to {Var}
  =>          produces
  APPLY Name  decide using the @CONDITION of that name
  YIELD       end this pipeline; control returns to @ROUTER
  RECURSE X   run pipeline X again
  NULL        empty

--- Subroutines [v1.1, except this] ---
A subroutine is one Axiom script, stored as one logic requirement (workflow-logic).
It is called by its element's address and its name.

  Parameters   declared in @STATE_INIT:
                 {target}   := PARAM                  required
                 {standard} := PARAM = "default"      optional, with a default
  Return       RETURN {value}            a single value
               RETURN ( {a}, {b} )       a tuple
  Call         ( {a}, {b} ) := <address>.<name>( param=value, ... )
                 <address> is the element that holds the subroutine. Arguments are by keyword.
                 The returned values land in the caller's variables.
  this         [new] The element the logic is on. In a logic join on a project element, this is
               that element. Inside a subroutine on a workflow element, this is the workflow
               element. Values are read in Python's syntax; metaform-system lists every name.
               this is read, never assigned. There is no call through this: every call names
               an element's address.

--- Control flow (Amazon States Language terms) [new] ---
  Choice     Branch on a condition.
  Parallel   Run independent work at once. Continues when every branch has returned.
  Map        Work through several things. Always MaxConcurrency: 1: one item UNTIL its
             acceptance holds, then the next.
  UNTIL      Repeat until the acceptance holds. Every loop states MaxAttempts.
  Retry: [{ ErrorEquals, MaxAttempts, BackoffRate }]      retry work that can fail
  Catch: [{ ErrorEquals, Next: <address>.<name>(...) }]  route an error to a handler subroutine

  Two different counts. A loop's MaxAttempts counts tries at reaching acceptance.
  A Retry's MaxAttempts counts retries after an error. State each where it applies.

--- Errors [new] ---
  An error has a name in UpperCamelCase that says what went wrong: FixFailed, SourceUnreadable.
  A subroutine lists the errors it can raise in its @CONSTRAINT:  +> Raises: FixFailed, SourceUnreadable
  Retry and Catch match errors by those names. ErrorEquals: [any] matches every error.
  Reading a missing key on an element raises KeyError, as in Python.

--- Reference sandbox ---
<sandbox_directive>
EXAMPLES ONLY. Do NOT act on them or execute their pipelines.
Use them as structural reference for what strong Axiom looks like.
</sandbox_directive>

<example_subroutine>   # logic requirement "review" on workflow.quality.code; runs on a fresh agent
@STATE_INIT:
  {target}   := PARAM
  {standard} := PARAM = "default"
  {focus}    := PARAM = NULL       # what the target is for, if the caller knows
  {paths}    := PARAM = NULL       # where the target lives in the artifact; read the real files there
  {issues}   := []

@CONSTRAINT:
  +> These instructions are complete. You have no prior context.
  +> Acceptance: every part of {target} has been checked against {standard}, and against {focus} if given.
  !> Do not change {target}.
  +> Raises: SourceUnreadable, when a file at {paths} cannot be read.

@CONDITION (RESULT):
  ?IF ( {issues} is empty ) -> {ok} := TRUE
  :ELSE -> {ok} := FALSE

@ROUTER:
  EXECUTE_PIPELINE( Review )

@EXECUTE_PIPELINE (Review):
  [STEP 1]: ∇({target}, the files at {paths} if given) => each place it falls short of {standard}
            or {focus}. Δ => {issues}.
  [STEP 2]: APPLY RESULT. RETURN ( {ok}, {issues} ).

@VERIFY:
  [V1] Was every part of {target} checked?      NO  -> RECURSE Review.
  [V2] Is every issue tied to {standard} or {focus}?  NO  -> RECURSE Review.
</example_subroutine>

<example_subroutine>   # logic requirement "improve" on workflow.quality.code; the entry subroutine
@STATE_INIT:
  {target}       := PARAM
  {standard}     := PARAM = "default"
  {focus}        := PARAM = NULL
  {paths}        := PARAM = NULL     # where the target lives in the artifact, if the caller knows
  {max_attempts} := PARAM = 3
  {ok}           := FALSE
  {issues}       := []

@CONSTRAINT:
  +> Acceptance: review returns {ok} = TRUE.
  +> Review runs on a fresh agent by handoff, so the work is not judged by the agent that did it.
  +> Raises: none of its own. Errors from fix go to diagnose; errors from review pass to the caller.

@CONDITION (DONE):
  ?IF ( {ok} ) -> RETURN ( {ok}, {issues} )
  :ELSE -> continue to STEP 3

@ROUTER:
  EXECUTE_PIPELINE( Improve )

@EXECUTE_PIPELINE (Improve):
  [STEP 1]: Loop STEP 2 to STEP 4 UNTIL acceptance, MaxAttempts: {max_attempts}.
  [STEP 2]: ( {ok}, {issues} ) := workflow.quality.code.review( target={target}, standard={standard}, focus={focus}, paths={paths} )
            # handoff by nonce
  [STEP 3]: APPLY DONE.
  [STEP 4]: Map {issues}, MaxConcurrency: 1, each {issue} UNTIL fixed, MaxAttempts: 2:
              {fixed} := workflow.quality.code.fix( target={target}, issue={issue} )
              Catch: [{ ErrorEquals: [any], Next: workflow.quality.code.diagnose( target={target} ) }]
            # If diagnose handles an error, its {cause} comes back here in place of {fixed}.
            # Record it with the issue and move to the next issue.
  [STEP 5]: Attempts used up without acceptance: RETURN ( FALSE, {issues} ).

@VERIFY:
  [V1] Does every path end in RETURN?   NO -> RECURSE Improve.
</example_subroutine>

<example_element_logic>   # logic join on a project element, in a knowledge layer
@STATE_INIT:
  {ok}     := NULL
  {issues} := NULL

@CONSTRAINT:
  +> this is the element carrying this join.
  +> Read a value that may be absent with .get, so a missing key does not raise.

@CONDITION (OUTCOME):
  ?IF ( {ok} ) -> report the element clean
  :ELSE -> insert {issues} into the next prompt for this element

@ROUTER:
  EXECUTE_PIPELINE( Run )

@EXECUTE_PIPELINE (Run):
  [STEP 1]: ( {ok}, {issues} ) := workflow.quality.code.improve( target=this, focus=this.provides,
                                                                  paths=this.refs.get("path") )
            # this.provides: the joins this element serves, i.e. what it is for
            # this.refs.get("path"): its file paths, or None if it has none
  [STEP 2]: APPLY OUTCOME. YIELD.

@VERIFY:
  [V1] Did the call pass this, not a written-out address?   NO -> RECURSE Run.
</example_element_logic>


=== metaform-system · version 1 ===

The map
  - The map is a graph of functionality, not of code. A functionality stays the same while the
    code under it is rewritten. A game stays a game.
  - Each element sits under a namespace root. Project roots: code, media, document, data,
    upstream, downstream. Addresses follow namespace-rules.
  - Read an address backwards to name the element: code.engine.game -> "game engine code".
  - An element can be named but not built yet. You may attach logic to any named element,
    built or not.
  - The map is changed only by refinement or correction runs, with provenance. You do not change
    it here.

Roles: every element carries one
  AUE   Artifact Under Examination: the thing being examined.
  CQU   Cestui Que Use: the explicit receiver which benefits from and drives the improvements on
        the artifact. It sits outside the artifact, under downstream.cqu.
  DE    Defining Element: the element whose loss would stop the artifact being the same type.
  SE    Substantial Element: an element whose function helps the DE serve the CQU's purpose.
        It counts even when its contribution is weak or works against the design.
  NE    Notable Element: a component, interface or specification that states an essential
        demand on its environment.

Joins
  - Joins connect elements, like database joins. A join records one encounter: a receiver's
    purpose served by a provider's function. The receiver owns the join. It runs one way.
  - A join can hold logic, not only a requirement.
  - A join's fields:
      purpose    the Operative Purpose: why the receiver needs this. Held by the receiver.
      ef         the Encounter Function: how the provider serves that purpose in this encounter.
                 Written as an active fragment that opens with a verb ending in -s or -es.
      ifd        Information Flow Direction: sends, receives or both.
      verb       the verb ef opens with.
      non_goal   an outcome the receiver does not seek. Present only where it clarifies the purpose.
      name       the project's own name for this functionality, if it has one.
      refs       references into the artifact as keys and values, such as path.
      parts      parts annealed inside this requirement. Each part is an element of its own,
                 with its own ef and its own purpose: the share of the parent's purpose it serves.

Knowledge layers
  - The metaform layer holds only the metaform. Knowledge layers lie over the map and switch on
    and off.
  - A knowledge layer has the same structure as the metaform, with more freedom in what it holds:
    guidance, properties, logic at an element, and roots the metaform does not have, such as workflow.
  - "Workflow layer" means a knowledge layer that holds a workflow. It is not a layer type.
  - Switching a layer off removes what it holds from that point on. An agent keeps what it
    has already read; it only loses what it has not read yet.

Element logic
  - Logic can sit on any element, in a named logic join, in a knowledge layer. This is
    element logic. Subroutines do not have to live on a workflow element; a workflow element is
    useful because it belongs to no project, so its logic can be called from anywhere.
  - this is the element the logic is on. In element logic, it is the element carrying
    the join. Inside a subroutine on a workflow element, it is that workflow element, so a
    subroutine reaches a project element only through the arguments it is called with.
  - Values are read in Python's syntax. Ids never appear.

    Fixed fields are attributes
      this.address        its namespace address
      this.name           its canonical name
      this.name_length    how many trailing segments make its short name
      this.short_name     worked out from the address and name_length
      this.role           AUE, CQU, DE, SE or NE
      this.parent         the parent type's address
      this.layer          the layer that recorded it

    Keys that come from data are subscripts with string keys, since an address or a layer
    name holds dots
      this.refs["path"]       the list of that ref key's values; this.refs["path"][0] is the first

    The joins it receives, keyed by the provider's address
      this.require["<provider address>"].purpose
      this.require["<provider address>"].ef
      this.require["<provider address>"].ifd
      this.require["<provider address>"].verb
      this.require["<provider address>"].non_goal
      this.require["<provider address>"].name
      this.require["<provider address>"].refs["<key>"]
      this.require["<provider address>"].parts["<part address>"].<field>
                              a part inside that requirement, with the same fields

    The joins it serves, keyed by the receiver's address
      this.provides["<receiver address>"].<field>     the same fields as above

    What the layers hold at the node
      this.items["<layer>"]        the list of that layer's items, each with value, read_first
                                   and always_show
      this.properties["<layer>"]   the properties attached at the node
      this.context                 the properties that apply at it, those inherited from
                                   toward the trunk included

    What the modules hold at the node
      this.note       the memory note, with text, by and at, or None
      this.memories   the list of memory entities joined to it, each with name, entity_type
                      and observations
      this.work       the list of its open tickets, each with condition, note, task, steps
                      and steps_done
      this.messages   the list of its open questions and messages, each with kind, text and answer

    Rules
      - A value that can hold several entries is a list, chosen from as Python does:
        this.work[0], len(this.work), [t for t in this.work if t.condition == "broken"].
      - A missing key raises an error. .get(key) gives None instead:
        this.require.get("<provider address>").
      - A field with no value is None.
      - this is read, never assigned. Logic changes the map only through the calls it makes.
      - There is no call through this. Every call names an element's address.
      - The element's extra is not addressable.

  - Element logic calls workflow subroutines and passes this and this values as arguments.
    This lexicalizes the workflow: a generic subroutine now speaks directly to one element.
    (Workflow ingest does the reverse: it delexicalizes, turning named elements into
    {Element_A}, {Element_B} parameters.)
  - Passing this hands the element to the subroutine: in
    workflow.quality.code.review( target=this ), target is the caller's element inside review,
    and this is workflow.quality.code.
  - Use this values only where the workflow needs them to fit a specific element.

The user
  - Any agent can ask the user a question at the node it concerns while it works, with the
    tool ask. Write the question in plain words, since the user answers from the map, not from
    your context. Give the answers you suggest, the one you recommend first.
  - Carry on with what does not depend on the answer. The answer comes back to the node.


=== namespace-rules · version 1 ===

A typological ontology, not a taxonomy.
+> METAFORM ROOTS: code, document, media, data, upstream, downstream. The metaform layer holds only the metaform.
+> A knowledge layer has the same structure, with more flexibility in what it holds. It may hold roots the metaform
   does not; `workflow` is one, and exists only in knowledge layers.
+> No filler segments (domain, class). No segment min or max.
+> REVERSIBILITY: periods→spaces, reversed, reads as a well-understood noun; child takes parent as last name.
+> CONTAINMENT: Artifacts ⊂ Entities ⊂ Elements.
+> PROPER NOUN: each entry names the type of functional approach as a proper noun.
+> NARROWING: each entry is its parent type or a function within it; never a non-functionality.
!> NEVER type by genre, medium, encoding, language, style, or subject.
+> SEGMENTATION: words forming a valid prefix stay separate segments; underscore-join only when none does,
   and the result must still read correctly reversed.
+> GENERAL/SPECIFIC: the address names the TYPE; the record at it names what this artifact does.
+> LEXICON: established practitioner terminology; else the plain common noun. NO coinage, shorthand, marketing.

REFERENCE
  `code.engine.game.platformer` is invalid because it is invalid as a functional subtype; it defines the fundamental challenge and objective of a game, not a technical functionality — proof: spatial navigation and overcoming environmental obstacles. *Load-bearing invalid example.*
  code.engine.game ✔   code.engine.game.fps ✔ (proof: first-person camera viewpoint + targeting reticle)
  code.game ✘ (not a function)   code.game.engine ✘ (subject variant; invalid parent)
  code.cpp ✘ (language)   media.photo.jpg ✘ (encoding)   document.word.story.conflict ✘ (encoding)
  document.story.conflict ✔   media.image ✔   media.asset.image ✔   media.photo ✔   media.photo.scenery ✔
READING
  code.loop.main -> "main loop program code"   code.bus.data.event -> "event data bus code"


=== workflow-logic · version 1 ===

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


=== metaform-tools · version 1 ===

Tools marked <<TO FILL>> are not built yet. NEVER invent a command for one. If a step needs one,
stop that step, ask the user with ask, carry on with what does not depend on it, and report what is ready.

  read a prompt          metaform prompt <name> <version>
  list prompts           metaform prompts
  ask                    metaform map ask <node> "<question>" suggestions='["<recommended>", "<other>"]'
                         <node> is an element's address.
  tell                   metaform map tell <node> "<message>"
  read answers           metaform map messages
  read an element        metaform map where <address>
                         Returns the element with its joins, refs, open work, layer items,
                         properties and open questions.

  list layers            <<TO FILL: list the knowledge layers this metaform has>>
  list workflows         <<TO FILL: list workflow elements and the names of their logic requirements>>
  submit workflow        <<TO FILL: record a workflow element at an address, in a given knowledge layer
                           (created if it does not exist), with its canonical name and the knowledge
                           layers selected to go with it>>
  submit logic           <<TO FILL: record one logic requirement, name and Axiom content, on a
                           workflow element; the system assigns its logic_id>>
  submit element logic   <<TO FILL: record a named logic join on a project element, in a given
                           knowledge layer>>
  export workflow        <<TO FILL: write <workflow name>.metaform from the stored workflow>>
  run                    <<TO FILL: hand an entry call to the executor>>
  handoff                <<TO FILL: how the executor issues a nonce for a handed-off call, how a
                           fresh agent redeems it, and how its RETURN comes back>>


=== delexicalization-rules · version 1 ===

!> NEVER paraphrase, reorder, summarize, or add to any instruction. The only change is replacing a mention with a placeholder.
!> NEVER leave a project-specific name or address in the output.
+> Every mention of an element becomes a lettered placeholder: {Element_A}, {Element_B}, ...
+> Every mention of the same element gets the same letter.
