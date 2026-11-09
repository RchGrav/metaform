# Evidence, execution and review limits

Review date: 2026-10-29. All implementation citations use pinned remote main unless a historical revision is named. Tests read, tests executed, historical results and proposed acceptance checks are separate below.

## Revision and working-tree record

| Item | Observation |
| --- | --- |
| Requested repository | `https://github.com/RchGrav/metaform` |
| Local branch/HEAD at start | main, `261a1cb7172159b4354308a423028a86ffc179f3`; commit `fix(autoticket): recover log readers and separate capture from filing`, 2026-10-23T22:39:48-04:00 |
| Initial status | `git status --short --branch` reported `main...origin/main [ahead 1, behind 2]` and no modified/untracked entries. `git status --porcelain=v1` was empty. |
| Target remote main | `fceef55a2fb6bd9bf5f8a46310e1af84276fa9f9`, commit `docs: archive next Metaform specification under next_spec`, 2026-10-28T20:52:14-04:00 |
| Remote verification | `git ls-remote origin refs/heads/main` returned the same full target SHA as origin/main. No fetch, merge, reset, stash, switch or commit was needed. |
| Source materialization | `git archive origin/main` was read through Python tarfile into `/tmp/metaform-review-20261029-fceef55a`, with data-only extraction. ZIP source members were path-checked and extracted under its review-sources directory. No archived executable was run. |
| Why separate source was necessary | Local main lacked next_spec/ and ecs/. The local-only commit changes autoticket capture/recovery, while two remote commits add review archives. `git diff --name-status <local> <target> -- src/metaform specifications tests conftest.py pyproject.toml` bounded implementation divergence to autoticket paths. The isolated target was used for all six reviewers. |
| Final source safety | Final status/diff/integrity results are recorded in SOURCE-CHECKS.json and ARTIFACT-CHECKS.json. The intended only workspace changes are newly created files beneath this review directory. Existing implementation, prompts, instructions and reports remain unchanged. |

## Archive identity and new integrity checks

| Archive on pinned main | SHA-256 | Inspection/new source-integrity result |
| --- | --- | --- |
| `next_spec/metaform-specifications-2026-10-28.zip` | `0ed29b853d95f01f4bd545c7fb68380962abce3831f4f31d439ae3a13963bcb9` | Matches committed SHA256SUMS. All 33 internal manifest entries verified for byte length and SHA-256. |
| `ecs/Inference-Metaform-ECS-Terminology-Review.zip` | `046eafd31b067e32dee11e5fec08fbfe60c17de7cfba848957721f806de3a9e4` | All 23 ECS members adopted into the next-spec archive compared byte-identical with this packet. |

[SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) lists all archive members and computed member digests. [SOURCE-CHECKS.json](SOURCE-CHECKS.json) records the new hash/byte comparison results. These are new source-integrity checks, not integration tests. The internal archive manifest omits its own self-digest, so 33 verified entries is not represented as every ZIP member.

The next-spec archive's provenance identifies ECS source commit `75302f8fa577f5729abe47ba21a19c358ce3d20f`. It explicitly excludes raw private conversations, original uploaded ZIPs, Page exports and the original BMAD workflow/memlog. Those absent private sources were not invented or treated as reviewed. Consequential requirements are taken from the committed archive plus this session's owner amendments.

## Documents and implementation inspected

- Root `AGENTS.md`, `CLAUDE.md`, `README.md`, `specifications/00-index.md` and relevant active BASE/CLI/storage/context/MCP records. The pinned-tree instruction-file inventory found only the root AGENTS.md and CLAUDE.md. No instruction file was edited.
- `next_spec/README.md`, SPEC.md, decisions, agent-interface, lifecycle-and-delivery, acceptance, traceability, completion-work, completeness-review, provenance and member manifest within the ZIP. Archived findings retain proposal/historical status.
- ECS START-HERE/README/triage/paper/technical specification, relevant graph/projection/read/event/handoff/skill/spatial contracts and verification README/results. The combined manuscript is a generated duplicate, not a separate independent source. The coordinator read the canonical numbered documents; scoped reviewers state their inspected ranges and limits.
- Chassis/public base: `cli.py`, `module.py`, `module_metadata.py`, `loader.py`, `settings.py`, `context.py`, `grammar.py`, `results.py`, `home.py`, `prompt_files.py`, `instructions.py`, `caller.py`, `frames.py`, `shown.py`, `events.py`, `changes.py`, `relay.py` and reached data/prompt/history/projection/record paths.
- Module paths: template and fork fallback/copy mechanics; MCP catalog/shaping/server/transport/declaration; intake declarations/schema/served procedure/resources; agents/role/context ledger; memory delivery; reached dispatch runner/proxy/serve/registry/signals/peering/orchestration and orchestration state/episodes; current node README and JavaScript build manifests/entry points.
- This is bounded source/caller review of requested candidates, not an all-lines audit of every optional feature. Each independent report supplies its actual source ranges, consumers and unresolved limits. Filename inventories and lexical hit lists alone are not treated as behavior evidence.

## Historical Ladybug recovery evidence

Primary recovered commits: `98926298ae96be0be5f1e7282ff5cfb2492fa506` (Sept6 native source), `8c2f4a3ae6f8d858a14939f11a85450d9d5f3157` (Sept10 strongest adapter/service/caller/test cut), `3d3543bc84047d86faac59e3533f3f92fcbd72aa` (Sept11 native retirement), `6d991b7a8bf15bfdb2500adc2aef96eb1109a2e6` (Sept21 runtime removal).

Read-only history search covered 1,591 reachable commits in a non-shallow repository and captured 559 branch/tracking/tag ref identities. Nine retained root ZIPs were hashed/scanned. [reviewer05-evidence.json](reviewers/reviewer05-evidence.json) preserves ref identities, root-archive digests/member hits and current lexical coupling candidates.

`metaform.zip` SHA-256 `7705d9bd2bd634e503be73e13cb34f225cfffe88b5477e99a096b48d527110b6` contains backends.py/service.py members matching Sept10 Git blobs. `metaform_2.zip` SHA-256 `7be9449087fac8b681000a461ae02a7a9854d4d127dc772f13f2261f3be5d196` is post-retirement. Member digests, driver version, DDL, queries, callers, transaction and test evidence are detailed in [SEPTEMBER-LADYBUG-RECOVERY.md](SEPTEMBER-LADYBUG-RECOVERY.md).

Searches included Ladybug/LadybugDB/lbug/Kuzu/Cypher hints, but conclusions use actual `ladybug.Database`/Connection calls, manifest identity, schema, query and service-routing evidence. Current GrandCypher/NetworkX was separately identified. No native engine or recovered service was launched. `rich/backups`, nested archives, unrepresented remote refs and unreachable/pruned objects were not exhaustively read. The native implementation was recovered without them.

## Tests inspected

Reviewer 6's AST-only inventory found 177 test files and 2,584 `test_` function definitions in chassis/module trees. These are static definitions, not collected parametrized cases or a run result.

Actual relevant bodies read include:

- Chassis/template/CLI/lifecycle: `tests/test_base.py`, `test_cli.py`, `test_lifecycle.py`, `test_module_tables.py`, `test_module_data_source.py`, `test_feature_storage_boundary.py`, `test_install.py`, template `test_template.py` and fork `test_fork.py`.
- Storage/projections/settings/prompts/history: `tests/test_store_log.py`, `test_store_concurrency.py`, `test_store_map.py`, `test_store_reads.py`, `test_scoped_knowledge.py`, `test_settings_changes.py`, `test_prompts.py`, `test_history.py`, `test_map_changed.py` and `test_relay.py`.
- MCP/intake: `mcp/tests/test_module_discovery.py`, `test_shaping.py`, `test_mcp.py`, `test_mcp_skills.py`, `test_upgrade.py`; `intake/tests/test_intake.py` and `test_guidance.py`.
- Context/memory/runtime: `agents/tests/test_authored_roles.py`, `memory/tests/test_delivery.py`, dispatch `test_informational_delivery.py`, `test_compaction_observations.py`, `test_session_reopen.py`, `test_orchestration_transport.py`, `test_orchestration_runtime.py`, `test_dispatch.py`; orchestration `test_episodes.py`. `test_auto_delivery.py` was read and excluded as context-retention evidence because it concerns commit/landing delivery.
- Historical Sept10: `tests/test_service_analysis.py`, selected `tests/test_knowledge_store.py` and installed-distribution assertion code in `tools/check_distribution.py`. Historical logs were read separately.

This list records files with relevant inspected bodies, not full-file coverage for every entry. Exact line ranges/assertions and full versus partial reads are in the independent reports and challenge. Before drawing bounded gaps, reviewers searched relevant symbols/imports/consumers. No global test-absence claim is inferred from a guessed filename or a plain text miss.

## Tests executed

**None.** Inspection resolved the material review uncertainties. The user authorized focused existing tests only where they would resolve such uncertainty. Running legacy SQLite/fake-harness tests would not establish target compatibility. No tests were added or rewritten.

Isolation was read first: `conftest.py:11` establishes a temporary process home, `:29` substitutes fake ACP/default Full Auto off, `:47` isolates per-test homes/credentials, and `:113` defines in-process versus subprocess CLI. Setup itself seeds SQLite settings. `pyproject.toml:48` selects both trees, enables xdist by default and excludes browser; `.github/workflows/checks.yml:25`, `:47` defines OS/Python checks and Node build/browser steps. This configuration was inspected, not run or asserted green. A later focused legacy check would normally use `uv run pytest -n 0 <selected paths>`.

## Historical results, not new results

- ECS verification/results.json reports sixteen local schema/reference-semantics checks. It explicitly lists Ladybug DDL/Cypher, MCP interoperability, ACP execution, Bevy/hardware and benchmarks as unexecuted, and records an absent driver/failed installation in its original environment. Its generator was not rerun.
- Sept10 `docs/verification.md:100`, `:121` and `docs/reviews/2026-09-09-system-review-evidence/baseline.json:10` report historical installed Ladybug/Cypher/distribution/suite checks. Those are source-attributed records, not this review's passes.
- Sept11 retirement log reports 101 owned-test passes for retirement-era behavior, not the target integration.

## Proposed acceptance checks

[SPEC-AMENDMENTS.md](SPEC-AMENDMENTS.md) and the topic reports propose later target demonstrations: coherent semantic submission/readback/refinement/retry/conflict, three views, exact source/epoch/skill boundaries, no routine live logging with purposeful peer delivery, general event/fallback identity parity, actual Python–Node streaming/cancel/reconnect ownership, target Ladybug transactions/runtime records and distinct unsigned-range sensor profiles. None was added or executed here.

## Material commands and outcomes

The following is a ledger of material commands and read families, not a byte-for-byte terminal transcript. Every reviewer separately records command families and any failed/corrected reads.

| Command/action | Outcome and limit |
| --- | --- |
| `pwd`; `git status --short --branch`; `git status --porcelain=v1`; `git rev-parse HEAD main origin/main`; `git ls-remote origin refs/heads/main` | Recorded clean diverged local main and verified remote target. No branch/worktree mutation. |
| `git log -4 --oneline --decorate --all`; `git log -1 --format=...`; `git diff --stat main origin/main`; scoped `git diff --name-status`; `git ls-tree -r --name-only origin/main next_spec ecs` | Located target archives and bounded local/remote implementation differences. |
| `git archive origin/main` through Python subprocess/tarfile; ZIP listing/path-checked extraction; hashlib/json/ZIP byte comparisons | Separate read source, archive manifests and 33/23 integrity results. No archived code execution. |
| `cat`, `rg --files`, `rg -n`, `nl -ba`, `sed -n`, `head`, `wc -l`, `diff -u`/`diff -q` | Read-only source/skills/tests/instruction inventory and bounded comparisons. Large/truncated reads were followed by exact smaller reads where conclusions depended on them. |
| AST-only Python reads of CLI reserved names/template keywords/test definitions | Confirmed start/demo registry drift and static test inventory without importing product runtime. These are inspection checks, not pytest results. |
| `git log --all` grep/date/path/-S searches, `git rev-list --all --count`, `git rev-parse --is-shallow-repository`, `git for-each-ref`, `git rev-list --all --objects`, `git show <commit>:<path>`, `git grep`, `git hash-object --stdin` | Recovered historical native integration, chronology, callers/tests/manifests and byte identity. No checkout/migration. |
| Read-only ZIP scan of nine root archives, SHA-256/member hashes | Found retained native and retirement-era artifacts. Scope and size/extension bounds are in reviewer 5. |
| System `python` BMAD helper attempts | Failed because system interpreter lacks stdlib tomllib. Corrected to existing `.venv/bin/python`3.13.5. No dependency installation. |
| `.venv/bin/python /home/rich/_bmad/scripts/resolve_customization.py --skill <installed bmad-review or bmad-spec> --project-root /home/rich/metaform --key workflow` | Resolved installed defaults, empty activation/on-complete hooks and no added workflow directives. Repository _bmad runtime is absent. |
| `.venv/bin/python /home/rich/_bmad/scripts/resolve_config.py --project-root /home/rich/metaform` | Failed explicitly: missing required `_bmad/config.toml`. User-specified destination, supplied intent and headless mode were used without creating project configuration or restarting discovery. |
| Installed shared `memlog.py init/append --workspace <this directory>` | Wrote append-only review/spec memory only. Derived SPEC.md preserves capability IDs, source distinctions and proposed status. No archived original memlog was fabricated. |
| Report-only `apply_patch` and Python Path writes | Created this new review directory, synthesis, independent reports and evidence artifacts. No implementation/prompt/instruction/test edit. |

Initial next_spec/ecs reads in the actual checkout failed because those paths were absent there. The verified target snapshot resolved that source issue. Some guessed data/MCP/historical filenames were absent and corrected by symbol/file searches. No absence finding relies on those guesses. Reviewer 4 records one corrected malformed read-only shell command.

## Connected tools and local dependency evidence

The Metaform skill was read and its active catalog used for instruction discovery, `metaform_instructions`, and a focused map_citing query for `src/metaform/module.py`. The latter returned no matches. A later MCP module discovery failed because the connected agents store reported version6 while the installed declaration reported version4. The review did not repair the running installation, run provisioning instructions or infer private map knowledge from that failed path. Source review continued within the user's report-only scope.

The codebase-memory skill was read. `list_projects`, `index_status`, `search_graph` and `check_index_coverage` identified `home-rich-metaform`, generation `2026-10-29T06:06:33Z`. Six key paths reported no recorded issue. The index root is the divergent local checkout. Graph positives were navigation hints, never proof of pinned-target completeness. The initial bounded symbol page was truncated; no exhaustive conclusion relies on it. Pinned direct source governs every material finding.

Cross-review additionally read installed `agent-client-protocol`0.12.1 source: `/home/rich/metaform/.venv/lib/python3.13/site-packages/acp/connection.py:111`, SHA-256 `03fd62e948dc2beb3672aaeaae78cd4e918d148453b50d7cc603345e78171fb8`. Transport send precedes OUTGOING observer, which precedes remote response future. This qualifies local send evidence only. It is environment dependency inspection, not a pinned repository file or live harness result.

Reviewer 4 used web read/search on primary MCP/OpenAI/ACP documentation for changing protocol claims. Exact links and access date are in [RUNTIME-AND-EVENTS.md](RUNTIME-AND-EVENTS.md). Codex support is attributed to the owner, with actual deployed capability/version/event-to-model proof left unverified.

## BMAD workflow application and limitations

Skills read before use: `/home/rich/metaform/.agents/skills/metaform-dev/SKILL.md`, installed `/home/rich/.codex/skills/metaform/SKILL.md`, `/home/rich/.codex/skills/codebase-memory/SKILL.md`, `/home/rich/.agents/skills/bmad-review/SKILL.md`, and `/home/rich/.agents/skills/bmad-spec/SKILL.md`. Review customization and adversarial/edge-case/verification references plus spec template/headless operation were read.

Review lenses were allocated inside the six domain scopes to honor the user's one-coordinator/six-reviewer fan-out. Independent first passes preceded any exchange of other reviewers' findings. Reviewer 6 then challenged all first passes and synthesis. The user-overridden adversarial quota was not applied. Editorial copy-editing/product-discovery workflows were not started.

BMAD specification ran as supplied-input, headless express derivation with an append-only `.memlog.md`, preserving CAP-1..CAP-16 and existing decision/acceptance identities. The report folder replaces the default output destination because the user explicitly requested it. SPEC.md is an amended capability proposal with companions, not a claim the missing original private workspace was reconstructed or the entire rebuild is ready. Coherence and source-preservation verdicts are recorded in the memlog. No stories or implementation were generated.

The frozen six independent pass hashes are in [INDEPENDENT-PASSES.json](INDEPENDENT-PASSES.json). Their original wording was preserved. Corrections are explicit in [06-CHALLENGE.md](reviewers/06-CHALLENGE.md) and the coordinator synthesis, including local-send receipt precision, internal runtime-persistence ownership, pure proxy imports and removal of an unrequested classifier prohibition.

## Overall limits

No current main runtime, September engine, target Ladybug schema/query, first-party Node service, live ACP/Codex harness, draft event transport, retained model context, physical sensor or virtual surround implementation was executed. No latency, cache economics, CPU, throughput or inference-savings measurement is claimed. Source inspection, meaningful legacy test assertions and historical records support the reuse classifications within their stated boundaries. Target interoperability and complete implementation contracts remain later work.
