# DeifiedVessel — verification notes for ACP harness resolutions

Per-finding evidence from `source/crates/acp-host/src/launch.rs` (the only supplied file).

| Finding | What launch.rs actually shows | Consequence for the decision |
|---|---|---|
| GF1 | `custom()` (235) = user-supplied; `parse_registry`/`autoselect` (96-138,214-231) = registered. No in-repo harness exists in this file. Cited `tables.rs`/`adapter.ts` absent from `source/`. | The "registered or user-supplied" catch-all cannot cover an in-repo, always-offered harness → real gap. Confirm "offered first"/v1 externally before asserting specifics. |
| GF2 | `builtin()` 78-90 pins claude-agent-acp@0.101.0, codex-acp@2.5.0, pi-acp@0.0.34, opencode-ai@1.19.5 `acp`. `autoselect` 230 = whole builtin() on Err; 222-227 = append builtins whose id the registry omits on Ok. | Finding fully verifiable. Record pins + both conditions. Package versions ≠ protocol versions (relates to GF6). |
| GF3 | `element.md:10` v1 uri vs `:55,57` v2 claims. | Internal inconsistency. Fix = state version scope, not swap uri to v2 (would then misrepresent v1 harnesses). |
| GF4 | No `initialize`/`session/*`/`set_config_option` anywhere; launch.rs is autoselection/launch only. | RPC list belongs to `code.client.agent` (referenced to design doc §4), not here. Add citations + scoping note; do NOT delete claims. |
| GF5 | launch.rs never reads protocol version — version-agnostic. | Gap is unstated *implication* of v1/v2, a description defect. State needs/supports/breaks. |
| GF6 | No RPCs in launch.rs; version split asserted in elephant. | Version-qualify the want's method list. |
| GF7 | Pi is a pinned builtin (line 87) → launchable in code. | "Never run" = recorded experience, not capability. Add reason/status to avoid false "unsupported" inference. |
| GF8 | Ambiguity is in wording of `element.md:57`. | Plain reword: what set, how inspected, against what criterion. |

Key distinction driving several decisions: **package version** (GF2, e.g. `codex-acp@2.5.0`) vs **ACP protocol version** (GF3/GF5/GF6, v1/v2) vs **session RPC set** (GF4/GF6, client element). Conflating these is the root of the comprehension findings.
