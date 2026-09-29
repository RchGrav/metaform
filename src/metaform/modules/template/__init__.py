"""template: the empty start of every module, BASE-019.

Copy this folder, rename it, set MODULE.id to the folder's name, write the
module's purpose, and enable it with `metaform enable <id>`. Every field
hello declares is here, empty. CHANGELOG.md records each change to the
module contract, so a copy can follow it.
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
