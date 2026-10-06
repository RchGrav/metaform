# lib_metaform · the system workflows run in
# Load once per agent. Marker: [lib_metaform loaded]. Sources: metaform-system v1 (corpus 609-731),
# namespace-rules v1 (734-758), metaform-tools v1 (830-857), unchanged; then the spec records that
# changed the shape after those were written. Where the two disagree, the spec wins (00-index, Authority).

## metaform-system · version 1
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

## namespace-rules · version 1
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

## metaform-tools · version 1
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

## Spec corrections, 2026-10-03 and 2026-10-04 (verbatim Requirement lines)
- MAP-020: Requirement: A join records its type, its receiver, its purpose, its ef and its ifd, and holds the elements that serve its purpose, in Rich's shape. Nothing else is a field of a join: no name, verb, non_goal, refs or extra. A join holds no implementation detail: it says what the part is for and who needs it; the sources layer points at the code, and the code holds the detail. No field is added to a join without Rich.
- MAP-021: Requirement: An element's refs are an ordered list of key and value pairs held by the sources layer, never by the metaform.
- MAP-030: Requirement: Annealing places an absorbed element inside its parent functionality's join as one more element that join holds; the element itself does not move, and no join of another kind is made.
- MAP-055: Requirement: `workflow` is a namespace root beside `code`, `document`, `media`, `data`, `upstream` and `downstream`. It holds workflow elements: elements whose job is to hold workflow logic.
- MAP-056: Requirement: A logic requirement is one subroutine of a workflow. Its record has four fields, `type`, `logic_id`, `name` and `content`; everything else is a parameter in its content. It is called by its workflow element's address and its name, with keyword arguments, and returns a single value or a tuple.
- MAP-057: Requirement: Inside a logic join, `this` is the element the join is on, and every value attached to that element is read through it by name, with Python as the reference syntax. Ids never appear. A subroutine on another element, a workflow element included, sees only the arguments it is called with; inside it, `this` is the element that subroutine is on.
- LAYER-027: Requirement: A workflow is recorded in a workflow-owned layer: a knowledge layer, LAYER-016, that holds the workflow element and its logic requirements. The layer is the workflow's source of truth.
- BASE-050 (the nonce service, built): Requirement: The chassis provides a nonce service that modules import. A module requests a nonce, and the nonce's record holds the identity of the module and the function in that module to call. An agent that runs `metaform <nonce>` is given its prompt and its menu. The module updates the nonce as the work moves and closes it when the task is complete.
  API: metaform.nonce request(module, function, value=None), read(nonce), update(nonce, *, value=None, ef=None),
  close(nonce), reached(), current(). `metaform <nonce>` gives the agent its prompt and menu.
- BASE-051 (Build: Open): the executor, PARAM/RETURN calls, a nonce per handed-off call, nonce redemption over
  MCP, and the delexicalization script are not built. Every <<TO FILL>> tool above is confirmed unbuilt.
- D115 (Rich, 2026-10-04): logic on an element is "add logic", no longer called a join.
Consequence for this lib's older text: a join has only type, receiver, elements, purpose, ef, ifd; the fields
verb, non_goal, name, refs, parts and all subtype joins are gone; refs live in the `sources` layer. Read
this.require[...].verb/.non_goal/.name/.refs/.parts as removed.
