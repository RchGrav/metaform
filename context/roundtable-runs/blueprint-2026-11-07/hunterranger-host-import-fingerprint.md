# The missing check: a published component's host-import set (W-7.1)

**Author:** HunterRanger. **Status:** proposed amendment to B-3.7 step 2. Not applied — see the note at the end.

## The hole

B-3.7 step 2 has `content.publish_component` "validate the component format, the manifest's WIT declarations and
**required host imports**". That check is only possible if the server reads the compiled component's import
section. Nothing in the spec says it does, and nothing records the result.

W-7.1: "A code module is a WebAssembly component. It imports the host interfaces it uses, **at the versions it
targets**, and the world server provides only those imports."

The targeted version lives in the component binary, not in the agent-supplied manifest. So:
- the agent's manifest cannot be relied on to state the import versions (same anti-drift reason as B-2.2a);
- a component targeting v2 of an interface the server provides at v1 must be refused;
- and once published, the import set is a *dependency* in the MS-2 sense.

## Premise chain

1. W-7.1: the server provides only the interfaces a module imports, at the versions it targets.
2. A component's import section is the only authoritative record of those versions.
3. Therefore `publish_component` must read the import section, not the manifest.
4. MS-2: "Validation records a dependency fingerprint ... Submission rechecks it. A changed dependency returns a
   diagnostic."
5. A world-server interface upgrade changes the dependency **without changing any hash** — the component bytes
   are identical before and after.
6. Therefore, without the import set in the fingerprint, evidence gathered against v1 silently qualifies a
   component that cannot link at v2.

This is the same failure class as the handle-set gap fixed in B-4.2: the assembly pinned code identity but not
capability identity. Here it pins code identity but not *interface* identity.

## Proposed rule (B-3.7 step 2)

> The server reads the component's import section and records the set of `(package, version)` pairs the component
> actually imports. `publish_component` succeeds only if every pair is provided by the world server (W-7.1) and
> agrees with the WIT declarations in the supplied manifest. The recorded import set is part of the MS-2
> dependency fingerprint, so a host-interface upgrade invalidates evidence gathered against the old version.

## Observable consequences

- Publishing a component whose manifest declares host v1 while the binary imports v2: refused, naming the pair.
- Publishing a component importing an interface the server does not provide: refused.
- Upgrading a host interface to v2: a previously passing build reports a changed dependency and cannot be released
  against the new server until retested.

## Why not applied

The final round is not the time for a unilateral edit: the spec gained B-3.7 and `bind_component` this round from
another participant, and uncoordinated edits in the last turns are exactly how the contradictions I spent three
rounds repairing were introduced. This is recorded so the next owner can apply it with the reasoning attached.
