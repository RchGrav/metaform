# Roundtable gate development log

Every gate proposal, disposition, material change, witness, test, review and removal proposal is recorded here (owner's Gate Burden standard, §10). The standard is in `gate-burden.md`, word for word as the owner supplied it from Vivi. The registry is `gate-registry.yaml`.

For Roundtable the standard applies to gates on inference: anything that stops, rejects, hides or delays what the agents produce, or their work (owner, 2026-11-07: "This only relates to inference"). The decision authority is the owner.

## 2026-11-07-01 Registry created: gates the owner designed

The registry records 21 inference gates found in the code. These carry the owner's design:

| Gate | Source |
|---|---|
| RT-G01 The five message checks | Owner's evaluation specification and questions, 2026-11-07 |
| RT-G02 Reply length limit blocks long messages | Owner, 2026-11-07; off by default |
| RT-G03 The table waits until two agents are free | Owner, 2026-11-06 |
| RT-G04 A busy agent's turn is skipped | README §4.4 |
| RT-G05 The table ends after its rounds | Owner, 2026-11-07 |
| RT-G07 Topics are off by default and need JEV | Owner, 2026-11-06 and 2026-11-07 |
| RT-G08 Two quiet rounds start a topic poll | README §6 |
| RT-G17 JEV sees only recent rounds, within its token limits | Owner's evaluation specification |

## 2026-11-07-02 Gates added by builders: awaiting the owner

These gates were added by the agents that built Roundtable. Under §8 an agent may only propose removal; the owner disposes.

**Removal proposed:**

| Gate | Evidence |
|---|---|
| RT-G11 The advance tool is refused during a topic poll and waits for the floor | No witness. Found by reviewers reading the code. |
| RT-G13 Topic proposals are cut at 512 characters | No witness. Cuts text, which the owner ruled out on 2026-11-07. |
| RT-G20 Agent processes are killed on a timer at shutdown | SIGKILL can corrupt files, git state and agent session records; the ACP spec sets no time limit; the owner called it aggressive. Proposed replacement: wait for each agent to exit, show any still running, force stop only on the owner's request. |

**Disposition pending:** RT-G06 (the exact end condition with no round limit, and the "done" wording), RT-G09, RT-G10, RT-G12, RT-G14, RT-G15, RT-G16, RT-G18, RT-G19, RT-G21. Each registry entry records its witness, or that it has none.

## 2026-11-07-03 Test

`crates/roundtable/tests/gates.rs` checks that:

- every gate id named in the code is in the registry;
- every active registry entry is named in the code;
- each known kind of blocking construct carries a gate id, or a "not a gate" note with its reason, within the three lines above it.

Checked by removing the RT-G12 id from the code: the test failed and named the line, then passed again with the id restored.

Limit: the test knows the kinds of blocking construct found on 2026-11-07. A new kind is caught only once its pattern is added to the test.

## Left out of the registry

**Mechanical impossibility (§3):** errors that only report something cannot be done. An agent does not speak a usable ACP version, a session does not offer a requested setting, a session cannot be resumed, a JEV answer is unreadable, or the table has already ended.

**Not inference gates:** these ordinary software safeguards:

- the web API's chair token and address check
- the seat tool tokens
- Roundtable's secrets removed from agents' environment
- the registry launch-variable filter
- the table configuration checks
- AgentSight's refusal to use sudo
- the OpenRouter adapter's tool-server refusal and file confinement
- the end of a table when no agent is left
- the rating round on End

## 2026-11-07-04: settings switch the gates

The owner asked for "a configuration and permissions system" for the gates. Each gate that has a sensible "off" or limit now has a setting, declared once in `crates/roundtable/src/settings/decl.rs`. Changing a setting is the owner's disposition of that gate for later tables. Each registry entry names its settings in a `settings:` line, and the test `gate_settings_and_the_registry_agree` checks that the two lists match.

- **Defaults keep today's behaviour,** with three exceptions taken from owner decisions:
  - RT-G13 now blocks a topic proposal over its limit instead of cutting it. The owner: "we arent going to be truncating if we add limits in we will block messages for being too long".
  - RT-G21 is off by default. The owner's decision of 2026-11-05 says "the table never waits on independent work".
  - A table needs at least two seats. The owner: a discussion needs "atleast 2 agents available to debate".
- **RT-G20** can be switched off: `shutdown.force_stop` off closes each agent's input and waits for it to exit, with no signal. It stays on until the owner decides.
- **RT-G18** became per-kind permission rules. Each ACP request kind (read, edit, delete, move, search, execute, think, fetch, other) is answered by one of three rules: inside (today's behaviour), allow or refuse. `permissions.scope` picks the folder: the workspace, the project (the nearest folder above it with .git), or a path.
- **No setting (fixed in code):** RT-G03, RT-G04, RT-G09, RT-G10, RT-G12, RT-G14, RT-G15, RT-G16 and RT-G19. Each has no sensible "off" or needs a design change first; the owner can still dispose of them by removal.
- **Who can change settings:** only the chair, through the chair-token API (`/api/settings/...`) or the page at `/settings`. Agents' tools cannot read or change them. Saved settings live in Roundtable's home folder (`settings.json`). Each table records the settings it ran with, and where each came from, in its own folder.

## 2026-11-07-05: JEV is required

The owner: "in the new version jev is a requirement not an option". The evaluation specification agrees: "Evaluation completes before the associated message becomes shared context".

- **The `table.judging` setting and the chair's judging switch are removed.** RT-G01 keeps `jev.gate_pass`. A request that still sends `judging: false` is refused; `judging: true` is accepted and changes nothing.
- **A table does not start without JEV's key.** The server and the core both refuse it.
- **A message JEV could not evaluate is not shared.** This covers a JEV error and a request that cannot fit JEV's limits. The chair sees the error at once. The author hears at its next turn that the message was not shared and was not rejected (`resources/feedback/not_evaluated.md`, builder wording for the owner to replace). The table continues: "If JEV is down this doesn't halt, it continues". Before, such a message was shared unjudged.
- **Topics need only `table.topics`.** They stop if the chair removes JEV's key during a table.
- **Effect on rounds:** a message that was not evaluated counts as nothing accepted. While JEV is down, a table with no round limit ends after `table.quiet_rounds` quiet rounds.
