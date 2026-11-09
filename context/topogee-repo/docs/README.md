# Project documentation

**Read this before you form an opinion on the design.**

These documents explain why Metaform exists, state its claims in full and record how a model misread it. A model wrote them at the founder's direction on 2026-10-30, after that failure. They are written for the next model and for people who work with it.

If you are a model, you will probably want to push back on some of what the project claims. Read `pushback.md` first, and read `claims.md` next. The aim is that you reason about the mechanism. The aim is not that you agree. Agreement without reading is on the list of failures.

## Reading order

| File | What it holds |
|---|---|
| [../TOPOGEE.md](../TOPOGEE.md) | The opening statement: what Metaform is and how it works, under the name Topogee. Read it first. |
| [../metaform-canonical.json](../metaform/metaform-canonical.json) | The functional map of the earlier system. Much of it is the design of the rebuild. |
| [metaform-concepts.md](../metaform/docs/metaform-concepts.md) | The key concepts explained for a new reader. |
| [pushback.md](pushback.md) | Eighteen tendencies, with evidence, and what to do instead. Where doubt belongs. The form for raising a gap. |
| [why.md](why.md) | The problems this project addresses, and the design that addresses them. |
| [claims.md](claims.md) | Twenty-two claims. Each gives what the author claims, its source, its mechanism and what I observed. |
| [countermeasures.md](countermeasures.md) | Each failure mapped to its mechanism. TASTE. Measurement. Working rules for today. |
| [reading-the-top.md](reading-the-top.md) | The record of what happened on 2026-10-30. |
| [address-only-example.md](address-only-example.md) | The founder's demonstration, unchanged. It is not a set of rules. |
| [owner-explanations.md](owner-explanations.md) | The founder's explanations of the system, copied by script. |
| [owner-statements-2026-10-30.md](owner-statements-2026-10-30.md) | The founder's words from that session, copied by script. |
| [preprint/](preprint/) | The preprint. |

## Authority

These documents do not override anything. The order stays the same as in `DECISIONS.md`: current founder decisions, then the current specification, then labelled technical proposals, then preserved historical evidence.

My readings are labelled as readings. The founder has not reviewed these documents. Where a document here and the founder's words disagree, the founder's words govern.

## Terms

| Term | Meaning here |
|---|---|
| metaform | The functional space of a project: nested addresses, elements and their knowledge. The preprint's name is Inference Metaform. |
| address | A namespace address, such as `code.engine.game.fps`. |
| want record | The receiver-owned record of why the receiver wants a provider and how the provider serves it, with intent. The specification stores it in the `wants` dictionary, keyed by provider address. Intake names its parts OP, EF and IFD; these are stored as `why`, `how` and `intent` (see `DECISIONS.md`). The papers call it a join or purpose record. |
| knowledge layer | Understanding held at the location it concerns, and selected for an operation. |
| functional map server | The Node process that holds the functional map of every project and is the only writer under `~/.metaform` (R-4.4). It is not the world server, which holds the game world. Do not shorten it to "map server". |
| intake | The procedure that establishes the base functional map. Its current project source is [metaform/Intake.xml](../metaform/Intake.xml); the diagram is [metaform/intake.mmd](../metaform/intake.mmd). |
| the founder | The person who designed this method and directs this project. |
| hallucination | Spelled as it is in the founder's words and the technical reference. |

## Status

This repository has no working application yet. `claims.md` keeps what the author claims separate from what I observed.

The current single-tool input is defined in [metaform/SPECIFICATION.md](../metaform/SPECIFICATION.md). [mcp-query-source.md](../metaform/docs/mcp-query-source.md) preserves the founder's supplied note; corrected machine-readable examples live at the project root.
