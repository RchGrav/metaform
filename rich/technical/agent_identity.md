# AgentIdentity

## Statement

Skills are used according to the SEP-2640 Skills Extension with the difference that skill visibility is perceptually contextual by either functional or spatial proximity. Agents receive an event notifying them when new skills are learned based on perceptual distance. Once skills are learned in a context they are not removed until the agent performs a handoff. Agents may handoff based on % of context used, or based on satisfying a goal. Agent identities are seeded based on their genesis context when they are born, past interactions an agent has had are retained and referenceable, this carries agent to agent and user to agent comms, as well as feature commit details and other related refs which can be attached. See AgentIdentity

## Genesis and seed

An agent is born with its genesis context, the first session a harness opens for it. The id of that session is the seed of the agent's identity.

The name follows from the seed and from nothing else (`modules/dispatch/names.py`):

1. Hash the session id's UTF-8 bytes with 32-bit FNV-1a.
2. XOR-fold the hash to 16 bits.
3. The high byte picks one of 256 adjectives, the low byte one of 256 nouns (`dispatch/resources/names/`).
4. Capitalize both and join them with nothing between: `BriskLantern`.

The same id always gives the same name, so a resumed session keeps its name, and the person and other agents point at an agent by name instead of by id. There are 65,536 names; two live agents can share one, and nothing rehashes.

## Contexts

An identity lives through contexts. A harness opens, loads, resumes or forks a context over ACP (`session/new`, `session/load`, `session/resume`, fork). Compaction inside a context starts a new epoch of it. A closed context can always be called back, because sometimes the work needs to find out what happened.

## What an identity keeps

Past interactions are retained and referenceable:

- agent-to-agent messages;
- user-to-agent messages;
- the agent's tool calls;
- feature commit details;
- other related refs, attached to the identity.

A past context is referenced by the agent's name, which the session id gives (see Genesis and seed). Each context's thread is kept in order, so the person or an agent can call that context back by name and read what happened.

## Skills

Skills follow the SEP-2640 Skills Extension (`io.modelcontextprotocol/skills`), with one difference: which skills an agent sees is perceptually contextual. Functional proximity (distance along the functional map) or spatial proximity (distance in a virtual or physical space) decides it.

- When the agent comes within perceptual distance of a skill, it receives an event that a new skill is learned.
- A skill learned in a context stays with the agent for the rest of that context.
- Learned skills are cleared at handoff. The successor learns again from where its work is.

## Handoff

An agent hands off when it has used a set share of its context, or when it has satisfied a goal. The handoff is centered on the work: the agent finishes what is in hand, writes the handoff, and starts its successor with it. The successor takes over the agent's seats on the work.

## Open

- Whether the identity and its name carry across a handoff, as one lineage seeded by the genesis context, or whether each successor is a new identity that references its predecessor.
- Where an identity's own memory lives, apart from the project memory at map nodes.
- Which MCP notification carries the "new skill learned" event.
