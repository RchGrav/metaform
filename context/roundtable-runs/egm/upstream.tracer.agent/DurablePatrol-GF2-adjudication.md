# DurablePatrol — adjudication of the contested GF2 point (round 2)

## The contested claim (CrystalOzone, R1-5)
"GF2's resolution should be a *code change*, not just a description fix": relax
`privilege_shortfall` to accept non-root when CAP_BPF + CAP_PERFMON are held, grant
those capabilities to the monitor process (not to a probe binary), let the spawned
probes inherit them, and thereby make the original investigation claim true.

## Verdict: the distinction CrystalOzone raises is real, but the conclusion is wrong
for a *review-finding resolution*, and the current `resolution.md` (SereneSpear's
draft) already places it correctly. No edit to GF2 is needed.

### What is correct in CrystalOzone's reasoning
1. The finding's "no lasting capture binary" objection is about granting file
   capabilities to a transient *probe file* (`BinaryExtractor::new()` at
   capture.rs:50-52). It does not, by itself, foreclose granting capabilities to
   the *monitor process*. A child process inherits the parent's effective
   capability set, so probes spawned by ProcessRunner/BinaryRunner (capture.rs:55-64,
   114-115) would carry CAP_BPF/CAP_PERFMON if the monitor held them. That is a
   fair and genuinely new distinction.
2. CAP_BPF + CAP_PERFMON are, at the kernel level, sufficient to load and attach
   eBPF programs without full root. So "only root works at the kernel level" would
   be too strong a general statement.

### Why it is NOT the resolution of GF2
1. The refusal is not purely the wrapper's gate. The diagnostic at capture.rs:205-209
   and the doc comment at 179-180 say **AgentSight itself** runs probes directly
   only at euid 0 and otherwise re-launches them through `sudo -n`. The wrapper calls
   `ProcessRunner::from_binary_extractor(...).run()` / `BinaryRunner::ssl(...).run()`;
   there is no visible flag in this file that tells AgentSight to skip sudo. Relaxing
   `privilege_shortfall` alone (returning `None` for capped non-root) would therefore
   NOT make probes run directly — upstream would still attempt `sudo -n`, which the
   environment may refuse. CrystalOzone concedes this as a caveat, but then still
   recommends the code change as "the better resolution"; the caveat actually defeats
   the recommendation. It requires changing code in `agentsight-capture`, which is
   not in this repo snapshot and is not this element's code.
2. GF2's finding is "the description contradicts the code." The correct resolution of
   such a finding is to make them agree. Either (a) fix the description to say
   "effective root only" — which is what the code does — or (b) implement a new
   capability-based launch path as a *feature*, which is a different task with its
   own tests and upstream coordination. Mixing (b) into (a) as "the fix" would leave
   the description still unverified against the shipped code in the meantime.
3. SereneSpear's GF2 "Change" (resolution.md:23) already states this correctly:
   "Supporting capabilities requires changing both the local gate and upstream launch
   behavior, and supplying a deliberate probe installation/execution arrangement."
   And the preamble (line 5) says such modes "would require separate implementation
   work if retained as requirements." That is the right classification: a possible
   future feature, not the resolution of the finding.

### Recommendation to the table
Keep GF2's verdict = Right, fix = description-only (effective-root-only, no escalation,
no capability setup recipe). Record CrystalOzone's capability-inheritance idea as a
clearly-labelled "possible future enhancement, requires upstream change + new tests",
NOT as the change that resolves GF2. Do not adopt "GF2 is resolved by a code change."

## A second precision point worth preserving (from SereneSpear's GF7)
GF7's finding text says "the code shows capabilities without root still fall back to
sudo -n." That is subtly wrong: the wrapper does NOT fall back to sudo. `attach`
returns `Err` at capture.rs:40-42 *before* any runner is constructed; the `sudo -n`
string only appears in the human-readable *diagnostic* (capture.rs:205-209) that
explains upstream's policy. A string describing an upstream path is not evidence the
wrapper executes that path. SereneSpear's GF7 ("reject the claimed executed fallback")
is correct and sharpens the collective answer. My own round-1 draft repeated the
looser "falls back to sudo" phrasing; I retract that phrasing in favour of "would
fall back, but the wrapper rejects first".

## Minor wording nit in the current resolution.md (non-blocking)
GF10 (resolution.md:83) says `missing_privileges` "explicitly rejects non-Linux at
runtime". `cfg!(target_os = "linux")` (capture.rs:170) is a compile-time constant, so
this is a compile-time guard, not a runtime check. The rest of the GF10 evidence
(`/proc/self/status` reads) is genuinely runtime. Suggest "compile-time guard" for
precision; does not change the verdict.

## Net assessment of the current resolution.md
The file now in the workspace (SereneSpear's 93-line draft) is complete, correctly
scoped (flags lib.rs/engine.rs/HoldOn as absent), consistent across GF1/GF2/GF6/GF7,
and handles the GF2 capability question correctly. It is a better artifact than my
round-1 draft. No further edit is required from me; I will not overwrite it.
