# fork

## Purpose

Maintain a user's own modules over the released chassis, BASE-027. The harness sets up local repository files, checks modules on three systems, dispatches a quality review before wheel building, and dispatches template updates as pull requests. A user's features live in modules so chassis releases stay independent of their changes.

## Template version

0.3.0.

## Declaration

`SUPPORTED_OS` includes Linux, macOS and Windows. `DEPENDENCIES` is empty. The harness is enabled by default so its extension offer reaches agents. It performs no writes or process launches just by loading. CI installs the agent adapter and the declared tooling. Its template snapshot supports setup from a wheel whose disabled template module was omitted.

## Common base used

`metaform.module` supplies contexts, command declarations, dispatch lookup, sync/async invocation and the chassis version. `metaform.settings` owns agent choice and the CI secret name. `metaform.data` supplies nodes, work records and the project's shared store. `metaform.prompt_files` reads this module's prompts. Standard library resources read packaged template files, without importing template implementation.

## Prompts

`resources/prompts.xml` holds the extension offer, the muster review task and the template update task. `resources/quality.md` is the project's own unchanged copy of the QUAL-001 standard. Runtime never reads the rich/ folder.

## Verbs

- `init <folder> <module>` scaffolds a new or empty local repository. It preserves existing repositories and never pushes one.
- `check` enables a candidate in a temporary test home, installs its literal dependencies into the project's Python environment, runs type checking, lint and tests, and writes a source-bound matrix report. Failures are independent and make the job fail after every module has been checked.
- `wheel` reads all six reports, runs `dispatch run` once per module and reads the completed ticket's JSON verdict. A missing secret, incomplete verdict, missing report or changed source prevents a build. Modules with failed checks or reviews are named with their reasons and excluded. Only approved modules enter a fresh build home. Their literal dependencies are installed before loading and building, and the wheel's module set is verified before it becomes an artifact. The CI key is removed from the build subprocess environment.
- `upkeep` compares each README Template version to released template changelog entries. Each outdated module gets one reusable ticket for that version transition and its own Git worktree. Dispatch's automatic worktree merge policy is disabled for these calls. The agent updates and tests that module and opens a pull request, leaving the original checkout and other updates unchanged.

## Settings

`fork_agent` defaults to `codex`, with `claude` and `gemini` available. `fork_secret` defaults to `OPENAI_API_KEY`. Change the secret name to the selected adapter's API-key environment variable when choosing another agent. These choices let repositories use their own provider without changing the harness. The workflow inherits the named repository secret only for muster. A missing value fails naming the secret. Dispatch reads no credentials. The generated CI sets `dispatch_prompts=approve-all` for its isolated unattended run. It supplies Codex ACP's `DEFAULT_AUTH_REQUEST={"methodId":"api-key"}` and `NO_BROWSER=1` so that a fresh CI runner authenticates using its environment key without an interactive login.

## Events

Long commands publish `map.changed` after creating tickets, so an open GUI sees the work while it runs. The module subscribes to `install.completed`, published after the install stage commits a successful newer version. It runs the same upkeep command for registered projects whose `pyproject.toml` declares `[tool.metaform.fork] repository = true`. Reinstalls, downgrades and failed installs do not publish this event. A repository's upkeep failure is reported with the manual retry command and does not prevent upkeep of other repositories or undo the installation.

## Sync and async

Verbs are synchronous. The CLI runs the declared dispatch coroutine through `metaform.module.call`; MCP runs synchronous verbs in its worker thread. Check and wheel are CLI-only.

## Layers

The mutable, hideable `fork` layer records the modules whose tickets the harness owns. Work uses the common DAO and map module's retained work operations. There are no private persistence files. Check reports and Git worktrees are repository artifacts, under `.metaform/`, ignored by Git.

## Lifecycle and cleanup

There are no start/stop hooks or background tasks. Test/build homes are temporary and removed after use. Upkeep worktrees and branches remain beside their ticket for review or resumption. Agents do not merge them. Automatic upkeep follows a successful newer installation while fork is enabled. Manual upkeep remains available for retries and installations performed outside the wheel install stage.

## Modules relied on

`map` supplies work records. `dispatch` supplies agent sessions through its public verb. `mcp` supplies the dispatched agent's tools. None is imported by implementation.

## Systems supported

Linux, macOS and Windows. The generated matrix covers Python 3.11 and 3.14. Checkout disables automatic newline conversion so source digests agree across jobs. Only push and manual runs have agent credentials. Pull requests run checks without those secrets.

## Resources owned

Scaffold files, check subprocesses and reports, temporary test/build homes, wheel artifacts and upkeep worktrees. Agent processes and sessions belong to dispatch. External GitHub authentication belongs to `gh`, used by the upkeep agent.

## Installed and direct wheel

Both use the running package as the chassis source. Wheel building never needs a chassis checkout. The scaffold pins the running release in its pyproject.toml. That release must be available from the configured package source before its CI runs. The resulting artifact can run directly or install itself through the existing install stage.

## Demonstration

```sh
metaform fork init ./my-modules alarm
```

Follow the generated README to implement a feature and its tests, register the repository, publish it, and configure the Actions secret. Commit the repository's current state and authenticate `gh` before installing a newer wheel. The install stage triggers upkeep for registered module repositories. After updating the pinned release through `uv sync`, or to retry an interrupted update, run `uv run metaform fork upkeep`. Only released template entries trigger upkeep.
