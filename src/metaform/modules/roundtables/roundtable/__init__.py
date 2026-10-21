"""roundtable: an MCP and A2A server that holds a discussion among models, where only real contributions are kept.

A chair opens a table with an opening message and its seats. The seats speak in turn, round robin, in a fixed order,
each at most 512 characters, and a submission enters the discussion only when Jev finds it new, valuable, relevant
and worth keeping, each at `keep` (0.83) or above. A vetoed submission is shown to every seat as its verdict, the four
questions with their nouls and a link to its text. The table ends after a full round that kept nothing, at its most
rounds or OpenRouter dollars, when OpenRouter is out of credits, or when its chair ends it; a seat at the table writes
the report, and the whole record is exported as JSON beside it.

Three protocols, each for its job: MCP is how clients open, chair and read tables (`server`); ACP runs the local
harness seats, Claude Code and Codex, through this server's own client (`harness`); A2A makes each table one context
anyone allowed can follow (`a2a_server`) and seats remote agents (`peers`).

The parts: `config` the settings, `prompts` every word sent, `store` the tables, `seats` who may sit, `names` each
seat's short name, `seat` the one interface every kind of seat goes through, with its kinds in `harness` (acp),
`openrouter` (a model, with prompt caching), `outside` (an agent that submits its own turns) and `peers` (a2a);
`judge` Jev's four nouls, `render` what each reader sees, `export` the structured record, `runner` the detached
process that runs a table, `server` the MCP tools and resources, `a2a_server` the A2A server, `web` the web page,
and `importing` a table Metaform recorded, taken in.
"""

__version__ = '0.1.0'
