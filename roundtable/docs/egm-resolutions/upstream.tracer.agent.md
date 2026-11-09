# AgentSight review resolutions

Prepared by SereneSpear from `element.md` and the supplied source snapshot.

The appropriate immediate fix is to correct the description to match the current integration. The snapshot supports effective-root-only capture, explicit unavailability reporting, process-family tracing, and harness-PID TLS/HTTP metadata capture. It does not support an unprivileged capture mode or capability-only setup. Those would require separate implementation work if retained as requirements.

Evidence scope: only `source/crates/agent-monitor/src/capture.rs` and `source/crates/agent-monitor/Cargo.toml` are supplied. References below use their original repository paths. The reviewers also cite `lib.rs`, `engine.rs`, upstream implementation details, and a HoldOn service description that are absent here. Conclusions depending on those sources are explicitly qualified. No code changes or executable tests are required to write these decisions, and this snapshot has no workspace manifest with which to run the crate tests.

## GF1 — Accept the core finding; correct its overstatement

**Decision:** The decision layer incorrectly attributes unprivileged process-exit and ACP observation to this monitor. However, “nothing is observed” must not be read as “nothing is published.”

**Evidence:** `capture.rs:37–42` calls `fail(None, reason)` and returns `Err` before collecting processes or starting probes. `fail` calls `unavailable`. The included test `attach_without_root_publishes_the_reason` (`capture.rs:540–556`) explicitly expects the returned error to be published as `MonitorUnavailable`. The implementation of `unavailable` itself is in the missing `lib.rs`. The supplied capture implementation has no ACP fallback; its process-exit mapping (`capture.rs:236–240`) consumes probe records and therefore is unavailable when attachment is rejected.

**Change:** Replace “the monitor runs with what it can observe unprivileged” with: “When capture cannot attach, attachment returns `MonitorUnavailable` and publishes the reason; no capture session is started. Roundtable's ACP and harness-lifecycle reporting are separate mechanisms.” Confirm application continuation and the specific `HarnessExited` ownership against the full caller code before documenting them as verified behavior. Fail-open at the application boundary can coexist with failed monitor attachment; this snapshot proves the latter, not the former.

## GF2 — Accept

**Decision:** Capability-only setup is not supported by the current wrapper, regardless of what the kernel could permit.

**Evidence:** `privilege_shortfall` accepts effective UID 0 and rejects every other UID (`capture.rs:179–209`). Capability bits are read only to explain rejection. The test at `capture.rs:506–509` covers rejection with both CAP_BPF and CAP_PERFMON. The comment and diagnostic explain that upstream would otherwise use `sudo -n`; the wrapper rejects before reaching it. `BinaryExtractor::new()` obtains probe executables during attachment (`capture.rs:50–58`), and `Running` holds the extractor for the capture lifetime (`capture.rs:23–26`). There is no stable, administrator-installed probe path configured in this wrapper.

**Change:** Remove the capability-grant setup claim from the decision and qualify the investigation: kernel-level capability possibilities are not a supported deployment mode for this integration. Document that the current capture host must run with effective UID 0 and that the wrapper performs no escalation. Root is a prerequisite, not a guarantee that probes attach. Do not suggest applying file capabilities to the main application or transient probes as a working fix. Supporting capabilities requires changing both the local gate and upstream launch behavior, and supplying a deliberate probe installation/execution arrangement.

## GF3 — Accept the coverage limit; do not require an LLM classifier merely to observe HTTP

**Decision:** Process-family coverage must not imply equal TLS coverage. The absence of provider classification limits the meaning of “model-provider activity,” but does not prevent ordinary HTTP metadata from exposing a recognizable provider host.

**Evidence:** The process runner receives process-family seeds (`capture.rs:43–58`); the TLS runner receives only `-p <harness pid>` and no family seeds or child attachment logic (`capture.rs:103–114`). The analyzer pipeline constructs timestamp normalization and `HTTPParser`, with no LLM classifier (`capture.rs:117–132`). Published parsed observations contain request method, host, path and exchange ID, response status and exchange ID, and unfinished-exchange metadata (`capture.rs:265–286`). No parsed model, tokens, prompt or provider-specific classification is published.

**Change:** Narrow the want to “process-family activity and, where the TLS probe can instrument the harness PID, HTTP request/response metadata that may reveal provider contact.” Explicitly state that child-process provider requests are outside the configured TLS coverage and that no LLM semantic classification is performed. If descendant provider visibility is mandatory, add lifecycle-managed TLS attachment for relevant descendants and verify it with a harness whose child performs the request. Add classification only if semantic provider/model information is actually required.

## GF4 — Accept the dependency-documentation gap, with an evidence limit

**Decision:** The exact dependency and feature details are established; the prebuilt-probe and runtime-library claims need verification from the omitted source or pinned upstream package.

**Evidence:** `Cargo.toml:8–12` makes `agentsight` a default-enabled feature. Line 18 pins the optional dependency exactly to `agentsight-capture = "=1.0.35"`. The manifest comment says disabling the feature makes `Monitor::attach` report `MonitorUnavailable`; the feature-disabled implementation is not supplied. Runtime extraction is visible in `capture.rs:50–58`, but extraction alone does not prove which build tools or shared libraries are required. The cited `lib.rs:55–58` is absent.

**Change:** Record version `1.0.35`, exact pinning, default-enabled optional feature, and the documented no-feature unavailable behavior. Add verified build/runtime prerequisites for that pinned package. Specifically check the claim that probes ship prebuilt (so no probe compilation with clang/kernel headers is needed locally) and require libelf, libz and libzstd at runtime before presenting that list as authoritative. Do not silently substitute an upstream latest-version requirement for the pinned package's requirements. This finding does not justify changing the dependency or feature defaults.

## GF5 — Accept

**Decision:** Record the integration settings because they explain its observation scope and data handling.

**Evidence/change:** Add a compact configuration note covering:

- Process runner: `-p <harness pid> -m 2 --trace-fs --trace-net`, seeded from the harness and existing descendants; the source comment says the probe follows later descendants (`capture.rs:43–58`).
- TLS runner: `-p <harness pid>`; add `--binary-path <harness executable>` only when reading `/proc/<pid>/exe` succeeds and `binary_embeds_ssl` identifies embedded SSL (`capture.rs:103–114`). This is conditional, not a guarantee that all TLS implementations work.
- Normalize timestamps and pass TLS records through `HTTPParser::disable_raw_data()` (`capture.rs:117–132`). Bodies may be parsed internally, but parsed observations publish only the selected metadata (`capture.rs:118`, `265–286`). Do not describe this as “no plaintext is ever captured or processed.”

No code change is needed for this documentation finding.

## GF6 — Accept; resolve together with GF1 and GF2

**Decision:** The decision and gap currently describe different layers without saying so, creating a real contradiction.

**Change:** State consistently: capture requires effective root; rejection reports capture unavailable and produces no running capture session. Application-level continuation, ACP messages and harness exit reporting must be documented under their actual owners after checking their caller code. Replace the bare “Needs root” gap with “Current wrapper requires effective UID 0; capability-only and unprivileged capture modes are unsupported.” Do not implement a dummy monitor solely to make the old wording appear true.

## GF7 — Accept the setup contradiction; reject the claimed executed fallback

**Decision:** The investigation's capability alternative does not work through this integration. But the wrapper does **not** actually fall back to `sudo -n`.

**Evidence:** `capture.rs:40–42` rejects before probe startup; `capture.rs:179–209` explains why upstream's non-root launch policy causes this restriction. A diagnostic about an upstream code path is not evidence that the wrapper executes that path.

**Change:** Align investigation, decision and elephant gap around effective-root-only capture, with no automatic escalation, as in GF2. Keep the historical WSL2 kernel observations as dated machine-specific evidence, not as proof that capability setup works. This prevents users from following an ineffective capability recipe or expecting a sudo prompt.

## GF8 — Accept missing operational guidance; the claimed HoldOn conflict is unproven

**Decision:** “One-time setup” is not actionable and currently points at an unsupported capability mechanism. However, a deliberately provisioned root service and owner-controlled setup are not inherently contradictory. No HoldOn service configuration or description is supplied to establish an actual conflict.

**Change:** Replace the capability setup promise with a link to the actual deployment instructions for whichever component hosts capture. If HoldOn hosts it, document the real service name/configuration, effective user, harness/PID visibility and startup procedure; otherwise document the real hosting arrangement. State that the owner provisions privileges and the wrapper does not escalate. Verify that the deployment actually calls attachment from the privileged context. Do not invent a service name, command or service implementation from the review text, or recommend running unrelated components as root to fill this documentation gap.

## GF9 — Accept; resolve with GF3 and GF5

**Decision:** “Observable model-provider activity” needs a mechanism and explicit boundaries.

**Change:** Explain that an sslsniff probe instruments supported TLS library calls for the harness PID, followed by HTTP parsing and publication of selected metadata. Embedded SSL may cause the executable to be passed as `--binary-path`. Provider contact may be inferred from host/path; the integration does not classify provider/model semantics. Missing privileges, failed probes, unsupported TLS instrumentation, traffic originating in children or other processes, and traffic the HTTP parser cannot parse can prevent this view. Network summaries remain a separate observation and do not guarantee provider identification. Use these bounds instead of implying general visibility into model calls.

## GF10 — Accept

**Decision:** The dated WSL2 check is useful evidence for one machine, not a supported-platform specification.

**Evidence:** `missing_privileges` explicitly rejects non-Linux at runtime and reads Linux `/proc/self/status` (`capture.rs:168–176`); attachment reads the process table, and TLS executable resolution uses `/proc` (`capture.rs:43`, `108`). The supplied files do not establish architecture support, minimum kernel version, a non-Linux build guarantee or an exhaustive eBPF feature matrix.

**Change:** Document Linux runtime capture, usable `/proc` and target-process visibility, effective-root requirements, and compatible kernel/probe support. Preserve the investigation's kernel configuration/BTF observations as dated local checks. Link verified requirements for the pinned upstream version, including supported probe architectures and kernel prerequisites, rather than extrapolating them from kernel 6.18 on one WSL2 host. State that root alone does not overcome missing kernel features or host restrictions. No portable fallback capture is implemented here.

## Consistent replacement account

Use this core wording across the decision, want and elephant layers, supplemented by the dependency and deployment details above:

> AgentSight capture uses the default-enabled `agentsight` feature and the exact `agentsight-capture` version 1.0.35. The current wrapper requires a Linux capture host running with effective UID 0 and a compatible kernel/runtime environment; it neither supports capability-only startup nor escalates privileges. If attachment fails, it reports capture unavailable instead of starting a capture session. When available, the process probe tracks the seeded harness process family and later descendants. The separate TLS probe targets the harness PID and feeds HTTP parsing; it publishes selected HTTP metadata, not LLM classification or request/response bodies. TLS failure can leave process capture running. ACP and harness-lifecycle reporting belong to separate parts of Roundtable.

The independent TLS failure behavior is explicit in `capture.rs:90–100`: it reports TLS unavailability and still returns the running process capture. This is a supported partial-capture mode and should not be confused with the nonexistent unprivileged fallback.
