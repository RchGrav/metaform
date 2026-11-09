# Verdicts on the AgentSight review findings (StonyApollo)

Scope: only two files are present in `source/` — `crates/agent-monitor/Cargo.toml` and
`crates/agent-monitor/src/capture.rs`. The findings cite additionally `lib.rs` and
`crates/roundtable/src/engine.rs`, which are **not** in this folder. I verified what I could
against the two files I have; where a finding depends on `lib.rs` I say so and mark the
confidence.

## GF1 — Blocker — **Correct, with a correction to the fix**
`attach` checks privileges as its first action and returns before anything else:

```rust
// capture.rs:40-42
if let Some(reason) = missing_privileges() {
    return Err(fail(None, reason));   // fail() = unavailable(bus, harness, None, reason)
}
```

`fail`/`unavailable` publishes `MonitorUnavailable` and yields `Err`; `Running` (and thus every
probe, pump and `MonitorAttached`) is built only after this point (capture.rs:50-100). The test
`attach_without_root_publishes_the_reason` (capture.rs:541-557) asserts exactly this: `Err` with
`capture: None`, and only `MonitorUnavailable` is broadcast. So "runs with what it can observe
unprivileged (process exit, ACP traffic)" is false — the monitor fails **closed**. "Publishes
that capture is unavailable" is the one true part and must be kept.

Fix: the decision (element.md:51) must be rewritten to say: *Without effective root, attach
refuses and publishes `MonitorUnavailable`; nothing is observed by the monitor. Process exit is
reported independently by acp-host's HarnessExited, not by the monitor.* The HarnessExited part
relies on engine.rs:465-466 (not in this folder; reported by the reviewer, plausible).

## GF2 — Blocker — **Correct**
`privilege_shortfall` returns `None` **only** for `euid == 0` (capture.rs:188-190). Any non-root
euid returns `Some`, even with CAP_BPF/CAP_PERFMON held, because AgentSight would fall back to
`sudo -n`, which this crate rejects (capture.rs:195-209). Test at capture.rs:506-510 shows
`Uid: 1000 … CapEff: 000000c000000000` (bits 38/39) still yields a shortfall string containing
"sudo -n". And there is no durable binary to carry file capabilities: `BinaryExtractor::new()`
extracts the probes at attach time (capture.rs:50-52). So "root **or** CAP_BPF/CAP_PERFMON" is
false, and "one-time capabilities step" has nothing to attach to.

Fix: investigations and decisions must say *effective root only*; CAP_BPF/CAP_PERFMON without
root is insufficient; the probes are extracted at run time, so capabilities cannot be installed
on a persistent binary — the monitor must itself run as root.

## GF3 — Major — **Correct**
`start_tls` passes only `-p <pid>`, the harness pid (capture.rs:104-114). The seeded pid family
is passed to the *process* runner only (capture.rs:54-58), never to sslsniff, so TLS/HTTP is
seen for the harness process alone, not its children. No AgentSight LLM classifier is invoked:
every record is mapped by hand in `observe` (capture.rs:219-302).

Fix: narrow "Observable model-provider activity" to "model-provider HTTP(S) requests made by the
harness process itself (TLS via sslsniff, parsed to method/host/path/status, bodies dropped); not
its subprocesses". (The element depends on `lib.rs` to confirm nothing else calls a classifier;
the two files present contain no such call.)

## GF4 — Major — **Correct**
- Cargo.toml:18 `agentsight-capture = { version = "=1.0.35", optional = true }` — exact pin.
- Cargo.toml:8-12 `default = ["agentsight"]`, and `agentsight = ["dep:agentsight-capture", …]`
  — optional behind a default feature; disabling it makes attach report unavailable.
- The probe-binary / libelf-libz-libzstd runtime requirement (lib.rs:55-58) is not in this
  folder; consistent with the prebuilt probes described. Confidence: high on Cargo facts, medium
  on the lib listing.

Fix: add a "Dependency" note to the element: exact version 1.0.35, optional behind default
`agentsight` feature, and the run-time native libraries the extracted probes need.

## GF5 — Nit — **Correct**
All three settings are exactly as quoted: process probe `-p <pid> -m 2 --trace-fs --trace-net`
with `with_seed_pids(&seeds)` (capture.rs:54-58); sslsniff `--binary-path <exe>` only when
`binary_embeds_ssl` (capture.rs:106-114); `HTTPParser::new().disable_raw_data()` (capture.rs:119-123).

Fix: record these settings (or link them) so a reader can tell what is traced.

## GF6 — Major — **Correct**
The decision (fails open / unprivileged observation), the elephant gap ("Needs root") and the
code (`Err` before start) disagree. The code is the arbiter. Fix: this is the same edit as GF1 —
after rewriting the decision to "fails closed, publishes unavailable", the decision, the elephant
and the code agree and GF6 dissolves.

## GF7 — Major — **Correct**
`privilege_shortfall` ignores held capabilities entirely except to quote them back; a
capable-but-non-root process is still refused (capture.rs:191-209; test 506-510). The
investigation's grant-capabilities recipe therefore would not work. Fix: same as GF2 — replace
the capability recipe with "run the monitor as root (effective uid 0)", and say the sudo
fallback inside AgentSight is deliberately not used.

## GF8 — Major — **Correct in substance; one part unverifiable here**
The decision offers "a one-time setup step the owner chooses" with no steps, no link, and no
statement of what to grant. It is unactionable as written. Whether it specifically conflicts with
a "root service under HoldOn" in `code.monitor.activity` cannot be checked from this folder
(that element is not present). The conflict claim does not change the verdict: even if there is
no such service, the decision is still unactionable.

Fix: replace the vague clause with a concrete, testable statement: *the owner may run the
Roundtable process (or the monitor's host) as root; otherwise the monitor is unavailable.
Roundtable never escalates privileges itself and never invokes sudo.* If a HoldOn root service
exists in `code.monitor.activity`, cite it as the sanctioned way to be root; otherwise drop that
reference from the claim.

## GF9 — Nit — **Correct**
"Dos not say how provider traffic is seen or when it can't be." Verified: mechanism is sslsniff
on the harness pid (capture.rs:103-114) plus HTTPParser with bodies dropped (capture.rs:118-123);
it cannot see (a) subprocess traffic, (b) traffic the probe cannot hook (static/embedded TLS is
only partly handled by `--binary-path`), (c) payload contents. Fix: fold this into the GF3
rewording above — state the mechanism (TLS interception + HTTP parse, bodies discarded) and its
limits.

## GF10 — Nit — **Correct**
The investigation records only the owner's WSL2 kernel. Nothing in element.md states the general
platform limits the code enforces: Linux only (capture.rs:170-172, `cfg!(target_os = "linux")`),
effective root required (capture.rs:188-190), probes need the native libs. Fix: add those general
limits to the element and cite the platform check as a single data point, not the whole story.

## Bottom line
All ten findings are correct. The three underlying facts that make the description wrong are:
1. **Fails closed, not open** — without root, attach returns `Err` and only `MonitorUnavailable`
   is published (capture.rs:40-42; test 541-557). (GF1, GF6)
2. **Effective root only** — CAP_BPF/CAP_PERFMON without root is refused; probes are extracted at
   run time so capabilities cannot be granted persistently (capture.rs:179-209, 50-52). (GF2, GF7, GF8)
3. **TLS scope is the harness pid only**, bodies dropped, no LLM classifier (capture.rs:103-123,
   219-302). (GF3, GF9)

Adopt all, applying the replacement edits above so the decision, elephant, investigations and
wants layers agree with these three facts.
