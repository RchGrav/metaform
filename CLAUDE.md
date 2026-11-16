# CLAUDE.md

I want to put forth some expectations up from when it comes to this project and it's design. I ask that you recognize and respect them.
@EXPECTATIONS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Read `AGENTS.md` first: it holds the rules for working with Rich on this project, including how specifications are written with him and that `rich/` is his folder, never modified.

## The intake procedure and its semantics are the founder's

The intake procedure, its terms, its definitions and its examples are the result of months of testing across models and kinds of artifact. Change them only on the founder's direct instruction. This covers the served files in `src/metaform/modules/intake/resources/` (`intake.axiom`, `intake.xml`, `metaform.axiom`, `layer.axiom`) and everything in `rich/`.

Treat that text as a formula. Leave every step, rule and definition in its words, its order and its length. A passage that reads as ambiguous is contextual: its meaning settles from the artifact in front of the model, as a symbol takes its meaning from its formula. Report such a passage to the founder and leave it as it is. The reason: agents went in to remove what read as ambiguity, the meaning changed, and intakes stopped working as designed.

Everything around the text is open to change: where the files live, how the text is served, and the code and the tool that use it.

Keep tests, checks and build steps independent of the procedure's content: its section names, its marks and its wording. The founder edits it, and nothing may fail when he does.

Agents working in a project need no glossary. Element addresses read as plain names, and fields and roles are written in full. The procedure's own terms are read by the agent that performs an intake, from the procedure.

## Commands

```bash
uv sync --extra dev                              # install, with pytest, pyright, ruff, playwright
uv run pyright                                   # strict type check of src/metaform (tests excluded)
uv run ruff check src tests conftest.py          # lint, 120-character lines
uv run pytest -n 0 path/to/test_file.py -k name  # one test; -n 0 skips the xdist workers the default run starts
uv run pytest -m browser path/to/test_file.py    # browser tests, left out of the default run
uv run metaform <command>                        # the CLI; also .venv/bin/python -m metaform
uv run metaform mcp serve                        # the MCP server over stdio, from a project folder
uv run metaform web start                        # the web GUI, http://127.0.0.1:7433 by default
```

Tests live in `tests/` (chassis) and `src/metaform/modules/<id>/tests/` (each module). CI (`.github/workflows/checks.yml`) runs pyright, ruff and pytest on Linux, macOS and Windows, Python 3.11 and 3.14.

`conftest.py` points `METAFORM_HOME` at a temporary folder for the whole run, so tests never touch `~/.metaform`. The `home` fixture gives each test a fresh home; the `run` fixture runs the real CLI in-process (marker `cli_process`, or `METAFORM_TEST_SUBPROCESS=1`, runs each call as its own process). `@pytest.mark.req('MAP-012')` ties a test to the specification record it protects.

## Architecture
This system is built for ultra-low latency and zero-overhead execution. Any code that breaks event-driven paradigms or introduces engine de-optimizations will be rejected at the code-review stage. **No exceptions.**

---

## 1. Zero-Tolerance Polling Ban
* **Rule:** Absolutely zero polling (`setInterval`, active `while(true)` sleep loops, or ticking loops checking for state changes).
* **Enforcement:** The system must be 100% reactive. If a state changes, the mutating entity **must** emit an event or call a direct callback. 
* **Correction:** If you need to know when data is ready, implement a Publisher/Subscriber model, Promises, or direct event listeners. If an upstream system forces polling, isolate that logic into a single dedicated worker thread so it does not block the main engine loop.
* **Use what exists.** The chassis already has the event system: the bus (`events.publish`, `publish_async`, `Subscription`), the cross-process relay of `map.changed` (`ctx.listen`, `events.listen`), `changes.note`/`announce` after writes, and `ctx.spawn` for owned tasks. A new kind of change becomes a topic on that bus or a field on `map.changed`, never a second mechanism. On the page, the live stream is the server's voice: its closing is how the page knows the server is gone.
* **Not polling:** a real deadline (a time limit on one request, a silence clock, a timer an agent set), a retry backoff after a failure, and pacing (audio playback, a demo's deliberate stagger). Each fires once for a reason; none wakes up to look for a change.

---

## 2. Event Handlers Do Only What the Event Requires
Removing timers is not enough: a handler that re-reads or recomputes everything on every event is polling triggered by events, and it costs more the busier the system gets (2026-10-15: ten idle runners at about 80% of a core each, and the page server spawning a subprocess per change).
* **Rule 1: Events Say What Changed.** Every event carries enough to decide who it concerns: the table or topic, and the ids it touches (project, ticket, session) and the kind of change. `map.changed` carries `work_ids`, `session_ids` and `kinds`.
* **Rule 2: Handlers Filter First.** A handler acts only on events that concern it, decided from the event alone, and then does only the work that change requires: read the one record, not the collection.
* **Rule 3: Never React to Your Own Writes.** A process ignores the events its own writes caused.
* **Rule 4: Coalesce Bursts.** Events that arrive while work for an earlier one is pending merge into that work; a burst costs one pass, not one per event.
* **Rule 5: Prove It.** A change to an event path shows, before and after: the process's CPU at idle over 60 s, and a test where a burst of events that do not concern the handler causes zero reads.

---

## 3. Object Shape Stability (Strict Monomorphism)
To keep the JavaScript JIT compiler running at native machine speeds, you must protect object shapes (Hidden Classes/Maps). Sections 3 and 4 bind hot paths: anything that runs per frame, per event, or per item of a large collection (nodes, joins, fibers, flow dots, figures). New code follows them everywhere; existing cold code (setup, menus, one-off settings) is not rewritten for them.
* **Rule 1: Fixed Constructors.** All objects must initialize every single one of their properties in the constructor. Initialize them to `null`, `undefined`, or a default value if they aren't ready yet.
* **Rule 2: Absolute Structural Order.** Properties must be assigned in the exact same textual order every single time. Never mix property layouts.
* **Rule 3: Ban Dynamic Mutations.** Do not add properties to an object after instantiation. Never use the `delete` keyword (e.g., `delete obj.property`); assign the value to `null` or `undefined` instead.
* **Rule 4: Avoid Megamorphism.** Functions that handle high-frequency events must only receive objects of the exact same shape. Passing more than 4 distinct object types to a hot function drops performance off a cliff.
* **Rule 5: Contiguous Arrays.** Arrays stay dense and hold one kind of element: no gaps (`arr[100] = x` on a short array), no mixing numbers with objects. A gap turns the array into a hash table. Numeric data in a hot path goes in a typed array (`Float32Array`, `Uint32Array`), sized once.
* **Rule 6: Structure of Arrays, not Array of Structures.** Hot data that is iterated by field is laid out one array per field, indexed by item: `x[i]`, `y[i]`, `z[i]`, `speed[i]` in typed arrays, not `items[i] = {x, y, z, speed}`. A loop then walks contiguous memory and touches only the fields it uses, there are no per-item objects to keep in one shape or to collect, and the arrays go to the GPU as buffer attributes as they are. An array of objects is fine for cold data looked up by id.

---

## 4. High-Frequency I/O & Graphics Rules (JS Context)
* **Rule 1: Zero Allocation in Hot Loops.** If a function fires inside an animation frame (`requestAnimationFrame`) or high-frequency event listener, it must allocate **zero** new memory. No `new Object()`, no `[]`, and no `{}`. Use pre-allocated **Object Pools**: made at start or when the map's size changes, each slot reused by flipping an active flag, never by creating and dropping objects. Temporary vectors and matrices (three.js) are module-level scratch objects, reused.
* **Rule 2: Batched State Mutations.** Do not update downstream systems piecemeal. Batch changes into packed data structures (like `Float32Array`) and flush them in a single, atomic draw or update call. In the 3D map that is the GPU buffers (instanced meshes, buffer attributes). The 2D map stays in SVG: there the batch is one set of DOM writes per frame, all reads before all writes.
* **Rule 3: Use requestAnimationFrame Only.** All visual loops and rendering pipelines must sync via `requestAnimationFrame`. Periodic timers (`setInterval`) for UI rendering are strictly banned.
* **Rule 4: Few Draw Calls, Few State Changes.** The cost in graphics is the traffic between the CPU and the GPU. Draw many alike things in one call (instancing, merged geometry). Put textures that are drawn together, such as labels, glyphs and bubbles, in one atlas. Sort what is drawn by material and shader, so the GPU changes state as rarely as possible. Count draw calls and program switches per frame (`renderer.info`) before and after.
* **Rule 5: Cheaper Frames, Never Fewer.** Performance work lowers the cost of each frame. It never throttles, caps or pauses the frame rate, and the map never idles to save work; lower graphics modes are the person's choice, not a fix. Measure frame time (median, p95, p99) on the real GPU, headless, before and after.

---

## 5. Hot Loop Optimization (Python Context)
If writing or interfacing with high-performance Python nodes. First remove work that need not happen (section 2); these rules then apply inside genuine hot loops, where a profile shows the time goes. Python 3.11 and later already speed up attribute and global lookups, so measure before and after rather than rewriting cold code for them.
* **Rule 1: Eliminate Attribute Lookup.** Avoid dot notation (`obj.method`) inside tight `for` loops. Bind the method or attribute to a local variable *before* entering the loop.
* **Rule 2: Local Scope Priority.** Keep high-intensity computing inside functions rather than the global scope to leverage fast local variable array indexing (`LOAD_FAST`).
* **Rule 3: Prefer C-Level Iteration.** Use built-in list comprehensions, `map()`, `filter()`, or `itertools` rather than manual `for` loops wherever possible.

---

## Structure

**Chassis and modules.** `src/metaform/*.py` is the chassis: CLI, settings, data, events, loader, home. Everything else is a module in `src/metaform/modules/<id>/`. A module reaches Metaform only through the public base: `metaform.module`, `settings`, `data`, `events`, `jev`, `prompt_files`, `home`, `outline`, `finish_xml`, `frames`, `skills`, `project`.

**One declaration drives every surface.** A module declares `Module`, `Verb`, `Noun` records (`src/metaform/module.py`). That declaration produces the CLI command `metaform <module> <verb>`, its help (`docs.py`), and its MCP tool. A verb receives one `Context` (`context.py`) and returns data, shown the same way on every surface (`results.py`).

**Settings** are declared in code by the module that owns them (`settings.text`, `number`, `boolean`, `items`, `choice`), and one declaration drives the CLI switch, help, validation, `metaform config --show` and the settings screen (`tui.py`). Values are stored in the home database's `settings` table by scope (folder or global), owner and key. `person_only` settings cannot be changed by an agent over MCP.

**Data.** Each project's map is a SQLite store in the Metaform home (`~/.metaform`), reached only through `metaform.data` (`data/store.py` and its neighbours). The map is a tripartite mesh of elements and joins addressed by namespace; layers add knowledge on top of a base without changing it. `home.py` holds the registry of projects, settings and backups.

**Modules shipped:** `map` (reading and writing the map, layers, work records), `intake` (serves the intake procedure and records its result), `memory` (a memory graph attached to map nodes), `dispatch` (starts and steers agents over ACP), `workflow` (Axiom subroutines), `web` (the web GUI: a standard-library HTTP server in `server.py` and the page in `page/`), `mcp` (the MCP server), `fork` (a user's own module repository). `hello` demonstrates every module feature; `template` is the empty start of every new module. `hello`, `template` and `packet` ship disabled.

**The template is the module contract in practice.** Any new capability a module can use is added to `modules/template` (code, `resources/prompts.xml`, README) and recorded in its `CHANGELOG.md`, so developers can start from it. `metaform fork init` copies it.

**Prompts.** The text a module sends to agents lives in its `resources/prompts.xml`: one element per prompt, sent exactly as written; an empty element inside a prompt marks a place the code fills in; comments are never sent. Comments are written as product documentation: what the prompt is, who receives it and when, how to change or turn it off. Read prompts with `metaform.prompt_files`. A module's own prompt is product text: an agent that finds one wrong or incomplete refines it as it refines code, or routes the fix to an agent that can. The intake procedure is the exception, covered above.

**MCP server.** One tool, `project`, on the server named `metaform`: its arguments are one command of the project engine (`metaform.project`), such as `{"map": "<project>"}` or `{"<project>.<root>.<steps>": {}}`, and its result is that command's answer. `metaform mcp project` serves it alone over Streamable HTTP, keeping no session (`modules/mcp/project_tool.py`); `metaform mcp serve` (`modules/mcp/server.py`) is the server dispatch gives its agents, which lists the same one tool and still serves an agent's task and rules as resources. No command is a tool: an agent runs `metaform <module> <verb>` in its shell, and `metaform help <module> <verb>` gives a command's arguments. An agent started on the intake is linked its task alone. Each project's map in the project store is one LadybugDB database under `<home>/maps`, held open by one single-writer service per home (`metaform.project.service`); every other process sends it commands. `metaform.project` is part of the public base: `run`, `drawn`, `clear`, `stored_name`.

## Instructing agents

Preserve the user's request and subsequent revisions as source material. Record interpretation and the proposed approach separately. Keep names, values, operative mechanisms, exceptions and distinctions faithful to their source. Use project-grounded lexicalization to resolve referents without changing the requested operation. A delegated assignment carries the exact source wording that matters to its contribution and a reference to the remaining source. A navigation summary does not replace that source.

Explain the purpose and functional relationships that make an instruction intelligible. Keep supplied research complete and addressable, distinguish its claims from the user's instructions, and reconcile it with current artifact evidence. Carry corrections into affected work while retaining their source. When existing evidence establishes a defect, use it to repair the cause rather than repeating the same assessment.

For context-delivery changes, compare the exact rendered payload and selected prompt-store version, including active role snapshots, with the intended source revision. A source-file edit alone does not establish what a running agent received. Native harness instructions and hidden model context require their own evidence.

## Specifications

`specifications/00-index.md` through `09-viewer.md` describe what is built and why, one record per requirement (`MAP-`, `LAYER-`, `STORE-`, `BASE-`, `CLI-`, `MCP-`, `QUAL-`, `PROJ-`, `VIEW-`), with open questions in `OPEN-QUESTIONS.md`. The other files in that folder are build logs, reviews and manual tests, not requirements.

## Retain in context, do not discard or compact.

@STATE_INIT:
  {Mode} := SYSTEM_PRELOAD
  {Register} := PEER_UNSLOP

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
