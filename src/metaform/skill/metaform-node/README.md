# The metaform-node skill

A person-invoked read of one node brief in Claude Code. Typing `/metaform-node <address>` has Claude check that the text is an Address and run `metaform map where '<address>'` in the project folder. The brief that prints is the element at that Address, what relies on it, what it relies on, and the counts held there, as the map holds them now. It goes through the `metaform` command line, not the MCP server, so it costs no MCP round trip and still works when the server is not connected.

Only `SKILL.md` is installed; this README stays in the package.

## Where it is installed, and when

- **Claude Code only**, at `~/.claude/skills/metaform-node/SKILL.md`, the folder Claude Code loads personal skills from. `metaform install claude` writes it, and so does `metaform provision claude`.
- **Never the shared `~/.agents/skills`.** Claude Code does not read that folder. Codex does, and it neither fills `$ARGUMENTS` nor honours `disable-model-invocation`. There the skill would be one more description listed to the model, with nothing to read.
- **Only while map is on.** The skill runs `metaform map where`, so it exists only while the map module is enabled and on the command surface of the folder where install, provision, enable or disable runs. With map off, install and provision leave it out and remove a copy already there. `metaform enable map` writes it and `metaform disable map` removes it, from the command line or the settings screen. Both act only where Metaform set Claude Code up, by install or provision. A disabled map never leaves a skill whose command answers that map is off.
- `metaform uninstall claude` removes it, with a backup, like the metaform skill.

## How the Address is handled

The skill hands the typed text to Claude as data. Claude checks that it is an Address: dotted segments of lowercase letters, digits and underscores, the same shape the store accepts. Empty text gets a request for an Address. Anything else gets "not an Address". Nothing runs in either case. A valid Address goes to the command as one single-quoted word, and `allowed-tools` grants only `Bash(metaform map where *)`.

`disable-model-invocation: true` keeps the skill person-invoked: Claude never loads it on its own, and its description does not compete with the MCP tool `map_where`.

## Why not a `!` block

A `!` block would run the command before Claude sees the skill, and save a model turn. Claude Code substitutes `$ARGUMENTS` into the command text before the shell parses it, so the typed text would be parsed as shell syntax. Every way of embedding it can be broken out of, a quoted heredoc included: an argument that holds the delimiter line ends it. Claude Code checks injected commands against the permission rules, but a session that bypasses permissions runs them. Checking the Address before anything runs is the safe order. The cost is one model turn and one Bash call.

## After compaction

Claude Code re-attaches the most recent invocation of each skill after compaction, which is this text with the Address filled in. The brief Claude read is not re-attached. Invoking the skill again reads the node anew. In an agent session (`METAFORM_SESSION` set, as dispatch sets it), map reads are told once, so a second read of the same node shows only what changed since the first.
