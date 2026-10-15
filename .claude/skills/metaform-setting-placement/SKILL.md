---
name: metaform-setting-placement
description: Use when adding, removing or placing a Metaform setting.
category: development
---
# Where a Metaform value lives

A value is a setting only when a person would sensibly choose it differently and the choice changes what the system does. Decide this before declaring any key.

- One right answer: a named constant beside its code, with the reason in a comment.
- Page look (layout, theme, map depth, flow mode, toggles): view state, kept per account by the web module's view.py. It is not a setting and `config --show` does not list it.
- One call's mode (a transport, a dry run, raw or critic output): a per_call switch, given on that call and never read from storage.
- A set of records (peers, routes, sources): module records with add and remove verbs, not a list setting. A list setting loses its other entries whenever one is saved.
- Two settings that mean one thing merge into one. voice_language is the single speech language now, replacing twilio_language and elevenlabs_scribe_language.
- Per-agent tuning: one dispatch strengths setting per agent that agent_choices() returns at load.
- Nothing reads it: delete it. Never switch it off.
- A choice that lets agents act without asking is risky: set needs --confirm.
- A value with a known closed set declares `choices` (a list, or a function of a Context reading them from their source). A list with choices refuses a member outside them on every surface, as a select always did, so a typo is never stored with exit 0. Only a value that is genuinely open (a URL, a command, a name) stays typed.
- A list whose check says what another member does keeps it: declare `beyond_choices=True` and let the check speak (`layers` keeps an unknown name with a notice, CLI-033). Do not use it to dodge choices.
- A select whose choices exist only after starting something (an agent's models) declares `choices_from=` with the command that reads them. The screens offer to run it; the select offers no more than its default until then.
- Still typed, because the list lives in a network catalog or the browser: ElevenLabs voices, provider model lists, Vultr region and plan, Paperclip ids. Each becomes a cached read before it becomes a list.
- A choice set added or changed updates the template README and CHANGELOG in the same change.

When a removed key's value must carry over, migrate it with the carry pattern in `metaform-development`.

After a cleanup, count in a scratch home with every module enabled: the rows of `metaform config --show` and the set list an agent sees. A count that drops with no new home for each removed key is a lost setting, not a cleanup.
