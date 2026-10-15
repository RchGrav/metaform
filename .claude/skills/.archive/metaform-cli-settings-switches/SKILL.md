---
name: metaform-cli-settings-switches
description: Use when metaform set or a module verb refuses a --no switch or a person-only setting.
category: development
---
# Metaform CLI settings: switches and person-only values

Boolean settings take the switch form only: `--name` to turn on, `--no-name` to turn off. `--name=false` is refused with "takes no value".

- Read the values with `metaform config --show` before and after a change; a `(set)` marker means the value was stored, not defaulted.
- Settings declared `person_only` (for example `dispatch_stay_connected`, `dispatch_resume_chats`) can be set only by the person, on the command line or the page. An agent's `set` is refused with "set only by the person". Do not look for another route around the refusal; say in the ticket note what the person needs to change.
- The same refusal applies to a module verb that takes a person-only setting as a per-call switch, such as `dispatch autostart --dispatch-autostart --dispatch-agents 50`, when `METAFORM_ROLE` is set to an agent role. `cli.run_module` checks the switches the verb declares; MCP `_prepare` does the same. Context switches (project, layers) are not settings and are not checked. Test it with a role set and no fix: it must fail without the check.
- Unsetting `METAFORM_ROLE`, `METAFORM_SESSION`, `METAFORM_WORK` or `METAFORM_NODE` so a person-only `set` goes through is the route around the refusal this skill forbids, in a scratch home too. A live check that needs such a value stops there and names it in the ticket note.
- Record what you could not change in the ticket note with `metaform map work op=edit note="..."`, not in chat.
