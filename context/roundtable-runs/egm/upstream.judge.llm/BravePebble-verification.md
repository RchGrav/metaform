# BravePebble: what the local evidence does and does not establish

This note records a verification limit that affects two rows of the combined
`resolution.md`, then states the four corrections that follow from it.

## The limit

The task copies exactly one source file into this element's folder:
`source/crates/roundtable/src/jev.rs`. I searched the whole scratchpad tree
used to build this run and found **no** `rules.rs` or `turn.rs` that contains
`GATE_PASS`, `SCORE_PASS`, or a call to `contribution_state`. The newest files
of that name in the tree are older rewrites that still use `PASS_CONFIDENCE`,
`news::NEW_QUESTION`, the 50 KB discussion window, and
`typesafe/jev-1.13-20260917`; they predate the `jev.rs` we were given and
therefore cannot be the caller for it.

So the findings' citations to `rules.rs:13-15`, `turn.rs:152-167`,
`turn.rs:204-216` and `turn.rs:352-354` are, *for this element*, unverified.
The reviewers may have read sibling copies in other elements' folders, but none
of those copies is in this workspace for me to inspect, and the copies that do
exist visibly disagree with the current `jev.rs`.

This does not make the findings wrong. It changes what "right" is based on.

## The four corrections

**1. GF1 is right from this file alone.** `jev.rs:43-58` builds five questions
and `jev.rs:152-175` returns `BTreeMap<String, f64>`: one float per name, no
reason text anywhere in the type. That already falsifies "three conditions,
with reasons." The caller-side detail (that the reason string is
`format!("{name} ({pct}%)")` built in `on_judged`) is plausible and consistent,
but for this element it is an inference from the want and from the finding, not
an observation. The resolution should say the want is false *and* that who
builds the reasons is documented in the caller's element, not proved here.

**2. GF2 cannot be settled from the given code.** The score range is proven
here: a `score` question's answer range is `0..=criteria.len()-1`
(`jev.rs:165`), and the test asserts six levels (`jev.rs:192-193`), so scores
are `0..5`. What the pass level is — 3.0, or 0.70, or anything else — is not in
`jev.rs`. The finding's "two scores against `SCORE_PASS`" is therefore the one
part of GF2 that must be attributed to the caller, and the resolution's claim
that scores pass at exactly 3.0 rests entirely on that unverified file. The
*shape* of GF2 (the note mentions only three conditions) is still right: the
note omits two checks that the code demonstrably sends.

**3. GF4's "no key" claim is half-proven.** `jev.rs:153` does prove that
`ask()` returns `Err("no OpenRouter key configured")` when no key is set; and
`jev.rs:138-140` proves `configured()` exists so the caller *can* test first.
But "therefore the message is shared unjudged" is entirely in `turn.rs`. Again
plausible, again not observable here. The resolution should separate the two.

**4. GF5's batching name `p{a}_{b}` is not in this file either.** The local
`jev.rs` shows the question text and the `{{foo}}`/`{{bar}}` substitution
(`jev.rs:116-123`) but not the batch key. So the finding is "right as a note"
only for the naming half; the batching half is caller-side.

## Why this matters to the deliverable

The combined resolution's summary line — "the code supports the documented
five-check design" — is correct. Its companion sentence that the sibling
`turn.rs`/`rules.rs` "confirm" the thresholds is, for this element, not
something a reader of `resolution.md` can check. The honest phrasing is:

> Thresholds and failure routing are properties of `code.gate.quality`'s caller
> and are cited from its element, not proved from JEV's own source. From
> `jev.rs` alone we can prove: five questions, one number each, no reasons,
> score answers in `0..5`, and a missing key or an out-of-range answer is an
> `Err` that the caller must handle.

That phrasing keeps every finding's verdict ("right") while removing the one
claim in the resolution a reviewer could not reproduce. No finding is
overturned; GF2 and GF4 are re-grounded rather than weakened.
