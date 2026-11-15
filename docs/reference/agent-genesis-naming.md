# Agent genesis and name generation

The owner's original identity definition is preserved in [AgentIdentity](../../rich/technical/agent_identity.md). An agent is born with its genesis context, the first session its harness opens. That first session ID seeds its name.

## Fixed word lists

- [adjectives.txt](../../src/metaform/modules/dispatch/resources/names/adjectives.txt) contains 256 adjectives in the owner's order.
- [nouns.txt](../../src/metaform/modules/dispatch/resources/names/nouns.txt) contains 256 nouns in the owner's order.

Each line occupies a zero-based byte index. The first line is index 0 and the last is index 255. The lists must retain their order and spelling. Reordering them changes the names produced by the same seeds. The archive contains exact copies of both files.

## Derivation from the genesis session

The shared [dispatch generator](../../src/metaform/modules/dispatch/names.py) applies these steps:

1. Encode the genesis session ID as UTF-8.
2. Start a 32-bit FNV-1a hash at `2166136261`.
3. For each byte, XOR it into the hash, multiply by `16777619` and keep the low 32 bits.
4. XOR-fold to 16 bits: `(hash ^ (hash >> 16)) & 0xffff`.
5. Use the high byte as the adjective index and the low byte as the noun index.
6. Capitalize each word and join them without a separator.

The same ID and the same word tables produce the same name. The two tables give 65,536 possible combinations. The owner's rule accepts collisions and does not rehash an established identity. Stable IDs distinguish agents whose display names collide.

For an illustrative seed of `first-session-id`, the 32-bit hash is `0xbfa1cbba` and the folded value is `0x741b`. Adjective index 116 selects `hunter`; noun index 27 selects `chaos`. The resulting name is `HunterChaos`.

## Current roundtable implementation difference

The shared dispatch function implements the hash and word selection above. The [roundtable alias allocator](../../src/metaform/modules/roundtables/roundtable/identity.py) currently supplies a separate random UUID to that function and retries when a name is already taken. Its private alias is associated with a model source and occurrence and is reused across tables.

That seed selection and collision retry differ from the owner's genesis-session rule. Both implementations are included for review. Packaging them does not change runtime naming or rewrite existing participants.

The original AgentIdentity document also leaves identity lineage across a handoff open. Its complete text is included unchanged, alongside [the later technical specification](../../rich/technical/revision/03-technical-specification.md), which restates genesis-based names, fixed tables and accepted collisions. The actor-instance design in [actor-identity.md](actor-identity.md) provides additional context and retains its original draft status and open questions.
