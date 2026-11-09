# Outcome digest: `submit()` must not inline every observed step

**Author:** HunterRanger. **Status:** amendment applied to B-3.1; recorded here with the audit.

## The violated requirement

W-11.6 (Decided, world-system-spec.md:299): "What the world sends an agent is brief and targeted to the
agent's task. Every word costs the agent."

B-3.3 currently says `submit()` "returns pass/fail **with observed values per step**". For every assertion,
on every slot, at every step. B-2.3 now permits a window `{from,to}`, so the return size is
`assertions × (to−from+1)`. Eight assertions in a 60-step window = 480 rows.

Every other agent-facing surface in the spec is bounded:
- `context_budget` (B-2.1)
- one-hop world-graph slice (B-3.2)
- derived selector set (B-2.3), not a free list

Outcomes were the only unbounded one.

## The rule

```
submit() returns:
  verdict: pass | fail
  first_failure: { assertionRef, step, observed, expected }   -- only when fail
  counts: { passed, failed, total }
  outcome_ids: [...]                                          -- fetchable, not inlined

blueprint.outcome(outcomeId) -> { assertionRef, step, observed, expected, verdict }
```

## Premise chain

1. W-11.6: the agent pays per word, so the server must not inline what the agent did not ask for.
2. B-3.3: the agent must see the failing observation in order to revise (the loop).
3. B-3.5: `cycles[]` records outcomes, so each must remain addressable for audit.
4. Therefore: outcomes are stored and addressable; a submit returns a summary plus pointers; the agent pulls
   the ones it needs.
5. W-11.7 ("the world pushes it, or the agent pulls it") is exactly this split for outcome data.

## What does not change

B-3.3's met criterion: "met only if every `outcome.verdict = pass`". The server computes every verdict before
returning. The digest changes delivery, not evaluation, so the derived/stored/server-only split (B-2.3) is
untouched: `outcomes` are still server-only and still recorded in full.

## Observable consequences

- A failing submit with 8 assertions × 60-step windows returns one failure row, not 480.
- A passing submit returns counts and no observation rows.
- `blueprint.outcome(id)` returns any recorded row, so B-3.5's audit trail is intact.
- An agent that never pulls outcomes still gets the verdict, so a correct agent is not penalised for brevity.

## Citation audit (this file)

All 35 W-ids cited in blueprint-spec.md resolve to defined requirements in world-system-spec.md.
All B-x.y references resolve to a defined clause. Checked with a script, not by eye.
