"""template: the empty start of every module, BASE-019.

Copy this folder, rename it, set MODULE.id to the folder's name, write the
module's purpose, and enable it with `metaform enable <id>`. Every field
hello declares is here, empty. CHANGELOG.md records each change to the
module contract, so a copy can follow it.

A module imports `metaform.nonce` to hand work to an agent by nonce, BASE-050.
`request(module, function, value=None)` issues a nonce, `read(nonce)` returns
its record, `update` changes the value or the function its next run is sent,
and `close` ends it and keeps its record, so its number is never issued
again. `reached()` is the nonce the running command came through, or None
when it did not come through one, and `current()` is that nonce, stopping
the command when there is none. `metaform <nonce>` runs the module's
function for it. hello's `noncedemo` shows it.

Every prompt an agent reads is in `resources/prompts.xml`, an element named
for the prompt, never in Python, MCP-031. `instructions` is listed in the
instructions agents read; a copy writes its own name in place of `template`.
"""
from __future__ import annotations

from metaform.module import Module

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = True

MODULE = Module(
    id='template',
    summary='The empty start of a module.',
    purpose='Replace this with two to four sentences: what the module is for, when an agent uses it, and '
            'where its details are. Details: metaform help template.',
    details='',
    verbs=(),
    subscriptions=(),
    start=None,
    stop=None,
    status=None,
)
