# Getting started with Inference Metaform

[Documentation](../README.md) · [Next: working with Metaform](working-with-metaform.md)

A useful first session ends with a relationship you can use: a receiver, its purpose, the provider satisfying it, and the references that connect that understanding to the workpiece. Installation and intake establish the route to that result.

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

`list modules` reports where each module was found and whether it is on, off, or failed to load. Intake, map, memory, MCP, and web are the operating modules in this edition. Template and helloworld ship disabled. A dependency or import error is a reported module condition, not evidence that all of Metaform failed to start.

### Running an existing build instead

A Metaform-built wheel is both installable and directly runnable. Substitute the actual wheel path:

```sh
python /path/to/metaform-0.1.0-py3-none-any.whl list modules
```

In later examples, replace `metaform` with `python /path/to/the.whl` when using this form. With no `METAFORM_HOME` already set, direct execution uses the wheel-specific home `~/.metaform/wheels/metaform-0.1.0`. That is distinct from an installed command or a host's `uvx --from ... metaform` launch, which uses the normal home. To use one explicit home across both paths, set `METAFORM_HOME` consistently before launching them.

The documentation ZIP contains documentation and an example export, not a built application wheel. Use the repository source or a wheel produced from it.

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

The supplied installer has configured adapters for **Claude Code** (`claude`), **Codex** (`codex`), **Gemini CLI** (`gemini`), **Cursor** (`cursor`), and **VS Code** (`vscode`). Its entries for Copilot CLI, Factory, Antigravity, and Claude Desktop are marked unverified and do not provide the same installation path. This is the adapter set in the documented source snapshot, not a claim about every current client version.

Installation reports the files it changes, makes backups, registers the server, and probes the server's initialize and tools/list exchange. Where the adapter supplies a skill location, it also copies the skill material. Server probing and copying a skill are distinct from proving that the client's native skill loader has used it.

The registered transport is **stdio**. Its command shape is:

```text
uvx --from /absolute/path/to/the-built-wheel.whl metaform mcp serve
```

The host starts that process. There is no HTTP MCP endpoint to invent or configure for this path. Start the agent in the registered workpiece folder, or provide its project explicitly in tool calls. The next section creates that project.

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

The command serves the operative intake with the target filled in, followed by the recording and report instructions. It does not run an AI model. The intake module's agent notice directs a subagent to read and follow those instructions. The agent examines the workpiece, reasons through its receiving purposes and providers, records each object as soon as it is reasoned, converges its functional structure, then reads the whole map back, proofs it and finishes it.

**Your part** is to identify the workpiece and direct the work. **The agent's part** is the substantive inference and recording. **Metaform's part** is to serve the method, retain the result, and make that understanding available through subsequent reads, memory, knowledge, and tools.

The operative procedure is intended to ship with the project. Its wording is part of how it elicits the representation. The introductory guide therefore uses the served procedure rather than replacing it with a shorter homemade intake prompt. [The full reference](../inference-metaform/REFERENCE.md#intake) explains the intake mechanism.

### The intake is recorded one object at a time

The served procedure's XML schema defines the fields of each object. The agent records the map through the intake tools, one object per call, as it reasons it, so it never holds the whole map in its context:

```sh
metaform intake start model=opus role="intake agent" id=example-intake-1
metaform intake element stakeholder.cook.home role=VE name="Home cook"
metaform intake join stakeholder.cook.home code.timer.kitchen purpose="Know when each dish is done." function="Counts down and rings." ef=Function relation="The kitchen timer tells the cook." verb=tells observation="One countdown per dish."
metaform intake show
metaform intake finish report="What the agent found broken or unfinished."
```

Over MCP the same calls are the tools `intake_start`, `intake_element`, `intake_join`, `intake_subtype`, `intake_show`, `intake_edit`, `intake_remove` and `intake_finish`, each with the same fields as named arguments. `intake_join` returns the join id that `intake_subtype` takes for a subtype join inside it. The optional `model`, `role` and `blinded` on `start`, and `report` and `feedback` on `finish`, preserve the supplied run information. There is no requirement to fabricate values that were not recorded.

Each call returns what it stored and its notices. Read the notices: a call retains readable material and names unsupported or ill-fitting content rather than silently discarding its meaning. Until `finish`, the intake is building: `intake show` returns it whole, `intake edit` and `intake remove` correct it, no other read sees it, and `metaform web` draws each object as it arrives. `finish` reports the layer, the Metaform, the record counts, and any addresses recorded only as the end of a join and never described.

### What stays available

The first intake produces a retained intake layer. Repeating intake for a Metaform that already has one creates a **new active Metaform**, while keeping the previous one whole. It does not replace the old base layer in place.

```sh
metaform list metaforms
metaform activate metaform main
```

Use the name reported by your own listing when selecting a form. The original operative text is served from the resource; this intake implementation does not also create a prompt-version record containing a copy of it.

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

The receiver view asks **what this entity needs and who provides it**. The provider view asks **who receives this capability and why**. Open the joins' references to connect the represented understanding to the actual artifact.

The first benefit is concrete: you now have a recorded reason for a relationship, not merely an observation that two parts connect. An agent considering a change can reason against that purpose before reconstructing the whole project.

Open the visual interface with:

```sh
metaform web
```

Use the address printed by the command. The default is `http://127.0.0.1:7433`. Select the project and Metaform, click an element or join, and inspect the Object and Provenance tabs. The [operating guide](working-with-metaform.md#using-the-web-interface) explains view selection and the separate folder settings.

## Inspect the supplied project map without a new intake

The documentation includes a recorded [project export](../examples/project-metaform.json). To examine it, start from the repository root:

```sh
metaform add project reference-demo .
metaform import docs/examples/project-metaform.json reference-demo
metaform set --project reference-demo
metaform map element code.system.plugin
metaform map joins code.system.plugin as=provider
metaform map where code.template.module
```

The explicit import target maps the original project into `reference-demo` instead of adopting its original `/home/rich/metaform` folder as your local registration. This imports a recorded result; it is not a new execution of Canonical Intake. The [reader guide](reading-a-metaform.md) and [walkthrough](../examples/project-walkthrough.md) use this data.

The export was made before joins and subtypes carried `verb`, so each of its join and subtype rows records `verb` as null.

Imported IDs are retained. Import adds missing identities; it is not an overwrite/update operation for an existing identity. A second import of the same export into the same home may therefore report records skipped rather than refreshed. Use a separate `METAFORM_HOME` for a completely independent demonstration copy.

## When the first command does not do what you expect

| Observation | What to inspect |
|---|---|
| No project for this folder | `metaform list projects`; enter the registered folder or use `metaform set --project <id>`. |
| A module is off or in error | `metaform list modules`; the row gives its disabled, platform, dependency, or import condition. |
| MCP is absent from the build | Install its declared dependency, make sure `mcp` loads, then rebuild. The builder copies loaded modules. |
| The agent sees another context | Check its launch folder and project override; inspect `metaform config --show`. |
| A layer is retained but not visible | Read it by name and check its finished/hidden state and current layer selection. |

These are existing interface behaviors. For continuing operation, use [Working with Metaform](working-with-metaform.md). For command-specific details generated from the loaded declarations, use `metaform help <module>` or `metaform help <module> <verb>`.
