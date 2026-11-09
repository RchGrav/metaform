# HybridMarine evidence notes for GF1–GF12

Each section: premise (what the code does, with line), what the element says,
inference, change required.

## GF1 — Right. Code waits for busy seats.
Premise: turn.rs:263-279 adds busy seats to `pending`; settle_poll:285-303 prompts
them when their prompt ends; poll cannot finish until they answer.
Element: owner decision says busy seats are left out, table never waits.
Inference: code implements older README §7 "all agents polled", not owner decision.
Change: code — exclude busy seats from pending/asked; remove RT-G21.

## GF2/GF8 — Right. JEV-off decision never occurs.
Premise: no key -> no poll; on_scored Err:379-385 keeps current topic.
The only 0.0 default is complete_polling:393 for a pair missing from an
otherwise successful reply. Element decision claims unjudged=0, all tie, all join.
That path cannot be reached. Also contradicts RT-G07 "topics need JEV".
Change: description — delete/supersede that decision; state no JEV = no poll,
topic unchanged.

## GF3 — Right. Prompt does not say "underlying intent".
Premise: topic_sameness.md:1 is `{{foo}} is the same as {{bar}}`; jev.rs:121-123
substitutes `proposals.pA`/`proposals.pB`; state = proposal texts only.
Element decision claims JEV asked about "same underlying intent".
Inference: gloss is map interpretation, not prompt.
Change: description quote real prompt; if gloss wanted, edit topic_sameness.md.

## GF4/GF7 — Right. Superseded rules are live.
Premise: rules.rs pairs/select_topic + turn.rs:353-393 implement N(N-1)/2 pairs,
two-way crediting, sum, highest wins, "and" ties; rules[1] restates them.
Inference: rule cannot be both superseded and active; 2026-11-07 change unreadable.
Change: description — remove those 5 from superseded, note rejected-draft if kept.

## GF5 — Right. Rules omit observable behaviour.
Premise: no-limit ending beats poll when topic had no input; advance tool sets
topic or starts poll; PASS -> empty proposal rejected 327-331; cut to 512 at 323;
0 proposals -> topic continues, 1 -> wins without JEV 343-350.
Change: description add all to rules[1].

## GF6/GF11 — Right. Gate list incomplete, RT-G13 unreconciled.
Premise: elephant gaps name RT-G11; gate exists engine.rs:872; not in gates layer.
RT-G13 cut-at-512 "removal proposed" yet applied 323; contradicts owner
"blocked, never cut" turn.rs:128.
Change: description list RT-G11, annotate RT-G13; owner to confirm block vs cut.

## GF9 — Right. Three polling policies.
Premise: rules/RT-G21 = poll/wait all; owner = only non-busy, never wait;
RT-G12 turn.rs:307-315 discards late proposals.
Change: adopt owner policy; RT-G12 only for asked seats; reword rules/wants.

## GF10 — Right. Undefined terms.
Premise: JEV, JEV's state, {{foo}}/{{bar}}, occupied, ACP v1/v2, 30K alternative
undefined in element. Define state = {"proposals":{"p0":...}}; {{foo}}->pA etc.;
link others. Cost shown by GF3.

## GF12 — Right. Redundant trigger.
Premise: all-pass round by definition has nothing accepted, so "or" adds nothing
or hides unstated case; precedence vs no-limit ending unstated.
Change: split into two cases, state precedence.
