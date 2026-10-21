# Choosing the AI tool, model and thinking level

Research delivered on 2026-10-20, kept whole. Assignment-time runtime selection uses advertised model descriptions
and the policy in BASE-066. Jev chooses when available. The Facilitator's full model decides when Jev cannot answer.
The ticket records agent, model, effort, decider and confidence. Person overrides remain effective.

---

Choose ChatGPT, Claude, or Jev based on whether you need open-ended generation, deep document/code reasoning, or high-speed, structured decision-making. [1](https://linas.substack.com/p/how-to-use-jev-ai), [2](https://www.knolli.ai/post/jev-vs-chatgpt-vs-claude)

## When to Choose ChatGPT (OpenAI)

- Best for: Broad, flexible workflows, everyday problem-solving, multi-modal tasks (voice, image generation), web-grounded search, and rapid prototyping/coding. [1](https://beampath.org/articles/which-model-should-i-use), [2](https://beampath.org/libraries/foundations/which-model-should-i-use), [3](https://sintra.ai/blog/anthropic-vs-chatgpt), [4](https://www.knolli.ai/post/jev-vs-chatgpt-vs-claude)
- Model Selection:
  - GPT-6 Astra / GPT-5.2 Thinking: Use for the most demanding, multi-step complex reasoning, architectural logic, and hard coding problems.
  - GPT-6.1 Sol: Use as a balanced daily driver when you need high intelligence combined with lower cost/latency.
  - GPT-6 Luna: Use for high-volume, cost-sensitive automated tasks where you don't need maximum heavy-duty reasoning.
  - Instant / lighter variants: Use for quick conversational turns, basic email drafts, and standard copy. [1](https://developers.openai.com/api/docs/models), [2](https://beampath.org/libraries/foundations/which-model-should-i-use)
- Thinking Levels / Effort:
  - Low Effort: Quick pattern matching, syntax formatting, or minor adjustments.
  - Medium Effort: Standard everyday bugs, clear features, and routine refactors.
  - High / Max Effort: Deep algorithmic complexity, multi-file codebases, or hard-to-reproduce bugs. [1](https://www.mindstudio.ai/blog/claude-code-effort-levels-explained)

## When to Choose Claude (Anthropic)

- Best for: Document-heavy workflows, long-context analysis (up to 200k+ tokens), nuanced writing, and complex multi-file repo coding. Anthropic models tend to be more careful, structured, and less prone to unprompted verbosity or motivated reasoning. [1](https://www.deeplearning.ai/the-batch/issue-372), [2](https://sintra.ai/blog/anthropic-vs-chatgpt), [3](https://www.knolli.ai/post/jev-vs-chatgpt-vs-claude), [4](https://beampath.org/articles/which-model-should-i-use)
- Model Selection:
  - Claude Opus 5.5 (or Opus 4.5): Use as the top-tier default for heavy knowledge work, complex business reports, hard coding, and max-intelligence requirements.
  - Claude Fable 5.1: Use for demanding agentic work and multi-step reasoning when Opus falls short on specific evaluations.
  - Sonnet / Haiku tiers: Use for a faster, more economical balance of everyday speed and quality. [1](https://platform.claude.com/docs/en/models/overview), [2](https://benchlm.ai/best/anthropic-models), [3](https://www.deeplearning.ai/the-batch/issue-372)
- Thinking Levels / Effort:
  - Low: Quick syntax fixes, simple boilerplate, and direct lookups.
  - Medium: Standard everyday tasks and familiar refactoring.
  - High / Max: Multi-file architectural design, hard debugging, and complex long-horizon planning. [1](https://www.reddit.com/r/ClaudeAI/comments/1uoyq1x/when_to_use_each_model_and_when_to_change_the/), [2](https://www.mindstudio.ai/blog/claude-code-effort-levels-explained)

## When to Choose Jev (TypeSafe AI)

- Best for: Strict programmatic decisions, classification, routing, scoring, and policy checks at scale (acting as a "smart switch statement" rather than a text generator). [1](https://www.knolli.ai/post/jev-vs-chatgpt-vs-claude), [2](https://linas.substack.com/p/how-to-use-jev-ai)
- What Jev Cannot Do: It does not generate natural language prose, summaries, or code. Use generative LLMs (GPT/Claude) to write the content, and hand off the decision/routing logic to Jev. [1](https://medium.com/@unicodeveloper/the-ultimate-guide-to-jev-the-new-frontier-ai-for-faster-decisions-acd78e5f4c56), [2](https://linas.substack.com/p/how-to-use-jev-ai), [3](https://www.knolli.ai/post/jev-vs-chatgpt-vs-claude)
- Output Types:
  - Choice: Picks a single predefined option out of up to 255.
  - Score: Rates an input against 2 to 10 ordered levels with calibrated probabilities.
  - Noul: Returns the strict true/false probability of a statement. [1](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [2](https://medium.com/@unicodeveloper/the-ultimate-guide-to-jev-the-new-frontier-ai-for-faster-decisions-acd78e5f4c56)
- Why use it: It executes in 70ms–500ms (vastly faster than standard LLMs), guarantees zero type errors by schema construction, and avoids open-ended text hallucinations. [1](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [2](https://medium.com/@unicodeveloper/the-ultimate-guide-to-jev-the-new-frontier-ai-for-faster-decisions-acd78e5f4c56)

## Quick Comparison Summary

| Workflow Need | Recommended Tool | Why |
|---|---|---|
| Writing copy, brainstorming, voice, web search | ChatGPT | Broad versatility and DALL·E/voice integration |
| Long documents, nuanced analysis, deep coding | Claude | Superior long-context tracking and careful reasoning |
| High-speed classification, if/else routing, scoring | Jev | Zero-hallucination schema enforcement and 40x–200x speed |

---

## Related

- [xinyao27/jevonian](https://github.com/xinyao27/jevonian), a project the person pointed to on 2026-10-20 as doing
  something similar: automatic selection with Jev. Without Jev, the Facilitator chooses each ticket's runtime.
  The person chooses `dispatch_system_agent` for the system agent, `dispatch_healing_agent` and `dispatch_healing_effort` for
  the system healing itself, each agent's own mode, model and thinking level under Agents, and `dispatch tune` for one
  ticket.

## Where it is applied

- `src/metaform/modules/orchestration/runtime.py`: constrained assignment-time runtime choices from advertised options.
- `src/metaform/modules/orchestration/resources/prompts.xml`: runtime questions and Facilitator fallback instructions.
- `HEALING_EFFORT`: a ticket of kind or condition broken, the system healing itself, is started at the highest thinking
  level, under the person's own choice for the ticket or the agent.
