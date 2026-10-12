# Metaform: what was lost in the move to `.metaform`, and what should come back

Date: 2026-09-13. Nothing in this document is decided. Where Rich's words from the 2026-09-13 conversation appear, they are talk-through for review in another session, not rulings. Read-only investigation. No Metaform command was run; every claim comes from source, specs, git history, and the state on disk. Files are cited by path.

## Scope and lineage

Metaform's git history (109 commits, 2026-09-05 to 2026-09-13) never contained `sessions.json`. The system that had it is TEMPO 0.5.2, installed at `~/.tempo/tempo` with live state under `~/.tempo`. Metaform's `NOTICE.md` attributes code to RchGrav/tempo, and its history manifest still carries TEMPO's `<sha>_0000` identity form and vivi's 16-hex form side by side. So "old" below means TEMPO 0.5.2, with the vivi spec cited where it refined a rule. "Current" means the Metaform checkout at HEAD `c96c145` plus the state under `~/.metaform`.

## 1. Division of state

### Intended, from `docs/SPEC.md` §13 and the portable-projects spec

| Location | Holds |
|---|---|
| `~/.metaform` | `config.json`, global inference graph, the knowledge service and its `service/knowledge.sqlite3`, assignment records, request schemas, workfolders |
| `<project>/.metaform` | `project.json` service marker, project graph in legacy mode, `state.sqlite3` execution state, `history/` origin copy and checkpoints, locks, outputs |
| `knowledge.sqlite3` | elements, joins, participants, observations keyed by owner `global` or `project:<uuid>`; `projects` registry; `imports`; `receipts`; `schemas`; `revision` |

Decided 2026-09-12, recorded in SPEC §9 and §13, not yet built: the base db also tracks each working folder and the last project selected from it, `begin` records the folder's assignment there instead of writing `.agentid/nonce`, a nonce idle for 24 hours behaves as absent, and reads of the base db are direct and never start the service.

### On disk today

- `~/.metaform` has two service directories with two different `service_id` values: `runtime/` (the newer global server, with `homes.json` and `projects.json`) and `service/` (the per-home service from the portable spec §6). Neither spec describes both coexisting.
- `runtime/projects.json` is not a registry. `viewer.py:35-112` writes it as the workbench's remembered list of opened projects. It currently lists three temp and test projects and not the Metaform checkout itself.
- `knowledge.sqlite3` `projects` holds two rows: `mgm-main` and a pytest temp folder. The Metaform checkout is not registered, has no `project.json`, and runs in legacy mode on a Ladybug backend.
- `~/.metaform/assignments/941428370.json` binds a folder `/home/rich/onhold` that is not in any registry.

So there are three partial project lists (viewer file, service table, assignment files) and no single place that answers "which projects exist and which folder was last working on which".

## 2. Repository and non-repository identification

### TEMPO 0.5.2

`SECURITY_AND_PROVENANCE.md`: repository identity is the pinned commit id with tree identity kept separately; file identity is SHA-256; directory and archive identity is a canonical content-manifest hash. Every variant carries the full source identity plus a `<first-12>_<FFFF>` lineage id. Repository state lives in the target repo's `.tempo`; non-repository state lives in the home. The home index locates all known variants.

### Metaform

`history.py:91-161`: if `git rev-parse --show-toplevel` equals the project root, the baseline is `git_commit`, `base_commit` is recorded, and `git archive HEAD` is unpacked into `.metaform/history/origin/`. Otherwise the baseline is `working_directory` and the tree is copied. In both cases identity is `origin_sha256`, the digest of the file manifest. The manifest stores `mform_sha_id` as the full digest plus `_0000` and `mform_id` as the first 12 hex plus `0000`. A separate project UUID exists only when a project is connected to the service.

State placement changed: a non-repository folder now gets `.metaform/` inside itself, origin copy included, instead of under the home.

Gap found: the Metaform checkout's own baseline is `base_commit b7aea901` from 2026-09-10. HEAD is 20 or more commits later. `history.initialize` returns the existing manifest unchanged, and no command re-anchors the origin.

Rich, in conversation 2026-09-13, not decided. A re-anchor is a whole new subfolder under `.metaform/history/`, keyed by the new base commit, holding its own origin copy and the diffs recorded against it. The earlier subfolder stays exactly as it was. A different commit is a different origin; the suffix is not involved. For a non-repository project the key is the content digest, the same rule the manifest uses for `origin_sha256`.

```
.metaform/history/
├── b7aea901.../        first base, 2026-09-10
│   ├── manifest.json
│   ├── origin/
│   └── versions/       diffs against this base
└── c96c145.../         re-anchored base
    ├── manifest.json
    ├── origin/
    └── versions/
```

Today `.metaform/history/` is one flat store with one base, and `checkpoint` copies every changed file in full into `versions/<id>/files/`; diffs are computed on demand by `history.diff`. Open with Rich: whether the checkpoint stores the diff itself in place of the full copies.

Identity form, Rich in conversation 2026-09-13, not decided: the identity is the first 12 hex of `origin_sha256` followed directly by the four-hex suffix, 16 characters, no underscore. That is the `mform_id` the manifest already writes. The `<sha>_0000` form, `mform_sha_id`, goes, and import folder names take the 16-character form. The full digest stays in the manifest as `origin_sha256`.

## 3. Provenance and origin

SPEC §15 specifies one-read provenance from any ref to its producer, rendered prompt, binding map, and bound refs. Plan unit 9 builds it; it does not exist yet. What exists is the history manifest above, `receipts` in the knowledge db, and `provenance.json` per checkpoint. `docs/reviews/2026-09-11-mgm-provenance-audit.md` shows why this matters: the archived MGM native sample already carried latent-perspective provenance on all 58 actuals, and the introduction point could not be found because intermediate storage was not retained.

## 4. Diffs against the original project state

### TEMPO 0.5.2

Every operation folder carried a patch against the origin: `git diff --no-index --binary` for non-repository work, the worktree diff for repositories, and the complete output when git was absent.

### Metaform

`history.diff(app, version)` at `history.py:338` diffs a checkpoint against its parent checkpoint only. Asking for `origin` returns an empty file list. There is no diff of the current working tree against `history/origin/`, even though every origin file is on disk with its hash. `change_report.py` compares source-file hashes against an intake's recorded baseline but returns counts only: added, modified, deleted, percentages. It runs only when an intake captured a `source_baseline`. Backlog items R37, R40 and S12 in `docs/repair-backlog.md` are open on exactly this.

Verdict: the capability is lost. The inputs to restore it are all present.

Rich, in conversation 2026-09-13, not decided, verbatim:

> it can store full versions on the disk but an export should seek to make the export smaller, the diff uses python diff now using the python git port that doesnt diff the binaries when they change it just updates the file, important thing is reconstruction, an export should export the most recent work off of the most recent origin thats stored.. the main thing that isnt covered right now is when you are running mutation experiments that might produce a ton of varients off of a single commit or hash.. the important factors are to support mutation operations where many worktrees are collected up. That mechanism should exist like we used to have otherwise you can export the the present repo state, we should have a mechanism that supports a bunch of mutations pinned to a common origin.. which is supported anyway as long as we always make new subfolders.. its very little storage,, and I take that back we should keep diffs off of the source commit.. so long as the variations can be easily recontructed from the menu python gives you (The old scripts arent needed since the new export format is a wheel

What this fixes, as read:

- Storage: diffs off the source commit, not full copies. Text files as diffs; a changed binary is stored whole, the way the Python git port does it.
- The base subfolder holds many variants pinned to one commit or hash. Mutation experiments that collect many worktrees each land as a variant under the common origin. New subfolders per origin already give this.
- Export: the most recent work off the most recent stored origin, kept small.
- Reconstruction is the requirement. Every variant is rebuilt from the menu the exported wheel gives you. The old scripts are not needed.

Rich, 2026-09-13: "you export a whole origin folder thats the point of its structure". An export is one base subfolder in full: the origin and every variant pinned to it.

Rich, 2026-09-13, verbatim: "The main difference is that the origin folder gets a copy of the commit itself they are diffed of off.. if they are web varients you should be able to launch multiple diffs in tabs each on a different port.."

As read: the origin subfolder carries a full copy of the commit it is keyed by, and every variant is a diff against that copy. Reconstruction applies a variant's diff to the copy. For web artifacts, reconstruction serves each variant on its own port, so several variants open side by side in browser tabs.

Rich, 2026-09-13, verbatim: "otherwise you can extract any of the varients of whatever it is or all of them from the wheel to external folders using a cli command"

As read: for any artifact, a CLI command on the exported wheel reconstructs one variant, several, or all of them into external folders. Serving on ports is the web case of the same reconstruction.

## 5. Imports and exports, and what resolves silently

### `package import` (`portable.py:541-748`)

1. If a folder named `<origin_sha256>_<suffix>` already exists and its working files or knowledge digest drifted, a checkpoint "Local continuation before import" is taken first. Good.
2. If the incoming history includes the local history, the local folder is replaced. The old folder is moved to a temp name and deleted. `replace_inclusive` defaults to true and `modules/package.py` never passes it, so no caller can decline.
3. If histories diverge, a new suffix is allocated and a sibling folder is created.
4. The return value carries `path`, `mform_sha_id`, `mform_id`, `unresolved`, and handoffs. It does not say whether case 2 or 3 happened.

Rich, in conversation 2026-09-13, not decided, verbatim: "if it would lose any data it just creates a new folder and keeps both increments the hash, there is no warning not to do it it just does it the agent can inform the user there is no harm in that but I dont know if it matters as long as you can still access them"

As read: an import that would lose any data creates a new folder, increments the four-hex suffix, and keeps both. No warning, no question. The agent may tell the user; it is not required. What matters is that both remain accessible.

Cases 2 and 3 are the silent resolutions. Rich's words above treat that silence as intended; not decided. Case 1 followed by case 3 is the common shape: local drift produces a checkpoint, the checkpoint makes the histories diverge, and the user ends with two folders and no message saying so. TEMPO 0.5.2 applied the same inclusive-replace and divergent-sibling rule with the same silence, so this is retained behaviour, not a regression. The vivi spec §80 states the rule explicitly as gates `GB-PACKET-ADOPTION-001` and `GB-LINEAGE-IMPORT-001`.

### `project connect` (`knowledge.py:560-660`)

Legacy graph import into the service is explicit. Conflicting records raise `migration_conflict` with both contents. Verification failure raises `migration_verification_failed`. Repeat imports are deduplicated by `(source_home, source_digest)`. Nothing is resolved silently here.

### Knowledge mutations

Receipts keyed by `(project_context, request_id)`; reuse with a different body returns `request_id_conflict`. Explicit.

## 6. `sessions.json`

TEMPO 0.5.2 kept one `sessions.json` in the home, never in a project. Per operating path it recorded: the selected origin, every known origin with its source path and target kind, per-path defaults, `retain_work`, whether the path is a repository, storage bytes, and an update time. Globally it recorded fanout defaults and git availability. `SECURITY_AND_PROVENANCE.md` and `TESTING_V052.md` describe it; the live file at `~/.tempo/sessions.json` shows three operating paths. Its purpose was resume: invoke from a folder and continue that folder's work.

Metaform has no equivalent. The CLI walks parent folders for `.metaform/state.sqlite3` and stops before `~` (`cli.py:51-56`). The 2026-09-12 decision in SPEC §13 restores the capability in the base db. That is the right home for it, and it should absorb the viewer's `runtime/projects.json` and the `assignments/<nonce>.json` files at the same time, so one table answers the question.

## 7. What Metaform had, has now, lost, and should get back

| Capability | TEMPO 0.5.2 had | Metaform has now | Status | Recommendation |
|---|---|---|---|---|
| Operating-path resume | `sessions.json` per working folder | parent walk for `state.sqlite3` | lost | restore as a base-db table, decided 2026-09-12, unit 8 |
| One index of all known projects | home `index.json` over every variant | three partial lists | lost | one `projects` table covering legacy, portable and service projects, with mode |
| Patch against origin | per operation, binary-safe | checkpoint vs parent only | lost | `history diff origin` from `history/origin/` vs current tree; patch export per checkpoint |
| Re-anchoring the origin | new variant from the operation pile | none; `base_commit` goes stale | lost | a new history subfolder keyed by the new base commit; the old subfolder is untouched |
| Repo identity by commit, non-repo by content hash | yes | yes, both plus content digest | retained | keep |
| Origin copy for non-repo work | `origin/` in home | `history/origin/` in project | changed | acceptable; note the folder now carries `.metaform` inside |
| Inclusive replace, divergent sibling on import | yes, silent | yes, silent, no opt-out | retained, by design | keep, per Rich's words, not decided; the result may name the folder it made |
| Legacy import conflicts reported | n/a | `migration_conflict` with both records | new | keep |
| One-read provenance | no | specified, unbuilt | new | unit 9 |
| Encrypted packet envelope | AES-256-GCM bound to manifest and origin | bundle hash only | dropped | not asked; flag only |
| Single service process | n/a | two service dirs, two ids | drift | unit 11; delete the stale one once the design is settled |

## 8. Order of restoration

1. Working-folder tracking in `knowledge.sqlite3`: `working_folder` primary key, `project_id`, `assignment_nonce`, `updated`. `begin` writes it, `done` clears it, reads are direct and read-only, and rows older than 24 hours are ignored at read time. Rich in conversation 2026-09-13, not decided: the record exists for provenance; `.agentid/nonce`, `assignments/*.json` and `runtime/projects.json` fold into it only as far as everything that works today keeps working.
2. Diffs off the source commit under each base subfolder, binaries stored whole, many variants pinned to one origin, reconstruction from the exported wheel's menu. Rich's words of 2026-09-13 in section 4, not decided. Closes R37 and R40.
3. Import keeps both on any data loss by incrementing the suffix, silently. Rich's words treat that as intended, not decided. Nothing to restore; the result may name the folder it made so the agent can mention it.
4. Re-anchor command creating a new history subfolder keyed by the base commit.
5. The knowledge service. Rich in conversation 2026-09-13, not decided, verbatim: "I have no idea who started this whole fukcing new port every time but I want it gone.." The service binds one fixed port every time. Today every entry point defaults `port=0`, an OS-assigned port per start: `service.py:107`, `:171`, `:254` and `viewer.py:731`, introduced by commit `4c81464` on 2026-09-09; the portable-projects spec §6 step 5 states "binds an OS-assigned loopback port", which his words would supersede if decided. Proposal, mine: one port number in `~/.metaform/config.json`, used by every start and restart unless overridden on the command line, so the link made once keeps working. Layout, mine: `runtime/` holds the process identity, token, endpoint, lock, log and `homes.json`; `service/` holds only `knowledge.sqlite3` and `analysis/`; the leftover identity and token files in `service/` are deleted.

## Unverified

- Whether a copied `project.json` at a second path produces the explicit location-mismatch result the portable spec promises. Not exercised.
- Whether the 24-hour rule is anywhere in code. The only expiry found is the assignment phase deadline at `continuation.py:26`.
- What produced the stale `service/` identity versus `runtime/`. Both are on disk; which one the current build starts was not run.

## Rich, 2026-09-13 early morning, on the history layout

Said in conversation after reading section 4; recorded in his words with punctuation fixed. The TEMPO copy under `tempo/` in this checkout is not the version to read: "you are looking at the wrong version, I have had to start over 8 times so far when the agent messed the project all up."

> It was a diff of all of the text. On disk, if it's a git repo, origin is based on the commit hash; origin is kept in the repo, and only extracted when you create an export. The Python menu should allow you to reconstruct the contents of the export right out to disk if you want.

> It doesn't handle binaries, just text, so images or whatever are just copied if they change.

> It only keeps an origin when the source isn't in a repo. And if it's not in a repo the data is stored in `~/.metaform/<folder>/<mform_sha_id>` (that's the 240 msb + 16 bit naming); `<mform_id>` is 48 msb + 16 bits. Repo is stored in the repo, non-repo is stored in global.

As read:

- A repository project keeps its data in the repo under `.metaform/`. Each base is keyed by the commit hash. There is no origin copy; the commit is the origin, extracted from git only at export.
- A variant is one diff of all the text against the commit, produced and applied by Python so the packet never needs git, plus whole copies of the binaries that changed. Per-file hashes in the changes map check reconstruction.
- A non-repository source keeps its data in the global home under a folder Rich has not named, one entry per `mform_sha_id`, and that is the only case with an origin copy. Proposed name, mine, until Rich gives his: `origins`.
- `mform_sha_id` is the 240 most significant bits of the origin digest followed by the 16-bit suffix, 64 hex characters, no underscore. `mform_id` is the 48 most significant bits plus the same suffix, 16 hex. Today's `<full digest>_0000` form changes to this; import folder names follow.
- Export extracts the origin, from git or from the copy, and carries the variants as diffs and binaries. The packet's Python menu reconstructs origin, one variant, several, or all of them to disk, each into its own folder.

## What the sources say, read 2026-09-13 early morning

Rich pointed at `RchGrav/tempo` on GitHub, its branches, and `~/vivi`. `~/vivi` is the same tree as the `main` branch of that repository, one commit, "Consolidate the project into one repository". TEMPO 0.5.2 is the `tempo-capsela-archive` branch. The `tempo/` folder inside this checkout is neither and is not to be read. Quotes are verbatim.

**The home folder for non-repository origins is `origins`.** `~/vivi/src/vivi/chassis/origins.py`, module docstring: "a repository origin's `.vivi/` directory lives at the repository's own working-tree root -- the commit id already anchors it, so no separate copy is needed. A non-repository origin's `.vivi/` directory lives under `~/.vivi/origins/<base_id>/.vivi/`, alongside the pre-workflow anchor copy the same ruling introduces at `~/.vivi/origins/<base_id>/origin/` (`base_id` is the origin's 12-hex derived identity, shared by every extension of the same underlying content)." Author ruling 2026-08-25. `topology.py` lists `origins` among the roots under `~/.vivi/`.

**Identity.** `~/vivi/specs/VIVI_SYSTEM_SPECIFICATION.md` section 20: "`origin_sha_id` is the commit or hash identity of the origin's on-disk context, distinct from Vivi's internal 64-bit `origin_id`. `origin_id` is 16 hexadecimal characters: 12 derived from the underlying hash identity plus a 4-character extension identifying one provenance-bearing instance. The extension is not a hash-collision counter." A new extension "MAY be required for repeated intake, deeper functional decomposition, special instructions establishing a distinct interpretation, or an import whose provenance cannot safely replace local provenance." TEMPO 0.5.2 (`capsela:README.md`) wrote the same identity as `<first-12-hex-of-full-source-identity>_<FFFF>`, first variant `_0001`, and kept "the full source identity in the database and packet for integrity." Rich's 2026-09-13 form for Metaform: `mform_sha_id` = 240 msb + 16-bit suffix (64 hex), `mform_id` = 48 msb + 16 bits (16 hex); the long form is the on-disk folder name for a non-repository origin, the short form matches vivi's `origin_id`.

**Import.** Section 20 and section 80: "Import advances an existing lineage only when the incoming provenance fully includes local provenance. Otherwise Vivi iterates the extension and keeps the incoming provenance as a distinguishable instance. Import can never silently erase provenance already known locally." Same rule as Metaform's `import_bundle` today.

**Sessions.** Section 14: "`~/.vivi/sessions.json` is the machine-level discovery index for operating contexts... A primary purpose is resume. When Vivi is invoked from a working folder it can identify the work associated with that operating context and restore the user's working position after a reboot or context reset. `sessions.json` exists at the user level, never inside an individual repository or origin store." Section 15, per operating path: "active session, selected origin, is_repo, retain_work, known origins, full source path for each known origin, runtime defaults, fanout settings, nofanout settings." This is the working-folder table Rich moved into the base db on 2026-09-12: folder, last project, and its state.

**Workspaces and collection.** Section 28: "Repository origins use Git worktrees; non-repository origins use temporary working folders." Section 32: "Vivi uses Git as a common diffing mechanism for repository and non-repository work, equivalent to `git diff --no-index --binary`... Collected changes belong to the producing operation and are retained with the origin's provenance." TEMPO 0.5.2 (`capsela:docs/SECURITY_AND_PROVENANCE.md`): "A six-digit Operation folder contains produced artifacts and the required binary patch or media assets. With Git available, non-repository work uses `git diff --no-index --binary`; repository work uses its worktree diff... If Git is absent, TEMPO retains the complete uncompressed output instead of failing... Every retained payload is hashed and verified." Rich's 2026-09-13 rule for Metaform: the diff is Python's, of all the text; binaries are copied whole when they change; the packet never needs git.

**Star model.** Section 23: "Every operation is grounded in one selected origin. Within one origin run each artifact-producing operation starts from the same baseline and results are sibling spokes. Sequential scheduling MUST NOT turn an earlier candidate into a later candidate's baseline." This is the mutation case: every variant is a diff off the origin, never off another variant. A result becomes a new origin only through an explicit recursion transition, which is the re-anchor.

**The packet.** Section 79: "A Vivi packet is the portable form of one tracked origin and its Vivi state. It carries enough information to identify the origin, materialize its represented source or output, carry operation data, carry workflow and provenance state, verify its contents, and resume work in a compatible environment." Section 81: "Packet export includes reassembly and launch support... The user does not need to replay the entire agent history to reconstruct or view the artifact." `~/vivi/README.md`: "the system keeps a git diff of your work — even if the source was never committed to git, even if it was never in a repository at all... You can launch multiple copies of your web project in browser tabs, each on its own port."

**Marker.** Section 30: "The canonical marker is a folder named `.agentid` containing a nonce file." Metaform has this today; Rich's 2026-09-12 decision replaces the file with the base db record.

## Shape of the history unit, 2026-09-13, from Rich's words and the sources

Rich: this version "gives a solid git sidechannel so worktrees can be diffed even if they were not committed"; his iterative self-play workflow "produces some legitimately cool work when applied to a metaform"; "when 10 copies off of a base are created it would be nice to keep those 10 variations"; not the main function of the tool, which "has evolved a lot into a whole context management framework", but "a shame to lose".

What exists in the checkout: `workfolders.create` copies the source into its own git repository with a baseline commit, `workfolders.diff` reads the changes against that baseline whether or not the source was committed, `history.initialize` keys a base by commit or content digest, and `portable.export` carries the base. What is missing is the last step: collection applies and cleans a workfolder instead of keeping it.

The unit: each collected workfolder becomes a variant under its base, stored as the diff of its text plus whole copies of changed binaries, keyed by the base commit for a repository or the content hash for a folder; reconstruction is origin plus diff, checked by the per-file hashes; export is the base subfolder in full; the packet's menu reconstructs any variant or all of them to disk. Nothing else in the context framework changes.

## What the PongClock variants show, 2026-09-13

Rich pointed at `~/tempotrials/samples` (six variants) and `~/tempotrials/results/pong12` (twelve operations off one origin) with `~/tempotrials/work/PongClock-main` as the origin. Read-only.

- The origin is a small multi-file project: `index.html` of 486 bytes, `css/`, `js/`, `fonts/`, `webfont.js`. Every variant is one HTML file of 21 to 30 KB that shares two or three percent of its lines with the origin, and two to eight percent with any other variant. Rich: "these were major variations, total rewrites... that was the intent. I think it depends on the project size." So a diff off the origin is the whole file for a rewrite and a few lines for an edit; the rule produces the right thing either way and the packet compresses it.
- The result layout is TEMPO 0.5.x's: `results/pong12/000001/` to `000012/`, each holding the produced project (`pongclock.zip`, the whole tree with the font binary) and `producing.prompt.txt`, the prompt that made it. A variant is the artifact plus the prompt that produced it. The Metaform variant record carries the producing operation, run and prompt revision, for the same reason.
- The producing prompt, in short: renew, expand, and refine the game, and "Maintain this one thing: A continuously self-playing game whose visible ongoing state remains readable as the current time. Everything else remains mutable." One invariant, everything else free. That is what an iterative self-play workflow feeds a Metaform: the invariant is the Type's Encounter Function, the rest is the mutation space.

Rich, 2026-09-13, on storage: "small things under 3 MB we can keep intact, how about that; if the text portion is lower than 3 MB." As read: a variant whose changed text totals under 3 MB is stored intact, the changed text files whole, as a checkpoint stores them today; above 3 MB the changed text is stored as the diff off the origin; changed binaries are copied whole in both cases; unchanged files are never stored and come from the origin; reconstruction is the same either way and the per-file hashes check it.

## Rich, 2026-09-13, on the intake answer form and validation

> I would prefer the intake is live as objects are added; that's what I have said since day one. This has to work with any AI model someone might be using. Is freeform JSON reliable? I have seen it isn't, and if it isn't then workflows take longer and inference keeps retrying.

As read and answered: the intake is one `intake.put` per object, live as each lands, through the MCP tool with named arguments or through the CLI with named flags (`--element <address> --ef "<sentence>"`, `--join <receiver> <provider> "<purpose>"`, `--subtype <address>`), so the model never authors JSON; the final message carries nothing to parse. Each put checks its own few fields and records a note for what missed, never a rejection. With that, the jsonschema library is not needed at runtime: our schemas use `type`, `$ref`, `properties`, `items`, `required`, `additionalProperties` and a handful of `enum`, `const`, `minimum`, `anyOf`, `allOf`, `if`/`then`, `pattern`; a small checker of our own covers the subset, jsonschema stays as a dev-only reference in one parity test, and rpds-py, the compiled wheel, and the floor extraction from unit 2 go with it. Observed and not patched: a final answer wrapped in a fenced ```json block fails `json.loads` today and is kept as raw text.

Evidence: harness.py reads Codex's last message with `--output-last-message` and `json.loads` with raw text on failure; Codex's strict output-schema mode is deliberately not used because it rejects open-ended schemas; MCP sampling parses the model's text the same way; only the tool path guarantees JSON by protocol.
