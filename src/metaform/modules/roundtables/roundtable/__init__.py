"""roundtable: an MCP and A2A server that holds a discussion among models, where only real contributions are kept.

A chair opens a table with an opening message and its participants. Ready participants speak while busy participants
work. Jev independently checks new content or a position on a recent matter, value and relevance, each at 70% by
default. Only accepted contributions reach peers. Rejected contributions return plain failed-condition feedback
only to their author, while the owner retains the full record. A judged discussion ends after two complete quiet
rounds with an actual opportunity for every participant in each. Unjudged discussion ends on unanimous PASS.
Chair advancement and the configured token budget also end discussion. Persistent generated names retain profiles
across sessions. The report and full private record are exported together.

Three protocols, each for its job: MCP is how clients open, chair and read tables (`server`); ACP runs the local
harness seats, Claude Code and Codex, through this server's own client (`harness`); A2A makes each table one context
anyone allowed can follow (`a2a_server`) and seats remote agents (`peers`).

The parts: `config` the settings, `prompts` every word sent, `store` the tables, `seats` who may sit, `names` each
seat's short name, `seat` the one interface every kind of seat goes through, with its kinds in `harness` (acp),
`openrouter` (a model, with prompt caching), `outside` (an agent that submits its own turns) and `peers` (a2a);
`judge` Jev's independent nouls, `render` what each reader sees, `export` the structured record, `runner` the detached
process that runs a table, `server` the MCP tools and resources, `a2a_server` the A2A server, `web` the web page,
and `importing` a table Metaform recorded, taken in.
"""

__version__ = '0.1.0'
