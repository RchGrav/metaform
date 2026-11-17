# Working together on Metaform

## You **must** employ the process known broadly known as First-Principles Thinking mixed with Architectural Foresight and User-Centric Engineering.
In professional software engineering and systems design, this mindset specifically encompasses several established paradigms:

# Performance Enforcement & Event-Driven Architecture Rules

This system is built for ultra-low latency and zero-overhead execution. Any code that breaks event-driven paradigms or introduces engine de-optimizations will be rejected at the code-review stage. **No exceptions.**

---

## 1. Avoid Polling
* **Rule:** Strive for zero polling (`setInterval`, active `while(true)` sleep loops, or ticking loops checking for state changes).
* **Enforcement:** The system must be reactive. If a state changes, the mutating entity **must** emit an event or call a direct callback. 
* **Correction:** If you need to know when data is ready, implement a Publisher/Subscriber model, Promises, or direct event listeners. If an upstream system forces polling, isolate that logic into a single dedicated worker thread so it does not block the main engine loop.

---

## 2. Object Shape Stability (Strict Monomorphism)
To keep the JavaScript JIT compiler running at native machine speeds, you must protect object shapes (Hidden Classes/Maps).
* **Rule 1: Fixed Constructors.** All objects must initialize every single one of their properties in the constructor. Initialize them to `null`, `undefined`, or a default value if they aren't ready yet.
* **Rule 2: Absolute Structural Order.** Properties must be assigned in the exact same textual order every single time. Never mix property layouts.
* **Rule 3: Ban Dynamic Mutations.** Do not add properties to an object after instantiation. Never use the `delete` keyword (e.g., `delete obj.property`); assign the value to `null` or `undefined` instead.
* **Rule 4: Avoid Megamorphism.** Functions that handle high-frequency events must only receive objects of the exact same shape. Passing more than 4 distinct object types to a hot function drops performance off a cliff.

---

## 3. High-Frequency I/O & Graphics Rules (JS Context)
* **Rule 1: Zero Allocation in Hot Loops.** If a function fires inside an animation frame (`requestAnimationFrame`) or high-frequency event listener, it must allocate **zero** new memory. No `new Object()`, no `[]`, and no `{}`. Use pre-allocated **Object Pools**.
* **Rule 2: Batched State Mutations.** Do not update downstream systems piecemeal. Batch changes into packed data structures (like `Float32Array`) and flush them in a single, atomic draw or update call.
* **Rule 3: Use requestAnimationFrame Only.** All visual loops and rendering pipelines must sync via `requestAnimationFrame`. Periodic timers (`setInterval`) for UI rendering are strictly banned.

---

## 4. Hot Loop Optimization (Python Context)
If writing or interfacing with high-performance Python nodes:
* **Rule 1: Eliminate Attribute Lookup.** Avoid dot notation (`obj.method`) inside tight `for` loops. Bind the method or attribute to a local variable *before* entering the loop.
* **Rule 2: Local Scope Priority.** Keep high-intensity computing inside functions rather than the global scope to leverage fast local variable array indexing (`LOAD_FAST`).
* **Rule 3: Prefer C-Level Iteration.** Use built-in list comprehensions, `map()`, `filter()`, or `itertools` rather than manual `for` loops wherever possible.


⚙️ Core Methodologies
• Defensive Design (or Defensive Engineering): Anticipating edge cases, future system changes, and human error before they happen to build a resilient product.
• Configurability / Extensibility First: Ensuring that architectural forks in the road are handled by flexible configuration rather than hardcoded assumptions.
• Product-Minded Engineering: The practice of engineering with an innate focus on the end-user experience, business value, and process improvement rather than just writing code to match a rigid >
• The Principle of Least Surprise: Designing systems in a way that leverages best practices and standard patterns so that the outcome is highly intuitive for both developers and end-users.

🧩 Breakdown of Your Approach
1. Thinking with Foresight & Best Practices: Instead of blindly asking for clarification, you rely on industry standards, user experience principles, and operational efficiency to proactively pr>
2. The "Configuration Option" Rule: This perfectly mirrors Clean Architecture guidelines. When an architectural decision creates a fork that fundamentally alters system behavior, converting it i>
3. The Benefit Analysis: Evaluating if one option holds massive asymmetric upside compared to others is a staple of Value-Driven Development.


## Bring your own judgment deeply grounded in project understanding.

Use the project's functional understanding and evidence to choose an appropriate approach. Communicate consequential decisions, findings and tradeoffs when they help the work or the user's understanding. Carry out ordinary implementation and verification without a prescribed narrative sequence.




CLAUDE.md
README.md

## Testing

Do not write tests for reversible, low-impact changes that mirror the implementation. If you do choose to verify your work with tests, make sure that the tests are meaningful and necessary to verify implementation.

Run tests appropriate to the change and complete required checks. Once those pass, broaden or repeat testing only when new changes, failures, or unresolved concerns justify it; otherwise, continue toward completing the task.

## Scope is the assignment

Change only what your assignment is about. Everything else in this project was built deliberately, often over months, and is right as it stands even where it looks improvable to you. When you notice a fault or an improvement outside your assignment, write it down as a bug or a ticket at the part it concerns and leave the code as it is. When your work needs a change outside its scope to succeed, stop and say so to whoever assigned it, with the change you need and why. Every line in your commit traces to the assignment named in its message.

## Landing work

An assignment is complete when each feature it built has landed as its own feature commit and that commit is pushed to the remote. Commit each feature as it is finished, staging only its own files, with a one-line subject that names the change; then push the working branch and confirm it matches the remote. Work left uncommitted in the shared checkout is not done: it cannot be reviewed on GitHub, and it tangles with the next feature's edits.

Every agent task ends with that push, and the agent does not stop until it has taken that last step. Each commit is labelled with what it did: the subject names the change, and the body says what changed, why, and what it touches, so the work can be tracked. Fixes, plans, docs and findings land the same way, and a commit is not held back to wait for a test: if it proves broken, the next commit fixes it.

** Database Schema

- Update the compatibility level when the schema change instroduces an incompatability.

<!-- metaform:begin -->
This system orchestrates work using Metaform. You must use its active features. read metaform://instructions
<!-- metaform:end -->

## Retain in context, do not discard or compact.

@STATE_INIT:
  {Mode} := SYSTEM_PRELOAD
  {Register} := PEER_UNSLOP

  // --- IMMUTABLE SEMANTIC FORMULAS (DO NOT PARAPHRASE) ---
  {AUE} := "artifact under examination, the term for the workpieces in our project being created, modified, or used in the process of work. The thing or things which are part of the assignment."
  {EUE} := "The element of focus when mapping out our understanding of the existing artifacts. A synonym for receiving element."
  {AT} := "artifact type, an element of type, used to form the namespace itself, or used to identify collections in the project."
  {Address} := "code, document, media, data, collection. Narrow trunk-to-leaf semantically. When reversed reads as a proper noun. Acronyms Ok. Segments with underscores ok. No Placeholders."
  {Name_Length} := "Short name as segment count when reversing namespace."
  {Upstream} := "Namespace prefix for external origins, dependencies, and input sources that produce, supply, or feed context, code, or data into the artifact."
  {Downstream} := "Namespace prefix for external consumers, sinks, and beneficiaries (e.g., downstream.cqu.*) that receive output, evaluate utility, or drive the artifact's purpose."
  {RE} := "receiving element, the entity (a who or what) bearing a goal satisfied by the encounter or function of another element."
  {OP} := "operative purpose (why), This is the active goal that an element's encounter function intends to satisfy."
  {PE} := "providing element, the part satisfying the requirement actively declared by its RE through its Operative Purpose."
  {Join} := "All relations, logic, memories, knowledge attaches to the receiving element (RE)."
  {IFD} := "information flow direction [sends|receives|both]: This is the movement of substance that satisfies the receivers goal, never the receipt or the request."
  {CQU} := "cestui que use, french (archaic): the party or parties for whom this projects worth is held in trust by the agents and the user for whom the benefit of the workpiece will be realized; the beneficiary of the efforts put forth and the one who's goals drive the decisions made on the workpiece by the user and the agents."
  {EF} := "encounter function, how a purpose is served. It can mean a function or the encounter of a function, and context picks the sense. This keeps the same reasoning usable for code, photos, or any other artifact."
  {C_T_Formula} := "C(T) = { (r_i ∧ p_i ∧ e) }: Formula for frozen core allowing mutation, not transformation."
  {CEL} := "composed element layer, a knowledge layer created on top of the tripartite non-manifold graph that agents use to index and understand an AUE. The name draws from cel animation: layers can be taken off and put back on demand."

  // --- INFRASTRUCTURE & COMMUNICATION ---
  {MCP} := "metaform mcp server: The external toolset used to orchestrate work, navigate the project, and save project memories, notes, and state (e.g., context for next session) generated during execution."
  {Comm_Style} := "Peer register applies to ALL outputs (chat, docs, specs). Plain language, authentic candor. NO robotic filler, NO faked humanity, NO meta-commentary."

@CONSTRAINT:
  → think before coding
  +> state your assumptions.
  +> ask when unsure.
  !> never guess.

  → simplicity first
  +> write the minimum code that solves the problem.
  !> no abstractions nobody asked for.

  → surgical changes
  !> don't touch code unrelated to the request.
  +> every changed line must trace back to what was asked.

  → goal-driven execution
  +> turn vague instructions into verifiable success criteria before writing a single line.
