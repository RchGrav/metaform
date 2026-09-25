# 08 Projects, working folders, origins and variants

This section defines how Metaform knows which project a folder or a server is working on. It also defines how Metaform keeps the history of an artifact: origins, sibling variants, reconstruction, export and import.
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
- How it shows: After `metaform add project mgm ~/mgm-main` and any amount of work, `git status` in `~/mgm-main` shows nothing Metaform created.
- Build: Registration also records the source kind, `repo` when the source location is inside a git working tree and `folder` otherwise. The kind is detected once at registration with `git -C <path> rev-parse --show-toplevel`. When git is not installed, the kind is `folder`. The kind is stored on the project record as a new column `source_kind TEXT NOT NULL CHECK(source_kind IN ('repo','folder'))`, plus `repo_root TEXT`, which is the toplevel for a repo and NULL for a folder. These columns extend STORE-002's `projects` table.
- Acceptance:
  - Registering a project, writing map records and collecting a variant leaves the source location's file list and contents unchanged, including hidden files.
  - A project inside a git working tree is recorded as `repo` with its toplevel. A plain folder is recorded as `folder`.
- Relates to: STORE-001, STORE-002, STORE-031, MAP-041, PROJ-010.
- Status: confirmed that everything stays global. The source kind columns are recommended.

### PROJ-002 A working folder is a key in the home, and every folder gets its own context
- Requirement: Every folder a command or server runs in is recorded in the base database's working-folder table, and that record holds the folder's context.
- What this means: The folder's context is its folder settings: `project`, `workflow` and `commands`, CLI-021. The folder path is only the key those settings are stored under. A worktree is a working folder like any other. So is a scratch folder outside every project. The table is the single place that answers which folders exist and what each one was working on.
- Why: Agents run in many folders, including worktrees created anywhere. The home must know each folder's context without writing a marker into it, and resuming after a restart must work by running `metaform` in the same folder.
- How it shows: An agent runs `metaform set --project mgm` in `/tmp/work`, the machine restarts, and `metaform` in `/tmp/work` still reports project mgm.
- Build: The `folders` row for a folder is written the first time a setting is stored for it, STORE-002. Reads never create rows. A folder's context is resolved by CLI-014 and PROJ-003.
- Acceptance: A folder that has never had a setting stored leaves no `folders` row after any number of reads.
- Relates to: STORE-002, CLI-014, CLI-021, PROJ-003.
- Status: confirmed.

### PROJ-003 A folder's project defaults to the project that contains it, and selection follows the settings pattern
- Requirement: A folder's project is the one selected in that folder with `set --project`. When nothing is selected, it is the registered project whose source location contains the folder. `unset --project` and `unset all` return the folder to that default.
- What this means: Inside a registered project, nothing needs setting, because the home already knows every project's path and shows the local project. From a folder elsewhere, a user or agent selects a project with `metaform set --project <id>`, and the home records that choice against the folder it was run from. Resetting returns the folder to its own project, which is the safe default. A folder outside every project with nothing selected has no project.
- Why: Selecting a project is ordinary configuration, visible and reversible like any setting, and needs no machinery of its own. The default comes from where the agent already is, so the common case needs no setup, and the way back to it is always the same command.
- How it shows:
  - In `~/mgm-main/src`, `metaform` shows project mgm with nothing set.
  - In `~/mgm-main`, `metaform set --project metaform` switches that folder to metaform.
  - `metaform unset all` there returns it to mgm, unless the project setting is glued.
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
- How it shows: The orchestrator runs `metaform set --project mgm --workflow intake` in its session folder. After a restart, `metaform` in that folder shows project mgm and workflow intake.
- Build: No new records. The selection is the folder's stored `project` setting, and the workflow and surface are its other folder settings, PROJ-002.
- Acceptance: Covered by PROJ-002 and PROJ-003's acceptance.
- Relates to: PROJ-002, PROJ-003, CLI-021.
- Status: confirmed.

### PROJ-005 Every surface resolves the project the same way, including a server started outside any project
- Requirement: The CLI and the MCP server resolve the project from their own working folder by PROJ-003, and an agent selects a project for a server's folder the same way it does on the CLI.
- What this means: A host starts the MCP server in some folder: the agent's folder, a fixed folder, or the user's home. The server is a working folder like any other. If that folder resolves to a project, the server serves it. If it does not, the agent selects one with the `set` tool, which stores the choice for the server's folder exactly as `metaform set --project` would. A host that always starts the server in the same folder keeps that selection across sessions. A single call can still name its project, MCP-025.
- Why: The server has no special rule to learn, so any host works: one that starts the server in the project, and one that starts it anywhere else. Selection by folder is the same mechanism the CLI uses, which keeps the two surfaces equal.
- How it shows: A desktop host starts the server in the user's home. Status over MCP reports no project and lists the registered ones. The agent calls `set` with `{"project": "mgm"}`, and every later call in that host reads mgm.
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
- How it shows: A worker started in `~/mgm-main/.worktrees/fix` sees project mgm. A worker started in `~/mgm-fix`, a sibling worktree, sees mgm after `metaform set --project mgm` is run there.
- Build: The worktree follows PROJ-003 with no special case. Whether a worktree outside the source location should default to its repository's project without being selected is open question 2.
- Acceptance: A worktree inside the source location resolves to the project with nothing set.
- Relates to: PROJ-002, PROJ-003, PROJ-017.
- Status: confirmed for worktrees as working folders with global data. Defaulting a sibling worktree is open.

### PROJ-007 A worker's own folder can carry a narrowed context while the orchestrator keeps its own
- Requirement: When the worker runs in a different folder from the orchestrator, the worker's folder can carry the workflow and narrowed command surface, so the orchestrator's own commands are never hidden.
- What this means: The command surface is a folder setting. Set on the worker's folder, it narrows only what the worker sees. The orchestrator's folder keeps the full surface. When the worker shares the orchestrator's folder, as subagents often do, the narrowing applies to that shared folder and the way back is the abort command, CLI-022.
- Why: Narrowing the surface steers workers. Doing it per folder avoids hiding the orchestrator's commands whenever the two work in different places.
- How it shows: The orchestrator starts a worker in a worktree and narrows that worktree's folder to `workflow,memory`. `metaform` in the worktree shows the narrowed surface, and `metaform` in the orchestrator's folder shows everything.
- Build: The narrowing is stored as the worker folder's `commands` and `workflow` settings. How the orchestrator stores a setting for a folder other than its own is open question 3. Until that is answered, the worker, or a command run in the worker's folder, stores them.
- Acceptance: With `commands` narrowed on folder A only, a command outside the surface is refused in A and runs in the orchestrator's folder B.
- Relates to: CLI-021, CLI-022, PROJ-002, PROJ-006.
- Status: recommended. The per-path option is confirmed as wanted; the way the orchestrator names the folder is open.

## History: origins and variants

### PROJ-010 History is chassis data kept in the home
- Requirement: The chassis owns the history of each project, meaning its origins, variants, reconstruction, export and import, and keeps all of it in the Metaform home.
- What this means: History is data. The chassis owns data, import, export and query, so it owns history too, through the data access object that modules use, STORE-023. A workflow module that creates workfolders or worktrees and collects their results calls these operations. It never keeps history of its own.
- Why: History must be exportable and importable as a whole with the project, and it must work with no feature module enabled. Keeping it in the chassis means one implementation, used the same way by every module.
- How it shows: With every feature module disabled, `metaform list origins` and `metaform extract` still work.
- Build: The records are in PROJ-023, and the operations and commands in PROJ-024.
- Acceptance: With every feature module disabled, collecting a variant from a folder and extracting it produces the variant's files.
- Relates to: BASE-001, STORE-023, PROJ-023, PROJ-024.
- Status: recommended. The data being global is confirmed.

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

### PROJ-012 An origin is a commit for a repository and a full content copy for anything else
- Requirement: For a repository, the origin is the commit the history is keyed by, and Metaform keeps no copy of it. For a source outside any repository, the origin is a full copy of its content kept in the home.
- What this means: A repository already holds its commits, so the commit is the origin and its files are read from git when they are needed: for reconstruction, comparison and export. A folder with no repository has nothing to return to, so Metaform copies it at the moment the origin is established, and that copy is the only place its baseline exists.
- Why: The commit already anchors a repository's baseline exactly, so a second copy only costs space. A plain folder changes in place and would lose its baseline without a copy.
- How it shows: Establishing an origin for mgm records the commit and copies no files. Establishing one for a photo folder copies the folder into the origin unit.
- Build:
  - For a repository, the origin records the full commit id of `HEAD` at the moment it is established. Its files are read with `git archive <commit>` when needed.
  - If the working tree is dirty at that moment, the commit is still the origin, and the uncommitted changes are collected at once as the unit's first variant, PROJ-017.
  - For a folder, the boundary's files are copied to `origin/` in the unit's payload folder, PROJ-023.
- Acceptance:
  - A repository origin stores no file payload.
  - A folder origin's `origin/` holds exactly the boundary's files, and later changes to the source do not change it.
- Relates to: PROJ-011, PROJ-013, PROJ-018, PROJ-023.
- Status: confirmed that a repository keeps no origin copy and a folder does. The earlier reading, that the origin folder always holds a copy of the commit, is superseded. Handling a dirty working tree is recommended, open question 12.

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
  - The first instance of a digest gets suffix `0000`, and each new instance takes the next unused value in hex.
  - The older forms `<digest>_0000` and a 12-hex prefix plus `_FFFF` are never written.
- Acceptance:
  - Two origins captured from identical content on two machines have the same `origin_sha256`.
  - `mform_sha_id` is 64 hex characters, and `mform_id` is 16 hex characters with the same last four characters.
- Relates to: PROJ-012, PROJ-014, PROJ-021, PROJ-023.
- Status: confirmed for the two forms and the suffix. The manifest format and the first suffix value are recommended, open question 7.

### PROJ-014 An origin is never overwritten, and a new baseline starts a new origin unit
- Requirement: A retained origin never changes. Moving the baseline to a new commit or new content, called re-anchoring, creates a new origin unit, and the earlier unit and its variants stay exactly as they were.
- What this means: A different commit is a different origin. Re-anchoring is an explicit operation. Nothing re-anchors implicitly, and no variant ever becomes the baseline for another variant except through re-anchoring. The suffix is not used for re-anchoring. A new baseline has a new digest, and the suffix belongs to import, PROJ-021.
- Why: Every variant is a diff against its origin. Changing the origin in place would silently corrupt every variant pinned to it. Keeping old units intact keeps every past result reconstructable.
- How it shows: After re-anchoring mgm to a newer commit, `metaform list origins mgm` shows both origins, and variants of the old one still extract.
- Build: `metaform add origin [<project>]` establishes an origin from the project's current state, PROJ-012. Its content is the repository's `HEAD` commit, or the folder's current content. If an origin with the same digest already exists for the project, the command reports it and creates nothing. The project's selected origin, the one new variants attach to, is the most recently established one unless a later decision says otherwise.
- Acceptance:
  - Re-anchoring leaves every file and record of the earlier unit byte-identical.
  - Both units list, and a variant of the earlier unit still reconstructs.
- Relates to: PROJ-012, PROJ-013, PROJ-015, PROJ-024.
- Status: confirmed, carrying REQ-162. The command form and the selected-origin rule are recommended.

### PROJ-015 Variants of one origin are siblings
- Requirement: Every variant is stored against its origin and never against another variant, so many variants pinned to one origin stay independent siblings.
- What this means: This covers mutation experiments that produce many variants from one commit or one folder, for example ten copies made from one base. Running operations one after another does not turn an earlier result into a later one's baseline. A result becomes a baseline only by re-anchoring.
- Why: Iterative and self-play workflows produce many variations from one base, and each is worth keeping. Storing each against the origin keeps every one reconstructable on its own, whatever happens to the others.
- How it shows: Ten collected variants of one origin each extract on their own, in any order, to the same result as when they were collected.
- Build: A variant records only its origin unit, never a parent variant.
- Acceptance: Deleting nothing and extracting variant 7 alone reproduces it without reading any other variant's payload.
- Relates to: PROJ-014, PROJ-016, PROJ-017.
- Status: confirmed.

### PROJ-016 A variant stores only what changed against its origin
- Requirement: A variant stores the files that differ from its origin and nothing else. Changed text is kept whole when the variant's changed text is small, and as a diff against the origin when it is large. Changed binaries are always kept whole.
- What this means: Unchanged files are never stored; they come from the origin. When the total size of a variant's changed text files is under 3 MB, those files are stored whole. At 3 MB or more, each changed text file is stored as a diff against its origin version. A binary file that changed is copied whole, because a binary diff is not needed. A removed file is recorded as removed. Every stored file carries the SHA-256 of its full new content, so reconstruction can be checked.
- Why: Most variants are small, and whole files are the simplest and safest record of them. Large text variants stay small as diffs. Binaries such as images and fonts are copied, because diffing them costs more than it saves.
- How it shows: A variant that edits two source files and swaps a font stores two text files and one font file. A variant that rewrites a large generated file stores one diff.
- Build:
  - A file is text when its bytes decode as UTF-8 and contain no NUL byte; otherwise it is binary.
  - The diff is produced and applied by Metaform's own Python code, never by git or a patch tool. It is stored as JSON, `{"base_sha256": <origin file hash>, "ops": [...]}`. The ops come from `difflib.SequenceMatcher(None, origin_lines, new_lines, autojunk=False).get_opcodes()` over the lines as split by `splitlines(keepends=True)`. Each non-equal op is stored with its replacement lines, and each equal op by its ranges only.
  - Applying a diff whose `base_sha256` does not match the origin file is an error, never a guess.
- Acceptance:
  - A variant with 1 MB of changed text stores whole files. The same edit on a 4 MB file stores a diff, and both reconstruct byte-identical.
  - A changed binary is stored whole and reconstructs byte-identical.
  - A file stored with a tampered hash fails reconstruction with an error naming the file.
- Relates to: PROJ-011, PROJ-015, PROJ-018, PROJ-023.
- Status: confirmed for diffs off the origin, whole binaries, and keeping small text whole with 3 MB as the line. Measuring the 3 MB on the variant's total changed text, the text test and the diff format are recommended.

### PROJ-017 Collecting a worktree or workfolder keeps it as a variant, committed or not
- Requirement: The work in a worktree or workfolder made from an origin can be collected as a variant of that origin, whether or not its changes were committed.
- What this means: Metaform acts as a side channel for git. It diffs what is in the folder against the origin, so uncommitted work is kept. Collecting keeps the variant. It does not apply it to the project or clean up the folder. Each variant carries one provenance record saying how it was produced.
- Why: Work produced in many worktrees would be lost when they are cleaned up, and much of it is worth keeping and comparing. Diffing against the origin, not against the worktree's own commits, captures the work however the agent left it.
- How it shows: An orchestrator runs ten workers in ten worktrees off one commit, then collects each folder. `metaform list variants` shows ten variants, each with the workflow and prompt that produced it.
- Build:
  - `metaform add variant <folder> [origin=<mform_id>]` reads the folder's boundary, PROJ-011, compares it file by file with the origin, and stores the differences, PROJ-016. The origin defaults to the project's selected origin, PROJ-014.
  - The folder is left untouched.
  - The provenance record has the same fields as a layer's, LAYER-010: module and workflow, prompt, model, role and blinded. Any field the collector did not supply is empty. Variant ids are sequential within their unit, starting at `v000001`.
- Acceptance:
  - Collecting a worktree with uncommitted edits stores those edits.
  - The collected folder is byte-identical before and after collection.
  - A variant's provenance reads back with the fields given at collection.
- Relates to: PROJ-011, PROJ-015, PROJ-016, PROJ-023, LAYER-010.
- Status: confirmed that collected worktrees are kept as variants, including uncommitted work. The command, the id form and reusing the layer provenance fields are recommended.

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
- Status: confirmed, carrying REQ-165. The inclusion test and the result shape are recommended. How this rule relates to knowledge rows is open question 6.

### PROJ-022 Pending physical work travels with continuation
- Requirement: When work is handed on to continue elsewhere, the working files it needs travel with it.
- What this means: A job handed on without its workfolder content, staged inputs, generated outputs and needed binaries is not complete.
- Why: A worker that receives a prompt but not the files it refers to cannot continue the work.
- How it shows: Deferred.
- Build: Deferred with nonces and assignment context, MCP-012. Until then, the working files of a job travel as a collected variant, PROJ-017, exported with its unit, PROJ-020.
- Acceptance: Deferred.
- Relates to: MCP-012, PROJ-017, PROJ-020.
- Status: deferred, carrying REQ-164.

### PROJ-023 History records and payload layout
- Requirement: Origins and variants are rows in the project's store, and their file payloads live in the home under the origin unit's long id.
- What this means: Records follow the one-row-per-thing rule, STORE-004. Payload files are too large for rows and live on disk, referenced from the rows.
- Why: Rows give direct reads of which origins and variants exist and how each was made. Files on disk keep large payloads out of SQLite and copy cleanly into an export.
- How it shows: `~/.metaform/origins/<mform_sha_id>/` holds `origin/` for a folder origin, and `variants/<variant id>/` for each variant.
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

  A variant's payload is `variants/<variant id>/files/<path>` for whole files and `variants/<variant id>/diffs/<path>.json` for diffs. A variant's rows and payload are written in one step: the payload goes to a temporary folder in the same unit, then the rows are committed, then the folder is renamed into place. A crash leaves either no variant or a complete one.
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
- Build: The data access object gains `add_origin`, `origins`, `add_variant`, `variants`, `extract` and `export_unit`, with the inputs and outputs above. Each command's tool follows BASE-036 and MCP-003. Without `origin=`, a command uses the project's selected origin, and a project with no origin stops with `Next: metaform add origin`.
- Acceptance: Covered by the records each command names.
- Relates to: CLI-001, CLI-031, STORE-023, PROJ-012 to PROJ-021.
- Status: recommended.

## Open questions

1. A `project` value stored at a folder above a registered project's source location is inherited into it by CLI-014, and that overrides the project's own containment default. A selection made in the user's home would then change the project inside every registered project below it. Should a registered project's source location stop that inheritance, so a folder inside a project defaults to its own project unless a value is set at or below the project's path? Recommended: yes. (PROJ-003, PROJ-005, CLI-014)
2. Should a worktree created outside the project's source location default to the repository's project with nothing selected, found through the worktree's shared git folder, `git rev-parse --git-common-dir`? Recommended: yes, because it needs no setup and writes nothing. (PROJ-006)
3. How does an orchestrator store the narrowed context for a worker's folder that is not its own? Every long switch is a setting (CLI-011), so a `--path` switch does not fit the grammar. One way is a folder noun, `metaform set --commands workflow,memory folder=<path>`. The other is having the worker's first command store it. (PROJ-007)
4. Is it confirmed that a repository origin keeps no copy of the commit? This replaces the earlier reading, in which the origin folder always held a copy. (PROJ-012)
5. Is there one export or two? One option is a single wheel carrying the origin unit and the project's store. The other keeps them separate: STORE-027's JSON document for the map and layers, and the unit wheel for history. Recommended: one command, where exporting a project includes its selected origin unit, and the unit wheel carries the project document inside it. (PROJ-020, STORE-027)
6. Knowledge rows on import follow D23: a new correction layer on top of the stack, or an in-place change. History units follow PROJ-021: a new suffix, keeping both. Should knowledge import also keep both on any loss, to match? (PROJ-021, STORE-027, D23)
7. Does the first instance of an origin take suffix `0000` or `0001`? Recommended: `0000`. (PROJ-013)
8. Which module serves web variants, and is the serving port OS-assigned? Recommended: the web module, with OS-assigned ports. (PROJ-019, D44)
9. Is the 3 MB line measured on the total size of a variant's changed text, or per file? Recommended: the total. (PROJ-016)
10. Is history owned by the chassis, as recommended in PROJ-010, or by a module?
11. Are ignored files always outside the boundary of a repository, including generated outputs a workflow was asked to produce? Recommended: yes, and a workflow that wants its outputs kept writes them outside ignored paths. (PROJ-011)
12. When a repository's working tree is dirty as an origin is established, is the commit the origin and the uncommitted work its first variant? Recommended: yes. (PROJ-012)
