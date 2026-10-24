"""Read historical assignment records without restoring the retired role organization."""
from __future__ import annotations

from typing import Any

from metaform.module import Context, Module, Noun, Verb

from .records import TABLES

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = True


def history(ctx: Context) -> dict[str, Any]:
    with ctx.require_store().tables(write=False) as tx:
        return {'assignments': [dict(r) for r in tx.rows('assignments', limit=0).results
                                if not ctx.nouns.get('work') or r['work_id'] == ctx.nouns['work']]}


MODULE = Module(
    id='orchestration', summary='Read historical assignments from the retired role organization.',
    purpose='Preserve prior records without roles, commissions, execution policy or automatic agent launches.',
    tables=TABLES,
    verbs=(Verb('history', history, 'Read historical assignment records without executing them.',
                nouns=(Noun('work', 'Optional historical work ID.', required=False),), effect='read'),),
)
