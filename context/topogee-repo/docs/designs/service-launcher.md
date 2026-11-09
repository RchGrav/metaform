# Service launcher design

**State:** draft, 2026-11-07, by Xander, the design reviewer. The founder has not reviewed it.

The launcher starts the project's services and gives each one only the permissions it needs. It is built from the tested core of the founder's HoldOn (`RchGrav/onhold`), customized, written in C and bundled with the project. The decisions behind it are in `DECISIONS.md`, "The service launcher".

Every item carries a status:

- **Decided:** the founder stated it. The source gives the founder's words.
- **Proposed:** the design reviewer proposes it, with the reason. The founder has not confirmed it.
- **Open:** the founder must decide it. Section 7 lists each one with a recommendation.

HoldOn paths below refer to the HoldOn repository at commit `e47b623`. Line counts are from that commit.

## 1. What is settled

**SL-1.1** The project builds its own launcher for starting services and assigning process permissions. It is a CLI command customized from HoldOn's approach and bundled with the project. HoldOn is not vendored.

**Status:** Decided. **Source:** "we will be creating our own controller for launching services and assigning process permissions... we are separating what we need and customizing it to be the launcher we bundle so we are not vendoring it".

**SL-1.2** The launcher keeps HoldOn's core in C, because that core is well tested.

**Status:** Decided. **Source:** "we are completely customizing the core for our purpose... its well tested so it should suit us just fine"; "Yes keep it in C its rock solid".

**SL-1.3** The first services are AgentSight and the Metaform server.

**Status:** Decided, on the design reviewer's recommendation. **Source:** "yes proceed with your recommendations".

**SL-1.4** Each service's permissions are declared in the settings system.

**Status:** Decided, on the design reviewer's recommendation. Section 4 recommends a correction for services that run as root.

## 2. What to keep from HoldOn

HoldOn's source is about 12,300 lines of C. The launcher keeps the parts that start, record, check and end a process, and drops the interactive parts.

| Keep | HoldOn files | Lines | Why |
|---|---|---|---|
| Launch with the exec handshake and rollback | `src/runtime/start.c` | 914 | A launch is recorded only if `exec` succeeded. A failed record write ends the process group. |
| Restart supervision | in `src/runtime/start.c` | | Policies `always`, `unless-stopped` and `on-failure:N`. |
| Identity check before every signal | `src/runtime/signal.c`, `src/runtime/state.c`, `src/platform/process.c`, `src/platform/boot.c` | 1,385 | A reused process id is never signaled. Stale or unclear state is refused. |
| Records, the public index and atomic writes | `src/store/*.c` | 867 | A root service is visible to normal users without its arguments, environment or log paths. |
| Start again from a recorded recipe | `src/runtime/call.c`, `src/runtime/resolve.c` | 590 | |
| Logs with an index file | `src/core/logidx.c` | 826 | Other tools can read and follow a service's output. |
| sudo detection and the two stores | `src/access/invocation.c`, `src/platform/paths.c` | 210 | A user and root each have their own store. |
| Shared helpers | `src/core/fs.c`, `json.c`, `util.c`, `validate.c`, `sha256.c` | 886 | |
| Command table and dispatch | `src/cli/specs.c`, `src/cli/main.c`, `src/runtime/commands.c`, `src/runtime/list.c` | 1,793 | Reworked for the launcher's own commands. |

| Drop | HoldOn files | Lines | Why |
|---|---|---|---|
| Log viewer | `src/viewer/*.c` | 2,513 | Services need plain and followed logs only. |
| Interactive console and attach | `src/console/*.c`, `src/term/*.c` | 1,414 | Services are not interactive. |
| The `hold on` session | `src/runtime/shell.c` | 397 | Adopting a foreground program is not a service task. |
| Live statistics | `src/runtime/stats.c` | 182 | |

`src/runtime/ports.c` and `src/runtime/observe.c` (249 lines) report the ports a process uses. **Proposed:** keep them, so `status` can show the Metaform server's port.

**SL-2.1** Files over the 500-line target are split as they are customized: `start.c` into launch, recipe capture and restart supervision; `signal.c` into checking and signaling; `logidx.c` into writing and reading. `cli/main.c` (684) and `runtime/list.c` (703) shrink when the dropped commands go.

**Status:** Decided for the split (CLAUDE.md, about 500 lines per file). The split points are Proposed.

**SL-2.2** HoldOn's tests for each kept part are kept and changed to match the launcher's commands. Tests for dropped parts are removed with them. `metaform/tests/test_hold.sh` (5,457 lines) checks behavior through the CLI; `metaform/tests/logidx_recovery_test.c` checks the log index.

**Status:** Decided in principle (SL-1.2: the tests are why HoldOn was chosen). The test split is Proposed. The carried HoldOn tests are an exception to the CLAUDE.md budget of five tests per feature; the budget applies to new launcher features. This exception is a default taken by the design reviewer from the founder's reasoning, and the founder can overrule it.

**Built 2026-11-07 (steps 1 and 2):** `launcher/` holds 7,207 lines of C in `src/`, no file over 500 lines. Carried tests: `metaform/tests/test_hold.sh` 91 passed, 1 failed, 13 skipped (they need root); the log-index recovery test and the smoke test pass. The failure is a HoldOn race: `rm --force` on a live call races the process that records its exit, so the record comes back. Unmodified HoldOn fails it the same way. It is to be fixed in the launcher's copy. Seven carried tests use `python3` to check JSON and as a sample long-running process. They stay as carried: Python is a test helper there, not a language boundary of the code under test.

## 3. Permissions

HoldOn runs a process as it is and isolates nothing. The launcher adds these steps, in this order, in the child process after `fork` and before `exec`:

1. Set the supplementary groups, then the group, then the user.
2. Keep only the declared Linux capabilities, and raise them into the ambient set so they survive `exec` under a normal user.
3. Set `no_new_privs`, so the service cannot gain privileges through a setuid program.
4. Later, when a service needs them: cgroup limits and Landlock file rules.

**SL-3.1** If any step fails, the child reports the error through HoldOn's existing exec-handshake pipe, and the launch rolls back. A service never starts with permissions other than those declared.

**Status:** Proposed. **Reason:** the handshake already carries `errno` from the child for a failed `setsid`, redirect or `exec`. A failed permission step is the same kind of failure.

**SL-3.2** The record stores the permissions that were applied: user, group, capabilities and `no_new_privs`. `status` shows them.

**Status:** Proposed. **Reason:** the founder accepted that permissions are recorded and inspectable (`DECISIONS.md`).

**SL-3.3** Capabilities are set with the `capset` and `prctl` system calls directly. The launcher does not link libcap.

**Status:** Proposed. **Reason:** HoldOn is one static binary with no library dependencies. Keeping it that way keeps installation simple.

**To verify on the development machine:** that ambient capabilities survive `exec` when `no_new_privs` is set, and which capabilities AgentSight needs on the WSL kernel. The working assumption is `CAP_BPF` and `CAP_PERFMON` (Linux 5.8 and later). AgentSight's uprobes might also need `CAP_SYS_RESOURCE` or `CAP_DAC_READ_SEARCH`. A test decides it, not this document.

## 4. Where permissions come from (recommended correction)

SL-1.4 puts each service's permissions in the settings system. For a service that runs as the user, that is safe. For a service that runs as root, it is not: `~/.metaform/settings.json` is writable by the user and by every agent that runs as the user. A root launcher that read its permissions from that file would let any agent grant AgentSight more power by changing a setting.

**SL-4.1** The settings system declares each service's permissions and shows them. For a service that runs as the user, the launcher reads them from the settings system at launch. For a service that runs as root, an elevated install step (`sudo`) copies the declared permissions into a root-owned recipe, and the launcher, running as root, reads only that recipe. When the declaration and the root recipe differ, `status` says so and names the command that applies the change.

**Status:** Decided, correcting SL-1.4. **Source:** "yes of course, thats literally a best practice and goes without saying" (2026-11-07).

**SL-4.2** A launcher running as root never reads a file that a normal user can write when it decides a service's command, environment or permissions.

**Status:** Decided with SL-4.1. **Reason:** this is the rule that SL-4.1 follows from. HoldOn already keeps root profiles in root-private files (`docs/store.md`).

## 5. Where the launcher keeps its records

The Metaform server is the only process that writes under `~/.metaform` (`metaform/SPEC.md` R-4.4). The launcher's records therefore live outside it.

**SL-5.1** User services: `$XDG_STATE_HOME/topogee/services/` (default `~/.local/state/topogee/services/`). Root services: `/var/lib/topogee/services/`, with the public index under `/var/lib/topogee/services/public/`.

**Status:** Proposed. **Reason:** R-4.4. HoldOn's own layout already separates a user store from a system store with a public index; only the paths change.

## 6. Starting services

HoldOn has no hook that starts a service when the machine starts. `--restart` keeps a service running only while the machine stays up. The founder ruled out systemd.

**SL-6.1** User services start on demand. The `topogee` command starts the Metaform server when a command needs it and the record shows it is not running.

**Status:** Proposed. **Reason:** no boot hook is needed for a service that only matters while someone uses the `topogee` command.

**SL-6.2** Root services start through an elevated command, and can also start at boot through the platform's own hook, set up by the installer: the `[boot] command` in `/etc/wsl.conf` on WSL, and a cron `@reboot` entry elsewhere.

**Status:** Default taken by the design reviewer, which the founder can overrule: AgentSight starts at boot on the development machine through `/etc/wsl.conf`. **Reason:** the founder asked for AgentSight "as a service so it persists for monitoring agents". The development machine's root access is for building; it is not a recommendation for how users run a system (founder, 2026-11-07).

**SL-6.3** The launcher is a branch of the `topogee` command, declared by its module: `topogee service list | status | start | stop | logs <name>`. The branch calls the C launcher binary.

**Status:** Proposed. **Reason:** each module owns its branch (`docs/designs/cli-design.md`, R-5.16). The command names follow HoldOn's verbs where they fit and the CLI design's rules.

## 7. Open decisions

| ID | Decision | Recommendation | Blocks |
|---|---|---|---|
| D-SL3 | The name of the CLI branch | `service`, matching what the launcher manages. | SL-6.3 |

## 8. First steps to build

1. Copy the kept HoldOn files into the project, with HoldOn's license notice, and remove the dropped parts. Keep the tests for the kept parts passing.
2. Split the files over the 500-line target.
3. Change the store paths (SL-5.1) and the command table (SL-6.3).
4. Add the permission steps (section 3) with their handshake errors, and test them on the development machine. **Built** (`launcher/README.md`, Permissions). **Verified on the development machine** (WSL2, Linux 6.18): ambient capabilities survive `exec` when `no_new_privs` is set. A service started as `nobody` with `--cap net_bind_service` showed `CapPrm`, `CapEff`, `CapAmb` and `CapBnd` all `0000000000000400` and `NoNewPrivs: 1`. The test is in `launcher/tests/test_hold.sh`. Which capabilities AgentSight needs is still open.
5. Write the Metaform server's recipe and start it on demand (SL-6.1). **Built** (Jorge, `metaform/rust/crates/metaform-server/src/start.rs`). When no server answers on a home's socket, the forwarder (`metaform mcp`) starts it through the launcher, as a user call: `hold -d --name metaform-<12 hex> --restart on-failure:3 -- <metaform> serve --home <home>`. The name is the FNV-1a hash of the home's canonical path, so every forwarder for the home finds the same call. The record lands in `~/.local/state/topogee/services/`. There is no `sudo`, `--user` or `--cap`: the server runs as the user (SL-5.1).
   - **Name collisions, as the launcher behaves:** `hold -d --name N` refuses with exit 5 ("call name 'N' already exists") if any call named N exists, in any state. So the forwarder creates first, and on that refusal starts the call again by name with `hold N`, which uses the recorded recipe. Exit 6 ("already running") is accepted. A lone `hold N` with no such call falls through to a PATH command, so creating first is the safe order.
   - **Which launcher:** the one `METAFORM_LAUNCHER` names, empty for none. If the variable is unset, `hold` on `PATH` is used only if `hold help system` names the `topogee/services` store, so another `hold`, such as HoldOn itself, is never used.
   - **`on-failure:3`** caps restarts, so a server that keeps exiting with status 3 (the home owned by another server) cannot restart forever.
   - **Tested** with a stub launcher, never the C runtime, in a Rust test (CLAUDE.md): the stable name, the refused duplicate create, the start again by name, and a working agent call each time.
6. Write AgentSight's recipe, its root-owned copy (SL-4.1) and its installer with the boot hook (SL-6.2).
