"""Durable instruction delivery history and context evidence for agent sessions."""
from __future__ import annotations

import hashlib
import time
from typing import Any, cast

from metaform import home
from metaform.data import Column, Index, Store, Table, Tables, prompts
from metaform.module import Context, Module, Noun, Provides, Stop, Subscription, Verb

from . import context as ledger

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = False

LAYER = 'agents'
VARIABLE = 'Which prompt versions each agent session in this project was sent.'

# Version 6 removes the operational role factory tables. Immutable definition history and delivery evidence stay.
# Earlier code needs the removed tables, so it cannot safely operate on this schema.
TABLES = Tables(version=6, compatible_from=6, tables=(
    Table('sent', place='project', key=('session_id', 'seq'),
          columns=(Column('session_id', required=True), Column('seq', 'int', required=True),
                   Column('work_id', required=True), Column('runner'), Column('role', required=True),
                   Column('agent'), Column('at', required=True), Column('prompts', 'json', required=True)),
          indexes=(Index(('runner',)),)),
    *ledger.TABLES,
))


def _native_sources(ctx: Context) -> dict[str, Any]:
    """Discover current local candidates without claiming the adapter loaded any of them."""
    sources: list[dict[str, Any]] = []
    for filename in ('AGENTS.md', 'CLAUDE.md', 'GEMINI.md'):
        path = ctx.folder / filename
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except FileNotFoundError:
            continue
        except OSError as error:
            sources.append({'path': str(path), 'digest': None, 'status': 'unread', 'problem': str(error)})
        else:
            sources.append({'path': str(path), 'digest': digest, 'status': 'discovered_not_confirmed_loaded'})
    return {'sources': sources, 'loaded_sources': 'unknown', 'internal_instructions': 'unknown',
            'observation': 'current_files_at_inspection'}


def _manifest(one: dict[str, Any]) -> dict[str, Any]:
    source = cast(dict[str, Any], one.get('source') or {})
    return {'name': one['name'], 'actual_version_id': one.get('version_id') or one.get('actual_version_id'),
            'selected_version_id': one.get('selected_version_id'), 'number': one.get('number'),
            'origin': one.get('origin'), 'rendered_digest': one.get('rendered_fingerprint'),
            'source': one.get('source') or {'kind': 'unknown', 'path': None, 'shipped_identity': None},
            'delivery_path': one.get('delivery_path') or 'unknown', 'problems': one.get('problems') or [],
            'snapshot': one.get('snapshot', source.get('snapshot', 'unknown'))}


def sent(ctx: Context) -> dict[str, Any]:
    """Accepted prompt delivery history by session or runner id."""
    given = str(ctx.nouns['session'])
    with ctx.require_store().tables(write=False) as tx:
        rows = tx.rows('sent', {'session_id': given}, by=('session_id', 'seq'), limit=0).results or \
            tx.rows('sent', {'runner': given}, limit=0).results
    if not rows:
        raise Stop(f'No prompts are recorded for session {given}: it started before the agents module was on, it was '
                   'not started by dispatch, or no turn of it has gone yet.', 'metaform dispatch sessions')
    ordered = sorted((dict(row) for row in rows), key=lambda row: int(row['seq']))
    first = ordered[0]
    versions: dict[str, list[int | None]] = {}
    effective: dict[str, dict[str, Any]] = {}
    for row in ordered:
        for one in cast(list[dict[str, Any]], row['prompts']):
            effective[str(one['name'])] = _manifest(one)
            numbers = versions.setdefault(str(one['name']), [])
            if one.get('number') not in numbers:
                numbers.append(one.get('number'))
    return {'session_id': first['session_id'], 'role': first['role'], 'agent': first['agent'],
            'work_id': first['work_id'], 'runners': sorted({str(row['runner']) for row in ordered if row['runner']}),
            'prompts': [{'name': name, 'versions': numbers} for name, numbers in versions.items()],
            'effective_instructions': list(effective.values()),
            'observation_scope': 'Metaform delivery history; current semantic retention is unknown',
            'native_instructions': _native_sources(ctx),
            'turns': [{'at': row['at'], 'runner': row['runner'], 'prompts': row['prompts']} for row in ordered],
            'next': 'metaform prompt <name> <version> reads the exact text of a version'}


def updates(ctx: Context) -> dict[str, Any]:
    """Inspect version-preserving prompt merges and custom selections deliberately left untouched."""
    name = ctx.nouns.get('name')
    return {'updates': prompts.prompt_merges(str(name) if name else None)}


_layered: set[tuple[str, str]] = set()  # the homes' projects this process has seen the layer in, read once each


def _layer(store: Store) -> None:
    """The agents layer, LAYER-001: made on the first record while the project has a metaform, so what each session
    was sent is linked from a layer, as memory's tables are from the memory layer."""
    seen = (str(home.home()), store.project_id)
    if seen in _layered or store.active_base() is None:
        return
    store.layer(LAYER, 'agents', VARIABLE, mutable=True, hideable=True, ready=True)  # made once, then returned
    _layered.add(seen)


def record(payload: dict[str, Any], ctx: Context) -> None:
    """A turn of a dispatch session went with these prompt versions, `prompt.sent`: one row, nothing else read."""
    session_id, given = payload.get('session_id'), payload.get('prompts')
    if not session_id or not isinstance(given, list) or not given:
        return
    store = ctx.require_store()
    row: dict[str, Any] = {'session_id': str(session_id), 'seq': time.time_ns(),
                           'work_id': str(payload.get('work_id') or ''), 'runner': payload.get('runner'),
                           'role': str(payload.get('role') or ''), 'agent': payload.get('agent'),
                           'at': str(payload.get('at') or ''), 'prompts': cast(list[Any], given)}
    with store.tables() as tx:
        tx.insert('sent', row)
    _layer(store)


SESSION = Noun('session', "The session id, or its runner's id (METAFORM_SESSION).")

MODULE = Module(
    id='agents',
    summary='Instruction delivery history and context evidence for agent sessions.',
    purpose='Record accepted instruction deliveries, context epochs, receipts and compaction evidence.',
    details='Delivery records establish what was sent. They do not establish which facts an agent retains.',
    verbs=(
        Verb('receipts', ledger.inspect_receipts, 'Read context delivery fingerprints and versions, without bodies.',
             nouns=(SESSION,), effect='read'),
        Verb('confirm', ledger.confirm_context, 'Report a startup context marker using your retained key; '
             'omit the key if unavailable. The observation does not establish which facts remain in context.',
             nouns=(Noun('checkpoint', 'The checkpoint in the startup request.'),
                    Noun('key', 'The key retained from the context instructions; omit if lost.', required=False)),
             effect='write'),
        Verb('updates', updates, 'Read selected prompt merge evidence, exact parent versions and retained conflicts.',
             nouns=(Noun('name', 'An existing prompt component identity; omit to read every applied update.',
                         required=False),), effect='read'),
        Verb('sent', sent, 'Read which prompt versions each session turn carried.', nouns=(SESSION,), effect='read'),
    ),
    subscriptions=(Subscription('prompt.sent', record), Subscription('session.compacted', ledger.compacted)),
    provides=(Provides('agent.context', ledger.SERVICE),),
    tables=TABLES,
)
