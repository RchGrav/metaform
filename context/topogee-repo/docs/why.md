# Why this project exists

This file states the problem and the design in project terms. Each statement names its source. Where I add my own reading, I label it. Quotes keep the founder's spelling.

## The question

The preprint states the organizing question:

> "what reasoning can be performed in advance to offset reasoning that an agent would otherwise have to perform while doing the work?" (preprint §1)

The founder states the prime focus of this project:

> "Our prime focus for this project is contextual precision"

The two statements work together. The first says what to prepare. The second says how to deliver it.

## The problems

### 1. Orientation is repeated work

An agent that arrives in a project must find out what the project does, how its parts relate and what a request refers to. The preprint calls these "inferential obligations". When the working agent carries them, "each work episode reconstructs some of the same understanding, with the particular session's attention determining which relationships become available." (preprint §1)

The founder states the cost directly:

> "How much reasoning do you think an agent uses when walking into a project just to orient itself?  its not nothing"

> "You can get a lot more done when somebody actually tells you about a system versus coming in and needing to figure everything out on your own, which is usually what models have to do. They're told about a problem and they have to use rip grep and do all these different things. It just takes a lot more effort."

### 2. Gaps get filled with invention

If a project does not supply names, functions and reasons, the agent supplies them. The technical reference describes the opposite condition: "Project names, functions, reasons, and prior conclusions are provided rather than left for the working agent to invent or reconstruct." (technical reference §11)

### 3. Models paraphrase, and shared context spreads

The founder's statement:

> "the issue is that models paraphrase, and you more and more tend to communicate through shared understanding when orchestrating which is fine and all but you also that infects everything you say and write.. and more than that in a system like this where agents can communicate, and context is based on functional topology, combined with the inability to know what is your own context and what is shared context, setting some solid rules here can really help"

### 4. Agents change what they do not fully carry

The intake terms are deliberately ambiguous contextual anchors. The founder's account of what happens when an agent touches them:

> "The danger here is that when an agent sees these prompts it will infer "I can improve this I will change words I will add constraints I will start talking about the process of analyzing the code and improve this process."  In the end what will happen is the code base ingest will still work, it will lose about 50% of its agent benefit because it will collapse everything into the agents register who touched it and none of us will notice it even happened"

The failure is silent. Code intake continues to work. The loss appears when the method meets non-code functionality. The preprint states the same risk: "replacing them with generic software-analysis terminology would change that operation." (preprint §4.3)

### 5. Agents treated the store as the interface

The founder's account of the last project:

> "The mistake I made last time was giving all the agents that context and instead of building a proper mcp interface they gave the agents direct access to the back end data and started treating it like an interface to maintain the db..   thats the wrong reasoning.."

The specification carries the correction: "MCP is a properly engineered agent interface to functional operations, not an exported database editor" (specification §8).

### 6. Knowledge reaches agents that should not carry it

The founder's statement:

> "this understanding doesnt need to live in the head of an agent to use this system, infact it would hurt them more than help.. and I suspect that is true of many systems.."

And later, on the intake rules: "here is why we might not want to and there is a idiom which matches it, its called "A little knowledge is dangerous"".

## The design

### Two sides

> "remember that there is two sides of it one is the unified functional space that stores the data and the other is the procedure"

The metaform is the functional space. The intake procedure is what establishes it.

> "the metaform itself is a pure functional undrstanding, not the programming language, no non functional properties at all..  its so strict it names platformer illegal during intake but fps valid  (Those rules ONLY apply to intake and expanding the base functional map.   outside of that process things go into knowledge layers"

### Internal and presented

> "we present to the users (ie the agents uising the context in the terms they understand and enforce TASTE, but internally storing data and procedurally we use the metaform context."

### The address

An address names a functional type. It reads as a functional name when reversed. Every prefix is a complete type. The address engages what the preprint calls primordial type understanding. The term "identifies the understanding engaged by meaningful types; it is not a claim that namespace segments address particular neurons or internal model activations." (preprint §3.1)

An address alone does not describe the project. "The typology supplies the kind of understanding to engage. The relational data supplies the artifact-specific content through which to engage it." (technical reference §2)

### The purpose record

A purpose record holds a receiver's Operative Purpose and the Encounter Function that serves it. The receiver owns it. It records why a connection exists, and the preprint treats it as the object later work reasons about. (preprint §4.2; the papers call it a join, and the current specification stores it in `wants[]`, with `goal`, `function`, and `intent`.)

### The name

The address gives the functional name. The `name` field gives the project's own name. Preprint §3.3: `code.system.plugin` reads as plugin system, and the project name is module contract and loader. The founder's example: `document.dialect.project` with `name_length` 2 reads Project Dialect, and the name is TASTE. The name "can be" the industry name, and "by definition it isnt".

### The knowledge layer

The founder's statements:

> "what is a knowledge layer..  its basically anything which is understanding which needs to be understood in that part of the project but is irrelevent elsewhere."

> "how its possible to magnify a propt across the whole functional topology of a project"

Preprint §7.2: "Its result can be retained in a knowledge layer whose variable identifies the question it answers." The result stays at the location it concerns. Selection decides what participates in a given operation. Storage and participation are separate. (technical reference §9)

The demonstration is in `address-only-example.md`. The addresses are nearly identical. The instruction was one line. The lists hardly overlap.

### Progressive discovery

The founder's statement, including the founder's comparison:

> "Everything is progressive discovery...   just like if you were in a game as a character in 3d space you benefit more from an array properties and distances, vectors between bounding boxes, more than vision helps..  thats a spacial topology, if you are an agent in a project you benefit from the skilles needed for the functional topology your are in, what are we providing to modules calling us, what are we calling, what skill do I use. what rules and knowledge is needed here by me. the bigger the project the more relevent this becomes.  So for an agent I think of functional space the same way as any other space..  it should be what you need to know, what matters to your job, what can we do in advance to orientate you to what you need to do.  When I showed up as a network engineer on a job I didnt give a shit about what the plumber is working on, understand?"

The October 27 revision states the delivery contract: "Arrival supplies orientation: the target Address, relevant receiving purposes and Encounters, current work, and descriptions of the attached material. Larger specifications, documents, memory bodies, and skill files are read when needed." (revision §8.1) The same section states the limit: "The objective is minimal unnecessary delivery, not minimal understanding."

### Specialists and ordinary agents

The founder's statement:

> "maybe just maybe we can slice up that context and deliver it on demand and create agents that do understand it like samurais of the method itself.  then it can be touched"

Ordinary agents use the map through the interface. Agents that perform intake or change the method carry the method. The current form of the intake context, in the founder's words: "intake needs metaform concepts plus TASTE concepts + procedure + patches".

## The intended result

The founder's statement:

> "It enables when implemented properly, less hallucination, better use of your ability for higher order reasoning, and more completed tasks."

`claims.md` documents each of these in full: what it says, how the mechanism produces it, what is on record and what is not.

## Status

This repository contains no working application. The specification is a candidate for founder review. The preprint's implementation tables describe an earlier snapshot, `chassis` commit `ce9062bdec9398ca1f23ac60684bd3cc7e37f23c`. They do not describe this repository. The rebuild is clean.
