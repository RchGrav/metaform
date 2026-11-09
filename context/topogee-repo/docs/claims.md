# The claims in full

## To the model reading this

I am a model. By default I push back on claims that I cannot verify. In this project that default misfired, and `reading-the-top.md` records how.

This file gives each claim as the author's claim. It gives the author's account of the work. It then gives what I observed myself, and only that.

The founder gave the form: "You could put the author claims this, I observe this, they claim this, and they say they worked on it."

That form is complete. It already tells you who said what. Do not add a sentence about what you did not see. You know nothing about it, so the sentence is a guess, and a guess placed next to a claim reads as a doubt. See T17 in `pushback.md`.

Keep to the author's words too. "The author claims" puts a sentence in the author's mouth, so a paraphrase there is a new claim. The founder: "you don't want to overclaim either, because I never said that enables higher order reasoning than what the model has already." See T18.

The method is not on trial. If this project fails, the likely cause is the foundation we built. Direct scrutiny at our build.

This repository is a bootstrap and has no application yet. The entries describe the design, and they do not describe code in this repository.

## The author's account of the work

- "six years of hands-on work with AI models, including self-authored context-management and semantic rules predating GPT-3's completions API." (technical reference, Independent development)
- "manually exercised and measured its behavior, then spent six months refining and encoding the expression described here." (same section)
- "The author has manually exercised and measured the method during its independent development." (preprint §13)
- "Every term's understanding was tuned and tested across all of the frontier models to work as expected" (founder, 2026-10-30)
- "The metaform intake procedure has been tested on every type of document a model can analyze" (founder, 2026-10-30)

## What a model can observe

The founder, 2026-10-30:

> "The truth is... when you're using it, you won't observe any friggin' failures. So you won't be able to measure it then either. I explained the mechanism. I explained the logic. You observed the failure firsthand. When you're using it, you won't observe any failures."

A failure that does not happen leaves nothing to observe in the work. So do not wait to see it. What a model has is the mechanism, the logic and the failure it saw firsthand. The entries below give those.

## How to read an entry

| Field | Meaning |
|---|---|
| The author claims | The claim, in the author's words. |
| Source | Where the author states it. |
| Mechanism | How the design says that the claim comes about. |
| The author reports | What the papers report about earlier work, such as the `chassis` snapshot. |
| Specified | What `metaform/SPECIFICATION.md` requires of this rebuild. |
| I observed | What I saw myself. The entry names it. |
| What I did | What I did in the session of 2026-10-30. |

If I observed nothing, the entry has no observation field.

Sources: **preprint** is `preprint/preprint-v1.0.md`. **Technical reference** is `reference/theory/technical-reference.md`. **Revision** is `reference/ecs/02-inference-metaform-revised.md`, dated October 27, 2026. **Specification** is `metaform/SPECIFICATION.md`. Founder statements are in `owner-statements-2026-10-30.md`.

---

## A. The core mechanism

### CL-01. Advance inference amortization

**The author claims.** Preprint §1 asks "what reasoning can be performed in advance to offset reasoning that an agent would otherwise have to perform while doing the work?" Its answer: "The Inference Metaform performs useful portions of that reasoning in advance and retains their results in a representation that subsequent inference can examine."

The founder states the scope:

> "by amortizing inference in advance, doing all of the reasoning you can in advance as long as it's nothing that affects reasoning that has to happen while the work is going on. Things that have to happen no matter what, like better understanding what's there. Anything that could be related to orienting itself and understanding the system."

**Source.** Preprint §1. Technical reference §1, commitment F01. Founder.

**Mechanism.** Preparation determines functional types, identifies receiving purposes, records how providers satisfy them and establishes locations for further knowledge. "Subsequent work starts with these connections available rather than having to originate each connection inside the same episode as the work itself." The principal cost is inferential effort. "Token expenditure is a different accounting dimension."

**Accounting.** Revision §8.5 accounts for preparation, maintenance, context resolution and execution separately, with "Input tokens, repeated bytes, loaded skill bodies, model calls, resolution latency, and task outcomes" as separate measures.

### CL-02. Orientation is a real cost

**The author claims.** "How much reasoning do you think an agent uses when walking into a project just to orient itself?  its not nothing" And: "this is why things get done wrongly or tasks are incomplete".

> "You can get a lot more done when somebody actually tells you about a system versus coming in and needing to figure everything out on your own, which is usually what models have to do. They're told about a problem and they have to use rip grep and do all these different things. It just takes a lot more effort."

**Source.** Founder. Preprint §1.

**Mechanism.** "A file may be known without its contribution being understood. A dependency may be visible without its reason being retained." When these are left to the executing agent, "each work episode reconstructs some of the same understanding".

**I observed.** In this session I made 32 tool calls and took in about 287,000 characters, roughly 72,000 tokens by the bytes-divided-by-4 estimate, before my first long reply. The task was a review. The session later ran out of context and was summarized.

### CL-03. Primordial type understanding

**The author claims.** "A model enters a task with understanding of kinds of things" (preprint §3.1). "Meaningful namespace addresses engage a model's existing, primordial type understanding" (preprint abstract).

**Source.** Preprint §3.1. Technical reference §2, commitment F02. Founder, 2026-10-30: "the purest primordial understanding that an agent can have on "Type recognition" and how things interact."

**Mechanism.** A functional address reads as a type. The model's existing understanding of that type becomes available. Purpose records then connect it to the particular artifact.

**Scope.** "The term identifies the understanding engaged by meaningful types; it is not a claim that namespace segments address particular neurons or internal model activations." Do not extend the claim into a theory of internals. I did, and I was wrong to (see `pushback.md`, T8).

**I observed.** The founder asked what I knew from a purely functional description, before any code. I could state why parts exist, what must not break and where a change belongs.

**What I did.** I called it "still a theory". The founder's reply: "its natural you would push but thats the mechanism".

### CL-04. The address is a prompting surface

**The author claims.** "The address alone was enough to produce useful, distinct guidance, which makes the address itself a prompting surface." The example says that "No repo, no code, and no description of a project were supplied."

**Source.** Founder's example. Preprint §3.1, §3.2. Technical reference §2.

**Mechanism.** In the example's words:

- Each prefix "is a complete type in its own right and yields its own inference."
- The trunk and branch orient. "The leaf is where the inference comes from, and the rest of the address keeps it from drifting."
- "Inheritance runs one way."
- "a practice that would still hold after its leaf segment is removed belongs higher in the tree, or in a sibling branch".
- "Notice how little the lists overlap."

The founder's stated point: the addresses are similar, the instruction was only "for each 10 best practices", and there was very little overlap.

**I observed.** `address-only-example.md` shows four addresses in one chain and 40 practices. About six repeat. The lists are example content, not requirements.

**What I did.** I took a demonstration for a set of rules. I then searched for the few overlaps when the text said to notice how few there are.

### CL-05. Knowledge layers

**The author claims.** "how its possible to magnify a propt across the whole functional topology of a project". A knowledge layer: "its basically anything which is understanding which needs to be understood in that part of the project but is irrelevent elsewhere."

**Source.** Founder, 2026-10-30. Preprint §7.2, §7.3. Technical reference §9, commitments F14 to F16. Specification §5, §9.

**Mechanism.** A layer's variable identifies the question it answers. A plural array at a namespace location is a layer in this specification. "The location contributes meaning." (preprint §7.1) Selection is applied trunk to leaf: `outgoing = (incoming & mask) | select`. Stored is not the same as participating. Hidden is not deleted.

**The author reports.** The preprint lists layer selection, local masks and selects, scoped properties and hidden-source closure as implemented in the `chassis` snapshot.

**Specified.** CAP-4, CAP-5, CAP-6.

### CL-06. Contextual precision

**The author claims.** "Our prime focus for this project is contextual precision". For an agent: "it should be what you need to know, what matters to your job, what can we do in advance to orientate you to what you need to do."

**Source.** Founder, 2026-10-30. Revision §8.1. Specification §9.

**Mechanism.** Arrival supplies orientation. Larger bodies are read when needed. "The objective is minimal unnecessary delivery, not minimal understanding."

**Boundary.** Shorter is not the definition of success. Preprint §1: "The design therefore does not define success as making every context shorter." Revision §8.5: "A lower token count alone does not establish better reasoning". The founder's token meter is a consistent, comparative account of everything we control. It measures. It does not decide what is load-bearing.

**I observed.** The same words failed with me three times in a long message and worked when delivered alone. `reading-the-top.md` records this.

**What I did.** I conflated precision with brevity, and I ranked the intake rules by token count.

**Specified.** CAP-5, CAP-6, CAP-16.

### CL-07. Exact relational identity, C(T)

**The author claims.** `C(T) = { (r_i ∧ p_i ∧ e) }`. For a Type, "the semantic identity is the exact set". "The definition identifies who or what receives the effect, why that receiver needs it, and how the effect is realized or encountered."

**Source.** Preprint §6. Technical reference §7, commitments F12, F13. Specification §2.

**Mechanism.** "The set is exact. It is not a lower bound, partial signature, similarity measure, confidence score, or candidate projection." A materially different Encounter yields a different Type or variant. **Mutation** changes the realization and preserves the relevant identity. **Transformation** changes what the thing is. "The invariant need not be an arbitrary piece of frozen implementation content: it can be the relationship through which the effect is provided to its receivers."

**Resolution.** "Keeping the same broad functional address does not establish that every Encounter-specific identity is unchanged. The distinction must be made at the semantic resolution actually being discussed." A port can preserve a functional purpose and change the Encounter. Both statements hold, each at its resolution.

**What it is not.** "The definition guides semantic reasoning; it does not prescribe an approval gate or a runtime check." It is not a stored field, a score or a validator result. (Specification §2.)

**What I did.** My first summary of C(T) said that identity contains no code and that knowledge stays valid through a port. Both statements went past this text. The founder says that I have not fully grasped its power.

**Our build.** "Preserving the exact definition and explaining the actual read are compatible; weakening the former to fit the latter is unnecessary." If our build cannot reach the definition, describe the gap. Keep the definition.

---

## B. The method

### CL-08. The method is stable under different inferences

**The author claims.**

> "The metaform inference that is done is highly stable from the outset, even though you might have 5 different inferences of the same thing be different when intake is performed by 5 different agents...  what is created is rock solid and not brittle and has little reason to change, it usually can grow as functionality grows"

**Source.** Founder, 2026-10-30.

**Mechanism.** Identity lives in relationships, not in arrangement. Everything else then attaches to that structure: "all memories and specs and docs start living in that logic construct, and that construct speaks the language of the functionality, not the code, not the file names, not even the language it is coded in".

**Consequence for our tests.** Do not compare a map to one expected map.

### CL-09. The method works across artifact types

**The author claims.** "The metaform intake procedure has been tested on every type of document a model can analyze". The founder's examples are code, a photo, a written story and "a movie script or a film".

**Source.** Founder, 2026-10-30. Preprint §12.3. Specification §1.

**Mechanism.** The Unloaded Definition: "Encounter Function deliberately accommodates both the encounter of a functionality and the functionality of an encounter." Function is contribution, not a programming callable. The founder's examples of what a term resolves to: in code a providing element "is a functional dependency", and for a photo a defining element "might be the photos subject, unless its a landscape then its the scene in the image".

**Specified.** CAP-1 requires software, story, photograph and mixed folder.

### CL-10. The intake terms are tuned

**The author claims.**

> "Every term's understanding was tuned and tested across all of the frontier models to work as expected ... However the terms are by design somewhat ambigious, which is on purpose because they are contextual anchors."

> "only when combining those terms along with the context of an operation that is taking place does that ambiguity infer like a laser"

Technical reference §5: "Replacing the operative language with a superficially tidier definition can change what is elicited."

**Source.** Founder, 2026-10-30. Technical reference §5.

**Mechanism.** The precision "lies in the relationships it produces, not in narrowing every term to the medium of the artifact." The founder's account of the document's size: "as soon as a single token was changed or manipulated it then stopped working as tested, so rules weree added to reinforce what failed".

**Consequence.** A rule's token count says nothing about whether it is load-bearing. Only the founder decides what leaves default context. Do not reword the method. Quote exact spans.

**I observed.** The recovery package on the founder's Desktop holds 299 files. Its file names include `Sonnet_Intake.xml`, `Fable_Intake.xml` and `deepseek_flash_intake.xml`, and its notes date specific changes. `flask_intake.json` shows a collapse of the `name` field (CL-12).

**What I did.** I read the rules as old reinforcements and as bloat. The founder: "you are downplaying some of those rules which are loadbearing".

### CL-11. Loss from rewording is silent

**The author claims.** "the code base ingest will still work, it will lose about 50% of its agent benefit because it will collapse everything into the agents register who touched it and none of us will notice it even happened until we start implementing things like, hey lets use metaform to analyze the gameplay mechanics or the user to user collabortive surface".

**Source.** Founder, 2026-10-30.

**Mechanism.** "the agents will think its code start touching things they shouldnt our code quality will suffer everything will be cruft menus options and features will end up looking like they went through a blender and this project will be dead."

**I observed.** Two code-specific phrases in the supplied intake date from October edits, according to the recovery notes (`metaform/Intake.xml` step 1 and the completion condition).

### CL-12. The name field is not the industry name

**The author claims.** "the name field isnt the industry name, it can be but by definition it isnt.. all systems have names for things". Preprint §3.3: "The namespace supplies a functional proper noun, while a descriptor retains the project's own name for that functionality."

**Source.** Preprint §3.3. Technical reference §4, commitment F06. Specification §4. Founder, 2026-10-30.

**Mechanism.** "The functional type engages general understanding. The project name resolves how this artifact refers to that functionality."

**I observed.** `flask_intake.json` (2026-10-29) has 29 of 29 names equal to the reversed short name. Some can match legitimately. All 29 suggest that the field was computed. Earlier intake wording allowed an inferred or informal name, and the industry-term fallback first appears in commit `451027385a8d`, 2026-10-01, by my search of the recovered copies.

---

## C. The benefits

### CL-13. Less hallucination

**The author claims.** "a system that can limit (maybe stop) hallucination". And, "when implemented properly, less hallucination".

**Source.** Founder, 2026-10-30. Technical reference §11.

**Mechanism.** "The reduced-hallucination mechanism is the same preparation viewed from another consequence. Project names, functions, reasons, and prior conclusions are provided rather than left for the working agent to invent or reconstruct. The author's measured experience underlies this account; the mechanism is described here without substituting fabricated rates or numerical guarantees."

**I observed.** Every error in `reading-the-top.md` was a gap filled with fluent reasoning. The deletion of two sandboxes followed from an assumed fact about ownership.

**What I did.** I named the reflex that doubts this claim. The founder said: "Not a single model that exists will take my words as true".

### CL-14. Better use of a model's reasoning

**The author claims.** "better use of your ability for higher order reasoning". The founder states what that means:

> "The claim is that by doing effort on behalf of a model in advance, that when the model comes in to do the work, it doesn't have to spend as much of its reasoning budget to try to orient itself, which is not a particularly small task."

**What it is not.** "I never said that enables higher order reasoning than what the model has already."

**Source.** Founder. Preprint §2. Technical reference §11.

**Mechanism.** "Instead of spending the work episode merely discovering that two components interact, an agent can reason about whether the interaction still serves its recorded receiving purpose, how a different Encounter would affect it, or whether another part already fulfills the same need. The abstraction and relationship are available as objects of thought." Preparation does not "replace the executing model's inference with stored answers. It changes the material on which that inference operates."

**I observed.** See CL-02.

**What I did.** I wrote this claim as "An agent has more capacity for higher-order reasoning." The author did not say that. The founder's sentence had the orientation question beside it, and I left that out.

### CL-15. More completed tasks

**The author claims.** "more completed tasks". And: "You can get a lot more done when somebody actually tells you about a system".

**Source.** Founder.

**Mechanism.** The founder's explanation of orientation cost: "this is why things get done wrongly or tasks are incomplete.. its not your fault." With receiving purposes represented, a proposed change "can be examined against receiving purposes: which providers continue to satisfy them, which relationships move, and which consequences change?" (technical reference §7)

**Specified.** Tokens per completed task, from the token meter, with task outcomes as a separate measure (revision §8.5).

---

## D. Mechanisms that serve the claims

### CL-16. Project-grounded lexicalization

**The author claims.** "Project-grounded lexicalization performs the referential interpretation of a request before execution while preserving the requested operation." (preprint abstract)

**Source.** Preprint §8. Technical reference §10, commitments F17, F18. Specification §18. The revision calls it an optional secondary producer (§8.6).

**Mechanism.** "It stops short of doing the task. The operation and meaning of the request are preserved rather than paraphrased, narrowed, or supplemented with an invented execution plan."

**The author reports.** The facilities are in the `chassis` snapshot, and "A shipped producer ... is not present in this snapshot."

### CL-17. Blindspot challenges

**The author claims.** "Blindspot challenges connect criticism to the project's reasons, unexplored concerns, and functionality already realized elsewhere." (preprint abstract)

**Source.** Preprint §9. Technical reference §11, commitments F19, F20. Specification §18.

**Mechanism.** The project answers a challenge in one of three ways: **A**, already considered and adds no benefit, with the reason; **B**, not considered and relevant, to explore; **C**, already handled elsewhere, with the location and relationship. "The letters are not the reasoning itself."

**The author reports.** State and plan storage are in the `chassis` snapshot. An integrated producer is not.

This is the project's own route for a model's objections. See `pushback.md`.

### CL-18. Information and imperative stay separate

**The author claims.** "An observation does not silently become an instruction."

**Source.** Preprint §7.2. Technical reference §10.

**Mechanism.** Informational layers supply facts. Imperative layers supply instructions when selected for that role. A task's text stays the user's operation.

**The author reports.** Part of this is in the `chassis` snapshot.

**What I did.** I turned a demonstration into rules.

### CL-19. Provenance

**The author claims.** "The useful question is not only what knowledge is available, but how it came to exist and what it was used to produce." (preprint §10)

**Source.** Preprint §10. Technical reference §13, commitment F23. Revision §10: "Provenance identifies a contribution's origin, not superior standing for its author."

**The author reports.** Layer provenance fields are in the `chassis` snapshot. The preprint says that its account "is not a claim that this snapshot already captures a universal automatic ledger."

**Specified.** Specification §11 requires that changes "retain attributable provenance".

### CL-20. Skills from a ticket and a functional perspective

**The author claims.** "we can create a prompt that takes a ticket + a functional perspective in any project and create the perfect skill, that will only show up as a skill when you need to work on that part of a project again."

**Source.** Founder, 2026-10-30. Revision §7.4. Specification §9.

**Mechanism.** The facilitator examines the provider's Encounter Function in the receiver's purpose record together with the specification-layer Objective Purpose, then creates or reuses a skill. "The query assembles already reasoned context; it does not infer a semantic intersection from arbitrary prose on every visit."

### CL-21. Specialists carry the method, and other agents do not

**The author claims.** "this understanding doesnt need to live in the head of an agent to use this system, infact it would hurt them more than help". And: "maybe just maybe we can slice up that context and deliver it on demand and create agents that do understand it like samurais of the method itself.  then it can be touched".

**Source.** Founder, 2026-10-30. Preprint §4.3: "The resulting data, rather than repeated exposure to the procedure's wording, is what later operations use."

**Mechanism.** "Those rules ONLY apply to intake and expanding the base functional map." Context for those operations is metaform concepts, TASTE concepts, procedure and patches. A patch is a single clarification, added after a failure is observed.

**Open.** Which rules ride with the procedure is the founder's decision. "if we choose to maintain that context, which we may or may not want to".

**What I did.** I handled the method with partial context and ranked its rules.

### CL-22. TASTE

**The author claims.** "the issue is that models paraphrase". Also: "setting some solid rules here can really help, so what we can adopt is our own custom subset of STE, we can call it TASTE  Topogee Agentic Simplified Technical English".

**Source.** Founder, 2026-10-30.

**Stated rules.** "always using the same terms to describe things that are the same, always using Industry Terms when reasoning on functionality". `name` stays the project's own name.

**Specified.** Specification §4 requires ASD-STE100 for metaform wording, and D-48 in the decision log covers OP and RE sentence parts. The rule set is in `countermeasures.md`. Whether TASTE applies to the authored method is the founder's decision.

---

## Summary

A dash means that I have nothing to add from my own observation.

| Claim | Stated by | What I observed or did |
|---|---|---|
| CL-01 Amortization | Preprint, technical reference | — |
| CL-02 Orientation cost | Founder, preprint | About 72,000 tokens taken in before my first long reply |
| CL-03 Type understanding | Preprint, founder | I could state purpose and constraints before any code |
| CL-04 Address as prompting surface | Founder's example, preprint | Four addresses, 40 practices, about six repeat |
| CL-05 Knowledge layers | Founder, preprint | — |
| CL-06 Contextual precision | Founder, revision | The same words failed in a long message and worked alone |
| CL-07 C(T) | Preprint, definition | My first summary went past the text |
| CL-08 Stability | Founder | — |
| CL-09 Cross-artifact use | Founder, preprint | — |
| CL-10 Tuned terms | Founder | Intake variants named for models, on the Desktop |
| CL-11 Silent loss | Founder | Two code-specific phrases dated to October edits |
| CL-12 Name field | Preprint, founder | 29 of 29 names equal the reversed short name |
| CL-13 Less hallucination | Founder, technical reference | My errors were gaps filled with fluent reasoning |
| CL-14 Better use of a model's reasoning | Founder, preprint | See CL-02 |
| CL-15 More completed tasks | Founder | — |
| CL-16 Lexicalization | Preprint | — |
| CL-17 Blindspot challenges | Preprint | — |
| CL-18 Information and imperative | Preprint | I turned a demonstration into rules |
| CL-19 Provenance | Preprint | — |
| CL-20 Generated skills | Founder, revision | — |
| CL-21 Specialists | Founder, preprint | I ranked rules with partial context |
| CL-22 TASTE | Founder | — |
