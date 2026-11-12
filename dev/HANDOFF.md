# Handoff, 2026-11-12

Read this first. It replaces the long session it came from. The founder is Richard. Call him the founder, not the owner.

## What the work is

Two things, in this order. Everything else is a side track.

1. **The intake procedure.** Get it to a form the founder accepts, tested on photos and then on code.
2. **The MCP server.** Make the tool accept what the procedure records, so that an agent records one element at a time and a person watches the map grow in the viewer.

## How to work with the founder

Each rule here was learned from a failure in the session. The reason is given so that you can apply it to a case this list does not name.

- **Do not copy his words into the project.** Work out what he means and why, and write that. Copied words lose the conditions they were said under, so an agent applies them where they were never meant.
- **Do not change his rules unless a test run shows a failure.** Show him the failure before you change anything. He tested the wording for months, and a change that looks harmless changes what a model infers.
- **An edit he invites is limited to the thing he named.** Do not expand, tidy or add rules around it.
- **Do not edit `~/brain`.** Read his notes from a copy. Agents altered them before, and he lost work.
- **Do not bring him inconsistencies to settle.** What he says in conversation governs. Where notes, specifications or code disagree with it, treat the older text as altered, decide, and record what you chose.
- **Every instruction and rule states its reason.** Without the reason an agent guesses one, or follows the words blindly.
- **Put a thing where the model needs it.** A model does not carry an instruction across many steps. This is why his procedure repeats a rule inside the step that uses it. That repetition is not redundancy.
- **Stay on the track he is on.** Finish what he is working on before you raise anything else.
- **Ask before you save a memory.**

## The current procedure

**`rich/intake_best.xml` is the working file.** The founder edits it. A snapshot is at `dev/intake-test/intake_best.snapshot-2026-11-12.xml`.

It is his cleaned canonical text (`~/brain/more/backups/Canonical_Intake_cleaned.xml`) with these changes:

- One `uri` for each element in place of member lists. For code it is the entry point. For a photo it is the path.
- Roots are `code`, `document`, `media`, `data`, `upstream`, `downstream`. There is no `collection` root: members that share a type are the same type, so a set needs no root of its own.
- The word "entity" is replaced by "element". Every entity is an element.
- "Join" is "dependency" in most places.
- Roles are `AUE`, `DE`, `SE`, `NE`, `CQU`, `UD`, `DD`. `CQU` is a person. `UD` is an upstream dependency. `DD` is a downstream dependant that is not a person. The address does not determine the role, so the role is stated. The viewer will colour and shape elements by role.
- `functional_name` replaces `name_length`. Reverse the segments of the address, then replace periods and underscores with spaces. The functional name is the leading words of the result.
- A dependency has the fields `pe`, `op`, `ef` and `ifd`. The values of `ifd` are inbound, outbound and two-way. The intake's own terms are the field names because a model infers from them. The viewer shows the full names.
- The schema at the end is flat: one object for each element, keyed by its full address.
- `code.game` is valid. A game names the project by its function, which is entertainment. `code.game.platformer` and `code.game.fps` are invalid because they name a genre. `code.game.engine` is invalid because an engine is not a child of a game.

**Decided by the founder and still true:** annealing stays as a step. The step-by-step form stays. "Divergent" is not a role. He prefers "Defining" to "Definitive".

## What the tests showed

All tests used 37 photos, each run in an isolated session.

- His cleaned text surveys every member. His short "pure" text does not: its runs opened 0 to 3 photos.
- A model writes invented file names when it holds the map until the end. Recording each uri when the member is observed stops it. An instruction to list the folder again was ignored.
- Removing the annealing step made the map grow from about 10 elements to between 13 and 29, in every run.
- The result holds on Haiku as well as Sonnet, with coarser maps.
- One invalid example changes the inference in every run. Do not add an example on your own judgment.
- The reference result: three types by what the photo presents (a person, a place, one object), background and signage as supporting elements, at least one CQU, one real uri each.

Working copies and their results are in `metaform/intake/stripped/README.md`.

## How to run a test

The scripts are in `dev/intake-test/`. They were written for a scratch folder and hold absolute paths that no longer exist, so set the paths at the top of each before use.

1. Unpack the photos from `/mnt/i/Downloads/sigma-fp2-review-samples.zip` into a folder named `photos`. Resize them with `resize.py` to 1280 pixels on the long side. Do not name the folder after the archive: the model reads a purpose from the name.
2. Run `variant_file.sh <procedure> <label> <runs>` for Sonnet, or `variant_file_haiku.sh` for Haiku. Each run starts `claude -p` in the photo folder with no project settings and no MCP servers.
3. Summarise with `flatsumm.py <label>` for the flat schema.

Do not ask a model to write its records into its reply as it goes. The API blocks that as a request to expose reasoning. Give it a file to record into.

## What is not done

**On the procedure**

- The run of the current file was in progress when this was written. Read its result before anything else.
- No test on code yet.
- The steps still say "SET purpose" and "SET provider", and describe `ifd` as sends, receives and both. The schema says `op`, `pe`, and inbound, outbound, two-way. No run has shown this to fail, so it is unchanged.
- One CQU example gives `downstream.code.*` for an SDK. Under the new roles that is a `DD`.

**On the server.** The build does not match the procedure. One run with the real tool showed the tool refuse:

- the roles (it accepts Definitive, Supportive, Notable, Divergent),
- more than one Defining Element,
- the dependency fields (it stores `wants` with `why`, `how`, `direction`),
- and `technical_name` where the procedure now says `functional_name`.

Also: the answer to a bare `help` request misled the model three times, two refusals return no usable command, and `search` is not built. The tool contract is protected: change it only on the founder's instruction.

**Other**

- The web interface he asked for, original and built from an empty page, is not started.
- `TASTE.md` is his experiment: 24 rules, each with its reason, uncommitted. Rules 9, 12, 15, 16, 17 and 18 were added or changed in the session.
- `metaform/PROJECT_SPECIFICATION.md` section 6.4 still explains the intake from the pure text. It needs rewriting from the current procedure.
- `SPEC.md`, the schema and the code still hold Divergent, `collection`, `wants`, `layer` and `technical_name`.

## Where things are

| Thing | Path |
|---|---|
| Working procedure | `rich/intake_best.xml` |
| Test copies and results | `metaform/intake/stripped/` |
| Test scripts | `dev/intake-test/` |
| Specification written in the session | `metaform/PROJECT_SPECIFICATION.md` |
| The founder's notes, read only | `~/brain/` |
| His cleaned canonical text | `~/brain/more/backups/Canonical_Intake_cleaned.xml` |
| Test homes made in the session | `~/.metaform-climb` to `~/.metaform-climb7` |
| Branch | `fable-climb` |

Never open `~/.metaform`, `~/.metaform-rust` or `~/.metaform-sqlite` in a test. Never use `pkill`, `killall` or `pgrep -f`.
