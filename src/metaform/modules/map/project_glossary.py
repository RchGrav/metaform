"""The glossary of a project held in the project store (`metaform.project`): its terms are read from that map and
written as records of its `glossary` overlay, at the element each term belongs to.

Kickoff 2026-11-17, Phase 3, decision t-legacy-keep: every feature of the old store is kept and moved onto the project
store. An element's name is a term, defined by the EF and OP its wants give it: a want's how is the EF of the element
wanted, how it serves what relies on it, and its why the OP of the element holding the want, the purpose it bears as
receiver. These are read from the map each time, never copied. A term added, an element's term edited and one removed
are each one record of the overlay `<project>.overlay.glossary`, defined on the first such write, at the node it was
found at, or for an element's term at that element. Each change names the record it found, id and revision (F02), so
it never lands on another term.

What has no faithful place there is refused by name. A term for the whole project, at no node: the project's root
holds only the specification's blocks (F07). A term's number at its node, `<address>#<n>`: the project store numbers
no item, so a term is named by its record id at its node. Terms the old store kept for a project before its map moved
are listed apart, labelled, and never mixed in or moved.
"""
from __future__ import annotations

from typing import Any, cast

from metaform import project as project_store
from metaform.module import Context, Stop

from . import glossary
from .glossary import _by, _clean, _need, _now, _prompt  # pyright: ignore[reportPrivateUsage]  # within the map module

OVERLAY = 'glossary'
HELP = 'metaform help map term'
DEFINITION: dict[str, object] = {
    'description': ("The project's own terms found at this element: each record is a term the person or an agent "
                    "added here, or an edit or removal of this element's name as a term."),
    'instruction': ("Add one record for each term, at the element it was found at. An element's name is its term "
                    "already: a record of it with state edited gives the project's own definition beside its wants, "
                    'and one with state removed hides it, with the why.'),
    'term': {'type': 'text', 'rule': 'The term, in the words the project uses for it.', 'example': 'kitchen timer'},
    'state': {'type': 'added | edited | removed',
              'rule': "added for a term of its own; edited for an element's name given the project's definition; "
                      "removed for an element's name hidden from the glossary.", 'example': 'added'},
    'definition': {'type': 'text', 'rule': 'What the term means in this project, in a sentence.',
                   'example': 'The countdown a cook sets for one dish.', 'optional': True},
    'why': {'type': 'text', 'rule': 'One line saying why the term is needed, or why it changes or goes.',
            'example': 'Cooks say timer, never countdown.'},
    'source': {'type': 'text', 'rule': 'Where it comes from: a file and line, or who uses it.',
               'example': 'src/timer.py:12', 'optional': True},
    'by': {'type': 'text', 'rule': 'Who wrote it: the person or an agent.', 'example': 'person', 'optional': True},
    'session': {'type': 'text', 'rule': "The agent's session that wrote it, when an agent did.",
                'example': 'claude-1a2b', 'optional': True},
    'at': {'type': 'text', 'rule': 'When it was written, as a date and time.', 'example': '2026-11-17T09:30:00Z'},
}


def _local(project: str, path: str) -> str:
    """An element's address without the project's name, as the glossary and the map verbs write it."""
    return path[len(project) + 1:] if path.startswith(project + '.') else ''


def _drawn(project: str) -> dict[str, Any]:
    drawn = project_store.drawn(project)
    if drawn is None:
        raise Stop(f"{project}'s map could not be read from the project store.", f'the project tool: {{"map": "{project}"}}')
    return drawn


def _records(project: str) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], project_store.overlay_records(project, OVERLAY) or [])


def _row(project: str, record: dict[str, Any]) -> dict[str, Any]:
    """A glossary record as the glossary merges a row of the old store's terms."""
    return {'key': glossary.key_of(str(record.get('term') or '')), 'term': record.get('term'),
            'state': record.get('state'), 'definition': record.get('definition'), 'why': record.get('why'),
            'source': record.get('source'), 'by': record.get('by'), 'number': None, 'record': record['record'],
            'address': _local(project, str(record['element'])) or None}


def derived(project: str, drawn: dict[str, Any]) -> dict[str, glossary.Term]:
    """The terms the elements' names give, each defined by the EF and OP its wants give it."""
    efs: dict[str, list[str]] = {}
    ops: dict[str, list[str]] = {}
    for want in cast(list[dict[str, Any]], drawn['wants']):
        ops.setdefault(_local(project, str(want['holder'])), []).append(str(want.get('why') or ''))
        efs.setdefault(_local(project, str(want['element'])), []).append(str(want.get('how') or ''))
    return glossary.named(((_local(project, str(one['address'])), cast(str | None, one.get('name')))
                           for one in cast(list[dict[str, Any]], drawn['elements'])
                           if _local(project, str(one['address']))), efs, ops)


def terms(project: str, drawn: dict[str, Any] | None = None) -> list[glossary.Term]:
    """Every term of the project's glossary, most used first, as `glossary.terms` gives an old store's."""
    drawn = drawn if drawn is not None else _drawn(project)
    said = ' '.join(f"{want.get('why') or ''} {want.get('how') or ''}" for want in cast(list[dict[str, Any]],
                                                                                         drawn['wants']))
    return glossary.merged(derived(project, drawn), [_row(project, one) for one in _records(project)], said)


def left_behind(store: Any) -> dict[str, Any]:
    """The terms the old store kept for this project before its map moved to the project store, listed apart and
    labelled; nothing when it kept none."""
    try:
        with store.tables(write=False) as tx:
            rows = [dict(row) for row in tx.rows('terms', limit=0).results]
    except Exception:  # noqa: BLE001  an old store without the table kept no terms
        return {}
    if not rows:
        return {}
    return {'old_store': {'note': ("Terms the old store kept before this project's map moved to the project store. "
                                   'They are not in the glossary; add each one again with metaform map term.'),
                          'results': [{name: row[name] for name in ('term', 'state', 'definition', 'why', 'source',
                                                                     'address') if row.get(name)} for row in rows]}}


def _done(answer: dict[str, object]) -> None:
    if answer.get('status') == 'error':
        raise Stop(str(answer.get('message') or 'The term was not changed.'), str(answer.get('remediation') or HELP))


def _defined(project: str, drawn: dict[str, Any]) -> None:
    """The glossary overlay is defined beneath the project's overlay root on its first write."""
    if not any(one.get('key') == OVERLAY for one in cast(list[dict[str, Any]], drawn['overlays'])):
        _done(project_store.run({'add': {f'{project}.overlay.{OVERLAY}': DEFINITION}}))


def term(ctx: Context, project: str, op: str, words: str, node: str | None) -> Any:
    """`map term` on a project held in the project store: add, edit or remove one record of its glossary overlay,
    with the same checks as the old store's terms."""
    key = glossary.key_of(words)
    drawn = _drawn(project)
    addresses = {_local(project, str(one['address'])) for one in cast(list[dict[str, Any]], drawn['elements'])}
    if node is not None and node not in addresses:
        raise Stop(f"{node} is not an element of {project}'s map.", f'the project tool: {{"map": "{project}"}}')
    current = {glossary.key_of(one.term): one for one in terms(project, drawn)}
    stored = next((one for one in reversed(_records(project))
                   if glossary.key_of(str(one.get('term') or '')) == key), None)
    element = derived(project, drawn).get(key)
    if op == 'add':
        _need(ctx, op, 'definition', 'why', *(() if ctx.surface == 'web' else ('source',)))
        if key in current:
            raise Stop(f'{words} is a term here already.', f'metaform map term op=edit term="{words}" definition=...')
        state = glossary.EDITED if element is not None else glossary.ADDED
    elif op == 'edit':
        if key not in current and not (stored and stored.get('state') == glossary.REMOVED):
            raise Stop(f'{words} is not a term here.', f'metaform map term op=add term="{words}" definition=... '
                                                       'why=... source=...')
        _need(ctx, op, 'why')
        state = glossary.EDITED if element is not None else glossary.ADDED
    else:
        if key not in current:
            raise Stop(f'{words} is not a term here.', 'metaform map glossary format=list')
        _need(ctx, op, 'why')
        state = glossary.REMOVED
    at = node or (_local(project, str(stored['element'])) if stored else None) or (
        element.addresses[0] if element is not None else None)
    if at is None:
        raise Stop(f"A term for the whole project has no place in the project store, where {project}'s map is kept: "
                   "its root holds only the specification's blocks. Add the term at the element it was found at.",
                   f'metaform map term op={op} term="{words}" node=<address> ...')
    fields: dict[str, object] = {'term': words if op == 'add' or not stored else stored['term'], 'state': state,
                                 'by': _by(ctx), 'at': _now()}
    if ctx.surface != 'web' and ctx.session:
        fields['session'] = ctx.session
    for name in ('definition', 'why', 'source'):
        if _clean(ctx.nouns.get(name)):
            fields[name] = str(ctx.nouns[name]).strip()
    path = f'{project}.{at}'
    if stored is not None and state == glossary.REMOVED and element is None:  # an added term goes
        _done(project_store.run({'delete': {str(stored['element']): {OVERLAY: [stored['record']]}}}))
    elif stored is not None and str(stored['element']) == path:  # changed where it is, naming the record it read
        _done(project_store.run({'update': {path: {OVERLAY: [
            {'position': stored['position'], 'record': stored['record'], 'revision': stored['revision'],
             **fields}]}}}))
    else:
        _defined(project, drawn)
        kept = {name: value for name, value in (stored or {}).items()
                if name in DEFINITION and name not in fields and value is not None}
        _done(project_store.run({'add': {path: {OVERLAY: [{**kept, **fields}]}}}))
        if stored is not None:  # moved to another node: the record it was is removed once the new one is written
            _done(project_store.run({'delete': {str(stored['element']): {OVERLAY: [stored['record']]}}}))
    if state == glossary.REMOVED:
        if ctx.surface == 'mcp':  # to an agent, one line: the write is done, MCP-037
            return _prompt('term_remove', term=words)
        return {'term': words, 'removed': True, 'why': fields.get('why')}
    row = next(one.row() for one in terms(project) if glossary.key_of(one.term) == key)
    if ctx.surface == 'mcp':  # the term is a read away, map_glossary term=, so it is not handed back whole
        return _prompt(f'term_{op}', term=str(row['term']), at=f" at {row['node']}" if row.get('node') else '')
    return row
