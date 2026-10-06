# 08 Projects, working folders, origins and variants

This section defines how Metaform knows which project a folder or a server is working on. It also defines how Metaform keeps the history of an artifact: origins, sibling variants, reconstruction, export and import. It ends with clearing a project: removing what Metaform inferred about it and keeping everything else.
All of it lives in the Metaform home. The folder tables are in the base database, STORE-002. The rows are stored as STORE defines. This section adds what those records mean, how every surface resolves them, and the history records the other sections do not cover.

## Terms used in this section

- **Source location:** the folder a registered project describes, STORE-031.
- **Working folder:** the folder a CLI command or an MCP server runs in. It is a key in the base database and nothing more.
- **Origin:** the baseline a history starts from. For a repository it is one commit. For a folder outside any repository it is a full copy of its content.
- **Origin unit:** one origin together with every variant pinned to it.
- **Variant:** the result of one piece of work against an origin, stored as its changes against that origin.
- **Suffix:** the 16-bit extension that tells apart instances of the same origin that carry different provenance.

Where sources disagree, the latest decision is the design. Earlier readings that a builder might meet in old code or documents are noted only where that helps.

## Projects and working folders

### PROJ-001 A project is a registered source location with all its Metaform data in the home
- Requirement: A project names a source location, and every record Metaform keeps about that project lives in the Metaform home, never in the source location.
- What this means: Registering a project records its id, its source location and its target, STORE-031. The map, the layers, the history and the settings for the project all live under `~/.metaform`. The source location is read and is never written by Metaform. This holds for a repository and for any other folder, and for every worktree of a repository.
- Why: Every agent, in any folder or worktree, reaches the same data. A project never carries a copy of Metaform state that goes stale, gets committed by accident, or is picked up by a tool that scans the tree. A stale `.metaform/history/origin/` copy inside a repository once made a package scanner build old packages. Keeping nothing in the source location removes that failure for good.
- How it shows: After `metaform add project notes ~/notes` and any amount of work, `git status` in `~/notes` shows nothing Metaform created.
- Build: Registration also records the source kind, `repo` when the source location is inside a git working tree and `folder` otherwise. The kind is detected once at registration with `git -C <path> rev-parse --show-toplevel`. When git is not installed, the kind is `folder`. The kind is stored on the project record as a new column `source_kind TEXT NOT NULL CHECK(source_kind IN ('repo','folder'))`, plus `repo_root TEXT`, which is the toplevel for a repo and NULL for a folder. These columns extend STORE-002's `projects` table.
- Acceptance:
  - Registering a project, writing map records and collecting a variant leaves the source location's file list and contents unchanged, including hidden files.
  - A project inside a git working tree is recorded as `repo` with its toplevel. A plain folder is recorded as `folder`.
- Relates to: STORE-001, STORE-002, STORE-031, MAP-041, PROJ-010.
- Status: confirmed that everything stays global. The source kind columns are recommended.

### PROJ-002 A working folder is a key in the home, and every folder gets its own context
- Requirement: Every folder a command or server runs in is recorded in the base database's working-folder table, and that record holds the folder's context.
- What this means: The folder's context is its folder settings: `project`, `workflow` and `modules`, CLI-021. The folder path is only the key those settings are stored under. A worktree is a working folder like any other. So is a scratch folder outside every project. The table is the single place that answers which folders exist and what each one was working on.
- Why: Agents run in many folders, including worktrees created anywhere. The home must know each folder's context without writing a marker into it, and resuming after a restart must work by running `metaform` in the same folder.
- How it shows: An agent runs `metaform set --project notes` in `/tmp/work`, the machine restarts, and `metaform` in `/tmp/work` still reports project notes.
- Build: The `folders` row for a folder is written the first time a setting is stored for it, STORE-002. Reads never create rows. A folder's context is resolved by CLI-014 and PROJ-003.
- Acceptance: A folder that has never had a setting stored leaves no `folders` row after any number of reads.
- Relates to: STORE-002, CLI-014, CLI-021, PROJ-003.
- Status: confirmed.

### PROJ-003 A folder's project defaults to the project that contains it, and selection follows the settings pattern
- Requirement: A folder's project is the one selected in that folder with `set --project`. When nothing is selected, it is the registered project whose source location contains the folder. `unset --project` and `unset all` return the folder to that default.
- What this means: Inside a registered project, nothing needs setting, because the home already knows every project's path and shows the local project. From a folder elsewhere, a user or agent selects a project with `metaform set --project <id>`, and the home records that choice against the folder it was run from. Resetting returns the folder to its own project, which is the safe default. A folder outside every project with nothing selected has no project.
- Why: Selecting a project is ordinary configuration, visible and reversible like any setting, and needs no machinery of its own. The default comes from where the agent already is, so the common case needs no setup, and the way back to it is always the same command.
- How it shows:
  - In `~/notes/src`, `metaform` shows project notes with nothing set.
  - In `~/notes`, `metaform set --project metaform` switches that folder to metaform.
  - `metaform unset all` there returns it to notes, unless the project setting is glued.
- Build: The resolution is STORE-002's rule. Take the folder's effective stored `project` value by CLI-014. If there is none, take the registered project whose `path_key` is the deepest prefix of the folder's `path_key` on a path-segment boundary. If there is none of those either, the folder has no project. Glue on `project` behaves as for any setting.
- Acceptance:
  - In a subfolder of a registered project with nothing set, the project is that project.
  - After `set --project other` and `unset all`, it is that project again.
  - A folder outside every project with nothing set reports no project in status.
- Relates to: STORE-002, CLI-014, CLI-021, CLI-030, PROJ-004, PROJ-005.
- Status: confirmed. How an inherited value from a folder above a project's path interacts with the containment default is open question 1.

### PROJ-004 Selecting a project records the orchestrator's working folder, which is also how work resumes
- Requirement: When an orchestrator selects a project, the home tracks the folder the CLI was run from against that project, and every later run from that folder resolves to it.
- What this means: The global store does not need the project folder to hold anything. The selection record is the connection between where the agent works and what it works on. The same record carries the folder's workflow and command surface, so a whole working position is restored by running `metaform` in the same folder.
- Why: An agent restarted after a reboot or a context reset needs to find its work from where it stands. That must work without markers in the folder and across hosts.
- How it shows: The orchestrator runs `metaform set --project notes --workflow intake` in its session folder. After a restart, `metaform` in that folder shows project notes and workflow intake.
- Build: No new records. The selection is the folder's stored `project` setting, and the workflow and surface are its other folder settings, PROJ-002.
- Acceptance: Covered by PROJ-002 and PROJ-003's acceptance.
- Relates to: PROJ-002, PROJ-003, CLI-021.
- Status: confirmed.

### PROJ-005 Every surface resolves the project the same way, including a server started outside any project
- Requirement: The CLI and the MCP server resolve the project from their own working folder by PROJ-003, and an agent selects a project for a server's folder the same way it does on the CLI.
- What this means: A host starts the MCP server in some folder: the agent's folder, a fixed folder, or the user's home. The server is a working folder like any other. If that folder resolves to a project, the server serves it. If it does not, the agent selects one with the `set` tool, which stores the choice for the server's folder exactly as `metaform set --project` would. A host that always starts the server in the same folder keeps that selection across sessions. A single call can still name its project, MCP-025.
- Why: The server has no special rule to learn, so any host works: one that starts the server in the project, and one that starts it anywhere else. Selection by folder is the same mechanism the CLI uses, which keeps the two surfaces equal.
- How it shows: A desktop host starts the server in the user's home. Status over MCP reports no project and lists the registered ones. The agent calls `set` with `{"project": "notes"}`, and every later call in that host reads notes.
- Build:
  - At each call, the server resolves the folder it was started in, `os.getcwd()` at start, by PROJ-003. The resolution happens per call, so a selection takes effect on the next call.
  - A call that names `project` uses it for that call only, MCP-025.
  - A tool that needs a project, when none resolves, stops with `No project for this folder.` and `Next: metaform set --project <id>`. Over MCP, the same text is returned as the tool error.
  - Status, and the MCP server's instructions, list the registered project ids when the folder has no project.
- Acceptance:
  - A server started in a folder outside every project serves no project. After a `set` call naming a registered project, the next read returns that project's data.
  - A second server started in a registered project's folder serves that project without any call to `set`.
- Relates to: MCP-011, MCP-025, CLI-021, PROJ-003, BASE-028.
- Status: confirmed as the rule. The per-call resolution, the stop text and listing projects in status are recommended.

### PROJ-006 A worktree is its own working folder wherever it lives
- Requirement: A git worktree, inside the project folder or anywhere else, is a working folder with its own context, and it reaches the same project data as every other folder.
- What this means: An agent started in a worktree has that worktree as its working path. A worktree inside the project's source location resolves to the project by containment. A worktree created elsewhere resolves to the project once it is selected there, by the orchestrator or by the agent. Because all data is global, no worktree ever needs a copy of Metaform state.
- Why: Orchestrators put workers in worktrees so their changes stay apart. The worker must reach the same project knowledge wherever git placed the worktree.
- How it shows: A worker started in `~/notes/.worktrees/fix` sees project notes. A worker started in `~/notes-fix`, a sibling worktree, sees notes after `metaform set --project notes` is run there.
- Build: The worktree follows PROJ-003 with no special case. Whether a worktree outside the source location should default to its repository's project without being selected is open question 2.
- Acceptance: A worktree inside the source location resolves to the project with nothing set.
- Relates to: PROJ-002, PROJ-003, PROJ-017.
- Status: confirmed for worktrees as working folders with global data. Defaulting a sibling worktree is open.

### PROJ-007 A worker's own folder can carry a narrowed context while the orchestrator keeps its own
- Requirement: When the worker runs in a different folder from the orchestrator, the worker's folder can carry the workflow and narrowed command surface, so the orchestrator's own commands are never hidden.
- What this means: The command surface is a folder setting. Set on the worker's folder, it narrows only what the worker sees. The orchestrator's folder keeps the full surface. When the worker shares the orchestrator's folder, as subagents often do, the narrowing applies to that shared folder and the way back is the abort command, CLI-022.
- Why: Narrowing the surface steers workers. Doing it per folder avoids hiding the orchestrator's commands whenever the two work in different places.
- How it shows: The orchestrator starts a worker in a worktree and narrows that worktree's folder to `workflow,memory`. `metaform` in the worktree shows the narrowed surface, and `metaform` in the orchestrator's folder shows everything.
- Build: The narrowing is stored as the worker folder's `modules` and `workflow` settings. The orchestrator stores them for the worker's folder before the worker starts, by passing a folder noun to `set`: `metaform set --modules workflow,memory folder=<path>`. The noun applies to `set`, `unset` and `config --show`; the path is resolved to an absolute path and becomes that folder's settings key, PROJ-002. This is the closest thing Metaform has to a handle for a worker's job: the worker needs nothing passed to it, because its folder already carries its context.
- Acceptance: With `modules` narrowed on folder A only, a command outside the surface is refused in A and runs in the orchestrator's folder B.
- Relates to: CLI-021, CLI-022, PROJ-002, PROJ-006.
- Status: confirmed, including the `folder=<path>` noun on `set`.

## History: origins and variants

### PROJ-010 History is chassis data kept in the home
- Requirement: History and provenance are chassis functions. The chassis owns the history of each project, meaning its origins, variants, reconstruction, export and import, and keeps all of it in the Metaform home.
- What this means: History is data. The chassis owns data, import, export and query, so it owns history too, through the data access object that modules use, STORE-023. A workflow module that creates workfolders or worktrees and collects their results calls these operations. It never keeps history of its own.
- Why: History must be exportable and importable as a whole with the project, and it must work with no feature module enabled. Keeping it in the chassis means one implementation, used the same way by every module.
- How it shows: With every feature module disabled, `metaform list origins` and `metaform extract` still work.
- Build: The records are in PROJ-023, and the operations and commands in PROJ-024.
- Acceptance: With every feature module disabled, collecting a variant from a folder and extracting it produces the variant's files.
- Relates to: BASE-001, STORE-023, PROJ-023, PROJ-024.
- Status: confirmed that history and provenance are chassis functions and that the data is global. Provenance tracks exactly two things, one record per layer and the intermediary diffs, LAYER-010.

### PROJ-011 Every history operation uses the same artifact boundary
- Requirement: Capturing an origin, collecting a variant, reconstructing, comparing and exporting all work on the same set of files: the project's source location within its boundary.
- What this means: The boundary for a repository is the files git would track or offer to track. That is every tracked file plus every untracked file that is not ignored. Ignored files are outside. For a folder outside any repository, the boundary is every file under the source location. Within the boundary, Metaform keeps binary files, added files, removed files and renamed files. It keeps the executable bit as the one piece of file metadata. A rename is kept as a removal and an addition, and reconstruction produces the same result.
- Why: If capture and reconstruction disagree about what belongs to the artifact, a reconstructed variant is not the variant that was collected. That breaks the only promise history makes.
- How it shows: A variant that adds an image, removes a script and edits a text file reconstructs with exactly those three changes, and with nothing from the ignored build folder.
- Build: For a repository, the file list is `git ls-files --cached --others --exclude-standard` run in the folder being captured. For a folder, it is a walk of the tree. In both cases the `.git` folder is skipped. Paths are stored relative to the boundary root, with `/` as the separator on every system. Metaform writes no markers anywhere, so no Metaform file can enter the boundary, STORE-001.
- Acceptance:
  - A collected variant containing a changed binary, an added file, a removed file and a renamed file reconstructs byte-identical to the collected folder within the boundary.
  - An ignored file present in the collected folder is absent from the reconstruction.
- Relates to: PROJ-012, PROJ-016, PROJ-018.
- Status: recommended, carrying REQ-160. Whether ignored files are always outside is open question 11.

### PROJ-012 An origin records the commit it is based on
- Requirement: For a repository, the origin records the commit hash as its base, and every variant's diff goes off that commit. For a source outside any repository, the origin is a full copy of its content kept in the home.
- What this means: A repository already holds its commits, so the origin is the commit hash, and the commit's files are read from git when they are needed: for making diffs, reconstruction, comparison and export. Metaform keeps no copy of the commit. A folder with no repository has nothing to return to, so Metaform copies it at the moment the origin is established, and that copy is the base its diffs go off.
- Why: The commit already anchors a repository's baseline exactly, so a second copy only costs space. A plain folder changes in place and would lose its baseline without a copy.
- How it shows: Establishing an origin for notes records the commit hash and copies no files. Establishing one for a photo folder copies the folder into the origin unit.
- Build:
  - For a repository, the origin records the full commit hash of `HEAD` at the moment it is established. Its files are read with `git archive <commit>` when needed.
  - If the working tree is dirty at that moment, the commit is still the origin, and the uncommitted changes are collected at once as the unit's first variant, PROJ-017. Dirty means what `git status --porcelain` reports for the project's folder, so a file git calls unchanged, such as one whose line endings git normalizes, never makes a first variant.
  - For a folder, the boundary's files are copied to `origin/` in the unit's payload folder, PROJ-023.
- Acceptance:
  - A repository origin stores its commit hash and no file payload.
  - A folder origin's `origin/` holds exactly the boundary's files, and later changes to the source do not change it.
- Relates to: PROJ-011, PROJ-013, PROJ-016, PROJ-018, PROJ-023.
- Status: confirmed that a repository origin records the commit hash as its base and diffs go off that commit. The folder copy is as previously settled. Handling a dirty working tree is recommended.

### PROJ-013 Origin identity has a long form and a short form
- Requirement: Every origin has a full digest, a long id `mform_sha_id` and a short id `mform_id`, both built from the digest and a 16-bit suffix.
- What this means:
  - The full digest `origin_sha256` is the SHA-256 of the origin's canonical content manifest.
  - `mform_sha_id` is the digest's 240 most significant bits followed by the 16-bit suffix, 64 hexadecimal characters.
  - `mform_id` is the digest's 48 most significant bits followed by the same suffix, 16 hexadecimal characters.
  - Neither form has an underscore. The long form names the unit's payload folder. The short form is what people and agents see. The full digest and, for a repository, the full commit id are kept as fields.
  - The suffix tells apart instances of the same content that carry different provenance. It is not a collision counter.
- Why: The digest identifies the content wherever it came from, so the same baseline is recognized on any machine. The suffix lets two lineages of the same content live side by side without either overwriting the other.
- How it shows: `metaform list origins` shows each origin's `mform_id`, its project, its kind and its commit or source path.
- Build:
  - The manifest lists every file in the boundary, sorted by path. Each line is `<path>\t<sha256 of the bytes>\t<mode>`, where mode is `755` for an executable file and `644` otherwise. Lines are separated by `\n` with a trailing `\n`, and the whole is encoded as UTF-8.
  - The first instance of a digest in a project gets suffix `0000`, and each new instance in that project takes the next unused value in hex. Two projects are two folders, PROJ-026, so the same content in each is `0000` in each.
  - The older forms `<digest>_0000` and a 12-hex prefix plus `_FFFF` are never written.
- Acceptance:
  - Two origins captured from identical content on two machines have the same `origin_sha256`.
  - `mform_sha_id` is 64 hex characters, and `mform_id` is 16 hex characters with the same last four characters.
- Relates to: PROJ-012, PROJ-014, PROJ-021, PROJ-023.
- Status: confirmed for the two forms and the suffix. The manifest format and the first suffix value are recommended, open question 7. Rich, 2026-09-30: the suffix counts within a project; two projects are two paths, so their origins cannot conflict.

### PROJ-014 An origin is never overwritten, and a new baseline starts a new origin unit
- Requirement: A retained origin never changes. Moving the baseline to a new commit or new content, called re-anchoring, creates a new origin unit, and the earlier unit and its variants stay exactly as they were.
- What this means: A different commit is a different origin. Re-anchoring is an explicit operation. Nothing re-anchors implicitly, and no variant ever becomes the baseline for another variant except through re-anchoring. The suffix is not used for re-anchoring. A new baseline has a new digest, and the suffix belongs to import, PROJ-021.
- Why: Every variant is a diff against its origin. Changing the origin in place would silently corrupt every variant pinned to it. Keeping old units intact keeps every past result reconstructable.
- How it shows: After re-anchoring notes to a newer commit, `metaform list origins notes` shows both origins, and variants of the old one still extract.
- Build: `metaform add origin [<project>]` establishes an origin from the project's current state, PROJ-012. Its content is the repository's `HEAD` commit, or the folder's current content. If an origin with the same digest already exists for the project, the command reports it and creates nothing. The project's selected origin, the one new variants attach to, is the most recently established one unless a later decision says otherwise.
- Acceptance:
  - Re-anchoring leaves every file and record of the earlier unit byte-identical.
  - Both units list, and a variant of the earlier unit still reconstructs.
- Relates to: PROJ-012, PROJ-013, PROJ-015, PROJ-024.
- Status: confirmed, carrying REQ-162. The command form and the selected-origin rule are recommended.

### PROJ-015 Variants of one origin are siblings
- Requirement: Every variant is stored against its origin and never against another variant, so many variants pinned to one origin stay independent siblings. Variants are intermediary checkpoints between real commits, and they relate only to worktrees and agent work.
- What this means: This covers mutation experiments that produce many variants from one commit or one folder, for example ten copies made from one base. Running operations one after another does not turn an earlier result into a later one's baseline. A result becomes a baseline only by re-anchoring.
- Why: Iterative and self-play workflows produce many variations from one base, and each is worth keeping. Storing each against the origin keeps every one reconstructable on its own, whatever happens to the others.
- How it shows: Ten collected variants of one origin each extract on their own, in any order, to the same result as when they were collected.
- Build: A variant records only its origin unit, never a parent variant.
- Acceptance: Deleting nothing and extracting variant 7 alone reproduces it without reading any other variant's payload.
- Relates to: PROJ-014, PROJ-016, PROJ-017.
- Status: confirmed, including that variants are intermediary checkpoints between real commits for worktrees and agent work only.

### PROJ-016 A variant stores only what changed against its origin
- Requirement: A variant stores the files that differ from its origin and nothing else. Changed text is kept whole when the variant's changed text is small, and as a diff against the origin when it is large. Changed binaries are always kept whole.
- What this means: Unchanged files are never stored; they come from the origin. When the total size of a variant's changed text files is under 3 MB, those files are stored whole. At 3 MB or more, each changed text file is stored as a diff against its origin version. A binary file that changed is copied whole, because a binary diff is not needed. A removed file is recorded as removed. Every stored file carries the SHA-256 of its full new content, so reconstruction can be checked.
- Why: Most variants are small, and whole files are the simplest and safest record of them. Large text variants stay small as diffs. Binaries such as images and fonts are copied, because diffing them costs more than it saves.
- How it shows: A variant that edits two source files and swaps a font stores two text files and one font file. A variant that rewrites a large generated file stores one diff.
- Build:
  - A file is text when its bytes decode as UTF-8 and contain no NUL byte; otherwise it is binary.
  - The diff is made with git diff, even when the source is not a repository: `git diff --no-index --no-color --no-ext-diff --full-index <origin file> <new file>`, run on the origin version and the collected version of one file. The output is stored as `variants/<variant id>/diffs/<path>.diff`, preceded by one line `base_sha256 <origin file hash>`.
  - Reconstruction applies the stored unified diff with Metaform's own Python code, so extraction needs no git, PROJ-018.
  - Applying a diff whose `base_sha256` does not match the origin file is an error, never a guess.
- Acceptance:
  - A variant with 1 MB of changed text stores whole files. The same edit on a 4 MB file stores a diff, and both reconstruct byte-identical.
  - A changed binary is stored whole and reconstructs byte-identical.
  - A file stored with a tampered hash fails reconstruction with an error naming the file.
- Relates to: PROJ-011, PROJ-015, PROJ-018, PROJ-023.
- Status: confirmed for diffs off the origin made with git diff, whole binaries, and keeping small text whole with 3 MB as the line. Measuring the 3 MB on the variant's total changed text, the text test, the stored diff layout and applying it in Python are recommended.

### PROJ-017 Collecting a worktree or workfolder keeps it as a variant, committed or not
- Requirement: The work in a worktree or workfolder made from an origin can be collected as a variant of that origin, whether or not its changes were committed.
- What this means: Metaform acts as a side channel for git. It diffs what is in the folder against the origin, so uncommitted work is kept. Collecting keeps the variant and never applies it to the project. When the worktree is collected, Metaform either makes the diff and leaves the worktree in place, or makes the diff and removes the worktree; both are options. Each variant carries one provenance record saying how it was produced.
- Why: Work produced in many worktrees would be lost when they are cleaned up, and much of it is worth keeping and comparing. Diffing against the origin, not against the worktree's own commits, captures the work however the agent left it.
- How it shows: An orchestrator runs ten workers in ten worktrees off one commit, then collects each folder. `metaform list variants` shows ten variants, each with the workflow and prompt that produced it.
- Build:
  - `metaform add variant <folder> [origin=<mform_id>]` reads the folder's boundary, PROJ-011, compares it file by file with the origin, and stores the differences, PROJ-016. The origin defaults to the project's selected origin, PROJ-014.
  - By default the folder is left in place, untouched. With `remove=true`, the folder is removed after the variant is stored and verified against its recorded hashes: a git worktree through `git worktree remove`, a workfolder Metaform created by deleting it. `remove=true` on any other folder is refused with `Next: metaform add variant <folder>`.
  - The provenance record has the same fields as a layer's, LAYER-010: module and workflow, prompt, model, role and blinded. Any field the collector did not supply is empty. Variant ids are sequential within their unit, starting at `v000001`.
- Acceptance:
  - Collecting a worktree with uncommitted edits stores those edits.
  - Without `remove=true`, the collected folder is byte-identical before and after collection.
  - With `remove=true`, the worktree is gone after collection, and the variant extracts byte-identical to what the folder held.
  - A variant's provenance reads back with the fields given at collection.
- Relates to: PROJ-011, PROJ-015, PROJ-016, PROJ-023, LAYER-010.
- Status: confirmed that collected worktrees are kept as variants, including uncommitted work, and that collection either removes the worktree or leaves it in place. The command, the id form and reusing the layer provenance fields are recommended.

### PROJ-018 Any variant, several, or all reconstruct with Python alone
- Requirement: One variant, several, or every variant of an origin unit can be reconstructed into external folders by a CLI command, using Python alone, with no git and no access to the original repository.
- What this means: Reconstruction starts from the origin's files, applies the variant's changes, and checks every file against its recorded hash. It works on the machine where the history was made and from an exported wheel anywhere else. The exported unit carries the origin's files for this reason, PROJ-020.
- Why: Reconstruction is the point of keeping history. A result is useful only if it can be brought back out to disk, anywhere, without the tools or the repository that made it.
- How it shows: `metaform extract v000003 ~/out/v3` writes variant 3 to `~/out/v3`. `metaform extract all ~/out` writes every variant of the selected origin, each into its own subfolder named by variant id.
- Build:
  - `metaform extract <variant id>... | all <folder> [origin=<mform_id>]`.
  - Each variant goes into `<folder>/<variant id>/`, or directly into `<folder>` when exactly one variant is named. A target folder that exists and is not empty is refused, with `Next: metaform extract <variant> <empty folder>`.
  - Locally, the origin's files come from `git archive` for a repository origin, or from `origin/` for a folder origin. From a wheel, they come from the exported origin copy.
  - The executable bit is restored where the system supports it.
- Acceptance:
  - In an environment with no git and without the source repository, a variant extracted from an exported wheel is byte-identical to the collected folder within the boundary.
  - `extract all` produces one folder per variant.
- Relates to: PROJ-016, PROJ-020, PROJ-024, BASE-042.
- Status: confirmed, carrying REQ-163. The command form is recommended.

### PROJ-019 Web variants can be served side by side
- Requirement: Variants of a web artifact can be launched together, each served on its own port, so they open side by side in browser tabs.
- What this means: Serving is the web case of reconstruction. Each chosen variant is reconstructed and served from its own folder on its own local port. This is separate from Metaform's own web interface, which is one instance on one fixed port.
- Why: Comparing web variants means seeing them run, and many variants from one origin are compared at once.
- How it shows: Serving three variants prints three local addresses, one per variant.
- Build: Serving belongs to the web module, which uses the chassis reconstruction of PROJ-018, pending D44. Each variant gets an OS-assigned free port on 127.0.0.1, and the command prints `<variant id>  http://127.0.0.1:<port>/` per variant.
- Acceptance: Two served variants answer on two different ports with their own content.
- Relates to: PROJ-018, D44.
- Status: confirmed as wanted. The owning module and the port choice are recommended, open question 8.

### PROJ-020 The export unit is a whole origin unit, delivered as a wheel
- Requirement: Exporting history exports a whole origin unit, meaning the origin and every variant pinned to it, as a wheel whose own CLI reconstructs any of its variants.
- What this means: The structure of an origin unit is what makes it portable. The exported wheel carries the origin's files, extracted from git for a repository origin, and every variant's stored changes. It also carries the manifest and hashes, and the chassis code that runs `extract` and `list variants`. It runs anywhere Python runs, with nothing installed. Text stays small because variants hold only their changes.
- Why: Results made in one place must be viewable and usable in another, including an uploaded wheel in a hosted code environment. No agent history has to be replayed to get the artifact back.
- How it shows: `metaform export origin=<mform_id> file=unit.whl`, then on another machine `python unit.whl extract all ~/out`.
- Build: The wheel is built as BASE-041 builds a chassis wheel. The origin unit's payload goes under `metaform_export/<mform_sha_id>/` inside it, with the unit's records as the JSON of STORE-027.
- Acceptance: A wheel exported from a repository origin with three variants reconstructs all three on a machine with no git, byte-identical within the boundary.
- Relates to: PROJ-018, PROJ-023, STORE-027, BASE-041, BASE-042.
- Status: confirmed that the export unit is a whole origin unit, the export format is a wheel, and reconstruction runs from it. How this export relates to STORE-027's project export is open question 5.

### PROJ-021 Import never loses data
- Requirement: An import that would lose any local data or provenance creates a new instance with the next suffix and keeps both. There is no warning or question, and the result names each identity and location so the agent can tell the user.
- What this means: When incoming history fully includes the local history, the local unit advances to it. When it does not, the incoming unit is stored beside the local one under the next unused suffix. Both stay accessible.
- Why: History and provenance are the record of how results came to be. Losing them silently is the one failure an import must never have. Keeping both costs little storage, and nothing needs deciding at import time.
- How it shows: Importing a unit whose history diverges from the local one prints both `mform_id`s, and `metaform list origins` shows both.
- Build: Incoming history includes local history when every local variant id and payload hash is present in the incoming unit, and every local record is present unchanged. Otherwise the incoming unit takes the next suffix. The import runs in one transaction and returns `{"mform_id", "path", "kept_local": true|false}` for each unit it wrote.
- Acceptance:
  - Importing a divergent unit leaves the local unit byte-identical and adds a second unit with the next suffix.
  - Importing a unit that includes the local one leaves one unit.
- Relates to: PROJ-013, PROJ-020, STORE-027.
- Status: confirmed, carrying REQ-165. The inclusion test and the result shape are recommended. This record conflicts with the later confirmed rule that everything exported carries its unique id and importing something that already exists does nothing, STORE-027: a unit arriving with an `mform_id` already present would, by that rule, do nothing, where this record keeps both or advances the local unit. Which rule governs history units is open question 13.

### PROJ-022 Pending physical work travels with continuation
- Requirement: When work is handed on to continue elsewhere, the working files it needs travel with it.
- What this means: A job handed on without its workfolder content, staged inputs, generated outputs and needed binaries is not complete.
- Why: A worker that receives a prompt but not the files it refers to cannot continue the work.
- How it shows: Deferred.
- Build: Deferred. Until it is specified, the working files of a job travel as a collected variant, PROJ-017, exported with its unit, PROJ-020.
- Acceptance: Deferred.
- Relates to: PROJ-017, PROJ-020.
- Status: deferred, carrying REQ-164.

### PROJ-023 History records and payload layout
- Requirement: Origins and variants are rows in the project's store, and their file payloads live in the project's folder in the home under the origin unit's long id, PROJ-026.
- What this means: Records follow the one-row-per-thing rule, STORE-004. Payload files are too large for rows and live on disk, referenced from the rows.
- Why: Rows give direct reads of which origins and variants exist and how each was made. Files on disk keep large payloads out of SQLite and copy cleanly into an export.
- How it shows: `origins/<mform_sha_id>/` in the project's folder, PROJ-026, holds `origin/` for a folder origin, and `variants/<variant id>/` for each variant. Each project's units are its own, so the same content in two projects is `0000` in each, and the next suffix is taken only on a conflict inside one project, PROJ-013 and PROJ-021.
- Build:

  ```sql
  CREATE TABLE origins(
    mform_sha_id  TEXT PRIMARY KEY,       -- PROJ-013, 64 hex
    mform_id      TEXT NOT NULL UNIQUE,   -- 16 hex
    origin_sha256 TEXT NOT NULL,
    suffix        TEXT NOT NULL,          -- 4 hex
    kind          TEXT NOT NULL CHECK(kind IN ('repo','folder')),
    commit_id     TEXT,                   -- full commit id for a repo origin
    source_path   TEXT NOT NULL,
    established   TEXT NOT NULL           -- ISO 8601 UTC
  );
  CREATE TABLE variants(
    mform_sha_id TEXT NOT NULL REFERENCES origins(mform_sha_id),
    variant_id   TEXT NOT NULL,           -- v000001 onward
    collected    TEXT NOT NULL,           -- ISO 8601 UTC
    source_path  TEXT NOT NULL,           -- the folder collected
    module TEXT, workflow TEXT, prompt TEXT, model TEXT, role TEXT, blinded INTEGER,
    PRIMARY KEY(mform_sha_id, variant_id)
  );
  CREATE TABLE variant_files(
    mform_sha_id TEXT NOT NULL,
    variant_id   TEXT NOT NULL,
    path         TEXT NOT NULL,           -- relative, '/' separators
    change       TEXT NOT NULL CHECK(change IN ('added','modified','removed')),
    storage      TEXT CHECK(storage IN ('whole','diff')),  -- NULL when removed
    sha256       TEXT,                    -- of the full new content; NULL when removed
    mode         TEXT,                    -- '755' or '644'; NULL when removed
    PRIMARY KEY(mform_sha_id, variant_id, path),
    FOREIGN KEY(mform_sha_id, variant_id) REFERENCES variants(mform_sha_id, variant_id)
  );
  ```

  A variant's payload is `variants/<variant id>/files/<path>` for whole files and `variants/<variant id>/diffs/<path>.diff` for diffs. A variant's rows and payload are written in one step: the payload goes to a temporary folder in the same unit and is renamed to `.pending-<variant id>` inside the transaction that writes the rows, the rows are committed, then the folder is renamed into place. A read that finds the rows and a pending folder finishes the rename, and a folder left for the next variant id by an interrupted write is cleared before it is used. A crash leaves either no variant or a complete one.
- Acceptance: A collection killed partway leaves no variant rows and no `variants/<id>/` folder.
- Relates to: STORE-003, STORE-004, STORE-006, PROJ-013, PROJ-016, PROJ-017.
- Status: recommended. The folder name `origins` is recommended.

### PROJ-024 History commands
- Requirement: The chassis provides these history commands, in the verb and noun grammar, CLI-001.
- What this means:

  | Command | Does |
  |---|---|
  | `metaform add origin [<project>]` | Establishes an origin from the project's current state, PROJ-012 and PROJ-014. |
  | `metaform list origins [<project>]` | One line per origin: `mform_id`, kind, commit or source path, established time, variant count. |
  | `metaform add variant <folder> [origin=<mform_id>]` | Collects a folder as a variant, PROJ-017. |
  | `metaform list variants [origin=<mform_id>]` | One line per variant: id, collected time, source path, workflow. |
  | `metaform extract <variant id>... \| all <folder> [origin=<mform_id>]` | Reconstructs, PROJ-018. |
  | `metaform export origin=<mform_id> [file=<file>]` | Writes the unit as a wheel, PROJ-020. |
  | `metaform import <file>` | Imports a unit wheel or a project document. For a unit it applies PROJ-021; for a project document, STORE-027. |

- Why: History uses the same grammar and the same data access object as everything else, so it needs nothing new to learn and works the same way over MCP.
- How it shows: The table.
- Build: The data access object gains `add_origin`, `origins`, `add_variant`, `variants`, `extract` and `export_unit`, with the inputs and outputs above. Each command's tool follows BASE-036 and MCP-003: `add_origin`, `list_origins`, `add_variant`, `list_variants` and `extract`, listed and callable while the chassis is on the folder's command surface, like the chassis commands on the command line, CLI-022; they are not among the tools that always run, MCP-004. Without `origin=`, a command uses the project's selected origin, and a project with no origin stops with `Next: metaform add origin`. The rows are in the project's history database, Q53.
- Acceptance: Covered by the records each command names.
- Relates to: CLI-001, CLI-031, STORE-023, PROJ-012 to PROJ-021.
- Status: recommended.

## Clearing a project

### PROJ-025 Clearing a project removes its metaforms and its reports, and keeps everything else
- Requirement: `metaform clear project [<project>] --confirm` removes every metaform of the project with its store, and the project's report, feedback and shape files, and keeps the project's registration, its folder and every file in it, its folder settings, and its history of origins and variants.
- What this means: After a clear the project is registered and empty, as it was the moment it was registered. It has no metaform until the next intake, or anything else that writes to the project, creates `main` again, STORE-041. The report, feedback and shape files are about the metaforms they were written against, so they go with them. History is the record of the artifact itself, not of Metaform's reading of it, so it stays. Nothing in the project's folder is touched, PROJ-001.
- Why: A project's map is taken again from nothing whenever what Metaform inferred about it is no longer wanted, for example after the intake procedure improves, MAP-045. Deleting the home, or the project's folder in it by hand, takes the registration, the settings and the history with it, which is a different act from clearing what Metaform inferred; a clear keeps what the person set up and removes only the inference. It is reached where the person sees the data, on the command line and on the page, VIEW-019.
- How it shows: `metaform clear project` in a project's folder prints what it will remove and stops. The same command with `--confirm` removes it and prints what it removed. `metaform` then shows `Metaform: none yet`, and `metaform list origins` lists the same origins as before.
- Build:
  - `clear` is a chassis verb, CLI-001, with the noun `project` and an optional project id, resolved as every chassis command resolves it, PROJ-003. It joins `RESERVED`, BASE-014, and the table of CLI-031.
  - It is a caution command, BASE-013 and CLI-018. Without `--confirm` it raises `Stop` with the caution `Clearing <project> removes <metaforms> and <reports>. Its registration, folder, settings, origins and variants stay.` and Next `If you are sure: metaform clear project <project> --confirm`. `<metaforms>` names the metaforms in the order they were created: `no metaforms`, `one metaform, main, with its store,` or `two metaforms, main and fresh, with their stores,`. `<reports>` is `no report files`, `one report file` or `two report files`.
  - Every count a person reads is written properly: `no` for none, the word for one to nine, the digits from 10, and the noun singular for one and plural otherwise. A list of names reads `main`, `main and fresh`, `main, fresh and draft`.
  - With `--confirm`: in one transaction of the project's `project.sqlite3` the project's `active_metaforms` and `metaforms` rows go, then each `<name>.metaform.sqlite3` and `reports/` in the project's folder, PROJ-026, are removed; the rows in the metaforms' stores go with the stores. The `projects` row, the `folders`, `settings` and `glue` rows, `history.sqlite3` and `origins/` in the folder are untouched. Output: `Cleared <project>: <metaforms> and <reports>. Its registration, folder, settings, origins and variants stay.`, where `<metaforms>` is `no metaforms`, `one metaform, main,` or `two metaforms, main and fresh,`.
  - A file or folder under those two folders that cannot be removed, such as a store a running web GUI holds open on Windows, or a file whose folder the person may not write to, stays on disk, and the command says so; it never reports a clear it did not finish. The metaform rows are removed either way. Each path that could not be removed is named with the system's reason, and a folder is named only when nothing inside it is, so each thing left is named once. After the Cleared line the command line prints `Not removed, still on disk:`, one line per path, `  <absolute path>: <reason>`, and `Next: Close any program that has it open, such as a running web GUI, or fix its permissions, then run metaform clear project <project> --confirm again.`, with `them` and `their` for more than one path. Running it again removes what was left, because it removes the two folders whole whatever the rows say. The exit code is 0: the project is cleared as far as Metaform reads it, and what is left is named.
  - The home notes that the project's metaforms changed, so the chassis fires `map.changed` with no metaform id when the command ends, VIEW-018, and an open page follows without a reload.
  - Over MCP the command is the tool `clear_project`, on the surface while the chassis is, like the history tools of PROJ-024, taking `confirm` and `project`. Without `confirm` true it returns the caution and `Next: If you are sure: call clear_project with confirm true`, MCP-006. With it, the result is `{"project": <id>, "metaforms": [<names>], "reports": <m>}`. When anything could not be removed, the result also holds `"not_removed": [{"path": <absolute path>, "reason": <the system's reason>}, ...]` and one notice, `where` `not_removed`, saying that it could not be removed and is still on disk, and what to do, ending `then call clear_project with confirm true again.`; `is_error` stays false, BASE-044.
  - On the web GUI it is the header's Clear project action, VIEW-019: the page shows this caution from `GET /api/clear-preview`, asks on the page, and clears through `POST /api/clear-project` with `confirm` true, which calls the same `clear_project` and is refused without `confirm` true as the command is without `--confirm`. It answers with the same fields as the tool, the Cleared line as `said`, and, when anything could not be removed, `not_removed` and the tool's notice ending `then use Clear project again.`.
- Acceptance:
  - Without `--confirm`: exit 2, nothing changed, and the caution names each metaform and the report count.
  - With `--confirm`, on a project with two metaforms, a memory item, a report file, an origin and a variant: `list metaforms` lists none, the metaform folders and the report files are gone, `list origins` and `list variants` answer as before, the registration and the folder's `project` setting stand, and the project folder's files are unchanged. A write to the project then creates `main` again.
  - A module subscribed to `map.changed` hears `{"project": <id>, "metaform_id": null}` once for the command, and once for the page's clear, VIEW-018.
  - Over MCP, `clear_project` without `confirm` returns `is_error` true with the caution and one Next line and changes nothing; with `confirm` true it clears; the tool is absent when the surface excludes the chassis.
  - The caution and the output read `no metaforms`, `one metaform, main, with its store,` and `two metaforms, main and fresh, with their stores,`, and `no report files`, `one report file`, never `(s)`.
  - With a report file that cannot be removed, made so on Linux and macOS by taking write permission off its folder and on Windows by holding it open: the command exits 0, the metaform rows are gone, the file is still on disk, and the output names that file alone, with its reason, and the Next line; over MCP the result names it in `not_removed` with one notice. Running the clear again once the file can be removed removes it.
  - On the web GUI, VIEW-019's acceptance.
- Relates to: PROJ-001, PROJ-003, PROJ-024, STORE-041, BASE-013, BASE-014, CLI-001, CLI-018, CLI-031, MCP-006, VIEW-011, VIEW-018, VIEW-019.
- Status: confirmed, 2026-09-13, for clearing a project's Metaform data, from the command line and from the page, so the intake starts again from nothing, keeping the project's registration, its folder and its files. Recommended, pending Rich: that history and folder settings stay and that report files go with the metaforms; that what could not be removed is named, and that counts are written as words, 2026-09-27; the words for one to nine, the wording of the Next line and exit 0.


### PROJ-030 A clear backs the project up first, and a backup is brought back by one command

- Requirement: Clearing a project saves what it is about to remove as a backup before it removes anything, and tells the person the backup's name and the one command that brings it back. `metaform restore project [<project>] [<backup>]` brings a backup back, the newest when none is named, and `metaform list backups [<project>]` lists them, the newest first. When the backup cannot be made, nothing is cleared.
- What this means: A backup holds what a clear removes, PROJ-025: every metaform of the project with its store, which of them was active, and the report, feedback and shape files. It is named by the moment it was made. Restoring puts the project back as it was at that moment. A project that holds metaforms or reports when a backup is restored is cleared first, which backs up what it holds, so a restore loses nothing either. A project with nothing to remove makes no backup. Backups are kept until a person removes them.
- Why: A map costs an intake to make, and answers, tasks and knowledge layers are added to it by hand afterwards, so what a clear removes cannot be made again by running the intake. A clear that cannot be undone makes every clear a risk, and people then avoid clearing when they should start fresh, as after the intake procedure improves, MAP-045. Backing up first, by the clear itself and not by a step the person must remember, means no clear is ever the loss of a map. It stops when the backup cannot be made because a clear without its backup is the loss this record exists to prevent, and the person would not know until they needed it.
- How it shows: `metaform clear project --confirm` prints what it removed, then `Backed up as 20260929T071500Z.` and `To bring it back: metaform restore project proj`. That command prints `Restored proj from 20260929T071500Z: one metaform, main, and one report file.`, and the map reads as it did.
- Build: `home.backup_project`, `home.backups` and `home.restore_project`; `home.clear_project` calls the first. A backup is the folder `<home>/backups/clear/<project>/<name>/` holding `metaforms/`, `reports/` and `rows.json`, the project's rows of the metaforms table and the id of the active one. A store is copied through SQLite's own backup, so a store another program holds open is copied whole. The name is the time in UTC as `YYYYMMDDTHHMMSSZ`, with `-2` and so on added when two are made in one second. The clear's result carries the backup's name, over MCP and to the web GUI as well, VIEW-019.
- Acceptance: After a clear the backup folder holds the stores and the report files the project had. `restore project` brings back the metaforms by name with the same one active, and a read of the map returns what it returned before the clear. Restoring over a project that holds a metaform backs that one up first. A clear of a project with nothing to remove makes no backup. With the backups folder not writable, the clear stops with the reason and the project still has its metaforms.
- Relates to: PROJ-025, STORE-041, MAP-045, VIEW-019, BASE-044.
- Status: asked for by Rich 2026-09-29: the clear backs it up and allows restoration easily, telling the user. The names, the place and restoring over a project that holds data are recommended.

### PROJ-031 An empty project is taken off the list by one command, and nothing of it is deleted

- Requirement: `metaform remove project [<project>] --confirm` takes a project off the list of projects: its registration goes, and the folder settings that select it. Only an empty project is removed, one with no metaforms and no report files; a project that holds any stops with what it holds and the next step to clear it, since a clear backs it up first, PROJ-030. Nothing in the home is deleted, and the project's own folder and files are never touched. Without `--confirm` it does nothing and says what it would do. The web GUI's Administration menu has Remove project, VIEW-019.
- What this means: A clear, PROJ-025, empties a project and keeps its name so an intake can start again; a remove then takes the name off the list. The backups the clears made and the project's history stay in the home, so registering the same id again brings them back into reach and `metaform restore project` can restore one.
- Why: Projects registered for trial runs stay listed after they are cleared, in `metaform list projects`, in status and on the web GUI, and nothing took them away, so the list only grew. A remove that deleted what it removed would lose a map without a backup; removing only an empty project, after the clear has backed it up, and deleting nothing, means no remove is ever that loss.
- How it shows: `metaform remove project old` on a project that holds a metaform stops with `old holds one metaform, main, and no report files. Only an empty project is removed; clearing it backs it up first.` and `Next: metaform clear project old --confirm`. Once cleared, it stops with the caution and `Next: If you are sure: metaform remove project old --confirm`; with `--confirm` it prints `Removed old. Its folder and files were not touched.`, and `metaform list projects` no longer lists it.
- Build: `home.not_empty`, `home.removal_caution` and `home.remove_project`, public names of the base, BASE-004. `remove_project` refuses a project that is not empty with what `not_empty` says, so no caller can skip the check, and otherwise deletes the project's rows of the projects, metaforms and active_metaforms tables and the folder settings whose `project` is it, and nothing on disk. The web GUI calls the same through `/api/remove-preview` and `/api/remove-project`, the second only with `confirm` true. It is not served as an MCP tool.
- Acceptance: A project with a metaform or a report file is not removed and nothing changes. An empty project, after the remove, is not listed, a folder that selected it selects no project, its folder in the home and its backups are still there, its own folder holds the files it held, and after registering the same id again its backups are listed. Without `--confirm` nothing changes. An unregistered id stops with `Next: metaform list projects`.
- Relates to: PROJ-025, PROJ-030, VIEW-019.
- Status: asked for by Rich 2026-09-30: clearing never removes the names, and the list grows; only empty projects can be removed, because a clear backs the project up. The command's name, its wording, deleting nothing and not serving it as a tool are recommended.

### PROJ-026 A project's folder in the home holds everything of the project

- Requirement: Each project has one folder in the home, and everything Metaform keeps for that project is inside it: its metaforms, its reports, its history with every origin and variant, its registration and target, which of its metaforms is active, the settings stored for its folders, and the prompt versions its layers were made from. The home's base database holds the list of projects and nothing a project needs in order to be read.
- Layout: the project's folder is named by the full path of its source with each separator replaced, followed by a number, `001` for the first. Inside it:
  - `.metaform/`, which holds the provenance and nothing else, and is never changed once written. No diff and no work is kept in it.
  - `origin/`, the backup of the source as it was at the commit: the source alone, PROJ-029, with none of git's files and nothing built.
  - one folder for each diff of work, named by the first bits of the commit the diff is taken from, 48 at least, in hex, followed by three or four hex characters that number the diffs off that commit, such as `fabba167bafe0001`. It holds `changes.diff`, the diff of the text between the origin and the work; `files/`, a whole copy of each binary file that differs from the origin's; and `removed.txt`, the files the work no longer has. A binary file that did not change is not copied, and no binary file is ever written as a diff. A file is text when it reads as UTF-8 and holds no zero byte.
  - the project's databases and its other data.
  A file in the folder states the source's real path, since replacing separators loses which were separators; the lookup from a working folder reads that file and never trusts the name alone. A source with no commits is keyed by a hash of its content in place of the commit.
- What this means: A project is carried by copying its folder. A zip of the folder is the whole project, PROJ-027, and unpacking it in another home and registering it gives the project back as it was. Nothing of one project is kept in another project's folder or in a file shared between projects. Nothing is written into the project's own source folder, STORE-001.
- Why everything is tied to a commit: a diff means something only against the exact source it was taken from. Naming its folder by that commit makes the tie impossible to lose, and work done between commits, in a worktree no one committed, is still kept as a diff, so it survives a cleanup or an agent that stopped. The diff compares two folders, so the worktree need not be a checkout.
- Why binary files are kept whole: a diff of a binary file cannot be read by a person and is applied correctly only by the tool that made it, so it ties the packet to that tool. A whole copy is the file, usable as it is, and keeping it only when it differs from the origin's costs nothing for the files that did not change.
- Why the origin is kept: a diff alone is half of the work. With the origin beside it, every diff in the folder can be expanded into the complete work it stands for, by anyone, without the repository it came from.
- Why: When one folder is one project, a person sees what Metaform holds for a project in one place, and moves or removes it without touching any other. Carrying a project then needs no special code that could leave something out, because the copy is the export. And what is shared between projects is where a fault in one reaches another; with nothing shared, it stays where it began. This follows the pattern of Tempo, where each source had its own folder holding all of its data.
- How it shows: Zipping `projects/<id>/` in one home and unpacking it in an empty one gives a project whose map, reports, history and settings read the same.
- Build: No database holds a list of projects. The home's `projects/` folder is the list: each project is one folder there, and nothing of a project is anywhere else.
  - Folder name: the source's resolved absolute path, compared as the system compares paths, `os.path.normcase`, with every character that is not a letter or a digit replaced by `-`, then `-` and a three-digit number, `001` for the first. `/home/rich/metaform` is `-home-rich-metaform-001`; `C:\Work\Proj` on Windows is `c--work-proj-001`. A second folder for the same name, a restored copy, PROJ-028, or another path that replaces to the same name, takes the next number.
  - `source.txt` in the folder holds the source's resolved absolute path, one line. It is the truth; the name is only where to look.
  - Finding a working folder's project: for the working folder, then each parent toward the root, the folders under `projects/` named for that path, in number order, whose `source.txt` names that path. The first found is the project, unless the working folder's `project` setting names another. Nothing but the file system is read.
  - `project.sqlite3` in the folder holds the project's registration: its id, the name people type, which stays `metaform add project <id> <path>` and `--project <id>`; its source path and its target, MAP-041; the time it was registered; its metaforms with their names and which is active, STORE-041; the settings and glue of folders inside the source, CLI-014; and the prompt versions its layers were made from, STORE-044. An id is unique across the home: registering one another folder already holds is refused, naming that folder.
  - Each metaform's store is `<metaform name>.metaform.sqlite3` in the folder, STORE-003.
  - `.metaform/` holds the provenance written when the project is registered: the source path, its commit or content hash, the time and the Metaform version. It is written once and never changed.
  - `origin/` holds the source as it was when the project was registered: for a git source the files of its current commit, as `git archive` gives them; for a plain folder a copy of it, leaving out `.git` and what is built from the source. Diffs of work are written only when a variant is collected, question 15, each in its folder named by its commit as above.
  - `history.sqlite3` and `reports/` stay in the folder as they are.
  - The chassis database, STORE-002, holds nothing of any project: module state, what the installer set up, nonces, and the settings of folders outside every project and of the global scope, the `project` setting among them.
  - Clear, backup, restore, remove, export and import act on the project's folder. Metaform holds no conversion of its own: a project under the earlier layout is not read, and upgrading one is a separate utility, not built.
- Why no list: a list of projects in one database is a file every project depends on, so one fault reaches all of them, and a project copied without it is not whole. Named by its path, a project is found by looking where its name says, and the folder is all there is.
- Acceptance: Open with the build. It will hold that a project's folder copied to an empty home reads back whole.
- Relates to: STORE-001, STORE-003, STORE-027, STORE-041, STORE-044, PROJ-010, PROJ-020, PROJ-021.
- Status: confirmed as design, 2026-09-28, the layout included. It follows the pattern of Tempo. Rich, 2026-09-30: no database holds a list of projects, each project is its own folder, and the build follows this record over STORE-001 to STORE-003, STORE-031 and STORE-041 where they differ. The dash, the three-digit number, `source.txt`, `project.sqlite3`, the store file names, and writing `origin/` and `.metaform/` at registration are recommended.

### PROJ-027 A project is exported as a plain zip whose provenance and data are sealed inside it

- Requirement: Exporting a project writes one plain ZIP. The work is visible in it at once: artifacts, diffs and reports, with a ZIP of the origin's files so the diffs can be expanded, and in its root a script that expands them, a terminal menu in bash and a windowed one in PowerShell with WinForms. Its `.metaform/` folder holds exactly two files: `manifest`, in plain text, with the packet's identity and a hash of each visible file; and one sealed file, an AES-256-GCM envelope around an inner ZIP that holds the provenance and all of the project's data.
- What this means: The whole ZIP is never encrypted. The seal is a tamper seal and is not there for secrecy: any copy of the tool opens a packet. The sealed file's key is derived from the manifest and the packet's place in its lineage, so the packet carries no key and no recipe for opening it. In the home the databases are ordinary files that change as agents work, and the seal is made when the project is exported; in flight, between one home and another, it is sealed. A `.metaform/` folder holding anything but those two files is refused.
- Why the packet carries its origin and its scripts: a packet is opened where there may be no Metaform, no git and no repository. With the origin inside it and a script in its root, the person who receives it expands any variation, or all of them, with what their system already has: bash on Linux and macOS, PowerShell on Windows.
- Why: The seal shows whether anything was changed, which is what makes the record provenance and not a note. The key comes from the manifest and the manifest holds the hashes of the visible work, so changing the work is caught by the hashes, and changing the work and the manifest together changes the key and the sealed file no longer opens. The data is inside the seal because it is what the work was made from: a map that could be edited after export would leave the provenance describing something that no longer exists. The work is outside the seal so that a person without Metaform opens the ZIP and uses it. And every part of a secure container is already in place, the authenticated envelope, the derived key and the tool-held evidence that enters the key, so someone who needs secrecy supplies secret evidence and changes nothing in the design.
- How it shows: A packet opens with any ZIP reader and shows its work. Changing one visible file, or one byte of the sealed file, makes the import refuse the packet as tampered.
- Build: The seal is built, as the module `packet`, which ships disabled: `packet seal`, `packet check` and `packet open`, for the command line only, with the container in `seal.py`. Exporting a project as a packet, the ZIP of the origin and the two scripts are open. The container follows Tempo's `tempo.data` contract, version 3, in `docs/tempo_data_container.md` on branch `archive/main-experiments-20260817` of the Tempo repository: the write order, the envelope, the key derivation and the failure semantics. The key's inputs are Tempo's five. The system evidence is a fixed value of 32 bytes or more shipped inside Metaform, so every copy of the tool opens every packet, which is what a tamper seal needs; someone who needs secrecy puts a secret value in its place. The wave number is the packet's place in its lineage: 0 for a first export, and the parent's number plus 1 for an export made from a restored packet, which carries the hash of its parent's manifest. Sealing needs AES-GCM, which Python's standard library lacks, so it is built as a module that declares the `cryptography` package, BASE-026. Each script applies the diff itself, with a function of its own, and calls on no git and no patch command: `scripts/expand.sh` needs bash and awk, and `scripts/expand.ps1` runs in Windows PowerShell 5.1 and PowerShell 7. A part of a diff applies at the lines it names or not at all. The reason: every diff in a packet was taken against the origin that travels in the same packet, so there is never a place to search for, and a line that does not match means the packet is not what it says it is; a general patch command searches nearby and guesses, and would expand a wrong origin into wrong work with no word of it. Writing the function also gives one behavior on every system, where a system's own patch command differs between versions and Windows has none. `vary.py` makes a variation and expands one, and the three give the same bytes, line endings and a missing last newline included. The menu and the window around the scripts are open. `metaform export` writes the JSON exchange document of STORE-027 today and seals nothing.
- Acceptance: A packet written and opened gives back its work and its data as they were, and its `.metaform/` holds two files. A changed work file, work and manifest changed together, and one changed byte of the sealed file are each reported as tampering. A packet sealed with other evidence is reported as that and not as tampering. The rest is open with the build.
- Relates to: PROJ-020, PROJ-021, PROJ-026, STORE-027, LAYER-010.
- Status: confirmed as design, 2026-09-28. It answers question 5: one packet carries the history and the data together.

### PROJ-028 A restored project comes in under the next number

- Requirement: Restoring a packet into a home that already holds the project places it in a folder of the same name with the next number, `002` after `001`, and changes nothing in the folder already there.
- What this means: Both stay in the home and both can be read. Nothing is asked and nothing is warned; the result names each folder so the agent can tell the person.
- Why: The local folder holds work that may not be in the packet, and the packet holds work that may not be local. Writing one over the other loses whichever was not kept, and nothing at the moment of restore can tell which matters. Keeping both costs little, since diffs are small, and leaves the choice to the person, who can see both.
- How it shows: Restoring a packet of `home-rich-app-001` into a home that has it gives `home-rich-app-002` beside it.
- Build: Open.
- Acceptance: Open with the build. It will hold that after a restore the folder that was there is byte for byte as it was.
- Relates to: PROJ-021, PROJ-026, PROJ-027.
- Status: confirmed as design, 2026-09-28. It answers question 13: history keeps both, and STORE-027's rule that importing what exists does nothing covers the map's exchange document only.

### PROJ-029 A small source is kept whole, with no diffs

- Requirement: For a source under 10 MB, Metaform makes no diffs: each variation of the work is kept as a whole copy of the source, and a set of variations is carried as a ZIP of whole copies.
- What this means: The size is that of the source alone, the files a person wrote. Git's own files are not counted and are never copied, and neither is byte code or anything else built from the source. A source of 10 MB or more is kept as diffs against its commit, PROJ-026.
- Why: A diff saves space only when the source is large; ten whole copies of a 2 MB project are 20 MB, which costs nothing. A whole copy needs no rebuilding, so every variation in the ZIP opens and runs as it is, where a diff has to be applied to its origin first and that step can fail. And the work that makes many variations of one artifact is mostly done on small artifacts, a game or a clock in a few files, so the common case gets the simple path. Counting only the source keeps a small project with a long history, or with built files beside it, from being treated as large.
- How it shows: Ten variations of a 300 KB game are ten folders in one ZIP, each complete.
- Build: Open. How a small source's variations are laid out in the project's folder, and whether each still sits under a folder named by its commit, is open, question 16.
- Acceptance: Open with the build.
- Relates to: PROJ-012, PROJ-015, PROJ-020, PROJ-026, PROJ-027.
- Status: confirmed, 2026-09-28: the threshold, whole copies under it, and the source alone counted and copied.

## Open questions

1. A `project` value stored at a folder above a registered project's source location is inherited into it by CLI-014, and that overrides the project's own containment default. A selection made in the user's home would then change the project inside every registered project below it. Should a registered project's source location stop that inheritance, so a folder inside a project defaults to its own project unless a value is set at or below the project's path? Recommended: yes. (PROJ-003, PROJ-005, CLI-014)
2. Should a worktree created outside the project's source location default to the repository's project with nothing selected, found through the worktree's shared git folder, `git rev-parse --git-common-dir`? Recommended: yes, because it needs no setup and writes nothing. (PROJ-006)
3. Answered: the orchestrator passes a folder noun, `metaform set --modules workflow,memory folder=<path>`, before the worker starts. PROJ-007, CLI-022.
4. Answered: a repository origin records the commit hash as its base, and diffs go off that commit. PROJ-012.
5. Answered 2026-09-28: one packet, PROJ-027. It asked: is there one export or two? One option is a single wheel carrying the origin unit and the project's store. The other keeps them separate: STORE-027's JSON document for the map and layers, and the unit wheel for history. Recommended: one command, where exporting a project includes its selected origin unit, and the unit wheel carries the project document inside it. (PROJ-020, STORE-027)
6. Answered: knowledge import adds only what the target does not hold, by unique id; importing something that already exists does nothing, STORE-027.
7. Does the first instance of an origin take suffix `0000` or `0001`? Recommended: `0000`. (PROJ-013)
8. Which module serves web variants, and is the serving port OS-assigned? Recommended: the web module, with OS-assigned ports. (PROJ-019, D44)
9. Is the 3 MB line measured on the total size of a variant's changed text, or per file? Recommended: the total. (PROJ-016)
10. Answered: history and provenance are chassis functions. PROJ-010, LAYER-010.
11. Are ignored files always outside the boundary of a repository, including generated outputs a workflow was asked to produce? Recommended: yes, and a workflow that wants its outputs kept writes them outside ignored paths. (PROJ-011)
12. When a repository's working tree is dirty as an origin is established, is the commit the origin and the uncommitted work its first variant? Recommended: yes. (PROJ-012)
13. Answered 2026-09-28: history keeps both, PROJ-028. It asked: everything exported carries its unique id, and importing something that already exists does nothing, STORE-027. PROJ-021 instead keeps both on divergence, with the next suffix, or advances the local unit when the incoming one includes it. Does the does-nothing rule govern history units too, so a unit whose `mform_id` already exists is skipped, or do history units keep PROJ-021's rule? (PROJ-021, STORE-027)
14. Answered 2026-09-28: by the full path of its source with each separator replaced, followed by a number, PROJ-026. It asked: how is a project's folder in the home named: by the identity of its source, as Tempo did, which is the same on every machine and survives a move; by its working folder's path with each separator replaced, as Claude Code does, which needs no lookup and can be read by eye; or by a name a person picks, as today? (PROJ-026)
15. NEW Are diffs of work made on their own between commits, and by what event, or only when `add_variant` is called? (PROJ-012, PROJ-015)
16. NEW For a source under 10 MB, do its variations still sit under a folder named by the commit they came from, holding whole copies in place of diffs? (PROJ-029)
17. Answered 2026-09-28: a fixed value shipped in Metaform, and the packet's place in its lineage, PROJ-027. It asked: what stands in Metaform for the two inputs of Tempo's key that Metaform does not have yet, the tool's system evidence and the wave number? (PROJ-027)
18. Answered 2026-09-28: each script has a function of its own that applies it, PROJ-027. It asked: how do the packet's bash and PowerShell scripts apply a text diff to the origin, where there is no git and PowerShell has no patch command? (PROJ-027)
