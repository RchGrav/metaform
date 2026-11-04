# Autoticket log capture and reader recovery

## Scope and state

Repository: `RchGrav/metaform`  
Branch: `fix/autoticket-log-capture-recovery`  
Base: `6ebe54b899c294629c5190655783e4d5ef5b759a`  
Verification recorded: 2026-10-24 UTC (October 23 in America/New_York).

This change implements the three log-reader corrections from the preceding review and separates committed log capture from repair-ticket policy. It does not implement the broader core strip-down. Intake, agent prompts, role definitions, orchestration, the dynamic blacklist, authorization settings and database schemas are unchanged. The branch is not a deployment and does not change `main`.

Implementation is complete for the scoped changes. Sixteen focused checks pass. Full Metaform integration, a real SSH server, macOS execution and repository-wide lint/type/test checks were not run here. Those verification limits are not represented as successful checks.

## Changes

### 1. Local partial-line truncation

File: `src/metaform/modules/autoticket/sources.py`, `LocalReader.follow`.

The original truncation comparison used `position`, the byte after the last complete line emitted. It ignored bytes already consumed into an unfinished line. An observed shrink could consequently leave the reader beyond the replacement data.

The comparison now uses `handle.tell()`, the actual read cursor. On an observed shrink it seeks to zero, clears the old partial-line buffer and emits the existing file-position reset event. Complete-line offsets retain their existing meaning; no stored offset format changes.

### 2. SSH file identity across rotation and reconnection

File: `sources.py`, `SshReader.follow`, `SshReader.run`, `REMOTE`.

On a `tail` replacement/appearance/truncation notice, the reader stops consuming that stream before emitting any replacement-file line. It emits a zero-offset generation boundary, closes the old stream and immediately starts a new remote handshake. That handshake binds the new file identity to its offset before reading replacement content.

An actual disconnect still retains the last complete-line identity and offset, records a drop and uses the existing bounded backoff. A file-generation change alone does not count as a network drop and has no failure backoff. Reconnection to the same file resumes rather than replaying it from zero. `LC_ALL=C` makes the remote diagnostics match the existing English notice recognizer.

This retains the existing system SSH, shell and `tail -F` dependencies. It does not install a remote agent or require Python on the remote host.

### 3. Local reader failure reporting and recovery

Files: `sources.py` and `src/metaform/modules/autoticket/watch.py`.

A local reader now emits a terminal `failed` event after closing its watcher when initialization or following fails unexpectedly. Intentional stop does not emit a failure. A lock protects stop/close interaction, and failed filesystem-watcher construction releases the descriptors it allocated.

The owning Watch records the failure, keeps that log's existing lease and schedules a retry deadline. Retry delays start at one second and increase up to the existing 60-second backoff ceiling; receiving a line resets the delay. Healthy readers continue normally. There is no periodic health-polling loop.

Before replacing a failed reader, Watch writes completed counts and the start of any unfinished multiline entry together. The replacement obtains its identity and offset from the committed log row. The pending assembler is rebuilt from that position, so the already counted entry is not counted again while the unfinished entry remains recoverable. A failed checkpoint prevents replacement from starting and propagates to the existing outer service recovery. Removed logs are not restarted.

### 4. Capture is independent of ticket policy

Files: `watch.py` and `src/metaform/modules/autoticket/__init__.py`.

`Watch.settle` no longer imports or directly calls `faults.tell`. After committing captured groups, it publishes:

```text
map.changed: tables=[autoticket.groups], kinds=[log_capture]
autoticket.captured: project and committed group IDs
```

The precise map-change metadata avoids treating a capture update as an unspecified work-queue change. The module declaration subscribes its small `captured` handler to `autoticket.captured`; that handler invokes the existing repair policy for the matching project.

**This separation does not disable automatic ticket filing.** The existing `autoticket_file`, `autoticket_reopen` and other policy settings and defaults remain unchanged. The collector can capture without the policy subscriber, and the current application still connects the existing policy through its event system. No new policy switch, permission model, coordinator or agent is introduced.

## Verification performed

The actual full reader and Watch source files were obtained from the pinned repository revision. Their original Git blob hashes were checked before editing. The uploaded candidate files are checked by Git blob hash against the files exercised locally.

| Check | Result | Boundary |
|---|---|---|
| Five selected regression cases against the original `sources.py` | Four fail, one passes | The complete-line truncation variant already passed; failures demonstrate the partial-line, missing-failure-event and SSH identity defects. |
| Reader checks | Eight pass | Real Linux files, threads and inotify; remote shell and `tail` run through a local SSH-command substitute. |
| Watch checks | Six pass | Real production event/recovery methods with a small SQLite-backed store fixture; not the complete Metaform DAO. |
| Capture-policy composition | Two pass | Actual module declaration and handler, with a spy replacing repair policy; not full event-bus integration. |
| Combined focused run | 16 pass, zero failures/skips; 10.48 seconds | Chassis declaration imports are substituted by the offline runner because the full application environment is unavailable. |
| Python compilation and 3.11 grammar parsing | Six changed/new Python files pass | Not a substitute for Ruff or Pyright. |
| Patch application and whitespace | `git apply --check --whitespace=error` passes against exact baseline files | Checks the scoped patch, not a complete local checkout. |

Reader cases cover partial-line truncation with and without earlier complete lines, unexpected notification failure, initialization failure, descriptor cleanup, rotation boundaries, rotation followed by disconnect and another replacement, same-file reconnect without replay, and truncation without a false network-drop count.

Watch cases cover persisted-position recovery with completed and unfinished entries, committed evidence before publication, collector operation without ticket methods, removal during recovery, backoff without idle reads, checkpoint failure before restart, and continued capture from a healthy second log.

### Idle and unrelated-event observations

Separate baseline and candidate reader processes were measured for 60 seconds using actual Linux notifications. The appended target line was delivered correctly afterward and both readers stopped cleanly.

| Reader observable | Baseline | Candidate |
|---|---:|---:|
| Elapsed seconds | 60.00022 | 60.00018 |
| Process CPU seconds | 0.000141651 | 0.000146738 |
| Target-log stat reads while idle | 0 | 0 |
| Unrelated writes in the same directory | 1,000 | 1,000 |
| Target-log stat reads caused by those unrelated writes | 0 | 0 |

These measurements support no observed idle-polling regression in this reader check. The tiny CPU difference is not a performance improvement claim. This is not a whole-server CPU measurement.

### Reproduce with a complete repository environment

```bash
uv run pytest -n 0 -q \
  src/metaform/modules/autoticket/tests/test_reader_recovery.py \
  src/metaform/modules/autoticket/tests/test_watch_recovery.py \
  src/metaform/modules/autoticket/tests/test_capture_policy.py
```

The accompanying evidence archive contains the offline runner, exact baseline and candidate files, test source, JUnit results, baseline failures, idle-measurement script and JSON, content hashes and the patch. The offline runner explicitly substitutes chassis declarations and the repair-policy integration; it does not simulate the installed application as a whole.

## CI and unperformed checks

Creating this branch triggered GitHub Actions run `40052991681` on the unchanged base commit. All six jobs reported failure before any job steps were available; no job logs were supplied. That run establishes neither a candidate failure nor a successful baseline. The underlying CI startup cause was not established here. The final branch check status is reported separately after publishing.

No real SSH-server transport, macOS/kqueue runtime, complete Metaform DAO/event-bus execution, repository-wide test suite, Ruff or Pyright was executed in this environment. The network-isolated working environment did not have the complete repository dependencies or those checkers. No tests or CI requirements were disabled to obtain the focused results.

The checks do not establish universal losslessness under every rotation race, inode reuse, a generation deleted before it can be read, or copy-truncation followed by rapid regrowth beyond the prior cursor. The implemented fixes address the reproduced sequences; no broader guarantee is claimed.

## Files changed

Product code: `sources.py`, `watch.py`, and `__init__.py` under `src/metaform/modules/autoticket/`.

New tests in that module: `test_reader_recovery.py`, `test_watch_recovery.py`, and `test_capture_policy.py`.

Documentation: this report. Existing prompts, Canonical Intake, settings values, schema declarations, specialist definitions and unrelated source files are not edited.

## Main integration follow-up, 2026-10-29

The original branch verification above records the October 23 work. The following checks were performed separately before integrating commit `261a1cb7172159b4354308a423028a86ffc179f3` into main at `5b080e25109f1cfb9bf55d31b1816292aac611a7`. The earlier rebuild review artifacts remain unchanged and continue to describe their pinned source revision.

Three independent review passes covered reader edge cases, Watch/event-policy integration and verification boundaries. They found one integration regression: `events.publish` converts subscriber exceptions into failed delivery outcomes, but the new `Watch.settle` discarded those outcomes. A failed repair-policy subscriber could therefore appear successful after capture counts and offsets committed.

The integration correction checks unsuccessful `autoticket.captured` deliveries, restores their touched group IDs on the same Watch and raises a diagnostic into the existing CLI/background failure path. Two parametrized regression cases exercise actual event dispatch and the declared subscriber with a failing or cancelled policy. Both failed before the correction and pass afterward. They verify committed count and offset preservation and explicit retry without recounting. This is restored failure visibility and in-memory retry preservation, not a durable outbox or guaranteed automatic replay after watcher/process replacement.

The two capture-policy composition tests also resolve the current module per test. Their original collection-time module reference became stale when an earlier test reset the loader. The ordered loader-reset/composition reproduction now passes.

| New check | Result | Limit |
|---|---|---|
| Original 16 regression cases, complete installed application environment | 16 passed | Uses Linux notifications, local SSH-command substitute and controlled Watch store/policy fixtures as described above. |
| Failed/cancelled subscriber regression | 2 failures before correction, 2 passes after | Actual event dispatch and declared capture handler, with controlled source context/store and policy failure. |
| Loader reset followed by both composition tests | 3 passed | Demonstrates test isolation across module reload. |
| Final complete autoticket module | 47 passed, 8 failed, zero skipped, 89.87 seconds | Full module is not green. All 18 new regression cases passed. |
| Identified failures on untouched main `5b080e25` | Same 8 failures, 1 additional selected case passed | Separate worktree, same environment. JUnit failure identities compared equal. These failures predate this integration. |
| Ruff over all six changed/new Python files | Passed | Focused lint, not repository-wide. |
| Pyright over the three product Python files | 0 errors, 0 warnings | Existing environment selected explicitly with `--venvpath`; not repository-wide. |
| Python patch whitespace | Passed | Original Markdown metadata deliberately uses two-space hard line breaks. |

The eight pre-existing failures are:

- `test_a_sixth_group_waits_while_five_are_open_and_is_filed_when_one_closes`
- `test_feedback_and_error_words_do_not_impose_unrequested_approval_gates`
- `test_recurrence_reopens_same_issue_and_assignment_but_cancel_stays_cancelled`
- `test_done_after_delivery_closes_fault_and_recurrence_restores_same_light`
- Both `test_fault_done_names_missing_delivery_and_keeps_light` parameter cases
- `test_old_code_fault_is_recorded_without_reopening_delivered_repair`
- `test_fault_fix_merged_to_main_closes_and_clears_open_condition`

No existing failing test, prompt, schema, unrelated orchestration behavior or CI requirement was changed to obtain the focused results. Test homes were isolated, autostart disabled and agents substituted by the repository fixtures. The merge test pushes only to its temporary local Git origin. No paid model session or production workflow was launched. Real SSH-server and macOS/kqueue execution remain unverified.

Commands used the existing environment without synchronization, with `UV_PROJECT_ENVIRONMENT=/home/rich/metaform/.venv` and `PYTHONPATH` set to each isolated worktree's `src`:

```bash
uv run --no-sync pytest -n 0 -q src/metaform/modules/autoticket/tests
uv run --no-sync ruff check src/metaform/modules/autoticket/__init__.py src/metaform/modules/autoticket/sources.py src/metaform/modules/autoticket/watch.py src/metaform/modules/autoticket/tests/test_capture_policy.py src/metaform/modules/autoticket/tests/test_reader_recovery.py src/metaform/modules/autoticket/tests/test_watch_recovery.py
uv run --no-sync pyright --venvpath /home/rich/metaform src/metaform/modules/autoticket/__init__.py src/metaform/modules/autoticket/sources.py src/metaform/modules/autoticket/watch.py
```

Baseline reproduction selected the named existing cases using pytest `-k` in a separate untouched main worktree. The final and baseline JUnit failure sets were compared programmatically. The intermediate all-module run exposed the two stale-module test errors; those were corrected and the final entire module was rerun without excluding the eight known failures.
