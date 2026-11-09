# GammaLiquid evidence notes

Only `source/crates/acp-host/src/launch.rs` is present under `source`.

| Evidence | What it establishes |
| --- | --- |
| Lines 78–90 | Four built-in harness recipes and exact pinned packages; no OpenRouter entry in this particular list. |
| Lines 117–130 | Installed binaries may differ from registry versions; registry launches can follow other paths. |
| Lines 195–198 | Built-in availability checks whether the command runner is on PATH. |
| Lines 212–231 | Fetch failure returns built-ins; successful registry parsing appends missing built-in IDs. A matching unavailable entry still suppresses its fallback. |
| Lines 274–339 | Tests concern launch selection, environment filtering, and command parsing. |

No supplied source shows ACP initialization, session RPC handling, negotiated protocol versions, OpenRouter ordering, recorded runs, or a dated registry-wide audit. Thus the central distinction in `resolution.md` is between verified launch behavior and reported protocol/runtime behavior. A package's major version and a registry URL's version segment cannot substitute for protocol-negotiation evidence.
