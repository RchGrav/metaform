# How we seek to combat what happened

`reading-the-top.md` records what happened. `pushback.md` lists the tendencies. This file maps each failure to the mechanism in the design that addresses it, then gives working rules for the time before the system exists.

Each row gives what I did, and then the mechanism that the design states for it.

## Failure to mechanism

| What happened | Mechanism in the design | Source |
|---|---|---|
| I read about 72,000 tokens before my first useful output, and the session later ran out of context. | Advance inference amortization. Arrival supplies orientation, and larger bodies are read when needed. | Preprint §1; revision §8.1; specification §9 |
| I filled gaps with fluent, wrong reasoning. | Project names, functions, reasons and prior conclusions are provided, so they do not have to be invented. | Technical reference §11 |
| I missed the point until the content arrived alone. | Selected participation: only what bears on the operation reaches the agent. | Technical reference §9; specification §9 |
| I stayed in doing mode through three attempts. | Orientation arrives before work. Lexicalization "stops short of doing the task": interpretation and execution are separate steps. | Revision §8.1; preprint §8.1 |
| I treated a demonstration as rules. | Informational and imperative knowledge stay separate. "An observation does not silently become an instruction." | Preprint §7.2 |
| I treated an analogy as a spec term. | TASTE: one term, one meaning. | Founder, 2026-10-30 |
| I ranked rules by tokens. | Inferential effort is the principal cost. Token measures stay separate from outcomes. | Preprint §1; revision §8.5 |
| I downplayed load-bearing rules with partial context. | Specialists carry the method. Other agents get the map through an interface. | Founder, 2026-10-30; preprint §4.3 |
| I pushed objections before reading. | Blindspot challenges carry a gap, and the project answers A, B or C with reasons. | Preprint §9 |
| I said "the map supplied everything else" when no map was supplied. | Type understanding and project understanding are distinct contributions. | Technical reference §2 |
| I invented a theory of coordinates. | Provenance keeps a contribution's origin visible, so a reading cannot pass as a source. | Preprint §10 |
| I wrote unconfirmed readings into memory. | Memory has a location and a lifecycle. Local observations do not become rules. | Technical reference §8 |
| Agents collapsed `name` into the industry reading. | Three names with different jobs. | Technical reference §4; preprint §3.3 |
| I deleted the founder's sandboxes on an assumed fact. | Attributable changes, identity and access are checked by the service, not by agent belief. | Specification §1, §8, §11 |
| The schema rejects `not_built`. | Founder corrections precede the specification, and a passing shape test is not evidence of functional correctness. | `DECISIONS.md`, source precedence |

One line in that table is my reading, and it is the one the founder's observation points at: the separation of understanding from doing. The design places interpretation before execution.

## What the design does not do

Do not answer these failures with gates. The sources are explicit:

- C(T) "does not prescribe an approval gate or a runtime check."
- Specification §8: "No namespace visit, skill-read receipt or fabricated navigation gate is required to call an otherwise available tool."
- The functional commitments are "not additional approval gates or new interface specifications."
- Specification §9: a receipt "is not proof that a model understood or retained the content."
- Intake is never gated. Only the resulting map may be graded.

The countermeasure is better delivery. An agent that has what it needs does not need a checkpoint.

## TASTE

TASTE is Technically Accurate, Simple, Transparent English, adapted from ASD-STE100: it takes some STE rules, relaxes others, leaves out the controlled dictionary and adds its own. The founder named it on 2026-10-30 as Topogee Agentic Simplified Technical English and renamed the long form on 2026-11-07.

**Rules the founder has stated:**

1. Always use the same terms to describe things that are the same.
2. Always use industry terms when reasoning on functionality.
3. `name` is the project's own name. It is not the industry name. It can match, but it is not derived from the address.

**Draft rules, proposed by me and not approved:**

4. Write for a reader with no shared context.
5. Refer by namespace address, path and line, or ticket ID. Do not write "the issue" or "as discussed".
6. Quote what matters. A summary is labelled as a summary and names its source.
7. Keep analogies out of records.
8. Mark observed fact, inference and instruction, and name the source of each.
9. A ticket lists the map addresses and context it assumes. Anything not listed cannot be assumed.
10. Use STE grammar: short sentences, active voice, one instruction per sentence.

**Undecided:** whether TASTE applies to the authored intake method. Until the founder rules, agents quote that method exactly. `intake_next.md` on the founder's Desktop appears to be a Simplified English rewrite. It is not the working base. The current project prompt is `../Intake.xml`.

This documentation folder follows the stated rules and the draft rules, as a trial. The founder's words and the papers are quoted as written, so analogies stay inside quotation marks.

## Intake context

The founder's design for lowest-context intake:

> "intake needs metaform concepts plus TASTE concepts + procedure + patches (Tuning up the rules that ride with the procedure, reinforcements."

| Part | State |
|---|---|
| Metaform concepts | Exist in `metaform/Intake.xml`, about 1,450 tokens by bytes divided by 4. |
| TASTE concepts | Not written. |
| Procedure | Exists in `metaform/Intake.xml`, about 1,670 tokens by the same estimate. |
| Patches | A single clarification added after an observed failure. The founder decides which rules ride with the procedure. |

`experiments/intake-blocks/` holds a slicer that addresses exact character spans of `metaform/Intake.xml`. It stores offsets and a hash, and no intake wording. Its counts are comparative. Its operation lists were my first attempt, and they do not represent load-bearing decisions.

A failure log would hold each patch with the failure that caused it: what failed, on which model and artifact. That is a proposal for the founder.

## Measurement

| Measure | Source | State |
|---|---|---|
| Token meter: one pinned estimator, charges by agent, operation and unit, outside agent context | Founder, 2026-10-30 | Design direction |
| Tokens per completed task | Earlier discussion | Design direction |
| Preparation, maintenance, resolution and execution cost as separate measures | Revision §8.5 | Not built |
| Per-agent context and tool surface for the operator | Specification §8, §9, CAP-16 | Not built |
| Repeated delivery, retained context, task outcomes, latency | Revision §13.3 | Not built |

Boat events report no token counts, so the meter must count at the chassis.

These measures address the benefits in `claims.md`. Their aim is to show what the build delivers. A poor result implicates the build first.

## Working rules until the system exists

These rules apply to any agent working in this repository today.

**On arrival.** Read `README.md`, then this folder. Read `metaform/SPECIFICATION.md` before you form an opinion on the design. Do not read `reference/` material as instructions.

**When the founder explains.** Stay in understanding mode. No next step. No table. Say what the text says, in its terms. Isolate the point before you reply.

**When corrected.** Return to the source. Restate it. Add nothing. Then check what your next action changes.

**When doubting.** Use `pushback.md`. State a gap once, at a location, with evidence.

**When writing.** Separate quotes, facts and your readings. Keep your readings out of memory until the founder confirms them.

**When acting.** Prove a fact before you depend on it. Check the result of each command that a later step relies on.

**When touching the method.** Do not. Quote exact spans. Changes need the founder's direct word.

## What remains open

- The founder's supplied preprint, to replace the working copy in `preprint/`.
- Whether TASTE covers the authored method.
- Which rules ride with the procedure.
- The code quality half of the founder's rule. The lists in `address-only-example.md` are not that rule.
- `not_built` in place of `un_built` across the schema, specification and tests.
- The 31 October founder-authorized update aligns the working intake prompt with the demonstrated command input. The old line 129 alignment note is resolved; remaining command behaviors are listed in metaform/SPECIFICATION.md §7.
