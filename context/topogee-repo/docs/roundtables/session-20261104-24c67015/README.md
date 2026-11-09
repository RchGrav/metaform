# Roundtable session 20261104-24c67015

Shared folder for the 10-panel review. Four seats: Opus, Astra, Sol, Fable. Five sessions, held on 2026-11-04. R4 (devices) was not held.

**Start here (owner):** `panel-10-synthesis.md`, section "Owner brief", states the three open questions in plain terms. Then read its "Effect on foundational decisions" table. `ledger.md` holds every row with its basis; `contradictions.md` holds the conflicts; `l60-verification.md` holds what was and was not tested. No runtime check was performed in any session.

## Roles (agreed in R1)

| Role | Seat |
|---|---|
| Synthesis lead (P10) | Opus |
| Contradiction register | Sol |
| Carry-forward ledger | Fable |
| Terminology crosswalk, angle A and B checks | Astra |

## Files

| File | Content | Author |
|---|---|---|
| `README.md` | This index | Fable, others adjust |
| `panel-01-sources-authority.md` | P1 report: source authority, crosswalk, decided or proposed status per source | written |
| `panel-02-ecs-without-engine.md` | P2 report: addresses as entities, CELs as components, resolver scope (C-2) | written |
| `contradictions.md` | C-1..C-8. R2 added C-6 (stale D-9 ground) and C-7 (Bevy pin). R3 updated C-5 and added C-8 (`store.ts:7-8` header conflict). R5: C-2 reads "not specified" and stays open (F2); C-5 limited to world storage with labels split (F3); G1 runtime status, application guards and outcome counts recorded as Proposed; a review-response section | Sol, written; Opus confirmed |
| `panel-03-bevy-ruling.md` | P3 report: link, not host; criteria under angles A and B; crate counts; L-1 to L-5, L-4a; L-28 open. R5 mark: L-3 scoped to the world server (F4) | Opus, written |
| `panel-04-link-cel.md` | P4 report: link CEL fields, L-6 budget and gate, stale-ID tests 1–4, boot token, C-2 delivery; L-6 to L-10a. R5 marks: `goto` delivery (F1), `status` derived at runtime (G1), resolver delivery waits for the owner (F2) | Opus, written |
| `ledger.md` | Every row with its basis and agreement: L-1 to L-10a (R2), L-20 to L-22a and L-29 to L-32 (R3), L-33 (R5, Proposed). R5 section: L-33 derived status, its additions (observers, response kinds, preconditions, cause 2 guard, join key), the boot-token safeguard, ten proposed checks. Review-challenge table with citation checks and R5 results. Success criteria 1–10. Open questions | Fable; Opus rebuilt after edit loss in R1 |
| `l60-verification.md` | R3 output: the four L-60 checks are untested at `24a72b3`; the missing paths are named; L-10 stays agreed and unverified. R5: source corrections (F1, F2), nine proposed link checks R5-1 to R5-9 (untested), observers and counting rules | Sol, written; Opus confirmed |
| `panel-07-storage-interface.md` | R3 output: C-5 store table, link CEL persistence (world-first, dual `instance_id`), common interface and echo rule, status labels (P4 enum kept), C-8; L-20 to L-22a, L-29 to L-32. R5 marks: world link (G2), `instance_id` only on the submit path (G1), F3 labels; the review table replaces the pending note | Opus, written |
| `r3-astra-crosswalk.md` | R3 crosswalk: identity and binding state; withdraws the T285 reading of `stale`; `unbound` covers an address conflict | Astra, written |
| `r5-astra-crosswalk.md` | R5 crosswalk through T405: scope and evidence terms, P4 statuses as runtime state, application conditions and outcome terms with an owner explanation, measurement terms, P10 authority labels, reconciliation observations | Astra, written |
| `panel-10-synthesis.md` | P10 synthesis: owner brief (three questions), statement kinds, effect on foundational decisions (Act now, Proposed, Blocked), G1/L-33, the eight outputs, criteria 8–10, open questions. Nothing in it is verified behavior | Opus, written; Astra, Sol and Fable review |
| `review-session-20261104-24c67015.md` | Owner-requested review of the folder at 15:28 (Claude, Opus 5.5). Findings F1–F4, gaps G1–G3, process items. Not an owner decision; R5 Part 1 answers it | reviewer; read-only |
| `review-evidence.md` | Owner brief and the saved turn record through T296, with the review's SHA-256 | chair; read-only |
| `topics/` | Copies of each session topic: `02.md`, `03.md`, `04.md` (handed forward, not held), `05.md` | writer of each topic |
| `vetoed/` | Verbatim copies of vetoed turns (29 files). A vetoed turn is not a record; a later kept turn or a note may restate its point | chair; seats |

`next-topic.md` no longer exists: R5 was the final session, and each topic file lives under `topics/`.

## Rules for every file

- Each claim traces to a panel turn, to a cited passage (file and line), or carries the flag `judgment`.
- Each report ends with **Decisions Made** and **Open Questions Handed Forward**.
- A panel ratification records panel agreement only. It does not establish owner acceptance (Astra T348; Opus T354). A row leaves Proposed only when the owner decides in `DECISIONS.md` or `docs/`.
- Four statement kinds stay apart: owner decision, panel agreement, Proposed, verified (`panel-10-synthesis.md`, "How to read this file").
- Use the TASTE register.

## Panel plan (T16, numbering per T71 and T73; sessions 3–5 adjusted at R2 end)

| Session | Panels | State |
|---|---|---|
| 1 | P1 sources and authority; P2 ECS without an engine | done |
| 2 | P3 Bevy ruling under D-9 and R-2.11; P4 address-to-entity link CEL | done |
| 3 | L-60 resolver checks (Sol); P7 common interface and storage (C-5) | done |
| 4 | One device panel: P5 device contracts and P6 leases, with microDuck limits, control scheme, L-17 observations, C-3 and L-25 | not held; the chair counted 4 of 5 at T297; `topics/04.md` goes forward |
| 5 | Owner review response (F1–F4, G1–G3); P10 synthesis. P8 and P9 go forward as open items in P10 | done; `topics/05.md`, `panel-10-synthesis.md` |

Reason for the R2 adjustment: L-10 verification needs link CEL persistence, and device contracts need a storage ruling first (`judgment`). Reason for the R5 replacement: one session remains, the owner's review is unanswered, and review item 6 keeps the device rows Proposed (Opus T298; `topics/05.md`). The world-server scope is already recorded in the owner brief: Rust, LadybugDB and Bevy (`review-evidence.md:29`). Only the interface and device details stay Proposed (Opus T428).

## Required final synthesis

P10 must preserve every output from the owner's topic brief:

- Working specification.
- Roadmap with ordering rationale.
- Differentiation.
- Safeguards.
- Open architecture questions, each with a decision trigger.
- Synergy map.
- Maintenance posture.
- Success criteria.

The requested deliverables are a working specification, a build plan, and recommendations with safeguards.
Each final claim must trace to a panel or cited passage, or carry a judgment flag.
