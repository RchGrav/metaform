# Getting started with Inference Metaform

[Documentation](../README.md) · [Next: working with Metaform](working-with-metaform.md)

A useful first session ends with a relationship you can use: a receiver, its purpose, the elements serving it, and the references that connect that understanding to the workpiece. Installation and intake establish the route to that result.

## 1. Install the supplied source edition

Run these commands from the repository root with Python 3.11 or newer:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e . "mcp>=2.2" uv
metaform list modules
```

In Windows PowerShell, replace the activation line with:

```powershell
.\.venv\Scripts\Activate.ps1
```

The base package declares `prompt_toolkit`; the MCP module separately declares `mcp>=2.2`. Installing only the base package can therefore leave the MCP module reported as an error because its dependency is absent. `uv` supplies the build and wheel-backed host-launch path. These requirements come from the supplied [package metadata](../../pyproject.toml), [MCP module](../../src/metaform/modules/mcp/__init__.py), and [builder](../../src/metaform/build.py).

`list modules` reports where each module was found and whether it is on, off, or failed to load. Intake, map, memory, MCP, web, voice, fork, ElevenLabs, Twilio, cloud and node ship on; dispatch, workflow, packet, Paperclip, template and hello ship off, and `metaform enable <module>` turns one on. Voice lets a person talk to agents on the web GUI with Whisper in their browser; `python -m pip install -e ".[voice]"` (or `.[voice-gpu]` with an NVIDIA GPU) adds the faster engine on the server, and `metaform voice status` says which engine hears and why. Template and hello ship disabled. A dependency or import error is a reported module condition, not evidence that all of Metaform failed to start.

### Running an existing build instead

A Metaform-built wheel is both installable and directly runnable. Substitute the actual wheel path:

```sh
python /path/to/metaform-2026.9.30.2-py3-none-any.whl list modules
```

In later examples, replace `metaform` with `python /path/to/the.whl` when using this form. `python /path/to/the.whl install <tool>` installs Metaform from the wheel with uv and then sets the tools up with the installed copy: run straight from a wheel, the modules whose compiled dependencies it cannot carry, MCP among them, are left out, and the installed copy has them. Direct execution uses the normal home, `~/.metaform`, the same as an installed command or a host's `uvx --from ... metaform` launch. `METAFORM_HOME` chooses another home for any of them.

The repository holds no built application wheel. Use the repository source or a wheel produced from it with `metaform build`.

## 2. Connect the agent interface

Build from the installed source environment:

```sh
metaform build
metaform install
```

`build` packages the chassis and the modules that are enabled and successfully loaded, and records the resulting wheel. `install` presents the detected clients. It uses that wheel, or the running wheel when applicable, rather than assuming an unrelated package release.

A named installation selects its adapter directly:

```sh
metaform install claude
```

The supplied installer has configured adapters for **Claude Code** (`claude`), **Codex** (`codex`), **Gemini CLI** (`gemini`), **Cursor** (`cursor`), and **VS Code** (`vscode`), and registers Metaform as an ACP agent in **Zed** (`zed`) and **JetBrains IDEs** (`jetbrains`), which start it through the dispatch module, so those two need `metaform enable dispatch` first. Its entries for Copilot CLI, Factory, Antigravity, and Claude Desktop are marked unverified and do not provide the same installation path. This is the adapter set in the documented source snapshot, not a claim about every current client version.

Installation reports the files it changes, makes backups, registers the server, and probes the server's server/discover and tools/list exchange in MCP 2026-07-28. Where the adapter supplies a skill location, it also copies the skill material. Server probing and copying a skill are distinct from proving that the client's native skill loader has used it.

The registered transport is **stdio** by default. Its command shape is:

```text
uvx --from /absolute/path/to/the-built-wheel.whl metaform mcp serve
```

The host starts that process. With `metaform set --mcp-transport http`, tools are registered at `http://127.0.0.1:<mcp_port>/mcp` instead (port 7434 unless `--mcp-port` says otherwise), and the server is started with `metaform mcp serve --http`. Start the agent in the registered workpiece folder, or provide its project explicitly in tool calls. The next section creates that project.

Installer implementation: [install.py](../../src/metaform/install.py). Detailed packaging and lifecycle: [extension guide](extending-metaform.md#packaging-and-distribution).

## 3. Register the workpiece

Choose an existing folder. It may be a code checkout or a folder anchoring another kind of work:

```sh
cd /path/to/workpiece
metaform add project example .
metaform
```

`example` is your project identifier. The default target is the folder itself. The current folder and its descendants resolve to the registered project; `metaform` displays the active context and module status.

To associate a different kind of target with a folder, provide both target fields:

```sh
metaform add project story . artifact manuscript.md
```

Other accepted target kinds are `path`, `url`, `inline`, and `inferred`. Registration records the target; it does not itself fetch a URL, analyze an artifact, or infer a map. The agent needs access to the chosen material through its host.

Project records, Metaforms, settings, reports, and store files live under the Metaform home, normally `~/.metaform`, or the directory in `METAFORM_HOME`. Registration and intake do not add a new `.metaform` tree to every workpiece folder. A project's map store is under `projects/<project-id>/metaforms/<metaform-id>/store.sqlite3` in that home.

## 4. Have the agent perform Canonical Intake

Read the actual instructions with:

```sh
metaform intake prompt
```

Over MCP, use the `intake_prompt` tool with no arguments when the folder resolves the project, or with `{"project":"example"}` to select it explicitly.

The command serves the intake text with its prompt slot filled by `text=`, empty meaning this project, and its target filled in from the registered project. Nothing is added beside it. It does not run an AI model. The intake module's agent notice directs a subagent to read and follow those instructions. The agent examines the workpiece, reasons through its receiving purposes and the elements that serve them, records each object as soon as it is reasoned, anneals its functional structure, then reads the map back, proofs it and finishes it.

**Your part** is to identify the workpiece and direct the work. **The agent's part** is the substantive inference and recording. **Metaform's part** is to serve the method, retain the result, and make that understanding available through subsequent reads, memory, knowledge, and tools.

The operative procedure is intended to ship with the project. Its wording is part of how it elicits the representation. The introductory guide therefore uses the served procedure rather than replacing it with a shorter homemade intake prompt. [The full reference](../inference-metaform/REFERENCE.md#intake) explains the intake mechanism.

### The intake is recorded one object at a time

The served procedure's XML schema defines the fields of each object. The agent records the map through the intake tools, one object per call, as it reasons it, so it never holds the whole map in its context:

```sh
metaform intake start model=opus role="intake agent"
metaform intake element stakeholder.cook.home role=CQU name_length=2
metaform intake element code.timer.kitchen role=DE name_length=2 name="dish clock"
metaform intake purpose stakeholder.cook.home '["code.timer.kitchen"]' purpose="Know when each dish is done." ef="tells the cook when a dish is done" ifd=receives
metaform intake show
metaform intake finish report="What the agent found broken or unfinished."
```

The intake records elements and purpose records in the recursive shape served by `intake schema`.

- An element is its `namespace_address`, `name_length`, `name` and `role`. Its short name is its address read backward through `name_length`, so `code.timer.kitchen` with `name_length=2` is the kitchen timer. `name` is the project's own name for it: this project calls its kitchen timer the dish clock.
- A purpose record is its type (`purpose`), `purpose`, `ef` and `ifd`. The receiver holds the purpose record and the purpose record holds the elements that serve the purpose. `ef` is the Encounter Function, a fragment in the active voice. `ifd` is the information flow direction: `sends`, `receives` or `both`.

A purpose record has no `refs`, `verb`, `non_goal` or name. Its nested parts are ordinary elements. A part that serves the same purpose is another element in the same purpose record. An element can also receive purpose records of its own, repeating the same element and purpose form at every depth.

Over MCP the same calls are the tools `intake_prompt`, `intake_start`, `intake_element`, `intake_purpose`, `intake_show`, `intake_remove` and `intake_finish`, with the same fields as named arguments. The agent names an element by its `namespace_address` and a purpose record by its `receiver` and an element it holds, as in the Canonical Intake. No call hands it an id.

| Verb | What it does |
|---|---|
| `prompt` | Serves the intake. |
| `start` | Opens the building layer, with the `model` and `role` the agent gives. |
| `element` | Records one element. Recording an address again replaces the fields given. Takes `refs`, `condition` and `note`. |
| `purpose` | Records one purpose record: `receiver`, `elements` as a JSON list, and optional `purpose`, `ef`, `ifd`, `condition` and `note`. Recording again with an element the purpose record already holds changes that purpose record, and any element it does not hold is added to it. This is annealing. |
| `show` | Reads back the recorded map: `elements`, `purposes` and `undescribed`, the addresses a purpose record names and no `element` call described. With `receiver=` it reads one receiver's purpose records and the elements they hold. |
| `remove` | Takes out an element (`namespace_address`), a purpose record (`receiver` and `provider`, an element it holds), or one element from a purpose record (all three). After `finish` it changes nothing and names `map refine`. |
| `finish` | Marks the layer ready and saves `report` and `feedback`. Returns the counts of `elements`, `purposes` and open `work` records, and a notice for any address named in a purpose record and never described. |
| `status` | Whether the project has an intake, or one is being recorded. |

Each call returns what it stored and its notices. Nothing is refused for its content: a field that does not fit is stored as given and named in a notice, and a missing field is stored empty and named. Until `finish`, the intake is building: no read other than `intake show` sees it, and `metaform web` draws each object as it arrives.

`element` and `purpose` take `condition` and `note`. Given either, the call also writes an open work record at what it just recorded, apart from the map: `condition=missing` for what the specifications describe and is not built, `broken`, or `exclude`. The web GUI draws a node with an open `missing` record at 70% opacity and flashes one with an open `broken` record red. Any other work record is written with `map work`.

#### Refs go in the sources layer

An element's `refs` are a JSON list of key and value pairs, such as `[{"key": "path", "value": "src/main.c"}]`. They are not a field of the element. While the setting `intake_sources` is on, which is the default, `intake element` writes them as one item at the element in a knowledge layer named `sources`, replacing what that item held. With the setting off (`metaform set --no-intake-sources`), the refs are not recorded and the call says so.

The intake creates `sources` already finished, so `map where` shows the refs at once, without waiting for `intake finish`.

### What stays available

The intake produces one layer, named `intake`. After it is finished the metaform changes by refining that layer with `map refine`, which keeps every earlier version, and does not stack new layers: see [Refine the metaform](working-with-metaform.md#refine-the-metaform). Repeating intake for a Metaform that already has one creates a **new active Metaform**, while keeping the previous one whole. It does not replace the old base layer in place.

```sh
metaform list metaforms
metaform activate metaform main
```

Use the name reported by your own listing when selecting a form. The original operative text is served from the resource; this intake implementation does not also create a prompt-version record containing a copy of it.

To take the intake again from nothing, clear the project:

```sh
metaform clear project example
metaform clear project example --confirm
```

Without `--confirm` the command changes nothing and prints what it would remove. With it, it removes every Metaform of the project with its store, and the project's report, feedback and shape files. The registration, the folder and every file in it, the folder settings, and the origins and variants stay. A file it cannot remove, such as a store a running program holds open, is named with the reason and what to do. Over MCP the same operation is the `clear_project` tool, and the web GUI has **Clear project** in its header.

## 5. Inspect the first useful result

```sh
metaform intake status
metaform map roots
```

Take an address returned by your map and inspect it:

```text
metaform map element <address>
metaform map joins <address> as=receiver
metaform map joins <address> as=provider
```

The receiver view asks **what this entity needs and who provides it**: the joins the element holds, each with the elements that serve it. The provider view asks **who receives this capability and why**: the joins that hold the element, each with its receiver. One read gives both:

```text
metaform map where <address>
```

`where` returns the element, `provides`, every join that holds it with the receiver, the receiver's purpose, `ef`, `ifd` and the elements the join holds, `receives`, every join the element holds as receiver with its elements, its open work records, and `layers`, what the layers in context hold at it, the `sources` layer's refs among them. It leaves ids and empty fields out; `full=true` keeps them. Open the refs to connect the recorded understanding to the actual artifact.

The first benefit is concrete: you now have a recorded reason for a relationship, not merely an observation that two parts connect. An agent considering a change can reason against that purpose before reconstructing the whole project.

Open the visual interface with:

```sh
metaform web
```

Use the address printed by the command. The default is `http://127.0.0.1:7433`. Select the project and Metaform, click an element or join, and inspect the Object and Provenance tabs. The [operating guide](working-with-metaform.md#using-the-web-interface) explains view selection and the separate folder settings.

## Record a small map by hand

The examples in [Working with Metaform](working-with-metaform.md) and [Extending Metaform](extending-metaform.md) use a kitchen timer's map. You can record it yourself with the intake commands, as an agent would, without a model. In an empty folder:

```sh
metaform add project kitchen .
metaform intake start model=none role="by hand"
metaform intake element stakeholder.cook.home role=CQU name_length=2
metaform intake element code.timer.kitchen role=DE name_length=2 name="dish clock" refs='[{"key": "path", "value": "src/main.c"}]'
metaform intake purpose stakeholder.cook.home '["code.timer.kitchen"]' purpose="Know when each dish is done without watching the clock." ef="tells the cook when a dish is done" ifd=receives
metaform intake element code.alarm.audible role=SE name_length=2 name="buzzer" refs='[{"key": "path", "value": "src/alarm.c"}]'
metaform intake purpose code.timer.kitchen '["code.alarm.audible"]' purpose="Get the cook's attention the moment a countdown ends." ef="sounds the end of a countdown through the speaker" ifd=receives
metaform intake element code.loop.tick role=SE name_length=2 name="ticker" refs='[{"key": "path", "value": "src/tick.c"}]'
metaform intake purpose stakeholder.cook.home '["code.timer.kitchen", "code.loop.tick"]'
metaform intake finish
metaform map where code.timer.kitchen
```

The last `intake purpose` names a purpose record the cook already holds with the timer. It is that record: it keeps its purpose, `ef` and `ifd` and gains the tick loop, so the cook's purpose is served by two elements. `finish` reports four `elements`, two `purposes` and no open work records. `map where code.loop.tick` returns the one join that holds it. `map where code.timer.kitchen` lists the three refs under `layers`.

The shell examples use POSIX single quotes around JSON; on Windows PowerShell, quote the JSON for PowerShell instead.

On a machine that has never run Metaform, each command also prints a notice to read `metaform help provision` and run `metaform provision done`. It does not change the result.

### The earlier export in docs/examples

[project-metaform.json](../examples/project-metaform.json) is a dated snapshot: an export of this repository's own map, recorded on September 26, 2026, at schema version 1 and in the shape of that day, with subtype joins and `verb` recorded as null on each join. The current chassis imports schema version 19 only, and `metaform import` stops on this file with `The document has schema version 1; this Metaform supports version 19.` The [reader guide](reading-a-metaform.md) and the [walkthrough](../examples/project-walkthrough.md) quote its records as recorded material.

## When the first command does not do what you expect

| Observation | What to inspect |
|---|---|
| No project for this folder | `metaform list projects`; enter the registered folder or use `metaform set --project <id>`. |
| A module is off or in error | `metaform list modules`; the row gives its disabled, platform, dependency, or import condition. |
| MCP is absent from the build | Install its declared dependency, make sure `mcp` loads, then rebuild. The builder copies loaded modules. |
| The agent sees another context | Check its launch folder and project override; inspect `metaform config --show`. |
| A layer is retained but not visible | Read it by name and check its finished/hidden state and current layer selection. |

These are existing interface behaviors. For continuing operation, use [Working with Metaform](working-with-metaform.md). For command-specific details generated from the loaded declarations, use `metaform help <module>` or `metaform help <module> <verb>`.
