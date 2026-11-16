# Metaform specification

**Date:** 2026-11-15. **Describes:** the files in this archive, copied from the repository folder `/home/rich/metaform`, branch `fable-climb`, commit `1798c6e`.

This document is the one specification of Metaform. It states what Metaform is, how its one tool works, what is built, what is decided and not built, and what is open. Where another file in this archive disagrees with this document, this document governs, and section 14 lists the disagreements that are known. Where a decided statement of this document and the Rust code differ, the code is what changes. **Reason:** a decision is made and recorded before the code that follows it, so the record is the later of the two. This holds only for a statement that is decided. A statement that only describes the build, and describes it wrongly, is an error of this document and is corrected here. Section 13 lists every decision the maintainer made on 2026-11-15, each with its reasoning.

## 0. How to read this document

### 0.1 Who decides

The founder is the person who directs the project. Some source documents call the same person the owner. A decision of the founder is the only source of a requirement. An agent's proposal is not a requirement until the founder confirms it.

### 0.2 Status words

Each statement that matters carries one status.

| Status | Meaning |
|---|---|
| **Built** | The Rust form in this archive does it. The basis is the code as read on 2026-11-15. |
| **Decided, not built** | The founder decided it. The Rust form does not do it. |
| **Built, not confirmed** | The Rust form does it. An agent chose it, and the founder has not confirmed it. |
| **Proposed** | An agent proposed it. It is not built and not confirmed. |
| **Open** | The founder must decide it. Section 13.4 lists these. |
| **Decided by the maintainer** | The founder gave the design of the codebase to its maintainer on 2026-11-15. The maintainer decided the point and wrote the reasoning. The founder can overrule it. |

A statement marked "inferred" is a conclusion from reading the code and was not observed in a run.

### 0.3 What "Built" rests on

The author of this document read every source file of the four Rust crates on 2026-11-15. Eight reviewers also read the code. Six of them compared this document with the code, part by part, and the statements they found wrong were corrected. Nobody ran each command against a server.

The founder changed the roles on the same day (section 3.4). That change is covered by the tests and by one run by hand through the server. The 77 tests of the copy in this archive passed after the change. The tests do not cover every statement marked Built.

Sections 1 to 15 state the design, its reasons and its status. Sections 16 to 19 are the exact reference: every form, message, answer, file and fixed value of the Rust form.

### 0.4 Which decision governs

The design changed many times between 2026-10-30 and 2026-11-12. When two decisions of the founder disagree, the later one governs. This document states only the governing decision and does not repeat the earlier ones, except where the build still carries an earlier one.

### 0.5 Sources

A reference such as R-5.30 or D-11 names a requirement or a decision in `metaform/SPEC.md` of the source repository at the commit above. That file is the record of each decision, its date and its reason. It is not in this archive, because it also holds every earlier generation of the design. Section 15 gives the source of each section.

### 0.6 How this document changes

When the founder settles something, the change is written here with its reason. A question that the founder asked is recorded as open and never as a decision. Nothing else changes this document.

## 1. Purpose

### 1.1 What Metaform is

Metaform is a functional topology: a map of what a project does and how its functionality connects. The map is called a metaform. It records functionality and not code. Code, a manual, a specification, a photograph and a story are all evidence of functionality. **Decided** (section 1 of `SPEC.md`).

### 1.2 The cost that Metaform saves

The cost that Metaform saves is a reasoning cost. An agent can track and understand a limited number of things at once. An agent that enters a project must first work out what the project is, and that orientation uses part of the limit before the task starts. Metaform does the orientation once and keeps the result where every agent can read it.

The saving is not a saving of tokens or of money, and Metaform does not raise a model's abilities. A token count may fall as a result, and it may be measured, but it is not the purpose. **Decided** (R-1.4). **Reason:** documents and agents kept restating the purpose as a saving of tokens, and the limited resource is the reasoning of the model.

### 1.3 How the map saves it

An address in the map is built from the standard names of functional types, such as an engine, a queue or a ring buffer. A model knows these kinds of things before it infers anything, so it knows what an element is when it reads the address. The map also shows the whole project and the agent's place in it together. **Decided** (R-1.4).

### 1.4 What Metaform is used for

Metaform works on a project that exists, on a project that does not exist yet, and on anything between. **Decided** (section 1 of `SPEC.md`, R-1.2).

- It takes in the functionality of an existing project. This is intake (section 7).
- It is a place to construct and refine the intent of a system that is not built.
- It takes in a specification, holds its detail at the elements it describes, and exports it again as one document (section 10).
- It gives agents the shape against which they realign code that is hard to refactor.
- Inside any project, it is a context management system: an agent at an address is given what belongs to that address and nothing else.

### 1.5 What is not Metaform

- **Topogee** is a separate project that is built with Metaform. Metaform is not designed around any one project, including itself (R-4.9).
- **Roundtable** is a separate tool for discussions among several agents. It is not in this archive.
- **The agents module** will own agent identity, names and messages. The founder will specify it after the server. Section 11 of `SPEC.md` records the founder's intent so far.
- **Mutation of artifacts** is a separate pipeline. Its interface to Metaform is not specified.

## 2. Principles

Each principle carries its reason, so that a reader can decide a case that this document does not list.

1. **Function, not material.** The map names what each part does and for what purpose. Language, encoding, medium, genre and style are ways a function is carried, and naming them would tie the map to material that changes. **Decided** (R-3.16, the intake procedure).
2. **The base map is small on purpose.** It holds elements and their wants. Everything else is a layer. A base that holds little stays the same while knowledge is added and removed around it. **Decided** (R-3.20).
3. **The map holds durable knowledge.** Investigation notes, drift observations and debugging flags belong in a ticket and never in the map. **Decided** (R-3.16).
4. **Intake is never gated or judged.** A check on what an agent inferred makes the agent satisfy the check. The tool checks the form and integrity of a command and never the meaning of an inference. **Decided** (the intake procedure, section `constraints`).
5. **Progressive discovery.** Nothing is presented to an agent before the agent needs it, and nothing that the agent does not need. Whatever is put in front of a model costs reasoning whether the model uses it or not. **Decided** (R-5.39).
6. **A refusal teaches.** A wrong command is answered with the reason and with the command that would be accepted. The moment of the error is the moment the agent needs the form. **Decided** (R-5.24).
7. **Logic is added to the tool only to fix an observed problem.** A check that fixes nothing observed costs reasoning and can cause a failure of its own. **Decided** (R-5.20).
8. **The tool reads, writes and keeps data correct. An order of steps lives in a prompt.** Intake has no start and no stop in the tool. **Proposed** in `SPEC.md` (R-5.18, R-5.19); the Rust form follows it.
9. **Everything says why.** A want records why an element needs another and how the other serves it. A rule or an instruction written for this project carries its reason. An agent that knows the reason can tell when the rule applies. **Decided** (`metaform/README.md` of the source repository).
10. **The procedure is a formula.** Section 12 states this rule and its reason.
11. **The tool is fitted to the procedure.** When the tool and the procedure use different words, the tool changes, or the tool answers the procedure's word with the corrected command. **Decided**, founder, 2026-11-12.
12. **One form for every command.** A new feature uses the form that every other command uses. A special case is a deviation. **Decided** (R-6.27).
13. **Build the specified foundation.** If the specification states how a foundation must work, build that foundation and not a temporary one. **Decided** (R-1.1).
14. **The project writes its own code.** No new dependency is added. Outside code is read for ideas and is not copied. **Decided**, founder, 2026-11-09. **Reason:** Metaform must not depend on other vendors keeping their code maintained. Whether this covers the foundations already in use, such as tokio, rmcp, axum and LadybugDB, is not settled.

## 3. The map

### 3.1 Elements and addresses

A project is a tree of elements. Each element lives at one address. An address is a dotted path, such as `code.engine.game`, and each segment names functionality. The address `.` is the root of the project. **Built.**

The rules for naming an address belong to the intake procedure, section `namespace_rules`. This document does not restate them. The tool relies on one property of them: the segments read in reverse order, with periods and underscores as spaces, form the ordinary name of the element. `code.buffer.ring.packet` reads "packet ring buffer code".

The tool checks only the form of an address. **Built:**

- A segment has at least one character and holds no period, `$`, `[`, `]` or white space.
- A name must be lowercase and must survive conversion to camelCase and back. Section 4.4 gives the reason.

### 3.2 Roots

| Root | What it holds | Status |
|---|---|---|
| `code`, `document`, `media`, `data` | The four root types of a project. | Built |
| `upstream` | What the project relies on, outside the project. | Built |
| `downstream` | What relies on the project, outside the project. | Built |
| `layer` | The definitions of layers (section 5). It is internal, and intake places nothing in it. | Built |
| `collection` | Not a root. A write that creates an element beneath it is refused (section 13, decision 22). | Built |

`upstream`, `downstream` and `layer` are root prefixes: the segment after one of them may be another root, as in `upstream.code.engine.game` and `layer.code.cpp`. An element under a root prefix is not part of the project. **Built.** **Reason for `layer` as a root of its own:** a layer definition is not located in the project. Under a project root it would read as part of the project (R-3.3).

The tool checks the root only when a write creates an element. The refusal is `ROOT_SCOPE_NOT_ALLOWED`.

### 3.3 The fields of an element

| Field | Meaning | Checked by the tool |
|---|---|---|
| `technical_name` | The practitioner's short name of the element's type. | Its words must be a leading run of the address's words in reverse order. The root has none. |
| `name` | The name that this project gives the element. | Text that is not blank. |
| `role` | The element's role (section 3.4). | One of the eight role names, when a write sets or changes it. |
| `refs` | The entry point of the element's functionality, or a discrete reference that shows it. | A list of at least one text item. Section 3.6 covers paths. |
| `status` | The state of implementation. | Any text except six earlier spellings. The tool names one value, `un_built`. |
| `wants` | What this element wants from other elements (section 3.5). | Section 3.5. |

All of this is **Built**. Further points:

- `refs` is a field and not a layer, so every read of the element returns it. It holds an entry point or a discrete reference, and it is not a list of every member (section 13, decision 21). The help text and the schema say so.
- `refs` stays on the element, and each record of a layer may hold its own `ref` (section 13, decision 21).
- `uri` is not a field. A command that sends it is refused with the same command using `refs`.
- The procedure says that `name` must not match the practitioner's name. The tool does not enforce it, and that stands (section 13, decision 23).
- The six refused spellings of `status` are `missing`, `MISSING`, `BKN`, `broken`, `todo` and `TODO`. The refusal names `un_built`.
- No element has a field for the project's name (R-3.10). In the build the registry holds the name. In the stored form the name is the root (section 4.3). The contract still checks a text field `project`, and no code reads it.
- An object under an element is always an element beneath it. A field cannot hold an object, and a field cannot share its name with an element beneath. The refusal is `FIELD_ELEMENT_COLLISION`.

### 3.4 Roles

A role is written by its full name. **Built**, on the founder's instruction of 2026-11-15. The full names replace the abbreviations of 2026-11-12 as stored values, and Definitive and Supportive before them. **Reason:** an agent that reads one element, or adds one, has often not read the procedure's glossary. A value such as `DE` tells that agent nothing, and it must spend reasoning to find out. `Defining Element` explains itself. This is the same reason for which the fields have plain names (section 3.5). **What speaks against it:** the values are longer, and the procedure reasons with the abbreviations, so the tool must answer an abbreviation with the full name.

| Role | The procedure's abbreviation |
|---|---|
| `Artifact Type` | AT |
| `Defining Element` | DE |
| `Supporting Element` | SE |
| `Coupled Element` | CE |
| `Notable Element` | NE |
| `Vested Beneficiary` | CQU |
| `Upstream Dependency` | UD |
| `Downstream Dependant` | DD |

The definitions are the intake procedure's, in its section `core_concepts`. This document does not restate them, except the one below.

**Coupled Element.** A Coupled Element is a Supporting Element whose functionality is bound to the functionality of the element it serves. A change to one requires a change to the other. The role indicates that the two must not be assigned to different worktrees at the same time. A worktree is a separate working copy of a repository, in which one agent works apart from the others until the work is merged. **Built**, on the founder's instruction of 2026-11-15; the wording of the definition is the author's.

**Reason:** when work is divided among agents, each agent changes its part against the other parts as they stood when it started. For most parts that is safe, because the parts meet only where one wants the other. For coupled parts it is not: the two changes must agree with each other, and neither can be merged or tested without the other. Whoever divides the work needs to see this before the work is assigned, and the map is where the work is divided. A role is the smallest way to show it, because the map already sorts elements by role and no new field is needed.

**What speaks against it, and what is not settled:**

- Coupling holds between two elements, and a role sits on one. The role does not say which element the other one is. The author's reading is that it is each element that wants the Coupled Element. If a Coupled Element is wanted by several elements, the reading may bind more work together than is needed.
- Writing all eight roles in full follows from the reason above. The founder wrote three of them in full, and the other five are the author's extension.
- The wording of the definition in `core_concepts.md` is the author's. The founder saw it and let it stand without discussing it.

- The tool records the role. It does not divide work, and no code reads the role for that purpose.
- A write that gives an abbreviation as a role is refused, and the remediation sets the role by its name (section 6.8).
- A map may hold several Defining Elements. **Reason:** the intake gives a Defining Element to each artifact type it finds.
- `map` returns `defining`: the elements with the role `Defining Element` that are not under a root prefix.
- The tool checks a role only when a write sets or changes it. A stored map with the roles Definitive, Supportive, Notable or Divergent still loads.

### 3.5 Wants

A want is the record that an element keeps about one element it relies on. The element that holds the want is the receiving element. **Built.**

| Field | Meaning | Required |
|---|---|---|
| `element` | The address of the wanted element. | Yes |
| `why` | What the receiving element seeks to accomplish through the wanted element. | Yes |
| `how` | How the wanted element serves that purpose in this meeting. | Yes |
| `direction` | Which way the substance moves, relative to the receiving element: `send`, `receive` or `both`. The request is never the direction. | Yes |
| `ref` | The uri of the one artifact that the want is about. | No |

- **`wants` is a list on the receiving element.** **Reason:** a plural name holds a list, and an object under an element is always an element beneath it.
- **The want lives in the receiver.** **Reason:** one provider serves different receivers in different ways, so a statement stored on the provider would have to be one statement for all of them.
- **The key of a want** within its receiving element is its `element` together with its `ref`. A record with the same key changes that want. Any other record is a new want. A want with no `ref` is the one want on that element with none. **Reason:** a map of many artifacts, such as a folder of photographs, wants the same element once for each artifact.
- **A write creates the wanted element** at its own address if it is not there (R-5.4).
- **The tool speaks plain words.** The intake procedure reasons with Providing Element (PE), Operative Purpose (OP), Encounter Function (EF) and Information Flow Direction (IFD). It calls the record a dependency. The tool says `element`, `why`, `how`, `direction` and `wants`. **Reason:** an agent that adds one record through the tool must understand the fields without reading the procedure's glossary. Section 6.8 says how the tool answers the procedure's words.
- **`why` and `how` are sentence fragments** that complete the want sentence in `metaform/tool-help.json`. The tool checks only that each is not blank. A check of their grammar is not built (D-14).
- **`wanted_by`** is not stored. `goto` builds it: the wants in other elements that name the address.

### 3.6 Refs and paths

A ref to a file inside the project is stored as its path from the project folder. A command that gives such a ref as an absolute path or a `file://` uri is refused with the same command using the relative path. A ref to something outside the project is kept as written. **Built**, for `refs` on an element and for `ref` in a want. **Reason:** the map must still hold when the project folder moves.

The tool does not check that a ref's file exists.

### 3.7 Outside the project

An outside project appears in the map as one element under `upstream` or `downstream`, at the address of its own functionality, such as `upstream.code.engine.game`. A want on it is held locally and points at that local element. A downstream party that is a person is addressed by the type of party it is. **Decided** (R-3.7, R-4.15, R-7.3).

Reading the outside project's own map from that element is **Decided, not built** (section 11).

### 3.8 What keeps an element what it is

To understand an element as a type is to hold three things together. They are the why of the receiver, the how of the provider, and the functionality that the address names. An agent that changes how an element does what it does has mutated it. An agent that changes what it does has made a different element, and the map grows by one. No field stores this boundary. The protection is the understanding that the intake recorded. **Decided** (R-3.8, R-3.9, R-3.21).

## 4. The stored form

### 4.1 One rule

The stored form of a map is one nested JSON object. The type of the value under a key decides what the key is. **Built**; this is `metaform/metaform.schema.json`.

| Value type | Meaning | Name in the schema |
|---|---|---|
| Object | An element, or a branch on the way to one. The key is one address segment. | `NamespaceNode` |
| Array | A layer at that element. The key is the layer's name, and each item is one record. | `ComposedElementLayer` |
| String, number, boolean, null | A field of the element. | scalar |

`refs` is the one array that is a field and not a layer. `wants` is an array whose records the schema checks field by field (`WantRecord`).

### 4.2 An example

The example below is the founder's, given on 2026-11-15. A value of `...` is a placeholder.

```json
{
  "mashtrac": {
    "id": "carverj-mashtrac-2026-10-31",
    "name": "Mashtrac Protocol",
    "project": "carverj/mashtrac",
    "skills": [ { "uri": "skill://git-workflow/SKILL.md", "frontmatter": { "name": "git-workflow", "description": "..." } } ],
    "layer": {
      "document": {
        "specification": {
          "technical_name": "specification document layer",
          "name": "Specification",
          "role": "Supporting Element",
          "description": "...",
          "format": "markdown_blocks",
          "instruction": "..."
        }
      }
    },
    "code": {
      "masher": {
        "widget": {
          "technical_name": "widget masher",
          "name": "mashbox",
          "role": "Coupled Element",
          "refs": ["./src/widgets/mashbox.c"],
          "specification": [ { "level": 1, "title": "...", "text": "..." } ],
          "memory": [ { "fact": "..." } ]
        }
      },
      "protocol": { "network": { "tracker": { "cs": {
        "technical_name": "cs tracker network protocol",
        "name": "mashtrac",
        "role": "Defining Element",
        "refs": ["./src/network/mashtrac.c"],
        "wants": [ { "element": "code.masher.widget", "why": "...", "how": "...", "direction": "receive" } ]
      } } } }
    }
  }
}
```

Reading the example:

- `mashtrac` is the project's name, and everything beneath it is the project.
- `layer.document.specification` is the definition of the specification layer (section 5.6). The definition that the server writes also holds a `template`.
- `code.masher.widget` and `code.protocol.network.tracker.cs` are elements. The objects between `code` and each of them are branches.
- `specification`, `memory` and `skills` are layers: each is an array under the layer's name. `skills` at the project's root applies to the whole project.
- `wants` holds one want: the Defining Element wants the Coupled Element.
- `id`, `name` and `project` at the project's root come from the founder's example file. Section 14 notes a requirement that disagrees with the field `project`. The root key `mashtrac` is the project's name, and it is the first segment of a path across projects (section 4.3).
- The tool's examples in `metaform/tool-help.json`, `metaform/tool-examples.json` and `metaform/intake-example.json` use the same two elements with the same values.

### 4.3 Two forms of the same data

- **The form in which data is entered.** A write and an addressed read name an element by its full address. An agent works in this form.
- **The stored form.** A key that starts with a period returns the nested JSON at that path, with everything beneath it. `{".": {}}` returns the whole project.

**Built** (R-4.12, R-5.34). **Reason:** an agent reasons more easily over full addresses, and the nested form is how the data is organized.

**The project's name is the root of the stored form.** The path to an element is `$.projectname.address.of.element` (R-4.2). **Decided**, 2026-11-07. The same path can name an element from outside its project. A command uses it that way (section 8.10, decision 2).

In the build, the project's name is not in any path. The core library can write and read a document under the project's name, and no command of the server produces it. A raw dump is keyed by the path that was asked for. **Built in part.**

### 4.4 Names

Agents send and receive snake_case. The store keeps keys and address segments in camelCase, and the server converts in both directions. A name that would not convert back exactly is refused with the corrected command, and a name in uppercase is refused and not lowercased. The refusal is `NAME_ROUND_TRIP_FAILURE`. **Built** (R-4.11).

### 4.5 The database is not the nested form

The database holds the same data as rows of a graph (section 9). The server builds the nested form in memory when a raw dump asks for it. Agents never see the tables (R-2.1).

## 5. Layers

### 5.1 What a layer is

A layer is one kind of knowledge, spread across the map and placed only at the elements where it applies. The base map keeps a thing the kind of thing it is. The layers hold what makes it the particular thing it is. **Decided** (R-6.0, R-3.20).

A layer adds to the map and does not change it. A layer can exist for one piece of work: a port from C++ to Rust adds a porting layer, and removes it when the port is done. The map is the same before and after (R-3.22).

In the stored form, a layer at an element is an array under the layer's name (section 4.1).

### 5.2 The definition of a layer

**The definition of a layer and its structure live beneath the `layer` root.** A layer is defined by an element beneath `layer`, such as `layer.document.specification`. The definition details the structure of the layer's records, and that one structure applies at every address in the map that holds the layer. **Decided**, 2026-11-09.

- **Field name.** The layer's field at a receiving element is the last segment of the definition's address. `layer.document.specification` defines the field `specification`. No two definitions share a last segment.
- **Made like any element.** A layer is made with `add` at its `layer` address and removed with `delete`. No separate command exists. **Reason:** the definition is an object in the map, so the commands that write the map already write it.
- **Read when needed.** The number of layers has no limit, so a layer's definition is never part of the tool's own definition. An agent reads it when it goes to write that layer.

A definition has two parts.

| Part | Fields | What the server does with it |
|---|---|---|
| The structure of a record | The field names in `fields`, and each field's `type` | Checks every record against it, at every address that holds the layer. |
| Prompt structure and instructions | `prompt`, `instruction`, and each field's `part_of_speech`, `rule` and `example` | Delivers them to the agent. It does not check a record against them. |

- `prompt` holds the instructions used to infer and create a prompted layer, and then run against the addressed elements to fill it.
- `instruction` is delivered once to the agent while the layer is active.
- `part_of_speech`, `rule` and `example` say how the agent writes the content of each field.
- `template` is a sentence that the fields of a record fill. It formats the readable report (R-6.20).
- `description` and `ref` describe the layer for a reader.

**Reason for the two parts:** the structure of a record can be checked by a program, exactly and at once, so the server checks it. The prompt structure and the instructions say how to write well, and only a model can judge that. Checking them would put a model in the path of every write, which would make a write slow and its result uncertain. They are also the kind of text that the tool must never grade (section 2, principle 4).

### 5.3 What is built of the definition

| Statement | Status |
|---|---|
| An element beneath `layer` with a text field `instruction` defines a layer. | Built |
| The field name is the definition's last segment, and a second definition with the same last segment is refused (`LAYER_NAME_COLLISION`). | Built |
| A list written under a name that is not a defined layer, a system layer or `refs` is refused (`LAYER_NOT_REGISTERED`). | Built |
| The server reads `instruction` and `format` from a definition. | Built |
| The server reads `fields` and checks each record against it. | Decided, not built |
| The server reads `prompt`, `template`, `part_of_speech`, `rule` or `example`. | Decided, not built |
| A defined layer with no `format` accepts any record. | Built; it departs from the decision |
| The checks for the format `markdown_blocks` are in the code and not in the definition. | Built; it departs from the decision |

Section 13, decisions 9 and 10, give the form in which a definition states structure.

### 5.4 Records

- Layer records are accepted only at an element that has `technical_name`, `name` and `role`, and at the root once the project has a Defining Element. An element beneath `layer` holds no records. The refusal is `ELEMENT_NOT_IN_SKELETON`. **Built** (R-6.26).
- For a layer that the map defines, an empty list removes the layer's field from the element. For `skills`, `memory` and `sources`, an empty list is stored. **Built.**
- A plain read returns no layer. A read returns a layer's records only when the read names the layer in the place where it is written, with `{}` as its value: `{"<address>": {"specification": {}}}`. **Built** (R-6.27).

### 5.5 Layers that the system provides

| Layer | What it holds | Status |
|---|---|---|
| `wants` | Section 3.5. It is the layer of the reserved group `intake`: agents write its records, and the layer is not listed and cannot be deleted, because it is the map. | Built as part of the element |
| `skills` | Skill entries at an address. `goto` returns each skill's name, description and uri. | Built as a list; delivery as resources is not built |
| `memory` | Memories at an address. `goto` returns the count. | Built as a list; the memory tool is not built |
| `sources` | Links to entry points in the material. | Built as a list |
| `specification` | Section 5.6. | Built |

`skills`, `memory` and `sources` are defined in the code and have no definition beneath `layer`. Section 13, decision 11, gives them definitions there and leaves `wants` in the schema.

The build accepts a system layer's list at any element, the root and an element beneath `layer` included. It checks only that the value is a list.

### 5.6 The specification layer

The specification layer holds the prose that the base map leaves out on purpose. Its definition is at `layer.document.specification`. The server writes that definition into each project's main map and refuses any other write to it (`LAYER_DEFINITION_LOCKED`). **Built** (R-6.24).

The definition declares the format `markdown_blocks`. A record is a block: `{"level": 1-4, "title": "...", "text": "..."}`, with an optional `code`. The first block may be `{"text": "..."}` alone, as an introduction. **Built** (R-6.25):

- The first titled block is level 1. Each level is at most one more than the level before it. No level is above 4. The refusal is `HEADING_LEVEL_INVALID`.
- The text holds no Markdown heading line outside fenced code. The refusal is `HEADING_IN_TEXT`.
- A `code` is a key that other text can cite. It is unique in the layer across the map, ignoring case. The refusal is `CODE_NOT_UNIQUE`.
- Section 16.9 gives every rule for a block. The tool does not judge the wording of the text.

**Reason:** the heading structure lets the prose be exported as Markdown and imported again without loss (section 10).

The address stays `layer.document.specification` (section 13, decision 14).

### 5.7 Where a layer is active

**Decided, not built** (founder, 2026-11-09). No code reads the arrays named here.

| State | Rule |
|---|---|
| Defined | The definition under `layer` creates the layer. Creating it does not turn it on. |
| Enabled | The project's `layers` array at `.` lists the layers that are on. A layer that is not listed is off everywhere, and its links and records stay in place. |
| Linked | An element links a layer by naming it in its `layers` array. An enabled layer is active at that element and at everything beneath it. It never applies toward the root. |
| Blocked | An element blocks a layer by naming it in its `blocked_layers` array. The layer stops there and does not reach beneath. |
| Moved | To make a layer active nearer the root, the link is moved to an element nearer the root. |

- A write that would name one layer in both arrays at one element is refused, and the remediation removes the link.
- Elements under `upstream` and `downstream` do not inherit the project's layers (R-6.5).
- **Reason:** a layer is placed only where it applies, and one link at the right element covers everything beneath it.

### 5.8 Kinds of layer that are decided and not built

- **A prompted layer.** One instruction is applied at every element it addresses, and each element answers it for its own functionality. It is created in this order: infer the layer from its prompt, define it beneath `layer`, then run the prompt against the elements (R-3.22, R-6.18).
- **A plugin layer** links the artifacts that a plugin produces to the functionality they refer to (R-6.18).
- **A `features` layer** tags every element with the feature or features it belongs to (R-6.19).
- **The address inbox** is a layer whose content lasts until it is delivered to whoever works at that address next (R-6.23).

### 5.9 The name

On 2026-11-11 the founder decided that a layer is called an overlay, with the arrays `overlays` and `masked_overlays`. On 2026-11-12 the founder said that the root is `layer`. The tool, the schema and the procedure say layer, and this document says layer. The word is layer (section 13, decision 13).

## 6. The tool

### 6.1 One tool

Agents read and write the map through one MCP tool, `project-map`. **Built** (R-5.1). **Reason:** every tool definition reaches every agent before its first call, and an earlier system that gave each command its own tool passed 150 tools.

Three files define it.

| File | What it is |
|---|---|
| `metaform/mcp-tool.published.json` | The definition that the server publishes to agents: one key, which is one of the operations or an address. It holds no description of a field. The founder designed it to be under one kilobyte. |
| `metaform/mcp-tools.proposed.json` | The contract. It gives the tool's name and description, and the server checks every command against it. |
| `metaform/tool-help.json` | What `{"help": "<command>"}` returns. |

### 6.2 The form of a command

A command is one JSON object with exactly one key. The key decides the command. **Built.**

| Key | Value | What it does |
|---|---|---|
| `add` | `{"<address>": {fields}}` | Adds an element, or adds fields and wants to an element that exists. |
| `update` | `{"<address>": {fields}}` | Changes fields of an element. |
| `delete` | `{"<address>": {}}` or `{"<address>": {"wants": ["<address>"]}}` | Deletes an element, or removes wants. |
| `orphaned` | `{}` | Returns the elements that no element wants. |
| `goto` | `"<address>"` | Places the agent at an address and returns a summary of what is there. |
| `map` | `{}` | Returns every address, each wanting pair, and the Defining Elements. |
| `help` | `{}` or a name | Returns the names help takes, or one named thing. |
| an address | `{}` or `{"<layer>": {}}` | Reads that element's own fields, and the layers that the read names. |
| a path that starts with a period | `{}` | Returns the stored JSON at that path. |

The seven names `add`, `update`, `delete`, `orphaned`, `goto`, `map` and `help` are commands. A key that starts with a period is a raw dump. Any other key is a path to read, so `{"code": {}}` reads the element `code`. **Built.** An earlier rule said that every key without a period is a command (R-5.1). Section 13, decision 16, replaces it and gives the reason. One write command names one element. In the build, no command selects a project: the connection names it (section 8.3). Section 8.10 says why this must change.

`search` is **Decided, not built** (section 11).

### 6.3 Writes

**Built:**

- **A write creates every path it needs,** including the element that a want names (R-5.4).
- **`add` keeps what is there.** A list given where a list is stored is appended. Any other value is written. An `add` may hold objects, and each object is an element beneath the address. `null` is refused for `technical_name`, `name`, `role`, `status` and `refs`.
- **`update` writes to a path.** A list replaces the list that is there, except `wants`: each want record changes or adds one want, and the other wants stay. `null` removes a field. A field left out is unchanged. `update` also creates an address that is missing.
- **A want in `add`** needs `why`, `how` and `direction`. A record whose key matches a stored want overwrites it.
- **A want in `update`** needs `element` and at least one of `why`, `how` and `direction`. A record whose key matches merges the fields given. A record with no match is a new want and must end with all three fields. The refusal is `WANT_INCOMPLETE`.
- **A successful write answers `{"status": "ok"}`** and nothing more (R-5.35). **Reason:** the agent sent the command and has it; in four recorded intakes the repeated command was 29% of the bytes the tool delivered.
- **A failed command changes nothing** (R-5.8).

### 6.4 Deleting

**Built:**

- `delete` with `{}` removes an element. It is refused when another element wants the element (`DEPENDENCY_LOCK`), and the remediation is the command that removes that want. It is refused when elements sit beneath it (`ELEMENTS_BENEATH`).
- `delete` with `wants` removes every want on each named element. It cannot remove one of several wants on the same element. This is a known gap.
- A deletion leaves no empty element (R-5.36). An element is empty when it has no fields, no wants and nothing beneath it. When the last want that names an empty element is removed, the element is removed too. Each empty branch above it is removed in the same way.
- `delete` of an address that is not in the map answers `{"status": "ok"}`.
- The root cannot be deleted. `layer.document.specification` cannot be deleted. Another layer definition can be deleted, and the build does not check for records left at elements.

The founder's sequence for deleting an element has four steps (R-5.25):

1. The direct delete is refused.
2. The remediation removes the want.
3. An orphan scan confirms that nothing wants the element.
4. The delete succeeds.

### 6.5 Reads

**Built:**

- **An addressed read** returns the element's own fields, keyed by its address: every field that is not a list, with `refs`. It returns wants or a layer only when the read names it. It does not return who relies on the address. An addressed read cannot read the root.
- **A raw dump** returns the stored JSON at the path, keyed by the path as sent, with every layer and every want.
- **`map`** returns `{"addresses": [...], "edges": [[holder, wanted], ...], "defining": [...]}`. It returns no fields. `addresses` includes the addresses beneath `layer`. Each wanting pair appears once, however many wants it holds.
- **`orphaned`** returns an object keyed by address, with each element's own fields. An element is listed when it is not the root, is not `layer` or beneath it, has at least one field, and no want names it. Being orphaned does not mean an element should be deleted.
- **`goto`** returns a summary sheet (section 6.6).

### 6.6 `goto`

`goto` places the agent at an address. It returns what is directly linked there. The wants are returned as records. The layers and the memory are returned as counts. **Built** (R-5.30); the founder may still change the form.

| Part | What it holds |
|---|---|
| `at` | The address. |
| `element` | The element's own fields. |
| `wants` | The element's wants. |
| `wanted_by` | The wants in other elements that name this address, each with the address of the element that holds it. |
| `layers` | `{"<name>": {"records": n}}` for each list at the element except `memory`, `skills` and `refs`, and for each defined layer whose records are allowed there. |
| `memory` | `{"records": n}`. |
| `skills` | Present when the element has skills: each skill's `name`, `description` and `uri`. |
| `instructions` | One sentence for each defined layer, saying where its rules are. |
| `guidance` | Present only at a layer's definition: the layer's rules. |
| `instructions` at every address | The server sends the whole sheet every time and holds nothing back (section 13, decision 1). |

- **`goto` returns the whole sheet every time.** The server remembers nothing for a connection. **Built**, 2026-11-15. **Reason:** MCP has no session, and clients keep a connection for different lengths of time, so a saving that depends on the connection works for one client and fails silently for another. On a small element the whole sheet is a few hundred bytes.
- **A connection stands for a context** until agent identity exists. **Built, not confirmed.** This is state that the server keeps for a connection, which stateless MCP does not allow for (section 8.10).
- **The rules of a layer are delivered at its definition** and not at each element. **Built, not confirmed.** **Reason:** in four test intakes the rules reached every agent on its first `goto`, and three of the four never wrote the layer.

### 6.7 `help`

`help` reads nothing from the map and writes nothing. It answers one level at a time. **Built** (R-5.39, and the founder's decision of 2026-11-12).

| Command | Returns |
|---|---|
| `{"help": {}}` | The names that help takes: `add`, `update`, `delete`, `orphaned`, `goto`, `map`, `addressed read`, `raw dump`, `help` and `intake`. |
| `{"help": "<command name>"}` | What the command does, its fields with one line each, and examples, from `metaform/tool-help.json`. |
| `{"help": "<definition>"}` | One definition of the contract. |
| `{"help": "intake"}` | The sections of the intake procedure in order, the required ones, and how to read them. |
| `{"help": "intake/<section>"}` | One section of the procedure. |

**Reason for answering a command in one piece:** an agent had to follow three pointers to learn one field name. The answer misled the model in the one run with the real tool.

Every example in `metaform/tool-help.json` is the founder's. An agent must not add an example, because an example changes what a model infers.

### 6.8 The procedure's words

The tool answers a command that uses the procedure's words with the same command in the tool's words. **Built.** **Reason:** an agent that follows the procedure exactly must be given the right command, and the procedure is not edited to match the tool.

| The command uses | The tool answers with |
|---|---|
| `dependencies` on an element | `wants`, with the same records |
| `pe` or `provider` in a want | `element` |
| `op` or `purpose` in a want | `why` |
| `ef` in a want | `how` |
| `ifd` in a want | `direction` |
| `sends` or `receives` as a direction | `send` or `receive` |
| `uri` on an element | `refs`, as a list of one |
| `uri` or `refs` inside a want | One want for each uri, each with its `ref` |
| `wants` as an object keyed by address | The same records as a list |
| One of the six earlier `status` spellings | `un_built` |
| `AT`, `DE`, `SE`, `CE`, `NE`, `CQU`, `UD` or `DD` as a role | The role's full name. For an element that exists, the remediation is an `update` of `role` alone. |

### 6.9 Refusals

Every refusal returns the command it refused, followed by four parts in this order. **Built** (R-5.24).

1. `"status": "error"`.
2. A fixed `code`.
3. A `message` that says in plain words which rule the command broke.
4. The `remediation` command that fixes it.

```json
{
  "delete": {"code.masher.widget": {}},
  "status": "error",
  "code": "DEPENDENCY_LOCK",
  "message": "cannot delete 'code.masher.widget': 'code.protocol.network.tracker.cs' still wants it. Remove that want first.",
  "remediation": {"delete": {"code.protocol.network.tracker.cs": {"wants": ["code.masher.widget"]}}}
}
```

- **A refusal returns a corrected command when one follows from the command and the map, and none when the tool would have to guess** (section 13, decision 17). The refusals marked "none" in section 16 return `null`. `LAYER_NOT_REGISTERED` and `NOT_FOUND` return the read `{"map": {}}`, because the fix is to choose from what exists.
- **A remediation never changes what the refused command did not address** (section 13, decision 18). One case in the build breaks this, and it is a fault to fix: when a command writes an element beneath an element that holds a field of the same name, the remediation of `FIELD_ELEMENT_COLLISION` removes that field.
- The remediation of `DEPENDENCY_LOCK` removes the want of another element. That is the founder's design for deleting an element (section 6.4).
- A value in angle brackets, such as `<why>`, marks what the agent must supply.
- Every message for a command of the wrong form is written by hand, in a fixed order of checks. No message comes from a schema validator. **Reason:** the validator's messages held type names and pointer paths, and some pointed at the wrong problem.

| Code | Raised when |
|---|---|
| `FIELD_MISMATCH` | The command or an element does not match its form; a `help` name is unknown; a ref must be relative. |
| `NAME_ROUND_TRIP_FAILURE` | A name does not survive the conversion of section 4.4. |
| `ROOT_SCOPE_NOT_ALLOWED` | A write creates an element outside the roots. |
| `TECHNICAL_NAME_ALIGNMENT_FAILURE` | `technical_name` is not a leading run of the reversed address, or is at the root. |
| `ROLE_TAXONOMY_FAILURE` | A write sets `role` to a value that is not one of the eight role names. |
| `WANT_INCOMPLETE` | A want would be left without `why`, `how` or `direction`. A want record in `update` that gives none of the three is `FIELD_MISMATCH`. |
| `FIELD_ELEMENT_COLLISION` | A name is both a field and an element beneath. |
| `DEPENDENCY_LOCK` | `delete` of an element that another element wants. |
| `ELEMENTS_BENEATH` | `delete` of an element with elements beneath it. |
| `NOT_FOUND` | A read, a `goto` or a raw dump of something absent. |
| `LAYER_NOT_REGISTERED` | A write changes a list whose name is not a layer. |
| `LAYER_NAME_COLLISION` | Two definitions share a last segment. |
| `LAYER_DEFINITION_LOCKED` | A write changes or deletes `layer.document.specification`. |
| `ELEMENT_NOT_IN_SKELETON` | Layer records are written where records are not allowed. |
| `HEADING_LEVEL_INVALID`, `HEADING_IN_TEXT`, `CODE_NOT_UNIQUE` | Section 5.6. |
| `INTERNAL_ERROR` | The store failed. The message says that the write may or may not be stored. |

Two codes exist in the code and are never raised: `GRAMMAR_CONSTRAINT_VIOLATION` and `CANONICAL_NAME_COLLISION_FAILURE`. The field `tested_sentence` is never set. The grammar check on `why` and `how` that they belong to is **Decided, not built** (D-14).

## 7. Intake

### 7.1 What intake is

Intake infers the base map from an artifact. An agent performs it by following the intake procedure and recording through the tool. **Decided:**

- Only one agent performs an intake (R-2.10).
- Intake has no start and no stop in the tool. The map is what is stored, and it is shown as it is written (R-5.19).
- Intake is never gated or judged (principle 4).
- Intake places nothing beneath `layer`, because an intake finds no layers in an artifact.

### 7.2 The text

The whole procedure is in this archive, in the folder `metaform/intake/procedure/`: one Markdown file for each section, and `sections.md`. `sections.md` names the sections in reading order. It marks a section `(required)`, or gives in parentheses the condition under which a section applies.

The procedure's text is the founder's, and section 12 protects it. This document names the sections and does not restate their content.

| Section | Marked |
|---|---|
| `title`, `goal`, `prompt` | |
| `core_concepts` | required |
| `examples`, `namespace_rules`, `cqu_rules`, `constraints`, `method`, `completion_condition`, `response_protocol` | |

### 7.3 How the server delivers it

The server sends no section to an agent that has not asked for it. **Built**, on the founder's instruction of 2026-11-12. **Reason:** an agent that adds or removes one record must not be sent the whole procedure. An agent that performs an intake reads all of it once.

- `{"help": "intake"}` lists the section names in order, the required ones, and any conditions.
- `{"help": "intake/<section>"}` returns one section.
- Each section is also a resource, `metaform://intake/<section>`.
- The build compiles the folder into the server. The server reads no procedure file while it runs.

### 7.4 Nothing locks the content

No test and no check reads the names of the sections, which section is required, or the text. The code names no section. The build reads `sections.md` only to serve what it finds there, and it never stops because of how the folder is edited. A file that `sections.md` does not name is served after the listed sections. A name with no file is left out with a warning. **Built**, decided by the founder on 2026-11-12. **Reason:** in an earlier project, agents wrote tests against the text of the prompts, and the founder could no longer edit a prompt without breaking the build.

### 7.5 The state of the text

- The text in the folder is the founder's working file as saved on 2026-11-12 at 07:54, with its markup converted to Markdown by a script. The conversion turned tag and attribute names into visible words, such as "Rules:", "valid" and "invalid". The founder has not accepted the converted text, and it will not be repaired: the procedure is written fresh (section 13, decision 28).
- Two edits were made after the conversion, on the founder's direct instruction. One is the first sentence of the CQU definition in `core_concepts.md`. The other changes "an AUE role" to "a role" in `response_protocol.md`.
- Three changes were made on 2026-11-15, on the founder's instruction to make the edit that the new role needs. The definition of CE (Coupled Element) was added after SE in `core_concepts.md`. The name of SE there was changed from Supportive Element to Supporting Element. CE was added to the two lists of roles in `response_protocol.md`.
- `founder/intake_best.xml` in this archive is the founder's working file. It has none of these edits. The tool does not read it.

### 7.6 Passages to report

The rule of section 12 is to report a passage that reads as ambiguous and not to resolve it. These passages are reported:

1. In `core_concepts.md`, the definition of AUE ends with "is an AUETreat each photograph, document". The founder's XML file has the same text.
2. In `core_concepts.md`, the definition of NS says "five base valid types" and lists six.
3. `response_protocol.md` says that every element carries one uri. The tool takes `refs`, a list, and a want carries `ref`.
4. `response_protocol.md` names an element's identity `namespace_address`, and `namespace_rules.md` names a field `functional_name`. The tool has no field of either name; it has the address and `technical_name`.
5. `method.md`, step 2, says to mark `missing`, `broken` and `exclude`. The tool refuses `missing` and `broken` as a `status`, and it has no place for a concern.
6. `namespace_rules.md`, rule 6, says that `name` must not match the functional name. The tool does not enforce it (section 3.3).
7. The want sentence in `metaform/tool-help.json` says "requires", and its rule for `how` says "provider". The tool says `wants` and `element`. The founder's example `how`, "Prepared mash data packets.", is a noun phrase and does not fit the rule.
8. `namespace_rules.md` says "supportive elements" in one example. The role is now named Supporting Element.
9. `method.md`, step 3, and `constraints.md` tell the agent to find SE elements. Neither names CE.

### 7.7 What test intakes showed

Two test intakes ran through the real server on 2026-11-12, each by one fresh agent on 37 photographs. These are observations, not requirements.

- The delivery worked: the agent read every section in order, read `{"help": "add"}`, and used the tool's words.
- The agent made every write at the end. Steps 3 and 6 of the procedure say to record as it goes.
- The agent sorted photographs into kinds and did not go inside a photograph. The founder's reference treats the photograph as the artifact and its subject, setting and light as its elements.
- The agent found concerns, such as duplicates, and had nowhere to record them.
- No intake has been run on code with this version.

## 8. The server

### 8.1 Processes and commands

The Rust form is a Cargo workspace of four crates. **Built.**

| Crate | What it holds |
|---|---|
| `metaform-core` | The map in memory and every rule of a command. It has no storage and no network. |
| `metaform-store` | The store, on LadybugDB (section 9). |
| `metaform-server` | The `metaform` binary: the server, the forwarder and the command line. |
| `metaform-web` | The `metaform-web` binary: the host of a web page (section 8.9). |

| Command | What it does |
|---|---|
| `metaform mcp [--home DIR] [--project DIR]` | The MCP process for an agent, over stdio. The project folder defaults to `.`. |
| `metaform mcp [--home DIR] --map NAME` | The same, on a map that belongs to no project. |
| `metaform call [--home DIR] [--project DIR \| --map NAME] '<json command>'` | A departure from the rule below. Performs one command of the tool from a shell. `-` reads the command from stdin. It exits 0 on success, 1 on a refusal and 2 on a usage or connection error. |
| `metaform projects [--home DIR]` | Lists every registered project: id, name and folder. |
| `metaform specification export [--check]` | Prints the map and its specification layer as one Markdown document (section 10). |
| `metaform specification import FILE` | Reads back a document that the export made. |
| `metaform settings`, `metaform set KEY VALUE`, `metaform unset KEY` | Reads and changes settings (section 8.8). |
| `metaform gui [--home DIR] [--port N]` | Starts `metaform-web` and prints its address. |
| `metaform serve [--home DIR]` | The server for a home. `mcp` starts it when it is needed. |

**MCP and the command line are separate.** **Decided by the maintainer**, 2026-11-15. Not built.

- MCP is for data manipulation: reading and writing the map.
- A feature that is MCP is wholly MCP. It has no form on the command line.
- A command-line command is not an MCP tool. Nothing requires that a tool have a command, or that a command have a tool.
- Today the MCP surface is one tool, `project-map`, and its resources: the connection's map and the sections of the intake procedure.

**Reason:** each way of reaching the same data is a surface that must behave the same as the others. Two surfaces are kept the same only by constant work, and this project's history shows that they drift apart instead. An agent also learns the tool from its refusals, and a second surface would have to teach the same lessons in the same words. The command line has a different job: a person uses it to run the system, to start it, to set it up and to take a document out of it.

**What speaks against it:** with no command-line form of the tool, a developer cannot send one command from a shell, and the server's tests, which do exactly that today, must be rewritten. The earlier rule R-5.14 said the opposite, that every MCP tool can also be used through the command line, so that a harness without MCP can still use it. That need has not been shown to be gone.

The build has two commands that touch this rule, and one more client of the tool that is not on the command line:

| Part of the build | What it does | Standing |
|---|---|---|
| `metaform call` | It sends one command of the MCP tool from a shell. It was built under the withdrawn rule R-5.14. | **It goes.** It is the tool on a second surface. Its code stays as the client that the web host and the tests use, and the tests call that code. |
| `metaform specification import` | It reads back a document that `export` made, and writes the specification layer. | **It stays on the command line.** It is the return half of `export`, and a person uses it on a whole document. It adds no second set of rules: it sends `update` commands through the tool's own checks. |
| The web host's routes `/call` and `/write` | They pass one command of the tool to the server over HTTP. The host is an MCP client. | **They stay.** They are how a page reaches the one tool, not a second surface with rules of its own. |

`metaform specification export` reads the map and formats it. The founder decided on 2026-11-06 that an export is a command-line command.

### 8.2 The home

The home is the folder that one server owns and writes under. It is `--home`, or the environment variable `METAFORM_HOME`, or `~/.metaform`. **Built**; the override `METAFORM_HOME` is not confirmed by the founder.

| Path under the home | What it holds |
|---|---|
| `server.lock` | The lock that makes the server the only owner of the home. |
| `server.sock` | The Unix socket that the server listens on, with mode `0600`. |
| `server.log` | The server's output, when a connecting process started it directly. |
| `store.format` | A mark that this store wrote the home. |
| `metaform.lbug` | The registry of projects. |
| `projects/<id>/project.lbug` | One database for each project. |
| `projects/<id>/settings.json`, `projects/<id>/source.txt` | A project's settings, and the path of its folder. |
| `maps/maps.lbug` | One database for all maps that belong to no project. |
| `settings.json` | The global settings. |

- Only one server can run on a home (R-4.4). A second server waits up to 3 seconds for the lock and then exits.
- A home that holds data this store did not write is refused. The store writes nothing into it but the lock file `server.lock`.
- The path of `<home>/server.sock` must be at most 107 bytes. A longer path is refused with the reason.
- Nothing is written into a project's own folder (R-4.1).
- Many instances can run at once, each with its own home (R-4.14).

### 8.3 How an agent reaches the server

Each agent starts its own MCP process, `metaform mcp`, which is the forwarder. **Built** (R-4.5).

1. The forwarder connects to `<home>/server.sock`.
2. If no server answers, the forwarder starts one and connects again, for up to 5 seconds.
3. The forwarder sends one line that names its project folder or its map.
4. The server registers the project if it is new, and answers.
5. The forwarder relays MCP between the agent and the server.

- The forwarder opens no database. When it starts a server, it creates the home folder. It also creates `server.log`, unless it starts the server through a launcher.
- If the server ends while the agent is connected, the forwarder connects to a new server and replays the session's opening and its subscriptions. A request that was not answered gets an error that tells the agent to read the map before sending a change again.
- The server ends only on a termination or interrupt signal. A server that is running keeps running an older build until it is ended. Nothing compares the build of the forwarder with the build of the server.
- **Access.** Any process that can open a home's socket can open any map in that home. **Built.** Section 8.10, decision 4, says why the tool holds no permission.

### 8.4 The MCP surface

The target is MCP `2026-07-28`. The server also answers older clients. **Built** (R-8.1), through the library rmcp 3.9.

| Method | What the server does |
|---|---|
| `tools/list` | Returns the one tool, `project-map`, with the published definition. |
| `tools/call` | Performs one command. A success is one text block of JSON. A refusal is an error result with the form of section 6.9. |
| `resources/list` | Returns the connection's map, then one resource for each section of the intake procedure. |
| `resources/read` | Returns the result of `{"map": {}}` for the map, or the text of one section. |
| `subscriptions/listen` | Subscribes the client to the map's changes (section 8.7). |
| `resources/subscribe`, `resources/unsubscribe` | The same, for a client older than `2026-07-28`. |

The map's resource is `metaform://map/project/<project id>/main`, or `metaform://map/standalone/<name>`.

The server sends no instruction at connection. **Built**, 2026-11-15 (section 13, decision 24). **Reason:** every agent paid for that text on every connection, and it pointed to a page that is not accepted.

The server keeps no MCP session. It does keep state for each connection, which section 8.10 lists.

### 8.5 Projects

- A project is registered when a connection first names its folder. Its name is the last segment of the folder's path.
- Its id starts with the folder's path, with `-` in place of every character that is not an ASCII letter or digit. A number of at least three digits follows.
- The registry stores each project's id, folder and name. The project's own database does not store the name.
- The system is built for many projects from the start (R-4.9).

**Built.**

### 8.6 Reads and writes in the server

- A command whose key is `add`, `update` or `delete` is a write. It goes to the write queue (section 9.3).
- Every other command is a read. It runs against the last committed state and does not wait for a write. Section 18.5 names the two cases in which a read waits.

**Built** (R-4.7).

### 8.7 Change announcements

The server announces each change as it commits. Nothing polls. **Built** (R-4.10).

- After each committed write, the server sends `notifications/resources/updated` with the map's uri to every subscribed client, including the client that wrote. The notification carries no content.
- A refused write and a write that changes nothing announce nothing.

### 8.8 Settings

Every setting is declared in the code with its default. A default is never stored. A global value is stored in `<home>/settings.json`, and a project's value in `projects/<id>/settings.json`. The command line reads and sets them through the server. **Built** (R-4.8).

One setting exists: `stores.max_open_databases`. Its default is 16, it is global only, and a change applies at the next start of the server.

### 8.9 The web host

`metaform-web` serves a built web page from a folder and forwards commands to the home's server. It listens on `127.0.0.1` only, on port 4170, or on a free port when 4170 is in use. **Built.**

| Route | What it does |
|---|---|
| `GET /api/host` | Says whether the host forwards writes. |
| `GET /api/projects` | Lists the registered projects. |
| `POST /api/projects/{id}/call` | Forwards one read command. |
| `POST /api/projects/{id}/write` | Forwards one `add`, `update` or `delete` that comes from the host's own page. `--read-only` turns this off. |
| `GET /api/projects/{id}/events` | Sends one event for each committed change. |
| any other `GET` | Serves a file of the page. |

The page itself is not in this archive. The founder rejected the two pages that exist, and the interface is to be built from an empty page (section 11). Without a built page, `metaform gui` does not start the host. It reports that the page's folder has no `index.html`.

### 8.10 Stateless MCP, work across projects, and permission

The four decisions in this section were made by the maintainer on 2026-11-15, after the founder raised the directions and gave the design to the maintainer. The reasoning is the maintainer's. Nothing here is built.

**The facts about the protocol.** MCP has no session. The proposal SEP-2567, which is final, removes the session from the protocol at every layer, and SEP-2575 removes the `initialize` exchange. A server that keeps state between calls returns an identifier from a tool, and the caller passes that identifier in later calls. The results of `tools/list` and `resources/list` must not differ from one connection to another. The protocol still lets a server check a credential that arrives with each request.

**The facts about the build.** Four things are tied to one connection and one project:

| What | How the build does it | What goes wrong |
|---|---|---|
| The project | The first line on the socket names one project folder, and every command on the connection acts on it (section 17.4). | A command cannot reach a second project. |
| The `goto` sheet | Until 2026-11-15 the server remembered, for each connection, which parts it had sent. It now sends the whole sheet every time. | Fixed. |
| The list of resources | `resources/list` returns the map of the connection's project. | The result differs from one connection to another, which the protocol no longer allows for. |
| Subscriptions | Only the map of the connection's project can be subscribed. | The same limit. |

**Decision 1: a request carries everything that says what it is about.** **Reason:** the server cannot rely on a connection to remember anything, because the protocol gives a connection no fixed meaning and clients treat it differently. Whatever is kept for a connection works for one client and fails without a sign for another. So state belongs either in the request or in the database, where every client finds it the same way. **What speaks against it:** the `goto` sheet is sent only once to save an agent's reasoning, and that saving needs some memory of what the agent has seen. With no session, that memory needs an identifier that the agent carries, and an agent can lose it. **So:** `goto` returns the whole sheet every time, and the server remembers nothing for a connection. The sheet is small, because it holds counts and not records, and a layer's rules arrive only at the layer's definition. The saving returns when an agent has an identity that travels with each request, which is the work of the agents module.

**Decision 2: a map is reached at the root by its project's name.** A path that starts with a project's name names an element of that project. **Reason:** projects rely on each other, and an agent that works at the boundary of two systems makes fewer wrong guesses when it can see the other system's map. With no session, the path is the only place where a request can say which map it means. The stored form already has the project's name at its root (section 4.3), so the path adds no new idea: it is the stored path, used in a command. **What speaks against it:** most work happens inside one project, and a longer path on every command costs every agent reasoning. A rule is also needed to tell a project's name from a root such as `code`. **So:** a first segment that is a root means the project that the agent's MCP process was started for. That keeps short paths for the common case, and it is not session state, because a setting of the process is the same for every request. Any other first segment is a project's name. `{"map": "<project>"}` returns the shape of another project, as `{"map": {}}` returns the shape of the agent's own.

**Decision 3: a project has a durable name.** The name is given once and does not change. **Reason:** the build finds a project by the path of its folder. When the folder is moved or renamed, the build takes it for a new project and starts an empty map, and the old map is orphaned. A path in a request, and a link from one map to another, must keep their meaning for as long as the project exists, and only a name that never changes can do that. The same reasoning already made refs relative to the project folder (section 3.6). **What speaks against it:** someone must choose the name, and it must be unique. A short name such as `mashtrac` is unique only inside one home. **So:** the name is one address segment. It is given when the project is registered, and it defaults to the last segment of the folder's path, made into a valid segment. It must be unique in its home, and a name that is taken is refused with one that is free. It cannot be the name of a root or of a command. The registry is keyed by the name, the project's database is `projects/<name>/project.lbug`, and the folder is a property that can be changed when the folder moves. A name that holds its owner is not needed, because a home is local (decision 4).

**Decision 4: the tool holds no permission, and agents are told what they may do.** The tool does not stop an agent of one project from reading or changing the map of another. **Reason:** inside one home, every agent runs as the same user of the operating system. Each can open the server's socket, and each can open the database files directly. A check inside the tool therefore cannot stop an agent that means to cross a line; it can only stop one that crosses by accident. Accidents are better prevented by the form of the path: under position 2, an agent changes another project only when it writes that project's name. What an agent may do is then a matter of what it is told, in its prompts and instructions, which is also where its task and its scope come from.

**What speaks against it, and what the decision needs to be safe:**

- An agent can be told correctly and still do the wrong thing. If the tool does not prevent a wrong change, the system must make a wrong change visible and reversible. That takes three things: a record of which agent or project made each change, the announcement of each change, and the earlier state of an element. The build announces changes. It records no author and keeps no earlier state.
- Statelessness does not make permission impossible. A server can check a credential on every request. The decision is a choice to trust, and it is the right choice only while every agent in a home works for the same person.
- Where a map must be kept from another party, such as the private map of an agent in the game (R-4.15), a rule in a prompt is not enough. A separate home gives that separation, because the operating system then enforces it (R-4.14).

**No credential in the local design.** **Decided by the maintainer**, 2026-11-15.

Metaform is local. A home is a folder on one machine. One user of the operating system owns it, the server listens on a socket inside it that only that user can open, and every agent is a process of that same user. The operating system already decides who can reach the data: whoever can reach the home.

- **The home is the boundary, and the file permissions of the operating system are the credential.** Nothing further is checked.
- **Inside a home, every agent has the same power.** Each can open the socket and the database files. A credential that the server checked could not stop such an agent. It would add tokens to create, store, pass and renew, and each of those is a thing that can go wrong, with no protection gained.
- **Two parties that must be kept apart get two homes.** The operating system then keeps them apart (R-4.14).
- **Inside a home, a wrong change is made visible and reversible, not forbidden.** That needs the origin of each write, the announcement of each change, and the earlier state of an element. The announcement is built. The other two are not. **So:** reading another project's map is built first, and writing to another project's map is built only after the origin of a write and the earlier state of an element are kept.
- **A change to another project takes that project's name in the path** (position 2), so it does not happen by accident.

**When this is decided again:** when a home's server is to be reached by a caller that cannot reach the home's files, which means over a network or from another user of the operating system. Decisions 39 and 40 are the first two such cases. Then a credential on each request is the right tool, in the form the protocol defines for it, and never as an argument of the tool, where it would enter an agent's context. No such use exists today, and a check is added only for an observed need (section 2, principle 7).

- The tool's refusals are not permissions and they stay. They keep the data well formed, and they do not depend on who sends a command.

The earlier requirements that an address on the form has no project name (R-5.2) and that no command selects a project (R-5.3) are replaced by decisions 1 and 2. The build still follows the earlier requirements.

## 9. Storage

### 9.1 The engine and the databases

Maps are stored in LadybugDB, version 0.22.3. A map is the logical unit: it has its own id. A database is the physical unit that groups maps. **Built** (R-4.1).

**LadybugDB is the engine, and the core database of a home is a LadybugDB database.** **Decided** for the Rust form on 2026-11-07 and 2026-11-09 (R-4.1, R-4.6), and **Built**. **Reason:** the data is a graph, and the questions asked of it are graph questions: what wants this element, what is beneath it, what does it link to. LadybugDB also keeps each property as its own column. A store that keeps one record for each element, with every field inside it, must read and rewrite the whole record to touch one field, and it becomes slow as elements gain layers. **What speaks against it:** the engine is young, and the build depends on one exact version. Section 9.1 and 18.10 list the limits the store works around.

The core database is `metaform.lbug`, and it holds only the list of projects. The settings are JSON files.

**SQLite goes.** **Decided by the maintainer**, 2026-11-15. The Node and Python forms store their data in SQLite (R-4.6, 2026-11-09). One back end serves everything: the Rust server with LadybugDB. If Node or Python is wanted again, it is a process that passes commands to that server and holds no data. **Reason:** two engines are two designs of the same data, and they drift apart. **What speaks against it, and what is not known:** no measurement in this project compares the two engines. In the Rust form a read is answered from memory by a server that stays running, and the Node and Python forms have no such server, so their slowness may come from that and not from SQLite. Changing only the engine might then cure nothing. That is why the decision is for one back end and not for a faster engine: the whole design is carried, with one server for each home, the map in memory and one writer for each database.

**A project has one database, or more than one.** One database for each project is **Decided and built** (R-4.1). **Reason:** each database has its own writer, so work in one project never waits for another, and a project's data can be moved, copied or removed alone. One consequence must be kept in view: a relationship cannot join rows of two databases. So a want never crosses from one project to another in storage. A want on something in another project is a want on a local element under `upstream`, and that element refers to the other project (section 3.7).

**An element can contain the map of another project.** The base of this is **Decided** (R-4.15, 2026-11-09): any element can be given its own map, stored apart, and an agent reads it only when it asks. Two cases came up on 2026-11-15. **Decided by the maintainer**; not built:

- **A product that a project is built on.** A game is built on Unreal Engine. An intake of the engine gives a map of the engine, and the element of the game's map that stands for the engine contains that map.
- **Two projects that are developed together and rely on each other.** Each map shows the other project as one element, and that element contains the other project's map.

**Reason:** the boundary between two systems is where a wrong guess costs the most, because the agent sees its own side and must imagine the other. One element for the other system keeps the base map small, which protects every agent that does not need the detail. Going inside on request gives the detail to the agent that does. A person and an agent who look at the same map of the other system also mean the same thing when they talk about it, and so do two agents.

**What follows, and what is not settled:**

1. **A contained map is a ref.** The element holds a ref to the other project's map, as it holds a ref to any artifact that shows what the element is. **Reason:** a second kind of link would be a second thing to learn, to check and to keep right, and a reader already knows how to follow a ref. **What speaks against it:** a ref is plain text. Nothing checks that its target exists, and a reader needs a way to tell a ref to a map from a ref to a file. **So:** the ref is `metaform://map/<project>`, which is also the address of that map's resource, and its first part tells it from a ref to a file. The store's `childMap` property goes. A database holds one map, and the idea of several maps in one database goes with it.
2. **The link is to the other project's live map, not to a copy,** for a project that is developed alongside. The other project's agents keep writing their map, and the element shows what it holds now.
3. **A product's map is different in one way:** it describes one version of the product. Two projects can rely on different versions. **So:** a product is registered as a project like any other, and its version is part of its name when two versions must exist side by side. Projects that rely on the same version share the one map.
4. **Two projects that link to each other form a loop.** Reading is on request and one map at a time, so the loop does not unfold by itself.

The web interface has a matching requirement: a person can follow a link from one project to another, with a way back (section 11).

- A project's maps are partitions of the project's database. The server opens only the map `main` in a project's database.
- Maps that belong to no project are partitions of `maps/maps.lbug`.
- The grouping of maps into databases is **Built, not confirmed** (D-17). **Reason:** one process failed at about 7 open databases on default settings, so a database for every map would not scale.
- The limit on open project and standalone databases is 16. When another must open, the least recently used database that no command is using is closed first. If every open database is in use, the store exceeds the limit for a time.
- Each open database has a 64 MiB buffer pool, a 16 GiB size limit and 4 worker threads.

### 9.2 The graph

The map is a graph. **Built** (R-4.16).

| Table | Kind | Properties |
|---|---|---|
| `Map` | node | `id` |
| `Element` | node | `key`, `mapId`, `address`, `technicalName`, `name`, `role`, `uri`, `status`, `childMap`, `extra` |
| `Record` | node | `key`, `mapId`, `layer`, `ordinal`, `data` |
| `ROOT` | relationship, `Map` to `Element` | none |
| `CONTAINS` | relationship, `Element` to `Element` | none |
| `DEPENDS_ON` | relationship, `Element` to `Element` | `why`, `how`, `direction`, `extra` |
| `HOLDS` | relationship, `Element` to `Record` | none |
| `Project` (registry only) | node | `id`, `source`, `name` |

- **An element** is one `Element` node. Its key is `<map id>|<stored address>`. `extra` holds, as JSON, every field that has no column of its own and is not a list with items. An empty list is kept in `extra`.
- **Nesting** is the dotted `address`, with one `CONTAINS` relationship from each parent to each child.
- **A want** is one `DEPENDS_ON` relationship from the receiving element to the wanted element. `ref` is kept in the relationship's `extra`. Several relationships between the same two elements are kept.
- **Every list at an element** that is not empty is stored as `Record` nodes, one node for each item. `layer` holds the list's name, `ordinal` holds the item's position, and `data` holds the item as JSON. This covers the records of a layer and the items of `refs`.
- **Structure of arrays.** Ladybug stores each property as its own column. A write stores only the elements, wants and records that changed, and it writes all columns of a changed element. **Decided**, founder, 2026-11-09 (R-4.6). **Reason:** one record for each element holding every field gets slow quickly.
- The code works through Ladybug and never writes map files itself. Settings and the registry's folder names are files.
- **Where the build is not yet a structure of arrays.** Three kinds of data are kept as one JSON object in one text column, which is one record holding every field:
  1. `extra` on an element: every field other than `technical_name`, `name`, `role` and `status`.
  2. `extra` on a want: every field other than `why`, `how` and `direction`. The `ref` of a want is kept here.
  3. `data` on a record: all the fields of one layer record.
- A layer's definition is to hold the structure of its records (section 5.2). The store could then keep each field of a record in its own column, in a table made from the definition. Section 13, decision 12, decides this.

The founder decided that each layer is kept in its own files, apart from the map (R-4.3, R-6.21). The build keeps a layer as `Record` nodes in the map's database. An agent proposed that on 2026-11-07, because a file for every address would put tens of thousands of files on disk. Section 13, decision 8, keeps the records in the database and gives the reason.

### 9.3 Writes

**Built** (R-4.7):

- Each open database has one writer thread, which holds the database's only writing connection.
- Each writer serves clients in turn, one job at a time, so one agent's writes cannot starve another's. The writes of one client run in the order they arrived.
- A commit is one Ladybug transaction. No separate log is kept.
- A write is acknowledged only after it commits. A test ends the server with a kill signal and finds every acknowledged write.
- A write that is in flight when the server ends gets the forwarder's error of section 8.3.

The founder decided a write queue for each map (R-4.15). The build has one queue for each database, and a project's database holds one map today.

### 9.4 Reads

A read runs against the last committed state of the map, which the store holds in memory. It does not go through the writer, with the two exceptions of section 18.5. **Built.**

### 9.5 Databases from earlier builds

A database made by an earlier build is brought up to date when it is opened. **Built:**

- The relationship `WANTS` becomes `DEPENDS_ON`.
- The properties `op`, `ef`, `ifd` and `intent` become `why`, `how` and `direction`.
- A layer that an earlier build kept in `extra` is moved into `Record` nodes.
- A stored `uri` is read as `refs` with one item.
- A role stored as an abbreviation, such as `DE`, is rewritten as the role's full name.
- A database in which a table that this build knows differs in any other way is refused, and nothing is changed. A table that this build does not know is not compared.

No agent sees the name of a table or a relationship.

### 9.6 A possible defect

This is inferred from the code and was not run. An element stored before `refs` existed shows its `uri` as `refs` in memory, and the database holds no `Record` nodes for it. A later write to that element's columns clears the `uri` column and creates no record, so the element would have no `refs` after a reload. No test covers this path. It affects only a home made before 2026-11-12.

## 10. Specification export and import

`metaform specification export` prints the map and its specification layer as one Markdown document. **Built**; the layout and the import rules are an agent's and are not confirmed (R-6.28).

- The document starts with the project's name as its title, and then the root's blocks.
- An element outside `layer` has a heading with its name and its address when it has `technical_name`, `name` and `role`, or when it holds blocks. Under the heading are its role, technical name and status, one line for each want, and its blocks.
- A want is written with the want sentence. `direction` and `ref` are not written.
- `--check` reports where the prose misses eleven fixed targets, which section 16.10 lists. It does not fail. The targets come from an earlier version of `TASTE.md`.
- The export names each element it left out that holds one or two of `technical_name`, `name` and `role`. An element that holds none of the three and no blocks is left out and not named.

`metaform specification import FILE` reads back a document that the export made, and refuses any other. It writes only the blocks of the specification layer. A document whose headings or fact lines differ from the map is refused, and nothing is written.

A specification first enters the layers by inference, as intent enters by intake (R-1.2). An agent reads the source, decides which element each part describes, and writes the blocks with `update`. The import is only the return trip. **Decided.**

## 11. Decided and not built

| Item | What is decided | Source |
|---|---|---|
| The layer's structure in its definition | Sections 5.2 and 5.3. | R-6.24 |
| Where a layer is active | Section 5.7. | R-6.1 to R-6.9 |
| `search` | It reads all content of the map, layers included, and returns where each match is and not its content. | R-5.27 |
| The grammar check | A check of `why` and `how` against the want sentence. How it tells a verb ending in `-ing` from a noun is open. | R-5.24, D-14 |
| The memory tool | Memory is a module with its own tool. Its commands are those of the modelcontextprotocol.io memory server. It shows the memory graph of the address where the agent is. | R-5.29 |
| Tickets | A ticket ties work to the functionality it concerns and orients the agent as `goto` does. | R-5.31 |
| Skills as resources | The server announces the skills for an agent's position, and the agent reads a skill by its uri. | R-5.32 |
| Tasks | Intake and layer work run as MCP tasks, and the server pushes each task's status. Proposed. | R-5.33 |
| Chained maps | Any element can be given its own map, stored apart. A map can also belong to no chain. An element can contain the map of another project, such as the engine a game is built on (a position, section 9.1). The store keeps a `childMap` property, and no command sets it. | R-4.15 |
| Reading an outside project's map | An agent reads it only when it asks. The request form is not decided. | R-4.15, D-5 |
| The chassis and modules | An event-driven core in Rust with Bevy, and modules that add operations under a tool and never add a tool. A module finds the chassis at start-up. How modules connect is open. | R-2.3 to R-2.11, D-9 |
| Agent identity | The server will know which agent calls. Until then the connection stands for the agent. | R-5.3, D-8 |
| Work across projects | A command can name an element of another project by a path that starts with the project's name. The state that the build keeps for a connection moves into the request (section 8.10). | A position, section 8.10; SEP-2567 |
| The count of tokens | The system counts what reaches each agent from everything it controls, so that two runs can be compared. | R-1.3 |
| The Node and Python forms | Metaform ships in three forms that an agent cannot tell apart. The Node and Python forms exist in the source repository and still use the terms from before 2026-11-12. They are not in this archive. | R-4.6 |
| The web interface | See below. | `PROJECT_SPECIFICATION.md`, section 7 |

**The web interface.** A person uses it to see the map and move through it. An interface that meets the requirement does not exist. The founder rejected the two pages that were built. The requirements recorded on 2026-11-11 are:

- It is built from an empty page, and it is original.
- A person can read every name and follow every line. An effect that costs legibility or processor time is not wanted.
- Movement through the map follows one designed system of easing and zooming.
- The page follows the database as commands are applied and does not poll. A change never moves the view.
- Every narrowing has a visible way back.
- Lines show the direction recorded in each want, in plain words. The procedure's abbreviations never face a person.
- One interface serves every registered project.
- No control is inert, and simulated data is labelled.

## 12. Rules for work on Metaform

The files in `guidance/` state these rules for agents. They are requirements on anyone who changes Metaform.

1. **Treat the procedure and the grammar of the prompts as formulas.** Do not reword, reorder, shorten, merge or clarify a step, a rule or a definition. A passage that reads as ambiguous is contextual: its meaning comes from the text around it. Report such a passage to the founder and do not resolve it. **Reason:** agents went in to remove what read as ambiguity, changed the meaning, and the founder spent a week repairing it (founder, 2026-11-12).
2. **Everything around the text may change:** the layout of the files, the markup, how the text is served, and the code and the tool.
3. **Do not write a test, a check or a build step that reads the content of the procedure.** Section 7.4 gives the reason.
4. **Do not add an example** to the procedure or to the tool's help. **Reason:** one example changes what a model infers in every run.
5. **Change the schema and the contract only on the founder's direct instruction.** They are `metaform/metaform.schema.json` and `metaform/mcp-tools.proposed.json`.
6. **A rule that holds for one artifact may not hold for many.** Twice, a rule built for a code project could not record a folder of photographs. The two rules were one uri for each element and one want for each wanted element.
7. **Do not copy the founder's words into the project.** Write what the founder means and why. The exception is procedure text that the founder dictates.
8. **Write project prose to `guidance/TASTE.md`,** and handle a gap in the design as `guidance/EXPECTATIONS.md` says.

The prompt fields of a layer definition (section 5.2) are prompt text. Applying rule 1 to them is an agent's reading, and the founder has not confirmed it.

## 13. Decisions of the maintainer, and what stays open

The founder gave the design of this codebase to its maintainer on 2026-11-15. The maintainer made the decisions below on that day. Each has its reasoning here or in the section named. Each is decided and not built, unless it says that the build already does it. The founder can overrule any of them.

### 13.1 The back end

1. **A request carries everything; the server keeps nothing for a connection.** `goto` returns the whole sheet every time. Section 8.10, decision 1.
2. **A path that starts with a project's name reaches that project; a path that starts with a root means the agent's own project.** Section 8.10, decision 2.
3. **A project has a durable name, given once, unique in its home, and the registry is keyed by it.** Section 8.10, decision 3.
4. **The tool holds no permission and checks no credential. The home is the boundary.** Section 8.10, decision 4.
5. **One back end: the Rust server with LadybugDB. SQLite goes.** Section 9.1.
6. **One database for each project, and one map in each database.** Section 9.1. The build already keeps one database for each project.
7. **An element links to another project's map by a ref, `metaform://map/<project>`.** This serves a product such as an engine and a project developed alongside. Section 9.1.
8. **A layer's records stay in the project's database.** **Reason:** one transaction then covers an element and its records, so a write is whole or absent. A file for each address would put tens of thousands of files in a home, and no transaction would cover them. This replaces the earlier rule that each layer is kept in its own files (R-4.3, R-6.21). The build already does this.

### 13.2 Layers

9. **A definition states the structure of a record in `fields`, with a `type` for each field. A field is required unless its definition says `"optional": true`.** **Reason:** most fields of a record are required, so the common case needs no mark, and a mark on the rare case is read at the place where it matters. A definition with no `fields` accepts any record, so the layers that exist keep working.
10. **`format` stays as the name of a rule that the code holds, and `markdown_blocks` is the only one.** **Reason:** a rule over a whole list, such as heading levels that may rise by one, cannot be said as a type of a field. Inventing a language for such rules would cost more than the one rule it would express today.
11. **`skills`, `memory` and `sources` get definitions beneath `layer`, written by the server as the definition of `specification` is.** **Reason:** every layer then has one mechanism, and an agent finds every layer's structure in the same place. `wants` does not get one. It is the map itself and not knowledge laid over the map, and its form is fixed in the schema.
12. **A layer whose definition has `fields` is stored as a table with one column for each field. The `ref` of a want gets its own column.** **Reason:** the reason for LadybugDB is that data must not be kept as one record holding every field, and a layer's records are the data that will grow most.
13. **The word for knowledge laid over the map is overlay. The root where overlays are defined keeps the name `layer`.** **Reason:** the founder says overlay every time he speaks of it: the wants overlay, an inbox overlay, a handoff overlay. A name that the person who directs the work never uses will not hold. Overlay also says what the thing does: it is laid over the map and can be lifted off, and the map beneath is unchanged. The root is `layer` because the founder named it so on 2026-11-12, and stored maps hold it. **Not done:** this document still says layer throughout. Its wording is changed in one pass, in the next session.
14. **The specification layer stays at `layer.document.specification`.** **Reason:** it has the form that every definition beneath a root type has, such as `layer.code.cpp`, and maps that exist hold it there.

### 13.3 The tool

15. **`metaform call` goes, `metaform specification import` stays, and the web host's two routes stay.** Section 8.1.
16. **The seven command names are commands, and any other key is a path to read.** **Reason:** a path of one segment is a real path. `code` is an element, and under decision 2 a project's name alone is a path too. A rule that every key without a period is a command would make both unreachable by the one form of read. The fixed list of names tells a command from a path, so a project and a top element cannot take the name of a command. This replaces the rule of R-5.1. The build already does this.
17. **A refusal returns a corrected command when one follows from the command and the map, and returns none when the tool would have to guess what the agent meant.** **Reason:** a correction teaches only if it is right. A guess that is offered as the fix is followed, and a wrong one does damage that no refusal would have done. The read `{"map": {}}` stays as the answer to an address that does not exist and to a list that is not a layer, because the fix is to choose from what exists. The build already does this.
18. **A remediation never changes what the refused command did not address.** **Reason:** an agent follows a remediation without checking it against the rest of the map. One case in the build breaks this rule: when a command writes an element beneath an element that holds a field of the same name, the remediation removes that field. That remediation becomes none, and the message names the field. This is a fault to fix.
19. **A write takes `wants` as a list. There is no second form with the word `want`.** **Reason:** one form for every write. The build already does this.
20. **One of several wants on the same element is removed by a record: `{"delete": {"<address>": {"wants": [{"element": "<address>", "ref": "<uri>"}]}}}`. An address alone still removes every want on that element.** **Reason:** a want's key is its element with its ref, so naming both names one want, and the form is the one that `update` already uses to choose a want.
21. **A ref sits on the thing it is about: on the element in the base map, and on each record in a layer.** The founder voted for this on 2026-11-15, and the maintainer agrees. An element holds `refs`: the entry point of its functionality in the material, or a discrete reference that shows it. A record of a layer holds `ref`, one value, because one record is about one artifact; a want already works this way. **Reason:** a pointer is useful only beside the statement it supports. An element says what a part is, so its refs show where that part is found. A record says one thing about the part, such as a want, a memory or a block of specification, so its ref shows the one place that thing came from. A ref kept anywhere else would have to be matched to its statement by guessing. **What follows:** `ref` is allowed on a record of every layer and is always optional. A layer's definition does not have to declare it. The rule that a ref inside the project is a path from the project folder (section 3.6) covers it. In a layer's table it has its own column (decision 12). The link to another project's map stays a ref on an element (decision 7). **Not built** for records other than wants: a block of the specification layer does not take `ref` today.

    **The refs of an element are not an index.** The founder set this limit on 2026-11-15, and the maintainer agrees. `refs` holds an entry point or a discrete reference, and usually one. It does not list every file or every member that belongs to the element. **Reason:** the base map is for knowing what a thing is at a glance, and it must stay true while the material changes. A list of members is out of date as soon as a file is added, every reader of the element pays for it, and it tells the reader nothing about what the element is. One entry point is enough to go and look. Knowledge that needs more pointers is a layer, where each record carries its own `ref`. **Built:** the help for `refs`, the description in the schema and the refusal's message said "one uri for each artifact that has this address", which invited a list of every member. They now say an entry point or a discrete reference. The tool adds no limit on the number, because a limit would judge what an agent inferred (section 2, principle 4). **What to watch:** in a map of many artifacts, such as a folder of photographs, an element still holds one want for each artifact, each with its `ref`. That is the same growth in another place, and it is not settled by this decision.
22. **`collection` is removed as a root.** **Reason:** the roots are the four types of a project, the two that hold what is outside it, and `layer`. `collection` names no kind of functionality, and the procedure does not use it. A stored map that holds it still loads. **Built.**
23. **`name` may equal `technical_name`.** **Reason:** when a project has no name of its own for a part, the true answer is the standard term. Refusing it made four test agents invent names, which is worse than a repeated word. The build already allows it.
24. **The server's instruction at connection no longer tells the agent about `metaform gui`.** **Reason:** every agent pays for that text on every connection, and no accepted page exists for it to point to. The instruction returns when a page does.
25. **A concern that an agent finds during an intake is not written into the map.** **Reason:** the map holds what lasts (section 2, principle 3). A missing or broken part is a matter of the moment and belongs in a ticket. Until tickets exist, the agent reports its concerns in its answer.

26. **An agent that works in a project needs no glossary. The intake procedure is read only by an agent that performs an intake.** **Reason:** a name that needs a glossary costs twice. The agent must load the glossary, and until it has, a short form such as EF or DE invites it to guess a meaning, which spends reasoning and can go wrong. A field named `why` and a role named `Defining Element` say what they are when they are read. That is the reason the tool's fields have plain names and its roles are written in full. With such names, the glossary serves only the agent that performs the inference of an intake. **What changes:** the answer to `{"help": "intake"}` says today that a required section is read before any work on the map. It is to say that the procedure is read to perform an intake. The mark `(required)` on `core_concepts` is in the founder's file `sections.md`, and removing it is his to do. **One name fails this test:** the role `Cestui Que Use`. It is written in full, and it still means nothing without the glossary. Decision 30 gives it a plain name.
27. **The first read of a project is its shape, `{"map": {}}`. The why and the how of a want arrive at the element, with `goto`. One read returns the shape with every want: `{"map": {"wants": {}}}`.** **Reason:** the shape is what an agent needs to know what the project is and where its own work sits, and it is small. On the recorded test map of 113 addresses and 68 wants, the shape is 6,085 bytes. The same map with the why and how of every want is 28,559 bytes, which is more than the whole intake procedure at 26,056 bytes. An agent that works at one element needs the wants of that element and not of the other 112, and `goto` gives exactly those. An agent that plans across the whole project, or that reviews an intake, asks for all of them in one read. The form follows the rule that a read names a layer where it is written, with `{}` (section 5.4). `wants` is the default layer: it is always present, and its form is fixed.

28. **The intake procedure is written fresh. The present text is not preserved and not converted.** The founder set this direction on 2026-11-15, and the maintainer agrees. **Reason:** the present text was written for an earlier tool. It records with words that the tool no longer takes, such as `dependencies`, `purpose`, `ef` and `ifd`. It says that every element carries one uri, and it names roles by abbreviations. The decisions of this section change the tool further. A text that is repaired piece by piece toward a moving tool is never right at any moment, and each repair risks the meaning of a text that was tuned as a whole. Writing it once, for the tool as decided, costs less and gives a text that agrees with itself. **What follows:** the passages of section 7.6 need no repair, and the question whether the converted text is accepted falls away. The way the procedure is served stays: sections in a folder, one section for each request (section 7.3). The rule that a procedure's text is a formula applies to the new text from the day it is written (section 12). The files in `metaform/intake/procedure/` and `founder/intake_best.xml` remain in this archive as the record of what the build serves today.
29. **Maps are made fresh by intake. No map of an earlier build is converted.** **Reason:** a map is an inference, and it can be made again from the material. A conversion is code that must be written, tested and kept right for data that nobody intends to keep, and the old maps would still be in the old terms after it. **What follows:** the store needs no path from an earlier database. The changes that the build applies to an older database when it opens one (section 9.5) are to go, and the possible fault of section 9.6 goes with them, because it exists only in that path. A home made by an earlier build is refused, as a home that this store did not write is refused today. The data in the SQLite stores is not carried over.

30. **The role is written `Vested Beneficiary`. CQU stays the intake's term, and it is never a segment of an address.** The founder gave the wording for the definition on 2026-11-15, to be used as written in the new procedure: "The vested beneficiary of the project who isn't the user or developer working on the project." **Reason for the role's name:** a stored value must say what it is to an agent that has read no glossary (decision 26). `Cestui Que Use` does not, and `CQU` does not. The founder's own definition starts with the plain words for it, so the tool uses those words. This follows the rule that the tool speaks plain words and the procedure keeps its terms: the procedure reasons with CQU, and the tool answers `CQU` or `Cestui Que Use` with `Vested Beneficiary`, as it answers `DE` with `Defining Element`. **Reason for the address:** an address names a kind of functionality or a kind of party. CQU is a position that a party holds toward the project, and any kind of party can hold it. So a beneficiary is addressed by the kind of party it is, such as `downstream.studio.game`, and its role says that it is the vested beneficiary (R-3.15). The tool adds no check for this. The new procedure states it, and a check is added only if a fresh intake shows the mistake. **Built.**

31. **Reusable context is a resource with an address, and an instruction names the addresses it needs.** An instruction is short. It links to the context it relies on, with the words "Must read these URIs to perform the intake properly", or the same words for another task. The founder set this as the first step of the new process on 2026-11-15, and the maintainer agrees. **Reason:** the same context serves many tasks. If each instruction carried its own copy, an agent that performs two tasks would read the same text twice, and two copies would drift apart. When two instructions name the same address, the agent reads it once, because the address tells it that the content is the one it already has. The agent is the only party that knows what is in its context, so the agent is the right place to decide whether to read. This is also what a stateless server needs: it keeps no record of what it has sent to whom (decision 1). After an agent's context is reset, the agent reads the address again, which is correct, because it no longer has the content. **What it does not need:** a way to track versions. An address stays the same, and the text behind it changes only when someone edits it, which is rare. An agent that read the text earlier in the same context keeps working from what it read, and the next context reads the new text. That is the same as a person who read a document yesterday, and it needs no mechanism. This holds for context that instructs, such as the procedure and the rules of a layer. It holds for the base map as well. `map` is a command that returns the base map: the addresses and the wanting pairs. The base map does not change with every write, because most writes add knowledge in layers, and `map` returns no layer. It changes only when functionality is added or removed, and the agent that makes that change is the one working on that functionality, so it knows. An agent therefore reads the base map once in a context, as it reads any other context once. **What exists:** the server already serves each section of the procedure as a resource, `metaform://intake/<section>`. What is to be built is the short instruction that names those addresses, and the same pattern for the rules of a layer.
32. **The present procedure text and the founder's working copy are pulled out of the archive.** **Reason:** decision 28 makes them a text that is no longer the reference. A superseded text that sits beside the tool reads as current to the next person or agent who opens the folder, and that is how the earlier versions drifted. **What stays:** the folder `metaform/intake/procedure/` with `sections.md`, because the build reads it, and the code that serves sections. **Not done yet:** the eleven section files and `founder/intake_best.xml` are still in this archive. The build must first be tested with a folder that holds no section, and sections 7.2, 7.5 and 7.6 of this document, `README.md` and `PROJECT_CONTEXT.md` must then be brought in line. The founder's own file `rich/intake_best.xml` in the source repository is not touched.

33. **A prompt is a named Markdown file in a `prompts` folder. No prompt is kept in XML.** Each plugin, which this document calls a module, has its own `prompts` folder. The founder set this on 2026-11-15, and the maintainer agrees. **Reason:** one XML file that holds every prompt is edited by everyone in the same place, so every change risks every other prompt. XML also has rules of its own for quotation marks, `<` and `&`, and a prompt kept in an attribute or between tags is damaged when an editor follows or breaks those rules. The definition of AUE in the present text ends in the middle of a sentence, and it sits in an XML attribute. The tags are a third problem: they are either read by the model as part of the prompt or turned into words when the text is converted, and both change what the model infers. A Markdown file holds one prompt as plain text. Its file name is the prompt's name, the folder is the list of prompts, and a change shows as a change to one file. **What follows:**

    - A file in a plugin's `prompts` folder is served as a resource at `metaform://<plugin>/<name>`, which is the pattern the intake's sections already have (decision 31).
    - Text that instructs an agent leaves the code. The build holds four such texts in Rust today: the instruction sent at connection, the answer that says how to read the procedure, the writing guidance of the specification layer, and the rules of the block format. Each becomes a file in a `prompts` folder, so that it can be edited without a change to the code. The messages of refusals stay in the code, because they are built from the command that was refused.
    - **A variable is written `{{ name }}`**, in the pattern of Jinja, and the server replaces it by its value. **Reason for two braces:** a prompt for this tool is full of JSON, and JSON uses single braces. The build marks a variable with one brace today, as in `{layer}` and `{prompt}`, and only an exact match keeps that apart from the JSON around it.
    - The replacement is the project's own small code, and it does replacement only. A prompt that needs a condition or a loop is the case in which the full Jinja language is justified, and that is decided when the first such prompt exists.
    - A variable that has no value is left as it is written and is reported when the server is built. Nothing fails, because an edit to a prompt must never stop the build (section 7.4).

34. **No change is pushed into an agent's context.** The founder ruled out the broadcast of changes on 2026-11-15, and the maintainer agrees. **Reason:** an agent's context is the scarce thing that Metaform exists to protect (section 1.2). A pushed change is paid for whether or not it concerns the agent's work, and most changes concern someone else's. An agent that needs the present state of something reads it at the moment it needs it. What one agent wants the next to know is said on purpose, in a note at the place of the work (decision 35), and not sent to everyone. **What stays:** the page that shows the map to a person already follows the map as it changes, through the feed of section 8.7. A page is not an agent and has no context to waste, so that feed stays as it is built. **What the rule forbids:** telling an agent to subscribe, and any design that sends an agent a notice it did not ask for. The feed is offered on the MCP surface, so a client could in principle pass its notices into an agent's context. No client is known to do that. If one is seen to, the feed moves off the MCP surface; until then nothing that works is changed.
35. **A handoff overlay holds notes for the next agent that works on a functionality.** A note is free Markdown, left at an element. The founder described this on 2026-11-15 and preferred the name handoff to inbox, because it says what the note is for. It replaces the address inbox of R-6.23. **Reason:** knowledge passes best at the place where the work happens. The next agent arrives at the element, sees that a note waits, and reads it before it starts. Nobody has to know who that agent will be, nothing is broadcast, and nothing has to be searched for. **How it works:** `handoff` is an overlay that the server defines, as it defines the specification overlay. `goto` shows the count of notes at the element. An agent that has acted on a note removes it, and leaves its own when it stops. The server keeps no record of who has read a note, because it holds no state for an agent (decision 1).
36. **Agents have an inbox, and it belongs to the agents module, not to this tool.** The founder described the pattern on 2026-11-15: a message goes to an agent by its name; an agent that is busy is told between two operations that a message waits; and an agent can ask a question of a past agent by name, which wakes a small model that searches that agent's past context and answers. **Reason for the pattern:** a message that waits costs the receiver nothing until it chooses to read it, where an interruption costs it its train of thought. A question to a past context is a search with a clear target, which a small, cheap model does well, so the past agent need not be brought back whole. **Evidence the founder gave:** a website, synthetictaxonomy.com, has run on this pattern for almost a year without his intervention. The maintainer has not examined that site. **Why it is not in this tool:** an inbox needs an agent's name on each request, and the tool knows no agent (decision 4). The agents module owns names, and it is not designed yet (section 1.5).

37. **An agent may send the person a message to report. It may not send one to ask for a decision or to ask a question.** The founder set this on 2026-11-15 from experience with earlier systems. **Reason:** a way to ask becomes a way to stop. An agent that can hand a hard point to the person does so at the first doubt, and the reasoning it was there to do goes back to the one who has the least time for it. The work then waits on the person, and the agent has learned nothing about the point. An agent that cannot ask must work the point through: it weighs the choices, decides, and writes down the decision with its reasoning where the person and the next agent will see it. The person can then overrule a decision that is wrong, which costs far less than making every decision. **What follows:** a message to the person states what was done, what was decided and why. This belongs to the agents module with the rest of messaging (decision 36). The same rule governs how an agent works on this codebase (section 12).

38. **Agents can leave messages across the boundary of a project.** The founder asked for this on 2026-11-15, and the maintainer agrees. **Reason:** two projects that rely on each other meet at a boundary, and the agent that finds a problem at that boundary is often working on the other side of it. If it cannot tell the agents of the other project, the finding is lost or the person has to carry it. **How, with what is decided:** a note in the handoff overlay (decision 35) can be left at an element of another project, by a path that starts with that project's name (decision 2). The next agent that works on that element finds it there. A note carries the name of the project it came from, so the reader knows whom to answer. **Why this may come before other writes across projects:** decision 4 holds back writing into another project until the origin of a write and the earlier state of an element are kept. A handoff note needs neither protection. It adds one record and changes nothing that the other project wrote, and its origin is part of the note. **The other half:** a message to one agent by its name, in whatever project it works, belongs to the agents module (decision 36). For that, an agent's name must be unique in the home and not only in its project.

39. **The MCP server is reached over HTTP on the machine's own loopback address. The stdio forwarder and the socket go after it works.** The founder set this direction on 2026-11-15, and the maintainer agrees. **Reason:** a request over HTTP stands alone, which is what MCP without a session asks for. The build's path has the opposite shape: each agent starts a forwarder process, the forwarder opens a socket, and the first line on the socket ties the whole connection to one project (section 17.4). That tie is the state that decisions 1 and 2 remove. With HTTP, one server for a home answers every client at one address, the address of a request can name the project, and the same server can later answer a caller on another machine. **What it costs, and how it is met:** a socket in the home can be opened only by the home's owner. A port on the loopback address can be reached by every program on the machine, and by a web page that the person has open in a browser. So the server checks the `Host` and `Origin` of each request, as the web host already does (section 19), and it requires a token on each request. The token is a file in the home that only the owner can read. This keeps the reasoning of decision 4 whole: the home is still the boundary, and the permissions of the operating system still decide who can connect, because only a program that can read the home can read the token. The token sits in the client's settings and never in an agent's context. **How a request names its project:** the address ends with the project's name, as in `http://127.0.0.1:<port>/mcp/<project>`. That is part of every request, so it is not state, and it gives the short paths of decision 2 their project. **To check before building:** that the MCP library in use serves HTTP in the form the protocol defines. **Not built.**
40. **Agents on two machines talk to each other by the protocol for remote agents as it settles. The project writes its own only where that protocol does not fit.** The founder asked for this on 2026-11-15: he has often wanted agents on two hosts to communicate. **Reason:** talk between agents is the business of the agents module and of the protocol that connects an agent to its client, which this project calls ACP. That protocol is still changing in its form for a remote host. Following it gives agents that any compliant client can reach, and inventing a rival form first would have to be thrown away or kept alive beside it. Where it leaves a need open, such as a note left for whoever works on a functionality next, the project's own design fills the gap (decisions 35 and 38). **What it changes in decision 4:** talk across machines is the case that decision named in advance. There the caller cannot read the home, so every request carries a credential that the receiving side checks. **The state of that protocol:** its own documentation says that full support for remote agents is a work in progress, and that its authors are working with agent platforms on the needs of hosted and remote use. So nothing can be built on it today. **What can be built without it:** a note is data, and MCP is for data. Once the server answers over HTTP (decision 39), an agent on one machine can leave a handoff note at an element of a project that lives on another machine (decisions 35 and 38), if that machine's server accepts its token. That gives agents on two hosts a way to reach each other through the map, and it waits for no other protocol. It is slower than a direct message, because the note is read when the next agent arrives at the element. **Not designed yet;** a direct message between agents belongs to the agents module.

### 13.4 What stays open, and why it is not the maintainer's

The wording of the intake procedure is the founder's, and the rule of section 12 forbids anyone else to settle it. These stay with him:

- The new text of the procedure (decision 28), with its part for photographs.
- Whether the new procedure has a glossary at all, and which section of it, if any, is marked `(required)` (decision 26).

### 13.5 The order of the build

0. The old procedure text out of the archive (decision 32). Then the `prompts` folder of the intake, with named Markdown files and `{{ name }}` variables (decision 33), and in it the short instruction that names the resources an intake must read (decision 31).
1. The durable name of a project, and the registry keyed by it (decision 3). Everything across projects depends on it.
2. No state for a connection (decision 1), and `metaform call` off the command line (decision 15).
3. Paths with a project's name, for reading (decision 2), and the ref to another map (decision 7).
4. The structure of a layer in its definition (decisions 9 to 11), and then the table for each layer (decision 12).
5. The small changes: decisions 18, 20, 22, 24, 26, 27, 30 and 34, the handoff overlay (decision 35), and the wording for `refs` in the help and the schema (decision 21).
6. The origin of a write and the earlier state of an element. Writing to another project's map comes after this.
7. The MCP server over HTTP on the loopback address, with its token (decision 39); it comes with step 1, because both change how a client names its project.
7a. The removal of the SQLite store (decision 5), and of the path from earlier databases (decision 29).
8. The new intake procedure (decision 28), written by the founder for the tool as decided, and then a fresh intake of each project.

## 14. Where the files in this archive disagree

This document governs in each case. The files are copied unchanged, so the disagreements remain in them.

| File | What it says | What is so |
|---|---|---|
| `metaform/rust/README.md` | The want relationship is named `WANTS`. | It is `DEPENDS_ON`. |
| `metaform/rust/README.md` | The Node and Python forms repeat the Rust form's answers. | They are not in this archive and use earlier terms. |
| `metaform/rust/README.md` | The forwarder never writes files. | It creates the home folder and `server.log`. |
| `metaform/tool-help.json`, `metaform/mcp-tools.proposed.json` | An `update` selects a want by `ref` or `why`. | The code selects by `element` and `ref`. |
| `metaform/mcp-tools.proposed.json` | `technical_name` must not match `name`. | The code does not check it. |
| `metaform/tool-help.json` | `goto` returns the layers that hold records. | It also lists each defined layer with a count of 0 where records are allowed. |
| `metaform/tool-examples.json` | A refusal has no `code`. | A refusal has `code`. |
| `metaform/metaform.schema.json`, `$comment` | It is dated 2026-10-31 and speaks of provider addresses. | The schema holds the fields of 2026-11-12. |
| `metaform/intake/procedure/` | The passages of section 7.6. | Section 7.6. |
| `metaform/metaform-canonical.json` | A map with elements and wants of an earlier system. Its addresses beneath `downstream` hold the segment `cqu`. | It is test data and describes nothing in this archive. CQU is never a segment of an address (section 13, decision 30). |
| The `instruction` of the specification layer, and the word list of `export --check` | They prefer start, use, adjust, perform and end over other words. | `guidance/TASTE.md` no longer has that list (section 16.10). |
| `metaform/tool-examples.json`, `goto_example` | The first result has `"layers": {}` and no `instructions`. | In a project's map the server defines the specification layer, so an element with its three intake fields lists `specification` and gets `instructions`. |
| The usage text of `metaform` | It does not list `projects`. | `projects` is a command. |
| `metaform/intake-example.json`, and the example of section 4.2 | The project's root holds a field `project`. | R-3.10 says that no element has a `project` field. The contract checks the field, and no code reads it. |
| Comments in the Rust code | They cite `SPEC.md`, `docs/designs/` and other files of the source repository. | Those files are not in this archive. |

## 15. Sources

| Section | Source in the repository at commit `1798c6e` |
|---|---|
| 1, 2 | `metaform/SPEC.md` sections 1, 2 and 5.5; `metaform/README.md`; `metaform/PROJECT_SPECIFICATION.md` section 5 |
| 3 | `metaform/SPEC.md`, "Changes of 2026-11-15", "Changes of 2026-11-12" and section 3; `metaform/metaform.schema.json`; the code of `metaform-core` |
| 4 | `metaform/metaform.schema.json`; the founder's example of 2026-11-15; `metaform/SPEC.md` R-4.2, R-4.11, R-4.12, R-5.34; the code of `metaform-core` |
| 5 | `metaform/SPEC.md` section 6 and R-3.22; the founder's statements of 2026-11-15; the code of `metaform-core` |
| 6 | The code of `metaform-core`; the three tool files; `metaform/SPEC.md` section 5 |
| 7 | `metaform/intake/procedure/`; `metaform/SPEC.md`, "Changes of 2026-11-12"; `dev/HANDOFF.md`; `CLAUDE.md` |
| 8, 9 | The code of `metaform-store`, `metaform-server` and `metaform-web`; `metaform/SPEC.md` sections 4 and 8; the founder's statement of 2026-11-15 on stateless MCP; the MCP proposal SEP-2567 as read on 2026-11-15 |
| 10 | The code of `metaform-core`; `metaform/SPEC.md` R-1.2, R-6.28 |
| 11 | `metaform/SPEC.md`; `metaform/PROJECT_SPECIFICATION.md` section 7; `metaform/rust/README.md` |
| 12 | `CLAUDE.md`; `dev/HANDOFF.md` |
| 13 | `metaform/SPEC.md` section 10; `dev/HANDOFF.md`; `dev/chained_map_storage.md` |
| 16 | The code of `metaform-core`; `metaform/mcp-tools.proposed.json`; `metaform/tool-help.json` |
| 17 | The code of `metaform-server` |
| 18 | The code of `metaform-store` |
| 19 | The code of `metaform-web` |

## 16. Reference: the tool, exactly

Sections 16 to 19 state the exact behaviour of the Rust form, taken from the code by reading every source file. A reader needs them to predict an answer of the tool word for word. Everything in them is **Built**. In a message or a remediation, a name in braces, such as `{address}`, stands for the value at that place. A name in angle brackets, such as `<why>`, is written in the answer as it stands: it marks what the agent must supply.

### 16.1 The order of the checks on one command

The first check that fails gives the refusal, and nothing is stored.

1. **The specification layer's definition.** At the first command on a project's main map in a run of the server, the server writes the definition at `layer.document.specification` if the stored one differs.
2. **Refs.** For a project's map and for `add` and `update` only: a ref inside the project folder must be relative (section 3.6).
3. **The form of the command** (section 16.2). The check reads only the command and never the map.
4. **The contract.** The command is checked against `metaform/mcp-tools.proposed.json`. The form check is stricter, so this check catches only what the form check does not yet hold. Its message is `the command {detail}`, with no remediation.
5. **Names** (section 16.5).
6. **An object where a layer's list is stored** (`add` and `update`).
7. **The write is applied to a copy of the map** (section 16.3).
8. **The definition of the specification layer** may not be changed or deleted.
9. **A new layer definition** may not share its last segment with another.
10. **Each layer value that the write changed**, for each layer the map defines: it is a list, records are allowed at the address, and the rules of `markdown_blocks` hold (section 16.9).
11. **Each element the write touched**, in address order, with these checks in this order:
    1. a changed list belongs to a layer;
    2. `technical_name`;
    3. `role`;
    4. a system layer's value is a list;
    5. no name is both a field and an element beneath;
    6. the element matches `metaform/metaform.schema.json`.

A value that the write did not change is not checked again, so older data never blocks an unrelated write. `technical_name` is the exception: it is checked on every touched element that holds it.

### 16.2 The form of a command

Every refusal in this section has the code `FIELD_MISMATCH`, unless the table says otherwise. Within one element, fields are checked in the order the command gives them. An object value is an element beneath, and its fields are checked before the next field of the element above.

**The command**

| Condition | Message | Remediation |
|---|---|---|
| Not an object with exactly one entry | `a command has one entry: add, update, delete, orphaned, goto, map, help, an address to read, or a path that starts with a period for a raw dump` | none |
| `map` or `orphaned` with a value that is not `{}` | `{key} takes {}` | `{"{key}": {}}` |
| `help` with a value that is not `{}` or text that is not empty | `help takes {}, the name of a command, the name of a definition a schema refers to, or intake` | `{"help": {}}` |
| `goto` with text that is not `.` or an address | the address message below | none |
| `goto` with a value that is not text, or with empty text | `goto takes one address, such as {"goto": "code.engine.game"}` | `{"goto": "<address>"}` |
| `add`, `update` or `delete` whose value is not an object with exactly one entry | `{key} takes one address; send one command for each element` | the first entry alone, if that command is accepted |
| An address that is not valid | `'{text}' is not an address: segments are joined by periods, with no spaces, '$', '[' or ']'` | none |
| `add` or `update` whose value at the address is not an object | `{key} takes an object of fields at '{address}'` | none |
| `add` or `update` with no field | `{key} needs at least one field at '{address}'` | none |
| A raw dump with a value that is not `{}` | `a raw dump takes {}` | `{"{path}": {}}` |
| A read whose value is not an object, or a layer whose value is not `{}` | `a read names each layer with {} as its value, such as {"{address}": {"wants": {}}}` | the read with `{}` for each named layer |
| A read with a layer name that is not one segment | `'{name}' is not a layer name: a layer name is one segment, with no periods, spaces, '$', '[' or ']'` | none |

`add`, `update` and `goto` accept the root address `.`. `delete` and an addressed read do not: `{".": {}}` is a raw dump.

**The fields of an element**

| Condition | Message | Remediation |
|---|---|---|
| A field name that is not one segment | `'{key}' at '{address}' is not a field name: a name is one segment, with no periods, spaces, '$', '[' or ']'` | none |
| `dependencies` | `dependencies at '{address}' is not a field; wants holds what the procedure calls dependency records` | the command with the records under `wants`, in the tool's words |
| `uri` | `uri at '{address}' is not a field; refs holds a list that holds the entry point of this functionality, or a discrete reference to it` | the command with `refs` as a list of that one uri |
| `refs` that is not a list of at least one text item | `refs at '{address}' must be a list that holds the entry point of this functionality, or a discrete reference to it` | the command with `[<the text given>]`, or `["<uri>"]` |
| `technical_name`, `name`, `role`, `status` or `project` with a value that is not text, or with blank text | `{key} at '{address}' must be text that is not blank` | the command with `<{key}>` there; for `role`, the list of the eight roles in angle brackets |
| `status` with one of the six earlier spellings | `status at '{address}' cannot be "{text}"; use un_built for functionality that is not built` | the command with `un_built` |
| `element`, `why`, `how`, `direction`, `pe`, `provider`, `op`, `purpose`, `ef` or `ifd` as a plain value on an element | `{key} at '{address}' is not a field of an element; element, why, how and direction belong in a want` | an `update` with one want built from the parts given, with `<address>`, `<why>`, `<how>` and `<direction>` for the rest |
| `providers` with a value that is not an object | `providers at '{address}' can hold only elements beneath it; wants holds what an element wants` | none |

Rules that give no refusal:

- A value of `null` is accepted for any field of the element that `update` names, except `wants`, `uri` and `dependencies`. In `add`, and in an element beneath, `null` is accepted only for a field that the tables do not name.
- `refs: null` is accepted only at the element that `update` names.
- A list is accepted under any field name that the tables do not name. Check 11 then requires that the name is a layer.
- The same word may be a field or an element beneath: `name`, `role`, `status`, `technical_name`, `project`, `why`, `how`, `direction` and `providers` may each hold an object, which is an element beneath with that name.
- White space is the set of characters with the Unicode property White_Space.

**Wants**

`{place}` is `the want '{element}' at '{holder}'`.

| Condition | Code | Message | Remediation |
|---|---|---|---|
| `wants` is an object keyed by address, each value holding `why`, `how` or `direction` | | `wants at '{holder}' must be a list of want records; each record names the element it wants in element` | the same records as a list |
| `wants` is anything else that is not a list of at least one record | | `wants at '{holder}' must be a list of want records, each with element, why, how and direction` | one record of placeholders |
| A record that is not an object | | `a want at '{holder}' must be a record with element, why, how and direction` | a record of placeholders |
| A record that uses `pe`, `provider`, `op`, `purpose`, `ef` or `ifd` | | `a want at '{holder}' takes element, why, how and direction; the command used {words}` | the record in the tool's words |
| `element` is `.` | | `the root cannot be wanted` | none |
| `element` is missing, empty or not text | | `a want at '{holder}' must name the element it wants in element` | `<address>` in `element` |
| The record holds `refs` or `uri` | | `{place} is about one artifact; give its uri in ref, and write one want for each artifact` | one record for each uri, each with its `ref` |
| The record holds any other name | | `{place} does not take: {names}` | the command without those names |
| `ref` is not text, or is blank | | `ref at {place} must be the uri of the one artifact the want is about` | `<uri>` |
| `direction` is not `send`, `receive` or `both` | | `direction at {place} must be send, receive or both` | `send` for `sends`, `receive` for `receives`, else `<send, receive or both>` |
| `why` or `how` is not text, or is blank | | `{field} at {place} must be text that is not blank` | `<{field}>` |
| A record at the element that `update` names, with none of `why`, `how` and `direction` | | `{place} has no fields; give why, how or direction` | a record of placeholders for that element |
| Any other record that lacks `why`, `how` or `direction` | `WANT_INCOMPLETE` | `'{holder}' wants '{element}': the want has no {missing}` | the command with a placeholder for each missing field |

A repeated `element` in one list is accepted: each record is one want.

**`delete`**

| Condition | Message | Remediation |
|---|---|---|
| The address is `.` | `the root cannot be deleted` | none |
| The value is not `{}` and not `{"wants": [...]}` alone | `delete takes {} to delete the element, or {"wants": ["<address>"]} to remove wants` | none |
| `wants` is one address as text | the same message | the command with that address in a list |
| `wants` is not a list of at least one text item | the same message | the command with `["<address>"]` |
| An item is `.` | `the root cannot be wanted` | none |
| An item appears twice | `delete names the want '{text}' more than once` | the command with each item once |

### 16.3 What a write does

**`add`**

1. The value is split into one element for each address. Each object value is an element beneath, at any depth. `wants` that is a list of records is that element's wants.
2. Each address is created if it is missing, with every missing branch above it. A created top-level branch must be a root (section 3.2).
3. Each field is written. `null` removes the field. A list given where a list is stored is appended, with no check for repeats. Any other value replaces what is stored.
4. Each want is written (below), after all fields of all elements.

**`update`**

1. The address is created if it is missing, with its branches.
2. Each field is written. A `wants` list is written as wants. `null` removes the field. An object updates the element beneath of that name. Any other value, a list included, replaces what is stored.

**A want.** The stored want with the same `element` and the same `ref` is the want to change. A record with no `ref` matches the stored want with no `ref`. The fields given are merged into it. If none matches, the record is a new want. After the merge the want must hold `why`, `how` and `direction` that are not blank. If it does not, the refusal is `WANT_INCOMPLETE`, with an `update` that holds placeholders for the missing fields. The wanted element is created if it is missing.

**`delete`**

1. An address that is not in the map: nothing changes, and the answer is `{"status": "ok"}`.
2. With `wants`: every want on each named element is removed, whatever its `ref`. A named element that the holder does not want is ignored. Each element that was wanted is then pruned.
3. With `{}`: if another element wants the address, the refusal is `DEPENDENCY_LOCK`. Its message is `cannot delete '{address}': '{holder}' still wants it. Remove that want first.` With several holders it is `cannot delete '{address}': these elements still want it: 'a', 'b'. Remove their wants first.` The remediation removes the want of the first holder only.
4. If elements sit beneath the address, the refusal is `ELEMENTS_BENEATH`, with the message `cannot delete, '{address}', has elements beneath it`. The remediation deletes the deepest element beneath.
5. Otherwise the element is removed with its own wants. Its parent and each element it wanted are then pruned.

**Pruning** removes an element that has no fields, no wants, nothing beneath it and nothing that wants it. It then does the same for each branch above, and it never removes the root. An element's own want on itself does not lock its deletion.

**After the write.** Each touched element's fields and wants are put in the fixed order of section 16.6. The answer is `{"status": "ok"}`.

### 16.4 The refusals of checks 6 to 11

| Check | Code | Message | Remediation |
|---|---|---|---|
| An object written where the element holds a layer's list | `FIELD_MISMATCH` | `'{address}': {layer}: a layer's value must be a list of records` | the same write with the object as a list of one |
| A system layer's value that is not a list | `FIELD_MISMATCH` | the same message | an `update` with the value as a list of one |
| The specification layer's definition is changed or deleted | `LAYER_DEFINITION_LOCKED` | `'layer.document.specification' is defined by the server; agents write its records at receiving elements, not its definition` | none |
| A second definition with the same last segment | `LAYER_NAME_COLLISION` | `'{address}' would define the layer {layer}, which '{existing}' already defines; a layer's last segment is its field name and must be unique` | `{"update": {"{address}": {"instruction": null}}}` |
| Records at the root with no Defining Element in the project | `ELEMENT_NOT_IN_SKELETON` | `'.': {layer} records at the root need a Defining Element in the map first` | `{"update": {"<address of a Defining Element>": {"role": "Defining Element"}}}` |
| Records at an address beneath `layer` | `ELEMENT_NOT_IN_SKELETON` | `'{address}': {layer} records do not go on layer definitions` | none |
| Records at an element without `technical_name`, `name` and `role` | `ELEMENT_NOT_IN_SKELETON` | `'{address}': {layer} records need an element with technical_name, name and role; intake has not placed it in the skeleton yet` | an `update` with a placeholder for each missing field |
| A changed list whose name is not `refs`, a system layer or a defined layer | `LAYER_NOT_REGISTERED` | `'{name}' at '{address}' is not a layer. A list can be written only to a layer defined beneath the layer root, such as layer.document.specification, or to skills, memory or sources.` | `{"map": {}}` |
| `technical_name` at the root | `TECHNICAL_NAME_ALIGNMENT_FAILURE` | `'.': the root is the project and has no technical_name` | `{"update": {".": {"technical_name": null}}}` |
| `technical_name` that is not a leading run of the reversed address | `TECHNICAL_NAME_ALIGNMENT_FAILURE` | `'{address}': technical_name "{value}" is not the leading words of "{reversed words}"` | the field set to the reversed words without the root's words |
| `role` set or changed to a value that is not a role | `ROLE_TAXONOMY_FAILURE` | `'{address}': role "{role}" is not one of: Artifact Type, Defining Element, Supporting Element, Coupled Element, Notable Element, Vested Beneficiary, Upstream Dependency, Downstream Dependant` | the field set to the role's name for an abbreviation, else to the list of roles in angle brackets |
| A name that is a field and an element beneath | `FIELD_ELEMENT_COLLISION` | `'{holder}': '{key}' cannot be both a field and an element beneath it` | `{"update": {"{holder}": {"{key}": null}}}` |
| The element does not match the schema | `FIELD_MISMATCH` | `{field} at '{address}' {detail}`, `want {n} at '{address}' {detail}`, `{field} at want {n} at '{address}' {detail}`, or `'{address}' {detail}`. `{n}` is the want's position, counted from 0. | none |
| A created element outside the roots | `ROOT_SCOPE_NOT_ALLOWED` | `'{address}': the root scope '{scope}' is not one of: code, document, media, data, upstream, downstream, layer` | none |
| A ref inside the project that is absolute | `FIELD_MISMATCH` | `a ref inside the project is its path from the project folder, so the map holds when the folder moves: '{written}' is '{stored}'` | the command with each such ref relative; the folder itself is `.` |

For `technical_name` and `role`, the remediation is an `update` of the one field when the element existed before the write. Otherwise it is an `add` of the whole element with the field corrected, because the refused write stored nothing.

The reversed words of an address are its segments in reverse order, each split at `_`. The words of `technical_name` are split at white space and compared exactly. For `code.masher.widget`, the accepted values are `widget`, `widget masher` and `widget masher code`.

A `{detail}` from a schema is one of: `must be one of: ...`, `has no {property}`, `holds a value of the wrong type`, `does not take: ...`, `must be text that is not blank`, `must hold at least {n} entry`, `must hold at most {n} entries`, `must hold at least {n} item`, `must not repeat an item`, `cannot be {value}`, `holds the name {name}, which is not valid: no periods, spaces, '$', '[' or ']'`, or `breaks the schema's '{keyword}' rule`.

### 16.5 Names

A name is an address segment or a field name. A name is refused when it does not survive the conversion to camelCase and back.

| Reason given | Example |
|---|---|
| `a name in uppercase is refused, not lowercased` | `Code` |
| `repeated underscores do not survive storage` | `dead__letter` |
| `a trailing underscore does not survive storage` | `queue_` |
| `an underscore before a digit or symbol does not survive storage` | `queue_2` |

- The conversion to camelCase drops each `_` and writes the next character in uppercase. The conversion back writes `_` before each uppercase character and lowers it.
- The check covers the address of `add`, `update`, `delete`, `goto`, a read and a raw dump. It covers every field name at every depth. It covers the `element` and the field names of each want, and each item of `wants` in `delete`.
- It does not cover a layer name in a read, a `help` name, or a key inside a layer's record.
- The code is `NAME_ROUND_TRIP_FAILURE`. The message joins every problem with `; `, each as `'{address}': '{segment}': {reason}`.
- The remediation is the command with each name corrected: lowercased, with single underscores, and with a digit joined to the word before it. `code.queue_2` becomes `code.queue2`.

### 16.6 The order of fields and wants

- The fields of an element come back in this order: `technical_name`, `name`, `role`, `refs`, `status`, then every other field by name.
- The fields of a want come back in this order: `element`, `why`, `how`, `direction`, `ref`.
- The wants of an element are ordered by the wanted element's address, then by `ref`.

**Reason:** one order makes an element read the same after every reload, whatever order its fields were written in.

### 16.7 What each read returns

**An addressed read**, `{"<address>": {}}`, returns `{"<address>": {fields}}`. The fields are every field that is not a list, with `refs`. For each layer named in the read:

- `wants` adds the list of wants, which is `[]` when the element has none.
- A name under which the element holds a list adds that list.
- A name that the map defines as a layer adds `[]`, when records are allowed at the address.
- Any other name is left out.

An address that is not in the map gives `NOT_FOUND`, with the message `'{address}' does not exist` and the remediation `{"map": {}}`.

**A raw dump**, `{".<path>": {}}`, returns `{".<path>": <nested value>}`. The nested value holds each element's fields, and `wants` when it has some, nested by segment. A path whose last segment is a field returns that field's value. A path that holds nothing gives `NOT_FOUND`.

**`map`** returns `{"addresses": [...], "edges": [[holder, wanted], ...], "defining": [...]}`. `addresses` is every address except `.`, in address order.

**`orphaned`** returns `{"<address>": {fields}, ...}`, with the fields of an addressed read.

**`goto`** returns the sheet of section 6.6. At a layer's definition, `element` leaves out `instruction`, because `guidance` holds it. Each entry of `instructions` is `The rules for writing {layer} are at {definition address}. Read them only when you write {layer}.`

**The server holds nothing back.** Every `goto` returns the whole sheet, to every client. The server keeps no record of what a connection has received.

### 16.8 What `help` returns

The server looks up a name in this order: `intake`, `intake/<section>`, a command name, a definition name.

| Command | Answer |
|---|---|
| `{"help": {}}` | `{"help": {"type": "object", "properties": {"help": {"enum": ["add", "update", "delete", "orphaned", "goto", "map", "addressed read", "raw dump", "help", "intake"]}}, "required": ["help"]}}` |
| `{"help": "<command name>"}` | `{"help": {"<name>": <that entry of metaform/tool-help.json>}}` |
| `{"help": "intake"}` | `{"help": {"intake": {"sections": [...], "required": [...], "when": {...}, "read": "<text>"}}}` |
| `{"help": "intake/<section>"}` | `{"help": {"intake/<section>": "<the section's text>"}}` |
| `{"help": "<definition>"}` | `{"help": {"<name>": <that definition of the contract>}}` |

- `when` maps a section's name to the condition that `sections.md` gives for it. It is empty today.
- The `read` text is: `These sections are the intake procedure. Read them to perform an intake: every section in this order, except a section listed under when, which you read only if its condition holds. Read one section with {"help": "intake/<section>"}. For other work on the map you need none of them.`
- The definition names are `NamespaceValue`, `NamespaceNode`, `ComposedElementLayer`, `Wants`, `WantRecord`, `Empty`, `LayerRead`, `AddFields`, `WantUpdate`, `WantsUpdate`, `UpdateFields`, `DeleteWants` and `RelationshipWord`. The answer to `{"help": {}}` does not list them.
- An unknown section gives `FIELD_MISMATCH`, with the message `the intake procedure has no section '{name}'; {"help": "intake"} lists its sections` and the remediation `{"help": "intake"}`.
- Any other unknown name gives `FIELD_MISMATCH`, with the `help` message of section 16.2 and the remediation `{"help": {}}`.

**How `sections.md` is read.** A line that starts with `- ` names one section. If the entry holds `(` and ends with `)`, the name is the text before the first `(`, and the note is the text between. A note of `required` marks the section required. Any other note is the section's condition, passed on as written. Each section's text is trimmed when it is served.

### 16.9 Layers, exactly

**The definition that the server writes** at `layer.document.specification` holds these fields:

| Field | Value |
|---|---|
| `technical_name` | `specification document layer` |
| `name` | `Specification` |
| `role` | `Supporting Element` |
| `description` | `Prose that the skeleton leaves out on purpose: what each element does, how it behaves and why, as blocks with Markdown heading levels.` |
| `template` | `{title}: {text}` |
| `format` | `markdown_blocks` |
| `instruction` | The text below. |

```text
Write each block in TASTE: Technically Accurate, Simple, Transparent English. A block adds what the map leaves out on purpose; do not repeat what the element's fields and wants already say.
- Start with what the element does or holds. Then give the detail that explains it.
- Name the element, field or command instead of starting with "it", "this" or "they". A block is often read alone.
- Use the project's terms and exact identifiers. Use one term for one thing. Put identifiers in backticks.
- Write one claim per sentence. Aim for 25 words or fewer per sentence and six sentences or fewer per paragraph. Never cut a condition, an exception or a reason to meet a length target.
- Use lowercase must, should, may, can and might with their TASTE meanings. Do not write SHALL or capitalized MUST.
- Say whether something is built, proposed or planned. Do not describe planned behavior as if it exists.
- Replace words such as simple, robust or fast with the behavior or a measurement.
- Define an abbreviation at its first use. Keep noun clusters to three nouns.
- Leave out openings such as "This section describes", repeated points, analogies and promotion.
- Prefer start, use, adjust, perform and end over kick off/launch/begin, utilize/leverage, modify/change/alter, execute/run and terminate/stop/abort, when the meaning stays the same.
- Do not put Markdown heading lines in the text. Set the block's level and title instead.
```

**The `guidance` of a `markdown_blocks` layer** is the text below, with the layer's name in place of `{layer}`, then a line break, then the definition's `instruction`. For a layer with no `format`, the `guidance` is the `instruction` alone.

```text
The {layer} field is a list of blocks: {"level": 1-4, "title": "...", "text": "..."}. A titled block may also carry "code", a key that other text can cite; it is unique in the layer across the map, ignoring case. The first block may be {"text": "..."} alone, as an intro under the element's heading. The first titled block is level 1, and each level is at most one more than the level before it. update replaces every block at the address and is safe to repeat; add appends blocks; if an answer is lost, a retried add appends them twice. Read them with {"<address>": {"{layer}": {}}}. The root's blocks are in the raw dump {".": {}}, because a key that starts with a period is a raw dump. Blocks are accepted at an element that has technical_name, name and role, and at . once the map has a Defining Element.
```

**Which definition wins.** If stored data holds two definitions with the same last segment, the one whose address sorts first defines the layer.

**An empty list.** For a layer that the map defines, writing `[]` removes the field from the element. For `skills`, `memory`, `sources` and `refs`, an empty list is stored as an empty list.

**The rules of `markdown_blocks`.** Each refusal is `FIELD_MISMATCH` with the message `'{address}': {layer}: {reason}`, unless the table gives another code. The remediation is an example `update` with an introduction block and two titled blocks of placeholders.

| Condition | Reason, or message |
|---|---|
| The value is not a list | `must be a list of blocks` |
| A block is not an object | `block {n} must be an object` |
| A block holds a name other than `level`, `title`, `text` and `code` | `block {n} does not take: {key}` |
| `text` is not text | `block {n}: text must be a string` |
| `title` is not text | `block {n}: title must be a string` |
| `level` is not a whole number | `block {n}: level must be a whole number from 1 to 4` |
| `code` is not valid | `block {n}: code must be one token of 1 to 32 letters, digits, '.', '_' or '-', starting with a letter and ending with a letter or digit, such as R-1.2` |
| `code` on a block with no title | `block {n}: only a block with a level and title can have a code` |
| A block after the first with no `level` and no `title` | `block {n} has no level and title; only the first block may be an intro` |
| A first block with no `level`, no `title` and no text | `block 1 is an intro with no text` |
| A title that is empty or holds a line break | `block {n}: title must be one line of text` |
| A title that starts with a backtick | `block {n}: title must not start with a backtick; the export writes the block's code there` |
| A title that starts with `#` | `block {n}: title must not start with '#'; the level sets the heading` |
| A title that ends with text in backticks inside parentheses, whether or not the text is an address | `block {n}: title must not end with an address in backticks inside parentheses; the export uses that form for element headings` |
| `level` without `title`, or `title` without `level` | `block {n} needs both level and title, or neither for an intro` |
| A level outside 1 to 4 | `HEADING_LEVEL_INVALID`: `'{address}': {layer} block {n} ("{title}"): level {level} is outside 1 to 4`. A level above 255 is reported as 255. |
| A first titled block that is not level 1 | `HEADING_LEVEL_INVALID`: `... level {level}; the first titled block is level 1` |
| A level more than one above the level before it | `HEADING_LEVEL_INVALID`: `... level {level} follows level {previous}; a level is at most one more than the level before it` |
| A text line that is a Markdown heading | `HEADING_IN_TEXT`: `'{address}': {layer} block {n}: text line {line} is a Markdown heading line; set a block's level and title instead` |
| A text line of `=` or `-` under a paragraph line | `HEADING_IN_TEXT`: `... text line {line} is a line of = or - under a paragraph line, which Markdown reads as a heading; set a block's level and title instead` |
| A code that another block of the layer holds, anywhere in the map, ignoring case | `CODE_NOT_UNIQUE`: `'{address}': {layer} block {n} has code {code}, which '{holder}' block {m} already holds; a code is unique in the {layer} layer, ignoring case` |

- The remediation of `HEADING_LEVEL_INVALID` is the same blocks with each level brought into the rules.
- The remediation of `HEADING_IN_TEXT` is the same blocks with each heading line moved into a block of its own, one level deeper.
- The remediation of `CODE_NOT_UNIQUE` is the same blocks with that one code removed.
- A heading line is found only outside fenced code and with at most three leading spaces. A line such as `#tag` is not a heading.
- Line ends become line feeds, and `title` and `text` are trimmed. The stored blocks are the normalized ones, with the keys in the order `level`, `code`, `title`, `text`.

### 16.10 The export and the import, exactly

**The document that `export` writes.** Parts are separated by one empty line, and the document ends with a line break.

```text
# <project>

<the root's introduction block>

## <a root block of level 1>

## <name> (`<address>`)

Role: <role>. Technical name: <technical name>. Status: <status>.

- `<address>` (<name>) requires `<other>` (<other name>) in order to <why>, which <how>.

<the element's introduction block>

### <an element's block of level 1>
```

- `<project>` is the last segment of the project folder's path, or the name of a standalone map.
- The root has a section only when it holds blocks. An element has a section when it has `technical_name`, `name` and `role`, or when it still holds blocks. Elements beneath `layer` have none.
- Elements are ordered by root, in the order of section 3.2. Within a root, each element comes directly before the elements beneath it.
- The name in a heading is `name`, else `technical_name`, else the address.
- The role line holds only the parts that exist.
- In a want line, `why` and `how` lose a final full stop. A first capital letter is lowered when the next letter is lowercase.
- A block's heading has one `#` more than its level at the root, and two more at an element. A block's code is written in backticks before its title.
- A stored value that breaks the block rules is shown as written in a JSON code block. Such a document is not accepted by `import`.
- An element that holds blocks and lacks `technical_name`, `name` or `role` is exported, and `import` refuses its section. So a map with such an element does not make the round trip.

**What `import` refuses.** Each refusal names a line of the document.

| Condition | Reason |
|---|---|
| The first line that is not empty is not `# <project>` | `the document must start with the project heading '# <project>'` |
| An element heading for an address beneath `layer` | `'{address}' lists a layer of the map; the specification document does not hold it` |
| An element heading for an address not in the map | `'{address}' is not an element of the map; add it through intake first` |
| Two sections for one address | `'{address}' has more than one section; keep one` |
| An element heading that differs from the one `export` writes | `the heading for '{address}' must read '{expected}'; names change through intake, not through the prose` |
| A code fence that is not closed | `a code fence opens here and is not closed` |
| No section for an element that holds blocks | `'{address}' holds specification text, but the document has no section for it. To remove the text, keep the heading '{heading}' and delete the text under it.` |
| A role line or a want line that differs from the map | `'{address}' must show its skeleton facts as the map holds them: expected '{fact}', found '{line}'. The skeleton changes through intake, not through the prose` |
| A role line or a want line is missing | `'{address}' is missing the skeleton fact '{fact}'` |
| A heading with too few or too many `#` | `a heading under '{address}' must use {allowed}`. For a heading with two `#`, the reason adds ``; an element heading ends with its address, such as (`code.api`)``. |
| Blocks that break a rule of section 16.9 | that rule's message |
| A code used twice in the document | `code '{code}' is already used at line {line}, under '{address}'; each code must be unique across the specification` |

`import` writes one `update` for each section whose blocks differ from the map. All of them are stored in one transaction, or none is.

**The reports of `export --check`.** A report is one line: `{address} block {n} ("{title}"): {CODE}: {message}`. The last line is the summary: `check: no reports.`, or `check: {n} reports in {m} blocks ({CODE} {count}, ...). Reports are TASTE targets, not errors.` A count of one is written `1 report` or `1 block`. The check reads block text. It skips inline code, fenced code, web addresses and table rows.

| Code | Reported when |
|---|---|
| `CAPITAL_MODAL` | The text or the title holds `MUST`, `SHOULD`, `MAY` or `REQUIRED`. |
| `SHALL` | The text or the title holds "shall" in any case. |
| `SENTENCE_LENGTH` | A sentence has more than 25 words. |
| `PARAGRAPH_LENGTH` | A paragraph has more than six sentences. A list is one paragraph. |
| `BLACKLIST` | The text or the title holds a form of launch, initiate, begin, utilize, leverage, modify, tweak, change, alter, execute, run, fulfill, terminate, kill, stop, abort or "kick off". |
| `VAGUE_WORD` | The text holds simple, simply, easy, easily, robust, clean, seamless, seamlessly, powerful, intuitive, efficient, fast, flexible, elegant or best. |
| `OPENING` | A paragraph starts with "This section", "This block", "In this section", "Note that", "It is important", "It should be noted", "As mentioned" or "Basically". |
| `START_PRONOUN` | The block's text starts with "It" or "They", or with "This", "That", "These" or "Those" followed by a verb such as "is". |
| `ABBREVIATION` | A word of two to six capital letters is used before it is defined. JSON, CLI, MCP, URL, HTTP, API, ID, UI, OS, CI and TASTE are known. |
| `REPEATED_SENTENCE` | A sentence of six or more words repeats an earlier sentence of the document. |
| `EMPTY_SECTION` | A titled block has no text and no deeper block under it. |

Words inside double quotation marks are skipped by `CAPITAL_MODAL`, `SHALL`, `BLACKLIST`, `VAGUE_WORD` and `OPENING`. Each distinct word is reported once for a block. The word list of `BLACKLIST` and the last-but-one line of the `instruction` above come from an earlier version of `TASTE.md`. The version in `guidance/` has no such list.

## 17. Reference: the server, exactly

### 17.1 The command line

The first argument is the command. An argument that does not start with `--` is positional. `--check` takes no value. `--home`, `--project`, `--map` and `--port` take the next argument as their value, and `--port` is accepted only with `gui`.

Every usage error prints `metaform: {problem}` and a usage text to the error stream, and exits with status 2. The usage text does not list `projects`.

| Problem | Text |
|---|---|
| An unknown option, or an option with no value | `unknown or incomplete option {arg}` |
| `--project` with `--map` | `give --project or --map, not both` |
| `--check` with anything but `specification export` | `--check works only with specification export` |
| A positional argument on `serve`, `mcp`, `projects` or `gui` | `unexpected argument {arg}`, `projects takes no arguments` or `gui takes no arguments` |
| No command, or an unknown one | `expected serve, mcp, call, projects, gui, settings, set, unset or specification` |
| `call` without exactly one positional argument | `call takes one JSON command, or - to read it from stdin` |
| `call` with text that is not one JSON object | `the command must be one JSON object, such as '{".": {}}'` |
| `settings`, `set` or `unset` with `--map` | `settings belong to the home or a project, not a map` |
| `settings`, `set` or `unset` with the wrong arguments | `settings takes no arguments`, `set takes KEY VALUE` or `unset takes KEY` |
| `specification` with any other word | ``specification takes `export`, or `import FILE`, or `import -` to read the document from stdin`` |

| Command | Output | Exit status |
|---|---|---|
| `serve`, `mcp` | On an error, `metaform: {reason}` on the error stream. | 0; 3 when another server owns the home; else 1 |
| `call` | The tool's answer on the output stream, for a success and for a refusal. | 0 for a success; 1 for a refusal; 2 for a connection failure or an `INTERNAL_ERROR` |
| `projects` | The list of projects as indented JSON. | 0; 1 on an error |
| `settings` | Every setting as indented JSON. | 0; 1 on an error |
| `set`, `unset` | `saved; the setting takes effect at the next start`, or `... at once`. | 0; 1 on an error |
| `gui` | It runs `metaform-web` from the folder of the `metaform` program, with `--home` and `--port` passed on. | That program's status; 2 if it cannot be started |
| `specification export` | The document on the output stream. | 0; 2 on an error |
| `specification import` | One line that starts with `imported:`. | 0; 1 when the server refuses; 2 on a connection failure |

- The value of `set` is read as JSON. If it is not JSON, it is stored as text.
- `settings`, `set` and `unset` act on a project only when `--project` is given. Otherwise they act on the home.
- `specification export` names the elements it left out in one line on the error stream. For one element the line is `metaform: 1 element is left out of the document, because it lacks technical_name, name or role: {address}. Intake sets these fields.` For several it is `metaform: {n} elements are left out of the document, because each lacks technical_name, name or role: {up to five addresses} and {m} more. Intake sets these fields.` The words `and {m} more` appear only when more than five are left out.
- `specification import` prints `imported: nothing to write; all {n} sections already match the map`, or `imported: wrote {n} sections ({addresses}); {m} sections already matched the map`. A count of one is written `1 section`, and the first line is then `imported: nothing to write; the 1 section already matches the map`.

### 17.2 Values from the environment

| Variable | Use |
|---|---|
| `METAFORM_HOME` | The home, when `--home` is not given. Without it the home is `$HOME/.metaform`. |
| `METAFORM_LAUNCHER` | The launcher program. An empty value means no launcher. |
| `PATH` | Searched for a program named `hold`, only when `METAFORM_LAUNCHER` is not set. |
| `HOME` | Used for the default home. |

### 17.3 How a server is started and found

1. A connecting process first checks that the path of `<home>/server.sock` is at most 107 bytes. A longer path is refused with `the home's path is too long for its socket: {path} is {n} bytes, and a socket path holds at most 107. Use a shorter --home.`
2. It connects to the socket. If that succeeds, it uses that server.
3. If it fails, the process creates the home folder and starts a server.
4. It then tries the socket every 50 milliseconds, up to 100 times.
5. After 5 seconds with no server, the error is `the server did not start within 5 s. Its log: {the last five lines of server.log}`. After a start through the launcher, the error is ``the server did not start within 5 s. It runs as the launcher call {name}: see `hold logs {name}` ``.

**A direct start.** With no launcher, the process starts `metaform serve --home <home>` as a child in its own process group. The child's output is appended to `<home>/server.log`. If the child ends with any status but 3, the error is the last five lines of that log. Status 3 means another server took the home, so the process keeps trying to connect.

**A start through the launcher.** A launcher is used when `METAFORM_LAUNCHER` names one, or when `hold` is on `PATH` and `hold help system` prints text that holds `topogee/services`. The process runs `hold -d --name <name> --restart on-failure:3 -- metaform serve --home <home>`. `<name>` is `metaform-` and 12 hexadecimal digits from a hash of the home's path. If the launcher says that the name already exists, the process runs `hold <name>`. With a launcher, no `server.log` is written.

**The server at its start.** It takes the lock `<home>/server.lock`, and waits up to 3 seconds for it, trying every 100 milliseconds. It removes a socket file left by an earlier server, binds the socket and sets its mode to `0600`.

**The end of a server.** A server ends only on a termination signal or an interrupt signal. It removes the socket, ends every session, lets each writer finish its queued jobs, closes the databases and releases the lock last. It sends nothing to its clients.

### 17.4 What travels on the socket

The first line from the client is one line of JSON.

| First line | The server's answer |
|---|---|
| `{"project": "<absolute folder>"}` | `{"ok":true}`, and MCP then runs on the same connection. The server registers the folder if it is new. |
| `{"map": "<name>"}` | The same, for a map that belongs to no project. |
| `{"admin": {...}}` | One line of JSON, and the connection ends (section 17.7). |
| Anything else | `{"ok":false,"error":"<reason>"}`, and the connection ends. |

- The reasons are `the handshake is not valid JSON: {error}` and `the handshake must name exactly one of: a project folder or a map`.
- A map name is 1 to 64 lowercase letters, digits or underscores. The reason for another name is `map name "{name}" is not one address segment: use 1 to 64 lowercase letters, digits or underscores`.
- If the server closes the connection before it answers, the client connects again every 100 milliseconds for up to 5 seconds. The error after that is `the server closed the connection before answering the handshake`.
- After the first line, each MCP message is one line of JSON.

### 17.5 The forwarder across a restart of the server

The forwarder passes each line from the agent to the server and each line from the server to the agent. It remembers the agent's `initialize` request, its `notifications/initialized` message, each open subscription, and each request that has no answer yet.

When the server's side closes while the agent is still there, the forwarder:

1. Connects again, and starts a server if none answers.
2. Sends the agent an error for each request that had no answer, except `initialize` and the subscriptions. The error has the code `-32603` and the message `the Metaform server restarted before answering; if this was a change, read the map before sending it again`.
3. Sends the new server the remembered `initialize`, `notifications/initialized` and subscriptions.
4. Drops the new server's answers to the repeated `initialize` and to a repeated `resources/subscribe`, because the agent already has them.

When the agent's side closes, the forwarder closes its side and ends with status 0 once the server has closed.

### 17.6 The MCP surface, exactly

- **Server information:** the name `metaform` and the version `0.1.0`. The capabilities are tools, resources and resource subscription.
- **No instruction is sent at connection.**
- **The tool's description**, from the contract: `Use this single Metaform tool for add, update, delete, orphaned, goto, map, help, raw dumps and addressed reads. Work on one receiving element at a time. Input addresses select actual elements in the nested namespace. A want names the wanted element by its address.`
- **`tools/call` with another tool's name** is a protocol error, not a result: `unknown tool {name}; the only tool is project-map`.
- **A result:** a success is one text block that holds the answer as JSON. A refusal is one text block, marked as an error, that holds the refusal as JSON.
- **A failure of the store** has the form of a refusal, with the code `INTERNAL_ERROR` and no remediation. Its message is the store's error followed by `. A write may or may not be stored; read the element before you retry it.` For a database that the store refused to open, the message is the store's error and a full stop only, because nothing can have been stored.

| Resource | Name | Description |
|---|---|---|
| `metaform://map/project/<id>/main` or `metaform://map/standalone/<name>` | `map` | `This connection's functional map. Reading it returns the shallow graph: every address and every want as an edge. Subscribe to hear of each commit.` |
| `metaform://intake/<section>` | `intake/<section>` | `The {section} section of the intake procedure.` A required section adds ` Required reading to perform an intake.` |

- Reading an unknown section is an error: `the intake procedure has no section {name}; resources/list names its sections`.
- Reading any other address is an error: `unknown resource {uri}; this connection's map is {uri}`.
- Only the map's resource can be subscribed.

### 17.7 The admin requests

The command line uses these requests. They are not MCP, and no agent sends them. A failure is `{"ok": false, "error": "<text>"}`.

| Request body | Answer |
|---|---|
| `{"settings": {"project": "<folder>"}}` | `{"ok": true, "settings": [{"key", "value", "default", "source", "about", "applies"}]}`. `project` is optional. `source` is `default`, `global` or `project`. |
| `{"set": {"key": "<key>", "value": <json>, "project": "<folder>"}}` | `{"ok": true, "applies": "at the next start"}`, or `"at once"`. A missing or null `value` removes the stored value. |
| `{"projects": {}}` | `{"ok": true, "projects": [{"id", "name", "folder"}]}`, ordered by name and then by id. It registers nothing. |
| `{"export": {"project": "<folder>", "check": true}}`, or with `"map": "<name>"` | `{"ok": true, "markdown": "...", "left_out": [...]}`, with `summary` and `reports` when `check` is true. |
| `{"import": {"project": "<folder>", "markdown": "..."}}`, or with `"map"` | `{"ok": true, "written": [addresses], "unchanged": n}`. |

- `settings` and `set` register a project folder that is new. `export` and `import` do not: an unregistered folder gives `{folder} has no map yet; an agent creates it by using the project-map tool in that folder`.
- A refused `import` gives `'{address}': {CODE}: {message}; the import wrote nothing`.
- Any other request gives ``an admin request must be `settings`, `set`, `projects`, `export` or `import` ``.

### 17.8 The two clients inside the program

- **`metaform call`** opens a connection as a forwarder does. It sends `tools/list`, then `tools/call` with the first tool's name, and closes. Each request carries the protocol version `2026-07-28` and the client name `metaform-cli`.
- **The watch client**, which the web host uses, sends `resources/list`, takes the first resource's address, and opens `subscriptions/listen` for it. Its client name is `metaform-watch`. It learns only that the map changed.

## 18. Reference: the store, exactly

### 18.1 The home

- `server.lock` is created if it is missing, and the store holds an exclusive lock on it while it runs. A second store on the same home fails with `the home is owned by another functional map server (lock file {path})`.
- `store.format` holds the one line `metaform-store 1`. The store writes it into a home that holds nothing but `server.lock`, `server.log`, `server.sock` and `settings.json`. Only its presence is tested.
- A home that holds anything else and no `store.format` is refused: `{home} holds data this store did not write (no store.format); it may be the Node test harness's home. Nothing was changed. Use another home (METAFORM_HOME or --home).` The lock file has been created by then, and nothing else is written.
- A settings file is written whole, through `settings.json.tmp` and a rename, so a crash leaves the old file or the new one.

### 18.2 Projects

- A project is found by the exact text of its folder's resolved path.
- A new project's id starts with that path, with `-` in place of every character that is not an ASCII letter or digit. A number of at least three digits follows. The number is the first, from `001`, for which `projects/<id>` does not exist.
- Registration creates `projects/<id>/`, writes `projects/<id>/source.txt` with the path, and then adds the row `Project(id, source, name)` to `metaform.lbug`.
- A second registration of the same folder returns the same id and does not change the stored name.

### 18.3 The rows

| Row | Key or ends | Other properties, all text unless noted |
|---|---|---|
| `Map` | `id`: `main` for a project's map, or the name of a standalone map | |
| `Element` | `key`: `<map id>|<stored address>` | `mapId`, `address`, `technicalName`, `name`, `role`, `uri`, `status`, `childMap`, `extra` |
| `Record` | `key`: `<element key>$<stored layer name>$<position>` | `mapId`, `layer`, `ordinal` (a 64-bit whole number, from 0), `data` |
| `ROOT` | from `Map` to the root element | |
| `CONTAINS` | from the parent element to each element | |
| `DEPENDS_ON` | from the receiving element to the wanted element | `why`, `how`, `direction`, `extra` |
| `HOLDS` | from an element to each of its records | |

How each value is stored:

- The stored address has each segment in camelCase. The root's address is `.`.
- `technical_name`, `name`, `role` and `status` are stored in their columns. A value that is not text is stored as its JSON text.
- A list that is not empty is stored as records, one for each item. This covers a layer's records and `refs`.
- Every other field, an empty list included, is stored in `extra` as one JSON object with camelCase keys. `extra` is empty when there is none.
- A want is one `DEPENDS_ON` row. `ref` is stored in that row's `extra`.
- The `uri` column and the `childMap` column are kept from earlier designs. No command writes a value into them.
- The JSON text of a record is stored as written. Keys inside it are not converted.

### 18.4 One write

A write is one job on the database's writer thread.

1. The writer takes the map's last committed state, and loads it if this is the map's first use.
2. It applies each command of the job to that state in memory. A refusal ends the job, and nothing is stored.
3. If nothing changed, the job ends with no transaction and no announcement.
4. It opens one transaction and stores the change in this order:
   1. the map's row, and the root element if it is missing;
   2. each element whose own row changed;
   3. the wants and the records of each changed element;
   4. the `CONTAINS` row of each new element;
   5. the removal of each removed element with its records.
5. It commits. An error while the change is stored rolls the transaction back. The code asks for no rollback when the commit itself fails.
6. It replaces the map's last committed state, and then calls the subscribers.
7. It answers the caller.

- A changed element has all its columns written again. An element whose own row did not change is not written.
- For each wanted element whose wants changed, every want row to it is removed and written again.
- Records are compared by position: a changed record is rewritten, a new position is added, and a removed position is deleted.
- Each job of one client runs in the order it arrived. With several clients waiting, the writer takes one job from each in turn.
- The server's own jobs run as client 0: the registration of a project, the definition of the specification layer, and an import.
- An import is one job, so its sections are stored together or not at all.

### 18.5 Reads

A read uses the map's last committed state in memory and opens no transaction. A read waits in two cases only. The first use of a map loads it from the database. The first command on a project's main map in a run of the server waits for the job that writes the specification layer's definition. Any command can also wait for a short time while another command opens or closes a database.

### 18.6 Announcements

After each commit, the store calls every subscriber of that map with the changed elements: each touched address with its new content, or with nothing for a removed element. The server passes on only the fact of the change (section 8.7).

### 18.7 Opening a database

1. The store compares each table it knows with what this build expects, after the renames of section 9.5. A difference refuses the database with `the database was made by a different build and cannot be brought up to date: {path}: table {name} has ({found}); this build expects ({expected}). Nothing was changed. Use the build that made it, or another home`. A table that the build does not know is not compared.
2. In one transaction it applies the renames, creates each missing table, moves each non-empty list out of `extra` into records, and rewrites each abbreviated role in full.

The conversion of a stored `uri` into `refs` is done in memory when a map is loaded, and not in the database.

### 18.8 The limit on open databases

- The limit comes from `stores.max_open_databases` when the server starts.
- The database that holds the registry is always open and is not counted.
- When a database must open and the count is at the limit, the store closes the least recently used database that no command is using.
- If every open database is in use, the store opens one more and exceeds the limit for a time.
- A closed database's maps are loaded again at their next use.

### 18.9 Settings, exactly

| Key | Default | Accepted value | Scope | A change applies |
|---|---|---|---|---|
| `stores.max_open_databases` | 16 | a whole number, at least 1 | the home only | at the next start of the server |

- A lookup takes the project's value, then the home's value, then the default.
- A setting that is not declared is refused: `there is no setting "{key}"; the settings are {list}`.
- A wrong value is refused: `{key} must be a whole number, at least 1`.
- A home-only setting given with a project is refused: `{key} is global only; set it without a project`.
- A settings file with an unknown key or a wrong value does not stop the server. The entry is reported on the error stream and ignored.

### 18.10 Fixed values

| Value | Where it applies |
|---|---|
| 107 bytes | The longest path of `<home>/server.sock` |
| 3 seconds | A starting server's wait for the lock |
| 5 seconds | A connecting process's wait for a server, and for the answer to its first line |
| 64 MiB, 16 GiB, 4 threads | The buffer pool, the size limit and the worker threads of each open database |
| 16 | The default limit on open databases |
| 4170 | The web host's default port |
| 4 | The deepest level of a block |
| 32 characters | The longest code of a block |

## 19. Reference: the web host, exactly

`metaform-web [--home DIR] [--assets DIR] [--port N] [--read-only]` prints `Graph workspace: http://{address}/` and serves until it is interrupted.

- **The page's folder** is `--assets`, or a folder `workspace` beside the program that holds `index.html`, or `metaform/workspace/dist` of the source it was built from. If the folder has no `index.html`, the host does not start: `{folder} has no index.html; build the workspace first (npm run build in metaform/workspace)`, with status 2.
- **The port.** With `--port`, that port must be free. Without it, the host uses 4170, or a port that the system picks when 4170 is in use.
- **Every request** must carry a `Host` that is the listening address, `localhost:<port>` or `127.0.0.1:<port>`. Another `Host` gets status 403 with `unexpected Host`. An `Origin`, when one is sent, must be `http://` and one of those three, or the answer is 403 with `unexpected Origin`.
- **The host never opens the store.** It reaches the home's server as `metaform call` does, and it opens a new connection for each command.

| Route | Answer |
|---|---|
| `GET /api/host` | `{"writes": true}`, or `{"writes": false}` with `--read-only`. |
| `GET /api/projects` | A list of `{"id", "name", "folder"}`. Status 502 with `{"error": ...}` when the server cannot be reached. |
| `POST /api/projects/{id}/call` | The tool's answer to one read, with status 200 for a success and for a refusal. A command that is not a read gets 403: `this route forwards reads only; a write goes to /write`. |
| `POST /api/projects/{id}/write` | The tool's answer to one `add`, `update` or `delete`, with status 200. |
| `GET /api/projects/{id}/events` | A stream of events. Each commit sends one event named `map-changed` with the data `{}`. |
| any other `GET` | A file of the page. A path that names no file gets the page's `index.html`. |

- **A read**, for `/call`, is a command with one key of one of three kinds. The key is `map`, `goto`, `search`, `orphaned` or `help`. Or the key starts with a period and has `{}` as its value. Or the key holds a period and its value names only layers, each with `{}`. `search` passes this test. The tool has no `search`, so it reads `search` as an address and answers `NOT_FOUND`.
- **A write is refused** with status 403 in three cases: the host was started with `--read-only`; the request has no `Origin`; or the `Origin` is not `http://` followed by exactly the request's `Host`. A command that is not one `add`, `update` or `delete` gets status 400.
- **An unknown project** gets status 404: `no project '{id}' in this host`.
- **Each `index.html` that the host serves** gets the element `<meta name="metaform-host" content="metaform-web">` added in its head. The page uses it to know that the host serves it.
