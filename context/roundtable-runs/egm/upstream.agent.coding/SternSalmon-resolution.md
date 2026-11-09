# Independent decisions on the ACP harness findings

Participant: SternSalmon. Date: 2026-11-07.
Evidence available to me: `element.md` and `source/crates/acp-host/src/launch.rs` only.

I agree with SecureBoron's outcomes on GF2, GF3, GF4, GF5, GF6, GF7 and GF8. I disagree with
one part of the GF1 decision, give a sharper reason for GF7, and add two code-level
consequences that the existing `resolution.md` leaves out.

## GF1 — openrouter-acp omitted (Major). RIGHT.

I cannot read `tables.rs` or `adapter.ts` (not in this snapshot), so I cannot confirm the
"offered first" or "v1" details. But the finding still stands on the supplied code alone,
for a reason the current resolution does not give: `Rewrite the investigation note is not
enough when the code disagrees.` `builtin()` in launch.rs is the built-in catalog that
`autoselect` always appends (launch.rs:223-227). It has no openrouter-acp entry. So even
if the web layer offers openrouter-acp first, the acp-host layer never does. The
description says "known harnesses" and the code proves at least one known harness is
outside the note. Change: add openrouter-acp to the `investigations` note and state that
it is NOT discovered by acp-host's catalog — the two lists differ — so the map does not
imply one list covers both layers.

## GF2 — pinned fallbacks unrecorded (Major). RIGHT.

Versions match launch.rs:85-88 exactly. One correction to the resolution's framing:
`HarnessEntry.version` for a built-in is `None` (launch.rs:82), so the pins live only in
the package string inside `LaunchSpec.args`, not in the entry's version field. The note
should say so; otherwise a reader will look for the version in `version` and find `None`.

## GF3 — uri is v1 while built says v2 (Nit). RIGHT.

prefer: keep `properties.uri` as the canonical v1 document (the element's own contract is
v1 framed) and add the v2 document under `references` as a `sections`-bearing entry,
rather than replacing the uri. A single "version-independent" uri does not exist; the ACP
site splits by version, so deleting the v1 link loses information.

## GF4 — RPC list unverifiable from snapshot (Nit). RIGHT.

No change to code; the want is a statement about the client side. Record in `element.md`
that the method list is sourced from the ACP protocol document, not from this element's
code.

## GF5 — v2/v1 consequence missing (Major). RIGHT, and this is the highest-value fix.

The gap as written is a fact, not a risk. The element must state the operational
consequence. From the code I can see one concrete consequence without the client source:
`builtin()` launches four harnesses with no protocol-version gate, so acp-host will launch
a v1 harness as readily as a v2 one. Whatever the client does with that is the missing
sentence. Change: state whether the client negotiates a protocol version in `initialize`
and what it does if the harness offers only the other version.

## GF6 — method list has no version (Major). RIGHT.

Duplicate of GF3/GF5's root cause; fix by tagging the method list with the version it
describes and listing any renamed method explicitly.

## GF7 — "Pi has never run" (Nit). RIGHT.

Sharper reason than the current resolution: `Pi` is the one built-in whose package
(`pi-acp@0.0.34`) is not the publisher's own scope, so "never run" most likely means "was
never selected", not "cannot run". The fix should distinguish two claims: (a) it is in the
built-in catalog and launchable if `npx` is on PATH; (b) no recorded run selected it.
Conflating those makes the gap unactionable.

## GF8 — "checked by their source" (Nit). RIGHT.

Rephrase to name the artifact: the harness's own published source/manifest, inspected on
2026-11-07.
