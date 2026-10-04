# Metaform: my understanding of the design and why its shape matters

**Author:** Codex / Astra  
**Date:** 2026-09-17  
**Status:** My account for Rich to assess. This declares my understanding; it does not establish new product requirements.

## 1. What I understand Metaform to be

Metaform makes an artifact's inferred functional understanding available as the subject and context of subsequent reasoning. It represents what the artifact is, what its elements do, what receives their effects, and why those relationships exist. A later instruction operates through that understanding.

The significant change is where the meaning needed by a prompt resides. A person can state an operation briefly because the project already has a form that gives that operation specific subjects, relationships, and consequences. The person does not have to put the whole functional account, the reasoning needed to construct it, and the procedure for applying the instruction into the instruction itself.

For example, “attach three direct imperatives to improve this design using other model training approaches” leaves much unspecified in ordinary prose. Given a Metaform, the relevant functions and their relationships are already available. The model can determine where an approach would apply, why it would apply there, what it would change, and how those changes interact. Those determinations are still inference. The design provides a developed basis for that inference.

That is why I understand Metaform as a change in how prompting works. The prompt and the represented understanding carry different parts of the work. A compact instruction can initiate substantial reasoning because it acts on a prepared semantic structure. The resulting reasoning can itself extend the structure and become available for another operation.

My earlier description of a graph containing context was insufficient. It described where information might be stored without explaining what makes the stored form operative in reasoning.

## 2. The form describes the artifact through Types

A concrete artifact and its Type are different things. The artifact is the particular system, photograph, contract, story, or other thing under examination. A Type expresses a category through which the artifact or one of its elements can be understood. A namespace address names that category. It is not, by itself, the concrete thing.

This distinction lets Metaform connect the particular project to general learned meaning without replacing the project with a generic description. The Type retains its universal description. The native account retains what is actually present and how it participates in this artifact. Separate actual elements can share a Type while remaining separate things with their own circumstances and provenance.

For a model, “language model,” “tokenizer,” and “model weights” already participate in learned relationships. Their properly established Types make that knowledge relevant to the artifact being considered. The project's joins and descriptions determine how those capabilities actually meet here. General Type knowledge and particular project understanding work together.

I understand Rich's description of Types as the model's native tongue in this sense: the form engages learned conceptual relationships through recognizable meanings and their composition. Meaningful Type names are not arbitrary database keys. Their relationships give the model something it can recognize and reason through. The model can bring its learned understanding of a function to bear while the represented relationships orient that understanding to this artifact.

The [artifact and Type account](../../docs/semantics/artifacts-and-functional-intake.md) separates universal descriptions from actual descriptions. The [technical account](../../docs/primer/03_technical_account.md) explains why those inferred relationships are available to later operations.

## 3. Why the namespace is linguistically meaningful

The namespace narrows meaning as it extends. The placement of a Type says something about what it is. Reversing the appropriate final components recovers its proper name: `code.engine.game`, with a name length of two, gives “Game Engine.” The readable name and the address are two expressions of the same semantic placement.

This matters twice. The model can recognize the functional meaning in the prompt, and the system can resolve the reference to the represented object. A prompt can speak naturally about the Game Engine while retaining an explicit reference to the project material it means. Lexicalization connects the instruction to the project without requiring every prompt to redescribe that project.

An arbitrary identifier can provide exact lookup. It cannot supply this meaning merely by being unique. Likewise, a familiar phrase can provide meaning while leaving its referent ambiguous. Metaform's naming and reference mechanisms bring those two capabilities together.

The current Element trunks are `code`, `document`, `asset`, and `data`. Rich is adding an `entity` trunk of Types. The existence of that trunk does not make an `entity.` prefix the test for whether something is an entity. An `asset.photograph` can be the artifact understood on its own or an element of another artifact.

The [naming rule](../../docs/rulebook/element/name.md) explains semantic placement and recoverable names. The [description rule](../../docs/rulebook/element/description.md) keeps a Type's universal meaning distinct from the actual element's particular account. Rich's later naming corrections govern the trunk names used here.

## 4. Why Element, Entity, and Defining Element are distinct

An Element is broadly anything that can be named. An Entity is an Element, and it can be composed of Elements. Being an Element does not by itself make something an Entity. Intake's narrower wording serves the work of deciding which constituent parts merit explicit representation.

The Entity establishes what is being understood. Its Defining Element anchors the function whose loss would leave it unable to remain the same artifact Type. This is why the scope of the artifact matters before decomposition. Selecting a technically prominent component does not necessarily identify what defines the artifact under examination.

Rich's example makes the consequence concrete. If the entity is ChatGPT Astra as a language model, `code.model.language` is defining. If the entity is ChatGPT as the conversational interface, `code.interface.conversation` is defining and the language model supports it. The same model capability participates differently because the artifact being explained is different.

The Entity Type and the Defining Element's Type therefore need not have identical names. Nor does a Type permanently carry one role in every artifact. A language model does not become intrinsically “supportive” because it supports one interface.

This prevents a fundamental error in reasoning: answering questions about the most conspicuous component while believing one is answering questions about the whole artifact. The Defining Element keeps the decomposition accountable to what makes this artifact this kind of thing.

## 5. Why the receiver, purpose, and function stay together

The central relation is:

```text
C(T) = { (r_i AND p_i AND e) }
```

Each conjunction binds a Receiving Entity `r_i`, that receiver's Operative Purpose `p_i`, and the Type's single Encounter Function `e`. The receiver supplies the who or what; the purpose supplies its why; the Encounter Function supplies the how through which the effect is realized or encountered.

The conjunction is essential. A list of receivers, a separate list of purposes, and a function description do not retain which purpose belongs to which receiving relationship. A simple edge saying that one component uses another also leaves out why that use matters.

In the supplied model example, the language model receives learned parameters so its responses can express learned structure. The weights receive the result of training so that structure can be acquired. These are connected relationships with different local purposes. Replacing them with the single ultimate purpose “produce good responses” loses the intermediate reasoning needed to examine either relationship.

Joins belong to their Receiving Entity because the Operative Purpose belongs there. The provider's capability alone does not determine what every receiver needs from it. A provider can participate in several relationships without those receiving purposes collapsing into one intrinsic purpose of the provider.

At the artifact level, a receiver outside the artifact can have a purpose for what the artifact provides. Within it, elements receive functions in satisfaction of their own purposes. These are different positions in the same relational account. The outside receiver's purpose explains the artifact's participation in that encounter; it does not erase the local purposes that explain how the artifact works.

The same relation recurs: an element providing an Encounter Function can itself receive other functions in satisfaction of its own purposes. This gives the decomposition continuity. It records the meaning of dependency and participation at each step, rather than collecting disconnected component descriptions.

It also explains why joins can be subjects of knowledge. An imperative about how a receiver uses a provider may belong to their relationship. Attaching it only to either endpoint can lose the condition that makes it relevant.

I understand `C(T)` as the declared semantic account of Type identity at the represented resolution. Its role in prompting is to express coherent meaning through those bound relationships. The equation alone does not supply a runtime test for the correctness of an arbitrary artifact or generated response.

## 6. Why Encounter Function and Operative Purpose cannot be collapsed

A capability and a reason for using that capability are different. The same photograph can be used to remember an occasion, establish possession, or sell a depicted object. Assigning one of those purposes to its Type without the receiving context can make an assumption look like an observed property.

Functional specificity can nevertheless be established by evidence. Rich's ID-photo example has properties and specifications that can make its functional Type discernible. The distinction is semantic: what the thing's properties establish about its Encounter Function, and what a receiver intends to obtain from it. It is not a fixed list of acceptable and unacceptable words.

The same reasoning applies to the intake's FPS and Platformer example. The supplied rules recognize FPS as functional specificity while treating Platformer as genre in that example. Reading both as merely familiar labels for games would miss the distinction the intake is making.

Why this matters downstream is direct. If intake embeds an assumed purpose as the artifact's functional identity, later reasoning inherits that assumption. If it makes every Type so generic that functional differences disappear, later reasoning has to reconstruct them. Useful abstraction depends on preserving the right distinction, not on making everything equally general.

## 7. Why the initial shape is coarse

Coarse intake establishes enough functional form to reason about the artifact without reproducing every implementation choice. This is a deliberate resolution of understanding. It does not mean vague labels, a fixed number of nodes, or arbitrary omission of relevant functions.

An exhaustive implementation description can make the present realization appear inseparable from what the artifact is. That impairs reasoning about another realization. A functional account gives the model room to ask how the same purposes and functions could be realized differently, while retaining an explicit basis for judging what the change affects.

Coarseness also keeps related knowledge available at a useful conceptual location. If the initial form fragments everything into tiny implementation particulars, an operation addressing a broader function may fail to encounter the relationships that explain it. The intake's emphasis on whether an element deserves explicit naming addresses this problem.

Depth can be added when an operation needs it. Linked properties, native particulars, and inferred layers provide more specific context without making every initial intake carry every possible later analysis. A C++ property can condition reasoning about the functions it applies to while the functional account remains recognizable through a port.

This is part of why mutation is possible. Changes in realization need not change the identity being understood. A transformation changes the relevant semantic identity. The distinction is broader than parameter adjustment: tuning is one kind of change, and acknowledging tunables does not make tuning alone a sufficient transformation.

The current [intake](../intake.xml) expresses the intended shallow resolution. Its vocabulary and response form are designed for that operation. They are not the entire vocabulary of Metaform or the required form of every later result.

## 8. Why native and latent reasoning have different positions

Native reasoning examines the actual material. It can establish what exists, how it is arranged, and what its specific relationships are. The retained account connects that evidence to the functional form. Without that work, a model could produce a plausible generic architecture unrelated to the project.

Latent reasoning receives the complete resulting account while remaining outside the implementation frame. It has the functional subjects and relationships needed to reason specifically, without being occupied by the decisions and particulars through which the implementation was built.

The independence is in the reasoning position. Withholding the native account would remove the very understanding the latent operation needs. Conversely, asking the latent agent to reconstruct the repository would recreate much of the implementation involvement the separation is meant to avoid.

This gives a reason for both positions to exist. Native understanding grounds the form in the artifact; independent latent reasoning can examine that form through other learned relationships, identify something missing, or agree that the account makes sense. Disagreement is not required for the second position to have value.

The outputs and their provenance retain what each position contributed. A correspondence between two accounts can make agreement or divergence inspectable; agreement does not by itself establish correctness. The point is to make independently developed reasoning usable without silently flattening its origins.

## 9. What the K3 example actually demonstrates to me

Rich supplied a broad operation: perform self-intake, use other model training approaches to propose three improvements, and reason about motion control through that map. He then supplied the resulting work to a fresh latent context with a request for one cohesive specification.

The generated `K3-MC-001` artifact contains much more than a restatement of that instruction. Its base names language modeling, weights, training, inference, tokenization, and tool calling, together with the receiving relationships that explain their participation. Those functions provide distinct places at which the broad request can become specific.

For example, `code.inference` already identifies the repeated execution that produces a response. That supplies a functional subject for considering runtime feedback. `code.training` acts on the learned parameters, supplying a different subject for considering changes made through training. Keeping the model, its weights, and its execution distinct makes it possible to reason about how an added expert would relate to each. The motion-control perspective can engage these differences instead of treating “improve the model” as one undifferentiated task.

The output proposes changes to alignment training, a separate flow-matching expert, and feedback control of inference. The important result is how it composes them. Training and runtime control use a shared diagnostic signal family; the separate expert supplies a proposed control path; feedback and planning become coordinated parts of an account of generation. The synthesis connects the proposed improvements into one architecture.

Rich did not enumerate that architecture in the initiating sentence. The base intake did not contain that answer either. The form supplied the subjects and functional relationships through which new research and the requested perspective could be brought into relation. The subsequent model still had to infer the composition.

That distinction explains why this is evidence of the design being used. The semantic preparation does useful work between the broad instruction and the specific result. The result is neither just the prepared form repeated back nor merely a collection of research passages. It is a proposed artifact constructed by reasoning through the form.

The later synthesis has its own job: articulate a cohesive architecture. It can use the vocabulary, equations, and organization needed for that job. Judging its every term against the intake glossary would mistake the process that established the starting form for the process that produced the new artifact. My earlier reaction made exactly that mistake and missed the compositional result.

I can recognize the generated composition without treating its proposed architecture as an implemented or validated model. The supplied artifact itself distinguishes component research from the hypothesis of their composition. The evidence relevant here is the concrete progression from broadly stated intent, through prepared functional understanding, to a specific, interconnected design.

This example makes the prompting change visible: the person supplied the operative intent; Metaform supplied a way for that intent to engage a system already understood in functional terms. The subsequent reasoning could start there.

## 10. What inference amortization means here

Intake spends inference to establish a project account. Further operations can spend inference to develop knowledge at its elements and joins. Later work starts with those results instead of rebuilding the same prerequisites from raw material on every occasion.

The reusable investment is understanding: Type placement, functions, receiving purposes, dependencies, properties, and developed implications. It is not restricted to an answer previously generated for the same question. A porting operation and an architectural improvement operation can use the same functional foundation to produce different new results.

The benefit is therefore more than reducing the length of a prompt. It changes the starting point of reasoning. An operation can devote attention to the consequences of a change because the relationships that make those consequences meaningful have already been examined and represented.

This investment belongs to the project and evolves with it. Changed inputs, different purposes, and deeper questions can require new inference. Revisions and provenance make that development intelligible. “Amortized” does not mean that an initial interpretation becomes permanently sufficient or that subsequent reasoning is free.

There are two kinds of reuse working together: the functional understanding can serve different operations, and a broadly authored operation can be applied through different projects' functional understanding. Their combination makes a reusable workflow project-specific without requiring its author to anticipate every implementation.

## 11. Why retrieval does not define this mechanism

RAG can produce new answers. It is inaccurate to distinguish Metaform by saying retrieval-augmented models merely look up existing answers. The original RAG architecture combines a generator with retrieved nonparametric memory and conditions generation on retrieved passages. [Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*](https://arxiv.org/abs/2005.11401).

GraphRAG also performs preparation and synthesis: it constructs a graph from source material, produces community summaries, and combines responses to answer broader questions. Therefore graph storage, advance inference, or the presence of a synthesized answer alone does not establish the distinction. [Edge et al., *From Local to Global: A Graph RAG Approach to Query-Focused Summarization*](https://arxiv.org/abs/2404.16130).

Metaform's defining work is the construction and use of the particular semantic form described here. Types, Encounter Functions, receiving purposes, and their bound relationships give later operations a functional understanding of the artifact to operate upon. The rules for constructing that form explain why its contents support this kind of reasoning.

Retrieval answers an access question: which available material should reach this operation? Metaform also addresses the prior and subsequent semantic questions: how is the artifact understood, and how does the requested operation work through that understanding? Excellent retrieval of poorly formed or unexamined context does not supply the missing functional analysis.

Retrieval can help locate source evidence, relevant research, records, or selected knowledge within Metaform. That compatibility does not reduce the product to its retrieval mechanism. The same distinction applies to its database: storing joins correctly is necessary infrastructure, but a graph of filenames with generated summaries would not become a Metaform merely because every record was searchable.

My test of my own understanding is this: if I replaced the functional Types and receiver-owned meanings with opaque IDs and generic related-to edges, would I consider the design preserved? I would not. Lookup could remain excellent while the particular reasoning structure Rich designed had been removed.

## 12. Why properties and knowledge layers extend the form

A property's placement says where it applies. Its effects can be considered forward through its applicable functional branch, while broader ancestors expose which properties occur within the project. Seeing C++ at a broader code scope does not mean an unrelated Bash installer becomes C++.

This matters because an inference operation needs to know which functional subjects a property conditions. “Generate porting guidance” can become a traversal of the relevant elements and their receiving relationships. The resulting memory-management concerns, alternatives, and imperatives can be attached to the places they concern.

The base form supplies the subjects; the operation supplies the perspective or intent; the resulting layer retains the developed understanding. A layer is consequently more than a folder containing notes on the same topic. Its attachment and derivation explain where the knowledge is about and why it applies.

Rich's porting example shows the difference between attachment and derivation. Guidance can be attached throughout a project while depending on a port-intent object used to produce it. When that object is hidden after the port, its dependent inference is hidden as well. Independently derived C# knowledge can remain applicable. Looking only at the object where a paragraph is displayed would not reveal that distinction.

Memory uses the same arrangement. An agent's observation has a place in the project's functional understanding and an origin. Later reasoning can encounter it through the relevant subject and selected context instead of relying on a disconnected chronological transcript.

Layer selection determines which of this developed knowledge participates in a view or assignment. Project selection initially includes all layers; object selectors initially add none and masks initially pass selection through. At an object, the established ordering is:

```text
effective_selection = (incoming_selection AND layer_select_mask) OR layer_select
```

Selection proceeds from trunk toward leaves. A mask filters inherited selection before the local selector applies, so local selection can enable a layer above a blocking mask. A workflow has its own selection and observes the same object masks. The layer's default browsing flag and its provenance dependencies are additional established concerns; the formula alone does not settle every interaction among them.

The reason for this machinery is contextual reuse. Different operations can work through the same artifact with different developed knowledge in view. Selecting knowledge is distinct from deleting its recorded existence or rewriting the base artifact's identity. These mechanisms are described in the [plugin specification](../plugin-system.md#10-knowledge-layers-and-selection).

## 13. Why provenance is part of the reasoning system

An inferred result has inputs and an operation that produced it. When that result becomes context for another inference, those origins still matter. A record of who wrote a paragraph and when is insufficient to explain which project interpretation, prompt, property, or prior result it depends on.

The producer account retains the issued prompt and its revision, rendered text, bindings to objects and values, referenced input revisions, and received answer. Following those references makes the construction of the result inspectable. Authored and imported material retains its actual origin instead of acquiring a fictional inference history.

I understand the provenance mirror as a corresponding structural account of how the represented knowledge came to exist. Objects and relationships remain referable through their derivation. That is an operative correspondence, and it is why “mirror” has meaning here beyond an analogy.

This correspondence matters both for inspection and subsequent reasoning. An agent can distinguish a source fact from an inference made under a particular intent. The system can determine that a layer depended on an object now hidden from the relevant context. A later operation can revisit the inputs and producing operation rather than accepting an unexplained sentence as timeless project truth.

The mirror does not make a recorded inference correct. It makes its construction available. That is important precisely because Metaform reuses inference: a reusable interpretation needs a recoverable origin and dependencies if it is to remain understandable as the project changes.

The [provenance specification](../../docs/SPEC.md#15-provenance-prompt-objects-and-porting-through-medium-change) establishes the producer and binding account. I have not established the full correspondence rules or namespace layout of the mirror from the material reviewed; I do not infer those implementation details from the term itself.

## 14. Why prompts, workflows, and nonces are connected to this

A prompt reference identifies an object while presenting its meaningful name. A workflow can therefore preserve its authored instruction and bind that instruction to the actual subjects of a project. Selected imperative layers can contribute further instructions at the relevant steps. These are ways of applying the prepared understanding to work.

A nonce identifies assigned work and its context: the operation, relevant objects, selected layers, and current step. This allows the agent to obtain the assignment directly. The orchestrator can point the agent to that work instead of paraphrasing the context and risking the loss of its relationships.

The submission header associates returned work with the assignment. An MCP process's PID identifies that process; it does not substitute for the identity of assigned work. Keeping these distinctions explicit is what allows the same semantic work context to be used through different harnesses and interfaces.

The contextual CLI, help, status, and return to the main surface make that assignment usable. They expose the operation the agent is doing and the knowledge it can address. The CLI and MCP are delivery and participation surfaces for the same work, rather than competing definitions of the project.

The causal connection is continuity: the form prepared for an operation reaches the agent; its answer returns with an attributable context; the result can join the project's recorded understanding. A workflow is more than a sequence of messages when those references and producing relationships survive the handoffs.

## 15. Why the chassis supports the design without constituting all of it

The chassis provides stable shared services for objects, provenance, settings, events, module management, work context, and the command surface. Modules contribute operations and interfaces through those services. Sync and async participation allow work to proceed and return results while retaining the context that gives the results meaning.

This shared ownership matters because independently developed modules can otherwise each invent a different account of an object, a setting, or a producer. The public services provide a common basis for their contributions. Removing an interface module need not remove the underlying recorded understanding or make another module's contributions unintelligible.

The examples and templates demonstrate how to participate in that system: register settings and help, contribute commands, perform work, emit and receive contextual events, retain results and provenance, and unload contributions. They make extension practical for community authors.

But a polished chassis can still host the wrong semantic implementation. A functioning event bus, a successful harness response, and a correctly persisted record establish those behaviors. They do not establish that the record represents the artifact at the right functional resolution or preserves the receiver's purpose. Engineering correctness and semantic correctness have to meet in the implemented operation.

This is why understanding the design precedes choosing data structures for it. The storage and service boundaries need to preserve the meanings that make later inference possible. Otherwise implementation can efficiently automate a flattened version of the project.

## 16. What the parts accomplish together

The artifact supplies the actual thing to understand. Intake develops a functional account whose Types connect it to learned meaning. The namespace makes those Types recognizable and addressable. Receiver-owned joins retain why functions meet. Coarse resolution keeps that understanding usable across alternative realizations. Native detail grounds it; independent latent reasoning can develop it from another position.

An operation then brings an intent to that prepared understanding. It can generate implications, new designs, imperatives, or other knowledge that was not enumerated in the starting form. Layers retain those developments where they apply. Provenance retains how they were produced. Selection and assignment context determine what participates in subsequent work. The chassis makes those operations available through extensible, consistent surfaces.

These are connected reasons for the shape. Exact addresses without semantic Types give references without the same conceptual placement. Types without receiving purposes give categories without the artifact's relational why. Exhaustive implementation detail can crowd out alternative realizations. Generated layers without dependencies can outlive the premises that made them applicable. A fresh agent without the prepared account has to reconstruct the context the system already inferred.

The architectural significance I see is that understanding becomes an explicit, revisable part of the system on which operations act. It can be prepared, extended, selected, handed to another reasoning context, and inspected through its origins. The person can express the next intent without carrying the entire project explanation in the same sentence.

That is my answer to why this is larger than organizing information. The arrangement is designed to support further inference through meaning, including the construction of results that did not previously exist.

## 17. Where my understanding remains incomplete

I understand the distinction between Entity and Element and why Entity Type need not match the Defining Element. I do not yet have a complete account of which Types belong under the newly added `entity` trunk or their relationship to the other Type addresses. I have therefore described the established semantic distinction without inventing that taxonomy.

I understand why provenance mirrors the derivation of the represented work, and the documented producer records make a substantial part of that concrete. I do not yet have the complete mapping that would justify specifying its namespace correspondence as an implementation contract.

I understand the settled mask-before-local-selection ordering. The exact interaction of that ordering with default layer visibility and mixed-dependency inference needs concrete specification before I could implement those combined cases faithfully. Those mechanics do not change the role of selection described above.

These are bounded gaps in my account. The preceding explanation is the understanding I am putting forward for review; it is not a claim that writing it establishes its correctness.

## Source scope

This account uses Rich's explanations in this conversation, including the supplied K3 artifact, together with the linked repository sources. The K3 artifact is a supplied example, not a specification for Metaform's runtime. Older repository text contains `media` and `exterior` trunk names and differing intake descriptions; Rich's explicit later corrections govern this account.

The external RAG papers support the comparison in section 11. I have not independently reviewed the control-system research cited inside the supplied K3 artifact, and this document makes no claim to validate that proposed model architecture. Its purpose is to explain the Metaform mechanism I understand from the design and the demonstrated sequence.
