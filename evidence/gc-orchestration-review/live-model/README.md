# Single real-model journey on the reviewed fix

## Outcome and exact candidate

The completed live run used source commit `03766976928aae6139563cdd9ec7075dd3541d7d`, tree `f8dbc2419e340f98f951fbe1aef57f24975ace71`. Source code remained unchanged throughout the run. The installed official `@agentclientprotocol/codex-acp` 2.2.2 adapter used Codex CLI 0.160.1, SDK 1.9.0, and the real `gpt-6.1-sol` model through an existing normal Codex ChatGPT login. No credential values were read or copied. The model's reported reasoning effort was low and its adapter mode was the existing `agent` default.

Root ticket `fcc7915d466e450eac7a45284cf63ddd` completed. Its GC requested a missing specialist itself, commissioned Role Creator, resumed after publication, waited for the generated specialist, independently validated its files, and delivered. Two independent functionality assessments passed. The PM then consumed three actual notification components, read the completed records, and gave the visible response in `pm-response.txt`. The isolated PM was stopped through the public CLI; final project and machine usage were both 0 with limit 1.

`live-journey.json` is the compact outcome/caveat index. `runtime-records.json` retains the native final assignments, pending transitions, generated role source/history, context receipts, notifications and indexed memory. `harness/` contains filtered operational exports obtained with official read-only `thread/read` for exactly these six current-run sessions:

| Actor | Assignment | Actual session |
| --- | --- | --- |
| GC | `78d96dd251ca55b2abb943084b145a8d` | `01a14e36-7ea1-7882-8b8c-3bf1ebd347a8` |
| Role Creator | `51357703485f49feae0338c96d5c21dd` | `01a14e37-0196-78f3-a7b8-6dbf4542fc8b` |
| Generated `label_normalizer` | `d6b63545b4dc47e48e38424fea95a854` | `01a14e38-d216-7e83-88fb-8d66fbfc37cf` |
| FQC1 | `a04354b70c9258b2b95169247ce63e74` | `01a14e3c-38f2-7e81-8029-22d1bfbca421` |
| FQC2 | `a2afce9f50295a159b37f19471a1e43b` | `01a14e3e-79fb-7fd2-ad9c-5c741f6211ba` |
| PM / triage conversation | No work assignment | `01a14e41-01da-7c92-86f8-0584d4d92209` |

## Actual task, validation and context

The small concrete task normalizes configuration labels: trim surrounding whitespace, replace each internal whitespace run with one underscore, lowercase, preserve punctuation, reject blank input. The exact assignment is `ticket-task.txt`; generated output is in `result/`. The generated duty is stored through the native provider as `metaform://role/label_normalizer`, prompt component `agents:generated_review_live_label_normalizer`, actual selected version `27355977ddd54ff4b210b9aac6ca367e`. The real Role Creator authored its duty, which the specialist received and used.

The specialist ran `python -m unittest -v`: 11 tests passed. The GC independently reran all 11 tests, checked six direct acceptance cases, and verified exact hashes. FQC1 independently reran the suite and hashes, checked all 29 Python Unicode whitespace characters and five idempotence cases. FQC2 independently reran the suite and hashes and inspected the typed API and functional memories. `model-command-results.json` retains the actual harness command output and exit codes, separate from the agents' reports.

- `label_tools.py`: `d7631640c4bff29ba8139c043b3a00dd59bd1e4ff440ee5888ddc68d028a7e50`
- `test_label_tools.py`: `5df3bb81b2da8eedade8e8602127c03c46e8708495cc003184f3fdf6b05dfd4d`

`recipient-evidence.json` compares exact delivered component text with actual harness user-input blocks. Each actor received its common component and native/generated duty exactly once in its active epoch. The GC resumed its original session twice; unchanged common/duty text was suppressed on those turns. PM runner `bd7c23d7095dce93` received three `dispatch:user-update:` components through `acp_prompt` at 09:04:06Z; each appears once in its actual inputs. `pm-notification-receipts.json` retains their full rendered content. Native memory records contain four entities, 19 observations, three relations and four functional joins; actual later role inputs and memory reads show their use.

Capacity was configured through the existing public settings path to project 1 and machine 1. `capacity-observations.json` and six retained public snapshots show maximum observed usage 1 and final usage 0. Durable suspend/relaunch transitions, real child sessions and the same resumed GC session demonstrate progress with a capacity-one parent/child path. These are stage observations, not a claim of continuous process sampling.

## Reproduction commands and scope

These are the commands used, with isolated paths. For a new run, use a fresh isolated home/project and update the helper constants accordingly. Existing public CLI permissions and the normal supported model login remain required; do not directly edit the settings store.

```sh
npm install --prefix /tmp/metaform-review-live-adapter --no-audit --no-fund \
  --cache /tmp/metaform-review-npm-cache --fetch-retries=0 --fetch-timeout=15000 \
  @agentclientprotocol/codex-acp@2.2.2
/tmp/metaform-review-live-adapter/node_modules/.bin/codex login status

export METAFORM_HOME=/tmp/metaform-review-live/home
/workspace/scratch/243b683ad142/metaform/.venv/bin/metaform add project review_live /tmp/metaform-review-live/project
cd /tmp/metaform-review-live/project
/workspace/scratch/243b683ad142/metaform/.venv/bin/metaform enable dispatch
/workspace/scratch/243b683ad142/metaform/.venv/bin/metaform set \
  --dispatch-codex /tmp/metaform-review-live-adapter/node_modules/.bin/codex-acp \
  --dispatch-agent codex --dispatch-agents 1 --dispatch-machine-agents 1
/workspace/scratch/243b683ad142/metaform/.venv/bin/python /tmp/metaform-review-live/setup_journey.py
/workspace/scratch/243b683ad142/metaform/.venv/bin/metaform dispatch start <created-ticket-id> codex --json
```

`setup_journey.py` and `setup-commands.jsonl` retain the exact public map/layer/ticket commands and results. `snapshot.py` performs public read-only state/capacity captures. The final PM path, after the child/FQC leases released, was:

```sh
metaform dispatch system agent=codex --json
metaform dispatch message conversation-system --json -- \
  "Report the completed status of root ticket fcc7915d466e450eac7a45284cf63ddd from its current records and the delivery/FQC updates supplied to you. Include the GC-requested generated role, specialist result, actual validation evidence, independent assessment result, and whether any work remains."
metaform dispatch stop conversation-system session=01a14e41-01da-7c92-86f8-0584d4d92209 --json
metaform dispatch agents --json
```

`preparation.json` preserves the separate minimal connectivity probe, the initial restricted-terminal settings refusal and the identical public settings command's successful normal-unsandboxed-terminal retry. No consent identity was emulated, guard changed, or direct settings-store write performed. Process/runtime launches and reads ran through the normal approved unsandboxed execution environment, which also supports the required process accounting.

## Observed limitations retained in the evidence

The live journey passed, and the actual model interactions exposed additional behavior:

- GC `delivered` triggered FQC1 automatically. The real GC subsequently invoked `orchestration_assess` during completion reconciliation, creating FQC2. Both ran serially and passed; the run did not suppress the duplicate assessment.
- FQC1 called `map_work done` before submitting its rich check-in. Its terminal assignment keeps an empty evidence list; the model retained its independent evidence in the root ticket note and the actual harness command record. FQC2 submitted its evidence with delivery.
- Two informational pass-result sends remain pending for the already-ended GC. There was no corrective finding to launch corrective work. The PM actually received and reported both notification updates.
- The conversational PM attempted assignment check-in and received `No recorded assignment for this call`. It still consumed notification context and reported completion. Its status response candidly identifies the old waiting check-in, `unbuilt` condition and 2-of-3 progress counter alongside the completed work/delivery records.
- Official Codex `thread/read` omits the in-flight commissioning MCP item when runtime suspension interrupts the turn. The native transcript retains tool ID `exec-87c49946-c366-434a-ba6b-423e0b834b91` as in progress and `Waiting for commissioned role creation`; creator launch and GC suspension are durably recorded at 08:53:06Z. The real Role Creator's publication and the GC's subsequent continuation are retained. No driver invoked commissioning for the model.
- The adapter emitted a goals-feature-disabled notice after cancellation. The real session resumed and completed. Recoverable tool-argument mistakes and their errors remain in the operational exports.

This one pass-only live journey required no specification adaptation, correction, second invocation of the registered role, peer interruption or compaction. Broader scripted/fake-ACP process and contract evidence for those paths is separate.

## Export boundaries

These are **filtered operational exports**, not lossless transcripts. Internal model reasoning/agent-thought items are omitted from both the official thread export and native snapshot/runtime streams. Authentication account identity is omitted from adapter state metadata. Task and role inputs, visible replies, completed tool calls/results, command output, file changes, context/version receipts and runtime ownership/delivery identifiers are retained. `harness/manifest.json` records thread-level filtering; `live-journey.json` records native filtering and limitations. `SHA256SUMS` covers this directory's delivered files.
