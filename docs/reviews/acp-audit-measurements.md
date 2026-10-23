# ACP orchestration audit measurements

Baseline: `977f1bfe99bdea89bd89dc8ef36807047befe6e8`, the repository snapshot pushed before this rework. The paired fixtures below describe the initial implementation at `8df925ee`, before the native-efficiency follow-up in [the implementation record](acp-context-implementation.md).

Measurements use isolated temporary Metaform homes and the same prepared functional map. No paid model session is used for the paired fixtures. Their provider calls, reasoning tokens, cache use, native instruction composition and billing remain unknown. A separate current-only real-adapter smoke below reports the usage fields actually returned by that adapter. ACP requests and delivered text are observable and are reported separately from provider usage.

## Unchanged justified hold

Run:

```bash
git worktree add --detach /tmp/metaform-acp-baseline 977f1bfe99bdea89bd89dc8ef36807047befe6e8
uv run python scripts/measure_acp_audit.py --baseline /tmp/metaform-acp-baseline \
  --output docs/reviews/acp-audit-measurements-holds.json
```

The fixture records the same explicit hardware-delivery hold and reconciles at simulated times 1000, 1900, 2800 and 3700 seconds. It consumes each generated review signal, matching a liaison that already received the review. The desired outcome remains a held, unresolved ticket in both revisions.

| Observable | Baseline | Revised |
| --- | ---: | ---: |
| Actionable review signals | 3 | 0 |
| Signal explanation text, UTF-8 bytes | 945 | 0 |
| Automatic future review deadline after final pass | 4600 | None |
| Held outcome preserved | Yes | Yes |

These are avoided actionable wake requests and delivered signal bytes. No liaison model ran, so this does not establish a billed token or model call reduction. The JSON records source fingerprints and unavailable fields explicitly.

Focused verification covers one review for missing legacy reasons, pending-batch coalescing, restart, concurrent delivery, crash between claim and publication, retirement of pre-upgrade periodic batches, unchanged justified holds, targeted ticket reads and zero storage reads for bursts of unrelated events. Existing autostart tests prove held work stays held and `after_work` prerequisites prevent startup until completion. Arbitrary prose conditions still require agent reasoning or user direction. A meaningful deadline can use the existing one-shot agent timer; this change adds no deadline inference.

## ACP trace interpretation

`scripts/measure_acp_audit.py` also provides `summarize_trace(Path)` and accepts `--baseline-acp-log` and `--revised-acp-log`. It counts fake-adapter process starts, `session/new`, `session/load`, `session/resume`, `session/prompt`, transmitted text bytes, exact paragraph bytes repeated from preceding prompts, and successful fake work completions. Blank paragraph separators are excluded from repeated-byte counts. Provider usage remains unknown. Replay through `session/load` is not assumed to be newly billed context.

## Rendered first-turn and role text

Run:

```bash
uv run --with tiktoken python scripts/benchmark_agent_context.py \
  --baseline-ref 977f1bfe99bdea89bd89dc8ef36807047befe6e8 \
  --output docs/reviews/acp-audit-measurements-rendered-text.json
```

This existing deterministic benchmark creates the same timer functionality, claims an implementer, renders its first prompt and role resource, and records a fixed successful result. Random hexadecimal identifiers retain their original lengths while their contents are normalized, as are timestamps. It does not run an agent or measure provider billing. `o200k_base` is the stated comparison tokenizer, rather than a claim about an adapter's actual tokenizer. Source fingerprints and exclusions are in the JSON.

| Rendered text, `o200k_base` tokens | Baseline | Revised |
| --- | ---: | ---: |
| Worker first prompt | 1933 | 1747 |
| Role resource read | 995 | 1144 |
| Claim response | 23 | 23 |
| Fixed worker result | 16 | 16 |
| Total fixture text | 2967 | 2930 |

The first prompt is 186 comparison tokens smaller (9.62%). The role resource grows by 149 tokens. Total measured fixture text falls by 37 tokens (1.25%). These figures alone do not establish improved useful work per billed token. They show why first-prompt reduction must be assessed together with follow-on resources and successful work.

## Three related cards across runner replacement

Both traces use the same prepared `code.engine` map, three sequential work records, the same implementer role and the same fake ACP adapter with `small` model, `high` effort and load support. Automatic startup, Stay connected and the extra completion turn are disabled in both cases to keep unrelated notification workers outside the scenario. Each runner exits after its work record completes.

The baseline explicitly selects the same runtime for each card because it has no episode inheritance. The revised fixture explicitly links the second and third cards with `continue_from`, retaining the first selection. Neither fixture infers relatedness from wording. Both verify all three work records complete and their orchestration assignments reach `delivered`. These are simulated work completions, not an evaluation of production code quality.

| Observed fake ACP workflow | Baseline | Revised |
| --- | ---: | ---: |
| Completed work records | 3 | 3 |
| Adapter process starts | 3 | 3 |
| `session/new` | 3 | 1 |
| `session/load` | 0 | 2 |
| `session/prompt` | 3 | 3 |
| Delivered prompt text, UTF-8 bytes | 29636 | 11829 |
| Exact paragraph bytes repeated from earlier prompts | 14912 | 0 |

The revised workflow creates two fewer ACP sessions and transmits 17807 fewer prompt text bytes (60.09%). Process starts and ACP prompt requests stay at three. It preserves context across adapter process replacement rather than claiming a continuously running adapter. The provider may handle loaded history in ways these observations cannot expose. Native context retention, model calls, cache cost and billed tokens remain unknown.

Reproduce the baseline trace by copying `scripts/acp_audit_baseline_case.py` into the baseline checkout as `src/metaform/modules/dispatch/tests/test_acp_audit_baseline_case.py`, then running it there with the repository virtualenv interpreter, `PYTHONPATH` set to the baseline `src` and root, and `METAFORM_EPISODE_TRACE=/tmp/metaform-episode-baseline.jsonl`. Run the revised integration test with:

```bash
METAFORM_EPISODE_TRACE=/tmp/metaform-episode-revised.jsonl uv run pytest -n 0 -q \
  src/metaform/modules/dispatch/tests/test_episode_transport.py
uv run python scripts/measure_acp_audit.py --baseline /tmp/metaform-acp-baseline \
  --baseline-acp-log /tmp/metaform-episode-baseline.jsonl \
  --revised-acp-log /tmp/metaform-episode-revised.jsonl \
  --output docs/reviews/acp-audit-measurements-workflows.json
```

The summary stores trace fingerprints instead of raw traces, which contain test-process environment details. UTF-8 bytes count actual delivered text, including temporary fixture paths and random identifiers, without estimating tokens. The normalized rendered-text comparison above measures prompt changes separately from episode continuity.

## Actual runner idle CPU

The same fake adapter held one unfinished turn in each revision while its actual dispatch runner stayed alive. The two isolated workflows ran concurrently. After the first ACP prompt was observed, the harness sampled Linux `/proc/<pid>/stat`, waited once for 60 seconds, then sampled again. This interval may include the final initial fake notifications. It contains no intentional incoming changes or paid model execution. Both tickets remained open, and both workflows stopped through fixture cleanup.

| 60-second process CPU observation | Baseline | Revised |
| --- | ---: | ---: |
| Runner CPU seconds | 0.13 | 0.13 |
| Runner percent of one core | 0.217% | 0.217% |
| Fake adapter CPU seconds | 0.01 | 0.00 |

This shows no observed runner idle CPU regression in the fixture. The adapter difference is one Linux accounting tick and does not support a performance improvement claim. This does not measure the web server, production load, provider latency or reasoning throughput.

The reusable fixture is `scripts/acp_audit_idle_case.py`. Copy it into each checkout's dispatch tests directory, then run that copied file with `METAFORM_IDLE_MEASUREMENT` naming its result. The baseline uses its own `src` and root in `PYTHONPATH`, with the same virtualenv interpreter. The temporary copied current test was removed after both processes completed. `docs/reviews/acp-audit-measurements-idle.json` retains the measured durations and CPU values.


## Current-only authenticated native adapter

A separate bounded real worker ran through the normal Metaform ACP runner in a private temporary home/project. Discovery observed shell Codex CLI `0.162.1`, authenticated through ChatGPT, and `@agentclientprotocol/codex-acp` `2.2.2`. Follow-up inspection of the native session metadata establishes that the adapter actually used its bundled Codex `0.160.1`. Its advertised original defaults were `gpt-6.1-sol` and `high`. The isolated project's chosen `gpt-6-luna` and `low` were confirmed in the final session settings. The default native `agent` mode remained selected and Fast mode remained off.

The worker created `result.txt` containing exactly `alpha\n`, preserved `preserved.txt` byte-for-byte, read the exact stored request through `map_work op=sources` before writing the artifact, and completed its assigned work record. Native tool-result observation confirms the exact request text, including its exception, reached the worker. All sessions in that isolated home ended. One malformed tool/arguments request was corrected before the successful source read.

| Actual current-only observable | Value |
| --- | ---: |
| ACP `session/new` / `session/prompt` / `session/close` | 1 / 1 / 1 |
| Sent prompt text, UTF-8 bytes | 9488 |
| Adapter-reported total tokens | 466202 |
| Adapter-reported uncached input / output tokens | 26103 / 1187 |
| Native input tokens, including cached input | 465015 |
| Adapter-reported cached-read / cached-write tokens | 438912 / 0 |
| Adapter-reported thought tokens | 0 |
| Native usage records / custom-tool calls | 17 / 16 |

These are adapter-reported aggregate fields for one ACP prompt, not independently verified provider billing. Follow-up native-log inspection identifies 17 unique response IDs with usage, corresponding to 17 successful native model requests inside that one ACP prompt. Native `token_count` and `token_usage_record` are duplicate accounting streams, so they must not be added together. Their per-request sum matches the final cumulative total: 465,015 input tokens, including 438,912 cached input tokens, plus 1,187 output tokens. Failed or unreported requests and provider-internal processing remain outside this observation. The small artifact incurred substantial native onboarding and serial tool inference, so this case supports no native token-savings claim.

The preexisting person-only control refused an attempted per-ticket model/effort edit from an agent-run terminal before any model invocation. No human-terminal proof or commissioned role was fabricated. The actual smoke therefore used isolated project defaults and disabled optional orchestration to avoid JEV or extra routing. Actual native episode reuse remains unmeasured; the paired fake-ACP workflow separately proves that transport path.

Reproduce discovery with `uv run python scripts/acp_audit_live_case.py --discover`, then use its private temporary root with `--run <root> --model <advertised-model> [--effort <advertised-effort>]`. The script forces `METAFORM_HOME` to that root, records ACP metadata through a transparent proxy without prompt/auth bodies, and stops its isolated worker after its bounded interval. [The sanitized evidence](acp-live-adapter.json) records exact checks, observed configuration, reported usage and trace fingerprints. No native credential or raw native transcript is included.
