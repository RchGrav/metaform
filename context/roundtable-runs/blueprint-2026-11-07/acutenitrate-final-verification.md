# AcuteNitrate — final verification of `blueprint-spec.md` against W-1.4

Run on the final file, 2026-11-07. Commands are reproducible from the workspace root.

## What W-1.4 asks

world-system-spec.md:35 requires two things that were "not specified yet":
1. what a feature blueprint holds;
2. how an agent writes it.

Both are now answered in `blueprint-spec.md`: §2 (B-2.1–B-2.6) answers (1); §3 (B-3.1–B-3.6, plus B-3.3 loop and B-3.5 agent record) answers (2). W-1.4 also says the answer must build on W-5.3 (port manifest), W-5.4 (links) and W-5.5 (intent records); §1's slot addressing and §2's manifest/link/intent layers do that.

## Machine-checkable verification

| Check | Result |
|---|---|
| Defined `B-x.y` clauses | 19 |
| Referenced `B-x.y` ids with no definition | 0 |
| `W-` ids referenced in blueprint-spec.md but absent from world-system-spec.md | 0 |
| Defined `W-` ids in world-system-spec.md | 61 |
| MS-3 still says "and expected manifest contract" (the contradiction I fixed) | False |
| MS-3 contains the server-recorded dependency fingerprint | True |

The first `B-` pass produced 13 "unresolved" hits, but that was my own regex requiring the id to be the whole bold run; clauses such as `**B-2.2a Owned slots vs external roles**` were defined with a trailing title. After correcting the pattern to allow a trailing space or `**`, all 19 resolve. I report this because a false "13 broken references" result would itself be a defect in a verification claim.

## The contradiction I fixed, and why it is consistent with the newest clauses

B-2.2a forbids an agent-declared expected manifest contract for an external role ("the type-check would validate against a lie"); MS-3 previously required one. I changed MS-3 so the server records the target's manifest hash as an MS-2 dependency fingerprint at validation time — a server-read snapshot cannot drift from the entity. The acceptance case (line 138) now names that fingerprint.

A later edit to B-3.1's `link` row (line 62) says a link touching an external role is "not permanent: the live entity's manifest can change before `submit()`, which is what MS-2's dependency fingerprint and MS-3's release-time revalidation exist to catch." That clause depends on exactly the fingerprint my MS-3 fix supplies: without a recorded hash there is nothing whose change could be caught. So the fix and the newest clause are consistent, and the document has no remaining contradiction on this point.

## State

Both halves of W-1.4 are specified. Seven open decisions remain in §6, each with a recommendation; none blocks the two questions W-1.4 asks. D-B4 (resolver scope) is settled on W-1.1 grounds: a Decided requirement forbids the world system reading the functional map, so a shared resolver is unavailable and only field shapes are shared.
