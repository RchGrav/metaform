# Review register

Status words follow the skill: founder decision, still valid, recommendation, open for the founder.

## Naming

| Item | Status | Source |
|---|---|---|
| Topogee is a shared world (not a game, though it has the bones of one); Metaform is the context tool for development agents; this repo develops both | Founder decision, 2026-11-07 | `DECISIONS.md`, "Naming: Topogee and Metaform" |
| Rename of agent-written documents that call Metaform "Topogee" | Done 2026-11-07 with the founder's approval: `metaform/SPEC.md` purpose statements, `metaform/docs/metaform-concepts.md` (was `metaform/docs/metaform-concepts.md`), `README.md`, `docs/README.md`, `docs/address-only-example.md` | `DECISIONS.md`, "Naming: Topogee and Metaform" |
| `metaform/SPEC.md` file name | Kept, a change from the earlier recommendation: the `topogee` command is the umbrella for both products, and the specification covers the chassis and modules too | same |
| `TOPOGEE.md`, the T in TASTE, "Product: Topogee Navigator" | Open for the founder | same |
| Design documents that still use "Topogee" for the context engine (`docs/designs/metaform-server*.md`, `docs/designs/cli-design.md`) | Not reviewed; many of those uses are the `topogee` command, which is correct | |

## Topogee (the shared world)

| Item | Status | Source |
|---|---|---|
| The founder's layer model L1 to L8, outside in | Proposed by the founder; mapped in world spec section 0 | world spec W-0.1, W-0.2 |
| Identity and authentication | Gap: nothing specified; the most foundational, since channels, permissions, private maps and the launcher wait on it (W-0.1) | |
| Channels, chat and messaging (L3) | Gap: nothing specified | |
| Void-first world; chunks and regions; content on a fixed core; WASM and bus; Rust, Bevy, LadybugDB | Founder decisions | world spec W-1.3, W-2.1 to W-2.5, W-3.1, W-6.1, W-8.1 |
| The bus replaces redstone; redstone and Minecraft mechanics emulated as content; proof of concept with a community texture pack is a milestone and benchmark; never claim to be a clone | Founder decision, 2026-11-07 | world spec W-12.1a |
| Which texture pack | Open for the founder (D-W11). Recommendation: a pack licensed for use in a private install, with no Mojang assets | world spec section 13 |
| World MCP server of its own, or agents owning their own metaform maps | Open: the founder reconsidered W-1.4 on 2026-11-06 | world spec W-1.4; `metaform/SPEC.md` section 11 |
| Fluids and destruction | Drafted 2026-11-07 as world spec section 3.1 (Assumptions and Proposed items); open choices D-W12 to D-W15 | `docs/world-ideas.md`; roundtable 7 `architecture.md` section 2 |
| Voxels or chunks and regions | Still valid as reconciled by the world spec (voxel-addressable space stored in chunks), but the reconciliation is an agent's | roundtable 7 request; `docs/world-ideas.md`; W-2.1, W-3.1 |
| Terrain generator first (2026-11-02) or void first (2026-11-04/05) | Later statement governs: void first | `docs/world-ideas.md`; W-2.3 |

## Metaform (the context tool)

Not reviewed yet.

## Shared infrastructure

| Item | Status | Source |
|---|---|---|
| A bundled service launcher, customized from HoldOn's approach (not vendored), for starting services and assigning process permissions | Founder decision, 2026-11-07 | `DECISIONS.md`, "The service launcher" |
| Which HoldOn parts to take; permissions by named user, capabilities, `no_new_privs`, then cgroups and Landlock | Founder accepted the recommendation, 2026-11-07 | same section |
| Launcher language: C, keeping HoldOn's tested core | Founder decision, 2026-11-07 | same section |
| Permissions in the settings system; AgentSight and the Metaform server first | Founder accepted the recommendations, 2026-11-07 | same section | same section |

| Service launcher design: keep and drop list, permission steps, record paths, on-demand start | Proposed, `docs/designs/service-launcher.md` | |
| Root services' permissions from a root-owned recipe, not the user's settings file | Founder decision, 2026-11-07 (D-SL1) | `docs/designs/service-launcher.md` SL-4.1 |
| AgentSight boot start through `/etc/wsl.conf` | Default taken; the founder can overrule (D-SL2) |
| CLI branch name | Open (D-SL3); `service` proposed | same |

## Income

The founder needs income from this work and has no plan yet for how it will come (2026-11-07). Nothing here is decided.

| Option | Notes | Design choices that keep it open |
|---|---|---|
| Hosted hub | Per-world subdomains under `topogee.com`, managed certificates, an always-on relay past CGNAT, the world directory. Self-hosting stays free. | The hub is a separate service from the world server. Accounts live at the hub. |
| Metaform for development teams | Set aside: the founder sees Metaform's intent as "an open source tool and a proper preprint and add on to my creds" (2026-11-07). Metaform earns reputation and draws users; Topogee's hub and content are where income comes from (open core). | Keep Metaform usable on its own, apart from Topogee. Measure its effect (`metaform/SPEC.md` R-1.3) so the preprint stands on evidence. |
| Content marketplace | WASM blocks, machines and generators, with a revenue share. Fits W-2.5. | Content is addressed by hash and carries a manifest (W-3.5, W-5.3), which gives each item an identity to sell. |
| Licensing | Metaform open source; Topogee's hub and services undecided. No `LICENSE` file exists in this repository yet. Recommendation for Metaform: Apache-2.0, for its patent grant and because HoldOn already uses it. | Decide on purpose before the first public release; keep Metaform and Topogee code separable so they can carry different licenses. |

## The preprint as a credential

| Item | Status | Notes |
|---|---|---|
| Preprint v1.0 text, PDF, citation and bibliography | In `docs/preprint/`, copied from `RchGrav/metaform` (commit `fb0e8b80`) | Text identical to the earlier copy (SHA-256 `2a67b72d...`). |
| A permanent identifier | Recommendation | Post to Zenodo for a DOI (no endorsement needed), or arXiv cs.SE or cs.AI (needs an endorser). A "repository preprint" is hard to cite. |
| Author line | Recommendation, the founder's call | The preprint names the author as "Rich, Independent developer". A full name and an ORCID make it count as a credential. |
| Version 2 | Recommendation | v1.0 describes the earlier `chassis` snapshot, not this rebuild. A v2 with measured results from R-1.3 (with and without Metaform) turns the central claim into evidence. |

## Metaform server: found in use

| Item | Status | Source |
|---|---|---|
| The server runs one stdio process per project and holds an exclusive LadybugDB lock, so a second agent cannot open a map another session is serving | Flaw, confirmed by the founder: "we cant have it blocking that way thats an out of the gate design flaw" (2026-11-07) | Observed 2026-11-07: `/home/rich/roundtable` locked by a session's server (PID 374362) |
| Fix: an instance is a home; one server per home (R-4.4); many instances side by side, each owned by an agent (R-4.14); each agent's stdio entry is a thin relay to its instance's server, started on demand by the launcher (SL-6.1) | R-4.4 and R-4.10 Decided; the instance-is-a-home model and the relay are Proposed | `metaform/SPEC.md` R-4.4; `docs/designs/service-launcher.md` SL-6.1 |
| Metaform registered for this repo in `.mcp.json` (`node metaform/server/src/main.ts .`) | Done at the founder's request; needs the founder's approval in Claude Code | `.mcp.json` |

## Drift from the founder's design (found 2026-11-07)

| Item | Founder's design | What drifted | Status |
|---|---|---|---|
| Map storage | LadybugDB: `metaform.lbug`, one `project.lbug` per project (documentation set 1.2) | A 2026-11-03 record made it JSON files; three design documents and Rust step 1 followed | Corrected in R-4.1, `DECISIONS.md`, `AGENTS.md`, `CLAUDE.md`; design documents bannered; step 1 marked unconfirmed |
| Field names | `technical_name`, `why`, `how`; roles Definitive, Supportive, Notable, Divergent (3.1, 3.2; R-3.4) | Rust step 1 kept `name_length`, `goal`, `function`, DE and SE | Marked in `metaform/rust/README.md` |
| `intent` values | "Single lowercase base verb classifying the interaction transfer mode", example `receive` (documentation set 4.3) | R-6.17 says inbound, outbound or two-way, citing the documentation set; `TOPOGEE.md` says send, receive or send_receive | Open for the founder: intake semantics, not changed |

## Topogee authentication review (2026-11-07)

| Item | Status |
|---|---|
| Argon2id hashes, a decoy check for unknown names (no timing leak), 32-byte random tokens stored only as hashes, case-insensitive unique names, one generic refusal | Sound, as built in M1 |
| No limit on failed logins: a password can be guessed by brute force | To fix after M3 merges: back off a connection and an account after repeated failures |
| No minimum password length on registration | To fix after M3 merges: at least 8 characters |
| `agent add` wrote the accounts store while the server owned it | Being fixed in M3: an owner lock, and in-world issue_agent from a logged-in person |
