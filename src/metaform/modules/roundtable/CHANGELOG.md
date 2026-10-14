# Changelog

Each change to the roundtable module, newest first.

## Unreleased

- The roundtable module, version one, BASE-066: a discussion among models at an Address, where a submission enters only when Jev finds it new, valuable, relevant and worth keeping, each at `roundtable_keep` or above. The verbs `open`, `comment`, `hold`, `continue`, `end`, `watch`, `status`, `list`, `read`, `turn`, `submit`, `submission`, `review` and `run`; the settings `roundtable_keep`, `roundtable_pause`, `roundtable_agent_wait` and `roundtable_reporter`; the tables `discussions`, `seats`, `submissions` and `waiting`, version 1; the resource templates `metaform://roundtable/discussion{discussion}/submission{submission}` and `metaform://roundtable/discussion{discussion}/review`. Seats are models through OpenRouter and agents that submit their own turns; ACP harness seats and A2A peer seats, MCP-040, are not built yet. Whoever opens a table names its seats; there is no default line-up. Ships enabled.
