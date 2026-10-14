# The floor: what it admits and what it rejects

Calibration of `roundtable_keep` against roundtable 1 (14 October 2026, 11 seats, 71 rounds, 775 turns). Reproduce
every number here with:

    uv run python scripts/floor_calibration.py          # the tables below, from experiment-one/discussion.json
    uv run python scripts/slow_seat_check.py            # the deadline behaviour in the last section

775 turns: 654 judged, 340 admitted, 314 vetoed, 116 with no submission at all, 5 over 512 characters.

**The threshold is not set here.** The number is the founder's to pick. What follows is what each candidate buys and
what it costs, with the examples attached.

---

## 1. The gate is one noul wide, not four

| noul | min | p05 | p25 | median | p75 | max | below 0.83 |
|---|---|---|---|---|---|---|---|
| `new` | 0.24 | 0.56 | 0.74 | **0.84** | 0.89 | 0.98 | **303 (46%)** |
| `valuable` | 0.07 | 0.86 | 0.90 | 0.91 | 0.92 | 0.94 | 15 (2%) |
| `relevant` | 0.04 | 0.88 | 0.93 | 0.95 | 0.96 | 0.98 | 15 (2%) |
| `keep` | 0.06 | 0.86 | 0.90 | 0.92 | 0.92 | 0.94 | 16 (2%) |

`valuable`, `relevant` and `keep` have almost no range. Their p05 sits at or above 0.86 — above the floor — so for
95% of submissions they are already a pass before the floor is consulted. They fire on 19 submissions in 654, and
nearly all 19 are genuinely off-pattern: a credit warning, a pass, a truncated fragment. They are a liveness check,
not a gradient.

So `roundtable_keep` is a single-dimension knob on `new` that happens to be spelled four times. Two consequences for
picking a number:

- **The usable range is 0 to 0.94, not 0 to 1.** `valuable` never scored above 0.94. Because all four are required
  together, a floor above 0.94 admits nothing at all, whatever the table. Against that span, 0.83 is 88% of the way
  up, not 83%; and the top of the span is 0.94, not 1.00, so "83" reads stricter than it looks.
- Moving the floor to tune novelty also moves the liveness check, in a band where it has no resolution.

## 2. What the floor admits, by kind

Four kinds, assigned structurally so the table is reproducible and no second judge is involved: `operational` is
traffic about the table rather than its subject; otherwise a submission is `novel`, `refinement` or `synthesis`
according to whether it cites nought, one, or two-or-more earlier turns by number.

**Read `refinement` and `synthesis` as floors, not counts.** A refinement that does not name the turn it refines
lands in `novel`. Section 4 shows why that limit matters more than it sounds.

| floor | novel (523) | refinement (102) | synthesis (25) | operational (4) | all (654) |
|---|---|---|---|---|---|
| 0.70 | 421 (80%) | 100 (98%) | 23 (92%) | 2 (50%) | 546 (83%) |
| 0.75 | 367 (70%) | 95 (93%) | 20 (80%) | 2 (50%) | 484 (74%) |
| 0.78 | 337 (64%) | 93 (91%) | 19 (76%) | 2 (50%) | 451 (69%) |
| 0.80 | 308 (59%) | 85 (83%) | 18 (72%) | 1 (25%) | 412 (63%) |
| **0.83** | **256 (49%)** | **69 (68%)** | **14 (56%)** | **1 (25%)** | **340 (52%)** |
| 0.85 | 220 (42%) | 57 (56%) | 12 (48%) | 1 (25%) | 290 (44%) |
| 0.90 | 77 (15%) | 16 (16%) | 6 (24%) | 0 (0%) | 99 (15%) |

What a lower floor would have added to the 340:

| floor | novel | refinement | synthesis | operational | all |
|---|---|---|---|---|---|
| 0.80 | +52 | +16 | +4 | +0 | **+72** |
| 0.78 | +81 | +24 | +5 | +1 | **+111** |
| 0.75 | +111 | +26 | +6 | +1 | **+144** |
| 0.70 | +165 | +31 | +9 | +1 | **+206** |

One correction to the failure audit. Explicitly-cited refinements are *not* the main casualty: they are admitted at
68% against novel proposals' 49%. Jev credits a turn that names what it is extending. The casualty is the novel
category — 267 of the 314 vetoes, 244 of them on `new` alone.

## 3. What is actually in the rejected pile

Of the 314 the floor rejects, 285 fail on `new` alone and nothing else. Where those 285 sit:

| `new` | count | kinds | what is in there |
|---|---|---|---|
| 0.80–0.83 | 69 | 50 novel, 15 refinement, 4 synthesis | substantive, mostly a distinct mechanism. See below. |
| 0.70–0.80 | 118 | 100 novel, 14 refinement, 3 synthesis | mixed: distinct proposals, and real restatement |
| 0.50–0.70 | 78 | 74 novel, 2 refinement, 2 synthesis | mostly restatement, some synthesis |
| below 0.50 | 20 | 20 novel | genuine duplication — and the single best synthesis at the table |

The 0.80–0.83 band is the band the threshold decision turns on — 72 turns counting the three that also missed on
another noul — so here is what is in it, verbatim:

- **T35 Sol** (0.80) — *"Separate 'motion completed' from 'goal achieved.' After placing an object, release it and
  observe whether it settles where intended."* A distinct verification stage nothing before it proposed.
- **T128 Sonnet** (0.81) — *"Add a watcher that isn't the actor. A second, cheap process sees the orbit view and the
  tick log, not the agent's reasoning."* A new component in the architecture.
- **T349 Fable** (0.81) — *"Put the hands in the picture. A head camera that leaves the gripper out of frame gives
  the model nothing to servo on."* A concrete perception defect with a fix.
- **T434 DeepSeek** (0.82) — *"Split control finer than takeover. The person can hold one thing while the agent keeps
  another: pin the left arm, govern grasp force."* Redefines an interaction the table had treated as a switch.
- **T547 Fable** (0.82) — *"Ship objects with a handling label... Tags were invented one at a time in this thread;
  make them a format."* Synthesis with a deliverable.

These are 5 of 72 at 0.80. On my reading, the band is dominated by material a report should have carried. That is an
argument for lowering the floor; it is not an argument for a particular number, because of section 4.

**One turn in the band is repetition, and it is the one that matters.** An earlier draft of this report said the band
contained none; that was wrong. T543 (Kimi) scores `new` 0.80 and is the twentieth verbatim resubmission of the same
paragraph — byte-identical to T268 once the seat's own `T###:` label is stripped. It is the only such case among the
72, and at a floor of 0.80 it clears all four nouls and enters the discussion. Section 4 measures what that costs.

And what the floor rightly refuses, for contrast:

- **T9 Qwen** (0.24) — *"Use observe-act-verify; split semantic skills from motor control. Agents see only
  first-person RGB/depth/body/contact... move/look/reach/grasp/release/stop with force/speed caps."* A compression of
  T1 and T2, eight turns later. Correctly out at any floor.
- **T475 Sol** (0.29), **T596 Sol** (0.31) — restatements of ground already taken.

## 4. How precisely `new` can be measured, which bounds what a threshold can mean

### 4a. The same text, judged 26 times

One seat gave the record a repeatability experiment by accident. Kimi resubmitted one paragraph — the readable-body
proposal — 26 times between T268 and T609, byte-identical every time once its self-authored `T###:` label is
stripped, and Jev vetoed all 26. Identical input, 26 judgments, so every difference below is the instrument and not
the submission:

| noul | min | max | spread | median | sd | per 100 turns |
|---|---|---|---|---|---|---|
| `new` | 0.42 | 0.80 | **0.38** | 0.71 | **0.099** | **+0.070** |
| `valuable` | 0.86 | 0.90 | 0.04 | 0.88 | 0.012 | −0.010 |
| `relevant` | 0.91 | 0.96 | 0.05 | 0.93 | 0.014 | −0.010 |
| `keep` | 0.77 | 0.88 | 0.11 | 0.85 | 0.029 | −0.024 |

Two things in that table, and they point opposite ways.

**The scatter.** `new` has a standard deviation of 0.099 and a range of 0.38 on text that never changed. The
0.80-versus-0.83 question is a 0.03 move: under a third of one sd, and a thirteenth of the observed range. Nothing
finer than about 0.05 is distinguishable from noise on this evidence, which is an argument for picking a round number
and not deliberating over hundredths. It also means **the floor cannot be calibrated more precisely than the judge
can score** — the limit is the instrument, not the threshold.

**The drift, which is worse.** The scatter is not random: `new` climbs with turn number, +0.070 per 100 turns, from
0.42 on the first resubmissions to 0.80 by T543. A verbatim repeat looked *more* novel the later it arrived, while
`keep` fell in the same stretch (−0.024 per 100 turns). The scores move in opposite directions on unchanging text, so
this is not one underlying judgement drifting — it is two nouls losing their footing as the context grows. Table 1
sent each seat its whole conversation with no system prompt and no caching, reaching 56–72k tokens, so the most
likely cause is context length rather than anything about the proposal. That is a defect in how the table was run,
not in the floor, but it bears directly on the number because it decides what the number buys:

| floor | verbatim repeats admitted, of 26 | which |
|---|---|---|
| 0.70 | 17 | T345 … T609 |
| 0.75 | 6 | T532, T543, T554, T565, T587, T598 |
| 0.78 | 3 | T543, T554, T587 |
| 0.80 | 1 | T543 |
| **0.83** | **0** | — |
| 0.85 | 0 | — |

**0.83 is the lowest floor in the candidate set that rejects all 26.** That is the strongest single argument for
leaving it where it is, and it is not an argument from taste: it is the only place in this record where the right
answer is known in advance and a floor can be scored against it. Read against section 3, the trade is explicit —
0.80 buys 72 substantive turns and admits 1 verbatim duplicate; 0.78 buys 111 and admits 3; 0.75 buys 144 and admits
6.

What this sample cannot carry: it is 26 judgements of one paragraph from one seat, in one stretch of one table. No
other pair of submissions in the 654 reaches even 0.60 token overlap, so there is no second cluster to check it
against. A table that repeats text on purpose would settle both the sd and the drift in one run; see section 7.

### 4b. The same ground, reached independently

Round 1. Eleven seats answered the same empty table with no prior turns in view but each other's:

| turn | seat | `new` | outcome |
|---|---|---|---|
| T1 | Astra | 0.98 | admitted |
| T2 | Sol | 0.92 | admitted |
| T3 | Gemini | 0.59 | **vetoed** |

T1, T2 and T3 are near-paraphrases of one another. All three open with observe → act → verify, all three list
move/look/reach/grasp/release/stop under force and speed caps, all three ask for a first-person view beside an orbit
camera, and T1 and T3 both cite Habitat. T2 is the closer restatement of T1 of the two; it scored 0.92 and entered,
and T3 scored 0.59 and did not.

**That is a 0.33 spread on functionally identical novelty** — independent corroboration of 4a, from a different
mechanism and at the opposite end of the table, and close to the 0.38 measured there.

### 4c. The same effect across all 71 rounds

Measured over the whole table. Whether the turn immediately before yours entered the discussion is
not something your own turn can control:

| the turn before yours | submissions | median `new` | admitted at 0.83 |
|---|---|---|---|
| entered the discussion | 278 | 0.80 | **41%** |
| was vetoed, or absent | 305 | 0.86 | **60%** |

A 19-point swing from position in a fixed rotation. And the per-seat shares, which therefore rank nothing:

| place | seat | judged | median `new` | admit 0.83 | admit 0.78 |
|---|---|---|---|---|---|
| 1 | Astra | 71 | 0.85 | 61% | 83% |
| 2 | Sol | 71 | 0.74 | 14% | 37% |
| 3 | Gemini | 56 | 0.90 | 91% | 96% |
| 4 | Kimi | 56 | 0.73 | 25% | 38% |
| 5 | DeepSeek | 60 | 0.81 | 32% | 58% |
| 6 | Opus | 70 | 0.88 | 71% | 84% |
| 7 | Sonnet | 69 | 0.86 | 58% | 78% |
| 8 | Fable | 67 | 0.87 | 79% | 93% |
| 9 | Qwen | 49 | 0.68 | 12% | 29% |
| 10 | GLM | 32 | 0.86 | 56% | 72% |
| 11 | Grok | 53 | 0.86 | 68% | 83% |

One refinement of the audit's third finding: the confound is real but it is **not a position gradient**. Place 2
retains 14% and place 3 retains 91%. Order moves individual turns, as T3 shows; across a whole table, seat-specific
style swamps it. Neither effect can be separated from the other in this data, which is the reason the shares cannot
rank seats. Rotating the order at the next table separates them.

## 5. The one thing no threshold fixes

**T348 Sonnet**, `new` **0.24**, vetoed:

> *"Name the invariants the list shares. Nearly every item reduces to five rules: the agent acts only on what it can
> perceive, with source and age; every act runs through one declared control under caps the controller enforces; stop
> and takeover are physical…"*

This is the best piece of synthesis at the table. It restates 300 turns *in order to name what they share*, and
`new` measures restatement, so it scored 0.24.

T9 — the round-1 compression of T1 and T2, correctly refused — also scored **0.24**. Not approximately: the same
number. The best synthesis at the table and its most redundant submission are the same point on this instrument, so
no floor can separate them. That is section 5's whole argument in one line.

It also lands in `novel` under the structural rule in section 2, because it cites no turn numbers. So the
`synthesis` row is undercounting the exact thing it was meant to measure.

Operational traffic is the same shape of problem, as the audit said. **T755 Sonnet**, scoring `relevant` 0.04,
`valuable` 0.20 — *"Flag for Rich rather than a T-entry: since about T616, most API seats fail with HTTP 402. The
OpenRouter key's credit is nearly gone… Top up the key or close the table so the report gets written."* Correct,
urgent, and correctly judged irrelevant *as a contribution*, because the gate has only one door. **T182 Opus** —
a voluntary pass plus a report outline — the same.

I take plan item 21 (routing by what a message *is*) as landing, and have not tried to compensate for it here. But
synthesis is a sharper case than operational traffic: operational traffic can be routed away because it announces
itself, whereas a synthesis is a proposal, belongs in the discussion, and is penalised precisely in proportion to how
well it does its job. Routing does not fix that; only a measure of novelty that isn't textual does.

## 6. Per-seat deadlines under a slow or failing provider

Table 1 never exercised a deadline. 116 turns produced no submission and **every one failed fast** — no turn at this
table ran out of time. All 116 were OpenRouter seats; no ACP seat ever failed to answer.

| seat | none | what the provider said |
|---|---|---|
| GLM | 38 | empty reply at HTTP 200 ×27, HTTP 402 out of credits ×11 |
| Qwen | 21 | empty reply ×9, HTTP 402 prompt tokens limit exceeded ×7, HTTP 429 ×3, HTTP 402 out of credits ×2 |
| Grok | 16 | HTTP 402 out of credits ×13, HTTP 402 prompt tokens limit ×2, connection reset by peer ×1 |
| Gemini | 15 | HTTP 402 out of credits ×15 |
| Kimi | 15 | HTTP 402 out of credits ×15 |
| DeepSeek | 11 | empty reply ×8, HTTP 402 out of credits ×3 |

The 44 empty replies at HTTP 200 are the mode worth naming: the provider charges, returns 200, and sends no content.
GLM did it 27 times, which is most of why GLM took only 32 judged turns out of a possible 71.

So I exercised the deadline deliberately, in `scripts/slow_seat_check.py`, against a stub OpenRouter on the loopback.
All eight checks pass, and together they say the two seat kinds have unrelated deadlines, only one of which is real:

```
ok  a provider sleeping 6s past a 3s deadline still enters: took 6.0s, no Late raised
ok  two 429s are retried over the whole 8s backoff: took 8.1s, 2.7x the deadline it was given
ok  so one turn's worst case is 3 attempts x 180s plus 8s backoff = 548s, against agent_wait 3s
ok  an empty reply at HTTP 200 passes the turn and is not delivered: the reply was empty.
ok  HTTP 402 is Unpaid and never a NoReply, so the table ends
ok  ModelSeat.exchange takes `seconds` and does not use it
ok  an ACP seat's deadline is real: harness.Session.prompt raises Late(seconds)
```

`runner.turn` passes `config.value('agent_wait')` to every seat alike (`runner.py:218`). `AcpSeat` honours it and
raises `Late`. **`ModelSeat.exchange` accepts `seconds` and discards it** (`openrouter.py:214`); an OpenRouter seat's
only deadline is the module constant `openrouter.TIMEOUT = 180.0`, which is a socket timeout *per HTTP attempt*, and
`openrouter.post` retries over `BACKOFF = (2.0, 6.0)`. With `agent_wait` at its default 300s:

- one OpenRouter turn's worst case is **548s**, 1.8× the configured wait;
- a slow OpenRouter seat never raises `Late` and so never records `no_reply_time`; it records a socket error;
- raising or lowering `agent_wait` has **no effect at all** on an OpenRouter seat.

A table of 11 OpenRouter seats all timing out is therefore a round of just over 100 minutes with `agent_wait` set to
five minutes. For scale from the real run: table 1's rounds took a median 230s and at most 390s wall clock (derived
from `dispatch.spend` sequence stamps; per-turn latency was not recorded by the version that ran).

This is a defect, not a calibration question, and it is in Metaform-adjacent seat code rather than the gate. Filed
separately; no fix is in this change.

## 7. What I would want before a number is fixed

Reported for the judgment, not as a recommendation:

- The floor's real range is 0 to 0.94, so 0.83 is 88% of the way up it.
- At 0.83 the gate takes 52% of submissions. Moving to 0.80 takes 63% (+72 turns); 0.78 takes 69% (+111).
- The 0.80–0.83 band (72 turns) reads as substantive on inspection, with one exception: T543, a verbatim repeat.
- The instrument's scatter on text that never changed is sd 0.099 and range 0.38 over 26 judgements, so the
  0.80-to-0.83 gap is under a third of one sd. Nothing finer than about 0.05 is above the noise.
- 0.83 is the lowest candidate floor that rejects all 26 verbatim resubmissions. 0.80 admits 1, 0.78 admits 3,
  0.75 admits 6, 0.70 admits 17.
- `new` drifts *upward* on unchanging text, +0.070 per 100 turns, while `keep` drifts down. A floor therefore does not
  mean the same thing in round 55 as in round 25, and the likely cause is the 56–72k-token uncached prompt.
- Synthesis is scored *inversely* to how well it synthesises, and that is not a threshold problem.

The cheapest thing that would make the next calibration decisive: run table 2 with the seat order rotated each round
and the floor set wherever he likes, then re-run `floor_calibration.py` on it. Rotation removes the one confound that
cannot be subtracted from this data, and the section 4c numbers become a clean measurement instead of a caveat.

Two additions to that table, now that 4a exists, both cheap and both pointed at the drift rather than the threshold:
plant one seat that resubmits a fixed paragraph on a schedule, which turns the accidental sample into a designed one
and measures sd and drift directly; and run it with the prompt trimmed or cached, which tests whether the drift is
context length as section 4a suspects. If it is, the drift is fixable without touching the floor at all.
