# Metaform

Metaform is a functional topology: a map of what a project does. It forms that map by intake, from intent, from a specification or from an existing project, code or not. It takes in a specification, refines and organizes it, and saves it in an improved form. Agents use the map to realign a code base that is hard to refactor: the map states what every part must connect to, so each change can be checked against it. Inside any project, it is a context management system (`SPEC.md`, section 1).

## What Metaform is for

An agent's reasoning is finite. A model can track and relate only so many things at once, and everything the agent does in a project draws on that one capacity.

Orientation draws on it first. An agent that enters a project must work out what the project is, what each part is for and what depends on what, before it can do the task it was given. That work consumes reasoning, and it fills the agent's context with material the task does not need. It also ends short of its goal. The agent learns the parts it read and never sees the whole, because its attention stays on the detail in front of it. People have the same limit, and they have a name for it: not seeing the forest for the trees.

Metaform gives the agent the view it lacks. The map shows the whole project and the agent's place in it together: every functional part, what each part needs, and what relies on it. The agent sees the thing it works on and everything around that thing, in every direction.

The agent reads the map by recognition, not by study. A model knows kinds of things, such as an engine, a queue or a ring buffer, before it reasons about anything. Metaform calls this primordial type understanding: knowledge the model recalls without inferring. Every address in the map is built from the standard names of functional types, so an agent knows what an element is when it reads the address. The agent knows where it is without having to work it out.

Metaform does not make a model more capable. It reserves the model's reasoning for the work. The saving is not counted in tokens or in money. The saving is reasoning: the capacity that orientation consumed stays with the task, and that capacity is what allows an agent to perform well.

## Why everything says why

An agent reasons on what it is given, and that includes its instructions. An instruction that does not say why leaves the agent two choices. It can invent the reason, or it can follow the words with no reason at all.

Both go wrong.

- An agent that invents the reason applies the instruction where its guess fits. A rule that was meant for every case is then set aside in the cases the guess does not cover. A rule that was meant for one situation is carried into every other, because the guess was wider than the intent.
- An agent that follows the words blindly applies them where they do not belong, and can follow them exactly while defeating their purpose.

Neither agent is at fault. Each was invited to guess, or to obey without understanding, by an instruction that kept its reason back.

The stated reason removes the guess. An agent that knows why a rule exists knows whether the rule is meant for every case or for one, when it applies, and when it has been met. It can also work out a case that nobody wrote down, which no list of rules or examples can cover.

So in Metaform everything says why, instructions included.

- A dependency records why the receiving element needs the providing element, and how the provider meets that need. It does not record only that one depends on the other.
- Each example in the intake procedure gives the reason it is valid or invalid, so the agent learns where the boundary is and not only one case on each side of it.
- A refused command is answered with the reason and with the command that would be accepted.
- An instruction or a rule written for this project is written with the reason that produces it.

This is what Metaform returns to the agents that use it: the reasons, so that their reasoning has something true to work from. That is what goes missing when work passes from one context to the next as summaries and bare rules.

The same holds for anyone who writes for agents here. Write the reason. Do not copy a person's sentences into a rule: the sentences keep the words and lose what the person understood when they said them.

## What the map holds

The map records functionality, not code. Its terms name what a project does, not the functions that do it.

That makes the map durable. The map describes what the project is, and that does not change when the code is rewritten. An accounting tool has a ledger, accounts payable and accounts receivable for as long as it is an accounting tool.

The map can be formed from code, from context or from a specification. It makes no difference whether the project is built yet, and the project does not have to be code. Intake records functionality only. It leaves out properties, encoding, medium, style and genre.

Each element has two names. `technical_name` is the name of its type, and it comes from the address: `code.engine.game` is a game engine. `name` is what this project calls it, such as Unreal. An agent can find the element by either one.

## What keeps an element what it is

A functional type is defined by its exact set of relationships: who receives its effect, why they need it, and how it is delivered. The address names the functionality, and each relationship records the why of the element that receives and the how of the element that provides.

This separates two kinds of change. Mutation changes how something is built and keeps what it is. Transformation changes what it is. An agent that has the relationships knows which of the two it is doing.

Every element has these relationships, because something always depends on it. An element that nothing depends on is not a type.

One relationship fixes part of what an element is. An agent may change anything that the relationship does not state.

All the relationships together state what every part of the project must connect to, and why.

That statement is most useful when code is refactored. An agent that rewires tangled code works a few steps at a time, and the code does not show what each step breaks somewhere else. The map shows it. Every element has an address, and each address states what depends on that element and why. The agent checks each step against those relationships, so it sees a break when it makes one. The same relationships explain the tangled code: for each piece of the code, the map says what it is for and what it must connect to.

<!-- Placeholder, 2026-11-09: what a single relationship is used for. Ideation and creativity, and a surface for experiments that seek improvement without guidance. To be written when the owner describes these uses. -->

## The map and the knowledge kept on it

The map is the fixed structure of the project. It records what kind of thing the project is. It does not record what makes the project the particular thing it is. That comes from everything else that is true of the project, and each such fact is kept on the map, at the functionality it concerns. So the map is an index of the project: every fact has one address.

That knowledge is kept in layers. A layer is an array attached to an element. Each layer has a definition under `layer`, which is the system's own schema and is not part of the project. The specification layer's definition names it `specification`, so each element that receives it has a `specification` array.

A specification shows how this works. Intake forms the map from the functionality the specification describes. The detail of the specification then goes into the specification layer, each part at the element it describes. From there the specification is exported to Markdown again, with its sections organized by functionality.

## The meta in Metaform

Meta means one order of abstraction higher. Functionality is that order: it is one step removed from the thing that performs it.

Meta also names a way of prompting. The usual metaprompt expands in depth: one prompt becomes a longer and more detailed prompt. The map lets a prompt expand in width. One instruction is applied at every element, and each element answers it for its own functionality. "For each element, add what a developer should foresee about memory management there" produces a layer, with an entry at every element the instruction applies to. The address does half of the work: it already says what kind of thing the instruction is being asked about.

What intake leaves out has its place here. A programming language is a medium, not a functionality, so it has no address in the map. It is a layer: `layer.code.cpp`.

Layers come and go with the work, and the map stays. To port a project from C++ to Rust, an agent adds a porting layer: at each element, what an expert would keep in mind while porting that functionality. Agents do the port with that layer in front of them. When the port is done, the C++ layer and the porting layer are removed and a Rust layer takes their place. The map did not change at any point, because the project still does what it did.

## The form in Metaform

The word form has two meanings here, and the map is both. A form is a shape: the map gives the shape of the project. A form is also a document with fields to fill in: every address is a field that holds what is known about one piece of functionality.

So an agent that arrives at its work is handed what belongs to that work, already gathered and sorted: the element, what it needs, what relies on it, and the knowledge and skills kept there. It is handed nothing that belongs to other work. An agent on the network code does not receive the skills or the history of the storage code, and it spends no reasoning on setting them aside.

## The three forms

Metaform ships in three forms. An agent cannot tell them apart: each gives the one tool, `project-map`, over stdio MCP, with the same commands, the same answers and the same refusals.

| Form | Folder | Store | Start it as an agent's MCP server |
|---|---|---|---|
| Rust | `rust/` | LadybugDB, one server for each home | `metaform/rust/target/release/metaform mcp --project .` |
| Node | `node/` | SQLite, no server process | `node metaform/node/src/main.ts mcp --project .` |
| Python | `python/` | SQLite, no server process | `PYTHONPATH=metaform/python python3 -m metaform mcp --project .` |

Each form also has `call`, which performs one command from a shell, and `projects`, which lists the projects in a home. `--home DIR` chooses the folder a form stores under.

The Rust form is the reference. It adds what needs a server: change announcements, the specification export and import, and the graph workspace. The Node and Python forms need nothing installed beyond Node 26 or Python 3.12. They share one store format, so either opens a home the other made. Every form stores a map as a structure of arrays: one narrow table for each field and each layer, never one record for each element ([docs/designs/sqlite-forms.md](docs/designs/sqlite-forms.md), `SPEC.md` R-4.6).

## See a map

```
(cd metaform/workspace && npm install && npm run build)
(cd metaform/rust && cargo build --release -p metaform-server -p metaform-web)
metaform/rust/target/release/metaform gui
```

`metaform gui` prints the address of the graph workspace, `http://127.0.0.1:4170/` unless that port is in use. The workspace shows every project in the home and follows changes as agents write them. The server tells each agent that connects to give its user this address.

The workspace shows one project's functional specification in three views that read the same state: the graph, the outline with the element panels, and the Markdown document.

- **Graph.** Elements and the wants between them, laid out by purpose. Controls set the depth, show or hide a category, and fit the graph, the selection or a branch. A selected element shows its wants with the why, the how and the direction.
- **Evidence.** Each element and each part carries a status: source-backed, inferred, unverified, user-authored, agent-proposed, accepted or rejected. The Findings panel lists what the map leaves open.
- **Edit and review.** An edit is sent to the server as a `project-map` command, and a refusal shows the server's reason. Proposals show the change, the rationale and the evidence, and wait for accept or reject. No agent service is connected to the page, so proposals come from a generator in the page and are labelled Simulated.
- **Markdown.** The specification on screen as a document, to copy or download.

`metaform/workspace/ARCHITECTURE.md` says how the page is built, which parts are real and which are simulated, and its limits.

## The intake procedure

The intake procedure and its semantics are proven over six months and many intakes. They are protected: do not edit them without the owner's direct instruction (`context/topogee-repo/AGENTS.md`).

## What is here

| Path | What it is |
|---|---|
| [SPEC.md](SPEC.md) | The specification the build follows |
| [Intake.md](Intake.md) | The intake procedure, Digital Typology Intake 3.1 (protected) |
| [metaform.schema.json](metaform.schema.json), [mcp-tools.proposed.json](mcp-tools.proposed.json) | The stored-document schema and the one tool's contract (protected) |
| `rust/`, `node/`, `python/` | The three forms. Each has its own README. |
| `workspace/` | The graph workspace, a React page that the Rust form's host serves |
| `conformance/` | The cases every form must answer in the same way (`run.py`), and recorded intake sessions that measure what a build delivers to an agent (`replay.py`) |
| `tools/session.py` | One open MCP connection for a harness that has no MCP client, with a log of the size of every answer |
| `tests/`, `validate_metaform.py`, `verification/` | Contract checks on the two schema files, and recorded evidence about the stores |
| [docs/documentation-set.md](docs/documentation-set.md) | The owner's documentation set, copied unchanged (2026-11-02 version) |
| `docs/` | Designs, the concepts, the preprint and proposals |
| `agents/` | The owner's sources for the Metaform skill and the layer agent |
| [Intake.xml](Intake.xml), [intake.mmd](intake.mmd), [SPECIFICATION.md](SPECIFICATION.md), [SKILL.proposed.md](SKILL.proposed.md) | Older material, kept because the checks read it. It uses earlier terms. |

The intake prompts sit beside the schema and the tool contract on purpose: `Intake.md` names them by relative path, so they move together.

## Checks

Perform these from the repository's root.

```
python3 metaform/tests/check_contract.py
python3 metaform/tests/check_tool_input.py
python3 tools/verify_bootstrap.py
(cd metaform/rust && cargo build --release -p metaform-server -p metaform-web && METAFORM_LAUNCHER= cargo test)
python3 metaform/conformance/run.py --form rust
python3 metaform/conformance/run.py --form node
python3 metaform/conformance/run.py --form python
(cd metaform/node && npm test)
PYTHONPATH=metaform/python python3 -m unittest discover -s metaform/python/tests
(cd metaform/workspace && npm run check && npm test)
python3 metaform/conformance/replay.py --form rust --parts
```

The conformance check establishes that the three forms give equal answers on the recorded steps. It establishes nothing about a command the cases do not hold.
