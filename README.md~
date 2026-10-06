
> "Empty your mind. Be formless, shapeless, like water. You put water into a cup,
> it becomes the cup. You put water into a bottle, it becomes the bottle.
> You put it in a teapot, it becomes the teapot. Water can flow, or it can crash.
> Be water, my friend."
> — Bruce Lee

---

## What is Metaform?

Metaform uses the concept of *meta* to abstract your ideas into their purest
functional form — then stores that form as a living, queryable structure your
agents navigate, recompose, and build from.

A codebase is a forest. An agent can have perfect memory of every file, every
doc, every past session — and still be lost, because memory doesn't say where
you are, what anything is for, or which direction serves the purpose. Metaform
is the view from above: the functional shape visible at once, purposes laid out
as terrain, every agent's position marked within it. And because ideas are
stored as functional forms rather than implementation descriptions, the forest
itself can be recomposed. The form is built once, before the work starts, and
amortized across every agent, every session, and every operation that follows.

## The name

**Meta** — showing or suggesting an explicit awareness of itself or oneself as
a member of its category : cleverly self-referential

**Form** — a type or kind of something
           to cause (something) to have a particular shape or form. 
           to get, create, or develop (something) over a period of time
           to make or create (something)
           to be arranged in (a shape)

## What it does

**Orients.** Every element has an address, a purpose, and a record of what
depends on it. Agents receive their position, their purpose, and exactly the
knowledge in scope — the stored functional record, not a paraphrase of last
session's chat.

**Abstracts.** The shape of your AI Agent's workpiece is derived from its functionality, not
its medium, genre, style, encoding, file layout, class hierarchy, or framework.

**Recomposes.** Functional forms can be rearranged. Attach knowledge layers,
hide old ones, swap realizations under stable purposes, graft a capability from
one project into another. The addresses don't move; the purposes don't change.

**Traces.** Every output binds back to the exact inputs that produced it — the
prompt, the knowledge selected, the run, the diff. *Why is it like this?* is a
query, not an excavation.

## What it looks like

An agent assigned to work on your event bus receives the stored record:

    code.bus.data.event
      join → code.runtime.execution
        op: "Run each subscriber's handler as attributable work, so a slow or
             failing handler is reported for that handler and never blocks
             the publisher or another module."
        observation: "An event data bus hands each delivery to a runtime that
                      executes the subscriber."

Every agent that touches this element — this session, next month, a different
model from a different vendor — sees the same stored purpose.

### Refactoring legacy code

A capability smeared across twelve files gets one coherent functional shape,
bound back to the exact locations where it lives. Ask "what is the
authentication flow" and get an answer that spans files, references exact
lines, and describes purposes and encounters — not which class calls which
method. The map is generated from what the code *does*, not from its AST, so it
stays stable while the implementation moves under it.

### Porting across languages

**Before:** elements carry layers of C++ best practices and memory-management
concerns, injected into prompts when agents work on those elements.
**During:** a "porting to Rust" layer attaches — ownership semantics, lifetime
annotations, error handling — while the C++ layers mask out.
**After:** the C++ layers hide (revisioned, resolvable, never deleted); the
Rust layers activate. Addresses unchanged. Purposes unchanged. The knowledge
swapped. Past prompts remain exactly as issued; future prompts receive the new
layers.
