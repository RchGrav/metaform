"""One-time withdrawal of procedural roles removed by the user."""
from __future__ import annotations

from metaform.data import TableTx


def upgrade_tables(tx: TableTx, previous: int) -> None:
    """Drop live registrations and duty references; retain historical definitions and delivery receipts.

    This is a v5 data migration, not a runtime role blacklist. Subsequent user-authored definitions use the
    ordinary registry without a permanent prohibition on these names.
    """
    if previous >= 5:
        return
    removed = {'investigator', 'requirements', 'interviewer', 'specialist', 'implementer', 'verifier',
               'reviewer', 'integrator', 'designer', 'synthesizer', 'dogfood', 'release'}
    for table, keys in (('definitions', ('name',)), ('role_sources', ('name', 'provider'))):
        for row in tx.rows(table, limit=0).results:
            key = {name: row[name] for name in keys}
            if row['name'] in removed:
                tx.delete(table, key)
                continue
            prompts = [name for name in row['prompts']
                       if name not in ('prompt.orchestration:specialist', 'orchestration:specialist')]
            if prompts != row['prompts']:
                tx.update(table, key, {'prompts': prompts})
