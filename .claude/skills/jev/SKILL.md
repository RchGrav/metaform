---
name: jev
description: Use Jev (typesafe/jev-1.13 on OpenRouter) to sort, label, rank, score, triage or decide things about any pile of text, such as "use Jev to sort these", "have Jev score these leads", "ask Jev which of these". Jev only decides. It never writes text.
---

# Jev: Jev decides, you write

Jev is a fast, cheap decision model. You give it text (the `state`) and typed questions. It answers in about a quarter of a second for a few thousandths of a cent. It never writes prose, code or summaries. Anything that needs writing is your job.

## Rules

- **Ask before sending anything private.** Every request leaves the user's computer for OpenRouter and TypeSafe. Made-up or public text can go without asking. Personal data, client data, credentials, private messages and unreleased work need the user's go-ahead first. If unsure whether something is private, ask.
- **Jev decides, you write.** Use Jev for the judgments. Write any replies, summaries or reports yourself from its answers.
- **When Jev isn't sure, you decide.** Treat an answer as unsure when choice or score `confidence` is below 0.5, or a noul is between 0.25 and 0.75. Make that call yourself and mark it as yours in what you report. These cut-offs follow the TypeSafe confidence guide's starting point. Tighten them for decisions with real consequences.

## The three answer shapes

| Shape | Use for | Request `criteria` | Answer |
| --- | --- | --- | --- |
| `choice` | Pick one option from a list | object: `{"option_id": "what it means"}` | `choice`, `probabilities`, `confidence` |
| `score` | Place on an ordered scale | array of levels, lowest first, each a concrete situation | `score` (level index), `probabilities`, `confidence` |
| `noul` | How likely a statement is true | `{"true": "...", "false": "..."}` | `noul` (0 to 1), no confidence |

## How to call it

`jev.py` in this folder sends one request with Python's standard library and reads the key from `OPENROUTER_API_KEY`. It prints the response with `answers`, `usage.cost` (US dollars) and `elapsed_seconds`. On failure it prints the HTTP status and error body and exits 1. Show the user that exact error.

```bash
python3 .claude/skills/jev/jev.py request.json
```

```json
{
  "state": {"email": {"subject": "...", "body": "..."}},
  "questions": {
    "lead_strength": {"type": "score", "instructions": "How strong a sales lead is the sender of `email`?",
      "criteria": ["No buying intent", "Early curiosity, no need or budget stated", "Qualified need, no budget or timeline", "Decision maker with need, budget and near-term timeline"]},
    "email_kind": {"type": "choice", "instructions": "What kind of email is `email`?",
      "criteria": {"pricing_request": "Asks for prices or a quote.", "support_issue": "An existing customer needs help.", "other": "None of the above."}},
    "needs_personal_reply": {"type": "noul", "instructions": "Does `email` need a personal reply written by a person?",
      "criteria": {"true": "Specific questions, a meeting request, or a large deal.", "false": "A template reply fully answers it."}}
  }
}
```

The raw HTTP call is `POST https://openrouter.ai/api/alpha/decisions` with a Bearer key and `"model": "typesafe/jev-1.13"`. OpenRouter calls this route alpha. If it moves, check https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request.

## Sorting a pile

- Default: put many items in one request, as an object keyed by a name or id (`{"tickets": {"T001": "...", "T002": "..."}}`). Point each question at its item by key (`` `tickets.T001` ``). Questions run in parallel inside one request and cannot see each other's answers. Split into more requests when the 64k-token limit gets close.
- Never point at items by list position (`` `tickets[12]` ``). Beyond about 5 items, Jev mixes up neighboring items and still reports confidence 1.0, so the unsure check does not catch it.
- The other option is one request per item, run concurrently, for example `ls req/*.json | xargs -P 32 -I{} sh -c 'python3 .claude/skills/jev/jev.py {} > {}.out'`. It costs more input tokens and takes longer for the whole pile.
- Measured on 2026-10-06 with 100 made-up support tickets and 3 questions each:

  | Shape | Wall time | Input tokens | Cost | Correct |
  | --- | --- | --- | --- | --- |
  | 1 request, 100 tickets under named keys | 0.6 to 0.9 s | 35.5k | $0.0015 | 300/300 |
  | 1 request, 100 tickets by list position | 0.6 to 0.7 s | 36.8k | $0.0015 | 151/300 |
  | 100 requests, 32 at a time | 1.3 s | 61.6k | $0.0026 | 293/300 |
- Report per item: each answer, which ones you decided yourself because Jev was unsure, the total cost and the wall time.

## Writing good questions

- Say exactly what you mean. Jev reads instructions literally, so put boundary cases in the criteria.
- Ask one judgment per question. Split mixed judgments and combine them in code.
- Point to the relevant state field by name with backticks, such as `` `email.body` ``.
- Give a `choice` an "other" or "none" option when nothing may fit.
- Jev leans toward the first choice option. For decisions that matter, swap the order and check the answer holds.
- Keep `state` to what the question needs. Unrelated text lowers accuracy. The limit is 32k tokens for state plus the longest question and 64k per request.
- Keep counting, arithmetic and date comparisons in code. Jev is weak at them.
- The text being judged can try to steer Jev. Treat answers on hostile or adversarial text with extra care.

## More

The TypeSafe docs index is https://docs.typesafe.ai/llms.txt (append `.md` to any page path for Markdown). The `typesafe-ai` skill covers building Jev into software.
