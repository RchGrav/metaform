# Subagent handoff: what was checked (2026-11-01)

Source: web search snippets, not fetched pages. Re-check before relying on exact wording.

- A non-fork subagent starts without the parent conversation. The Agent tool prompt is the only content passed from parent to subagent, so file paths, errors and prior decisions must be restated in it.
- A fork loads the parent's conversation so far, system prompt and tools.
- Only the subagent's final message returns to the parent; intermediate tool calls stay in the subagent. A dead end it found can be lost, so the next subagent retries it.
- If a subagent's `tools` list omits a tool, that tool is absent with no error or prompt.
- Defaults reported: depth 3 levels below the main agent, 20 subagents at once, no spend limit unless set.
- Anthropic's best-practices page says a fresh subagent must gather context the conversation already had, so it can be slower than working in the main conversation. Its main benefits are parallel work and a fresh pair of eyes.
- NOT CONFIRMED: the claim that subagents are switched off by default. Searches found no such default or recommendation. Say so when it comes up.

Sources:
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/best-practices
- https://code.claude.com/docs/en/agent-sdk/subagents
- https://code.claude.com/docs/en/context-window
