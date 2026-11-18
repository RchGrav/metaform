"""The project's glossary: its own terms, generated from its map and kept beside Metaform's own glossary, Phase 1c.

Two kinds of term make it. Every element of the map in context that has a name, its canonical name or the informal
name the intake recorded, is a term, defined by the element's EF, how it serves what relies on it, and its OP, the
purpose it bears as receiver. These are read from the map each time the glossary is read, never copied, so a name
refined, an element removed or a base changed is in step at once. Beside them are the terms the person or an agent
adds, at any node or for the whole project, each with a definition, a why and its source, file and line or who said
it; they are kept in the map module's `terms` table in the project's own database, so a new intake keeps them. A term
added at a node takes the next number there, `<address>#<n>`, and is read like any item. Editing an element's term
keeps an override beside it; removing one hides it, with the why, until it is added or edited again.

The glossary is rendered in the form of Metaform's own glossary block: the register standard first, sent exactly as
the person wrote it, then `@STATE_INIT`, one `{Term} := "definition"` line per term, and `@CONSTRAINT`. The form is
the map module's canonical prompt `glossary` in resources/prompts.xml, which ships with Metaform and is not edited at
runtime. Its size is held to the setting glossary_bytes: the most-used terms go in, the rest are counted with the call
that lists them all.

A project held in the project store reads its terms from that map and keeps them as records of its glossary overlay,
at the element each term belongs to: `project_glossary.py`.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from importlib import resources
from typing import Any

from metaform import project as project_store
from metaform import prompt_files, settings
from metaform.data import GraphPage, Store, reference
from metaform.module import Context, Noun, Pane, Stop, Verb

settings.number('glossary_bytes', 5120, min=1024, label='Project glossary size',
                help="The most bytes the project's glossary is given in, register standard included: the most-used "
                     'terms go in, and the rest are counted with the call that lists them.')
settings.choice('glossary_register', ['peer', 'none'], 'peer', label='Glossary register',
                help="The register the project's glossary sets: peer sends the peer register standard ahead of the "
                     'terms, as written; none sends the terms alone.')

ADDED, EDITED, REMOVED = 'added', 'edited', 'removed'
DEFINITION = 320  # the characters of a definition an element's term is given in the block; the list gives it whole
LIST = 50  # the terms a list read gives at a time


def _prompt(name: str, **fills: str) -> str:
    return prompt_files.text(resources.files(__package__ or 'metaform.modules.map'), name, **fills) or ''


def key_of(term: str) -> str:
    """How a term is told apart from another: its words in lower case, single-spaced."""
    return ' '.join(term.lower().split())


@dataclass
class Term:
    """One term as the glossary gives it: its words, its definition, where it comes from, the Addresses of the elements
    it names, and how much it is used."""
    term: str
    definition: str
    kind: str  # element, added or edited
    addresses: list[str] = field(default_factory=list[str])
    why: str | None = None
    source: str | None = None
    address: str | None = None  # the node it was added at
    number: int | None = None
    by: str | None = None
    uses: int = 0
    record: str | None = None  # in the project store: the id of the glossary record that holds it, F02


    def row(self) -> dict[str, Any]:
        shown: dict[str, Any] = {'term': self.term, 'definition': self.definition, 'kind': self.kind}
        for name in ('addresses', 'why', 'source', 'by', 'uses'):
            value = getattr(self, name)
            if value:
                shown[name] = value
        if self.address and self.number:
            shown['item'] = reference(self.address, self.number)
        if self.address and self.record:  # the project store numbers no item: the term is its record at its node
            shown['node'], shown['record'] = self.address, self.record
        return shown


def _clean(text: Any) -> str:
    return ' '.join(str(text or '').split())


def _definition(address: str, efs: Iterable[str], ops: Iterable[str]) -> str:
    """An element's definition from its EF and OP, in the glossary's words."""
    ef = '; '.join(dict.fromkeys(_clean(one).rstrip('.') for one in efs if _clean(one)))
    op = '; '.join(dict.fromkeys(_clean(one).rstrip('.') for one in ops if _clean(one)))
    said = ' '.join(part for part in (_prompt('glossary_ef', ef=ef) if ef else '',
                                      _prompt('glossary_op', op=op) if op else '') if part)
    return _prompt('glossary_element', address=address, said=said) if said else address


def derived(store: Store, graph: GraphPage | None = None) -> dict[str, Term]:
    """The terms the map in context names: each named element's name, defined by its EF and OP; two elements of one
    name share the term, each Address with its own definition. Used by how many joins name the element."""
    graph = graph if graph is not None else store.graph(limit=0)
    efs: dict[str, list[str]] = {}
    ops: dict[str, list[str]] = {}
    for join in graph.joins:
        if join.receiver_address:
            ops.setdefault(join.receiver_address, []).append(join.purpose or '')
        for held in join.elements:
            if held.address:
                efs.setdefault(held.address, []).append(join.ef or '')
    return named(((one.element.address, one.element.name) for one in graph.elements), efs, ops)


def named(elements: Iterable[tuple[str, str | None]], efs: dict[str, list[str]],
          ops: dict[str, list[str]]) -> dict[str, Term]:
    """The terms of named elements, each `(address, name)`: defined by the EF of what it provides and the OP of what it
    receives, and used once for each of them. Read from the old store's joins and from the project store's wants."""
    found: dict[str, Term] = {}
    for address, name in elements:
        name = _clean(name)
        if not name:
            continue
        said = _definition(address, efs.get(address, ()), ops.get(address, ()))
        uses = len(efs.get(address, ())) + len(ops.get(address, ()))
        held = found.get(key_of(name))
        if held is None:
            found[key_of(name)] = Term(name, said, 'element', [address], uses=uses)
        else:
            held.definition = f'{held.definition} | {said}'
            held.addresses.append(address)
            held.uses += uses
    return found


def _rows(store: Store) -> list[dict[str, Any]]:
    with store.tables(write=False) as tx:
        return [dict(row) for row in tx.rows('terms', limit=0).results]


def terms(store: Store) -> list[Term]:
    """Every term in the glossary, most used first: the map's own with the person's and agents' edits over them, and
    the terms added; a removed one is left out. Use is counted from the map: the joins naming the element, and every
    time the term's words appear in a purpose, an EF or another term's definition."""
    graph = store.graph(limit=0)
    return merged(derived(store, graph), _rows(store),
                  ' '.join(_clean(one) for join in graph.joins for one in (join.purpose, join.ef)))


def merged(found: dict[str, Term], rows: Iterable[dict[str, Any]], said: str) -> list[Term]:
    """The glossary from the elements' terms, `found`, and the rows added, edited or removed over them, most used
    first; `said` is the map's own words, where each term's use is counted."""
    for row in rows:
        key = str(row['key'])
        held = found.get(key)
        if row['state'] == REMOVED:
            found.pop(key, None)
            continue
        why, source, by = row['why'], row['source'], row['by']
        address, number, record = row['address'] or None, row['number'], row.get('record')
        if held is not None and row['state'] == EDITED:
            found[key] = replace(held, definition=_clean(row['definition']) or held.definition, kind=EDITED, why=why,
                                 source=source, address=address, number=number, by=by, record=record)
        else:
            found[key] = Term(str(row['term']), _clean(row['definition']), ADDED, [address] if address else [],
                              why=why, source=source, address=address, number=number, by=by, record=record)
    text = said.lower()
    texts = {key: one.definition.lower() for key, one in found.items()}
    for key, one in found.items():
        words = re.compile(r'(?<![\w])' + re.escape(key) + r'(?![\w])')
        one.uses += len(words.findall(text)) + sum(len(words.findall(said)) for other, said in texts.items()
                                                    if other != key)
    return sorted(found.values(), key=lambda one: (-one.uses, key_of(one.term)))


def _line(one: Term) -> str:
    said = one.definition if len(one.definition) <= DEFINITION else one.definition[:DEFINITION - 1].rstrip() + '…'
    return _prompt('glossary_term', term=one.term.replace('}', ')'), definition=said.replace('"', "'"))


def render(ctx: Context, project: str, listed: list[Term]) -> str:
    """The project's glossary as the canonical prompt `glossary` gives its form, within glossary_bytes."""
    peer = ctx.setting('glossary_register') == 'peer'
    budget = int(ctx.setting('glossary_bytes'))
    fills = {'register': _prompt('register_standard') + '\n\n' if peer else '', 'project': project,
             'mode': _prompt('glossary_mode_peer' if peer else 'glossary_mode_none'),
             'standard': '\n  ' + _prompt('glossary_standard') if peer else '',
             'add': ctx.calls('metaform map term op=add')}
    lines: list[str] = []

    def drawn(more: int) -> str:
        said = ctx.calls(_prompt('glossary_more', count=str(more), read=f'metaform map glossary format=list '
                                                                         f'after={len(lines)}')) if more else ''
        shown = lines or ([] if more else [_prompt('glossary_empty')])
        return _prompt('glossary', terms=''.join('\n  ' + line for line in shown),
                       more='\n  ' + said if said else '', **fills)
    for index, one in enumerate(listed):
        lines.append(_line(one))
        if len(drawn(len(listed) - index - 1).encode('utf-8')) > budget:
            lines.pop()
            break
    return drawn(len(listed) - len(lines))


def _by(ctx: Context) -> str:
    return ctx.client or ('person' if ctx.surface == 'web' or ctx.session is None else ctx.session)


def _need(ctx: Context, op: str, *names: str) -> None:
    missing = [name for name in names if not _clean(ctx.nouns.get(name))]
    if missing:
        steps = {'definition': 'add definition: what the term means here, in a sentence',
                 'why': 'add why: one line saying why the term is needed',
                 'source': 'add source: the file and line it comes from, or who uses it'}
        raise Stop(f'term op={op} has no {" and no ".join(missing)}.', '; '.join(steps.get(name, f'add {name}')
                                                                              for name in missing))


def glossary(ctx: Context) -> Any:
    """The project's glossary: the block an agent reads at `metaform://<project>`, or with format=list each term with
    its definition, why, source and uses, a page at a time; with term=, that one term."""
    store = ctx.require_store()
    name = project_store.stored_name(store.project_id)
    held = project_store.holds(name)  # its terms are the project store's, kickoff 2026-11-17 Phase 3
    from . import project_glossary  # it builds on this module's names
    listed = project_glossary.terms(name) if held else terms(store)
    given = _clean(ctx.nouns.get('term'))
    if given:
        found = next((one for one in listed if key_of(one.term) == key_of(given)), None)
        if found is None:
            raise Stop(f'{given} is not a term here.', f'metaform map term op=add term="{given}" definition=... '
                                                       'why=... source=...')
        return found.row()
    if str(ctx.nouns.get('format') or 'block') != 'list':
        return render(ctx, str(store.project_id), listed)
    start = int(ctx.nouns.get('after') or 0)
    limit = int(ctx.nouns.get('limit') or LIST)
    page = listed[start:start + limit] if limit else listed[start:]
    result: dict[str, Any] = {'project': store.project_id, 'total': len(listed), 'results': [one.row() for one in page]}
    if limit and start + limit < len(listed):
        result['next'] = str(start + limit)
    return result


def term(ctx: Context) -> Any:
    """Add, edit or remove a term of the project's glossary, at a node or for the whole project. An added term carries
    its definition, why and source; at a node it takes the next number there. Editing an element's term keeps an
    override of its definition; removing it hides it, with the why, until it is added or edited again."""
    store = ctx.require_store()
    op = str(ctx.nouns.get('op') or 'add')
    if op not in ('add', 'edit', 'remove'):
        raise Stop(f'{op!r} is not a term operation: op=add, edit or remove.', 'metaform help map term')
    _need(ctx, op, 'term')
    words = _clean(ctx.nouns['term'])
    key = key_of(words)
    node = _clean(ctx.nouns.get('node')) or None
    name = project_store.stored_name(store.project_id)
    if project_store.holds(name):  # its terms are records of the glossary overlay there
        from . import project_glossary  # it builds on this module's names
        return project_glossary.term(ctx, name, op, words, node)
    if node is not None and store.element(node) is None:
        from . import _missing  # pyright: ignore[reportPrivateUsage]  # shared within the map module
        raise _missing(store, node)
    current = {key_of(one.term): one for one in terms(store)}
    with store.tables(write=False) as tx:
        row = tx.get('terms', {'key': key})
    stored = dict(row) if row is not None else None
    element = derived(store).get(key)
    if op == 'add':
        _need(ctx, op, 'definition', 'why', *(() if ctx.surface == 'web' else ('source',)))
        if key in current:
            raise Stop(f'{words} is a term here already.', f'metaform map term op=edit term="{words}" definition=...')
        state = EDITED if element is not None else ADDED
    elif op == 'edit':
        if key not in current and not (stored and stored['state'] == REMOVED):
            raise Stop(f'{words} is not a term here.', f'metaform map term op=add term="{words}" definition=... '
                                                       'why=... source=...')
        _need(ctx, op, 'why')
        state = EDITED if element is not None else ADDED
    else:
        if key not in current:
            raise Stop(f'{words} is not a term here.', 'metaform map glossary format=list')
        _need(ctx, op, 'why')
        state = REMOVED
    fields: dict[str, Any] = {'term': words if op == 'add' or not stored else stored['term'], 'state': state,
                              'by': _by(ctx), 'session': None if ctx.surface == 'web' else ctx.session,
                              'at': _now()}
    for name in ('definition', 'why', 'source'):
        if _clean(ctx.nouns.get(name)):
            fields[name] = str(ctx.nouns[name]).strip()
    if node is not None:
        fields['address'] = node
    with store.tables() as tx:
        if state == REMOVED and element is None:  # an added term goes; its number is not reused
            tx.delete('terms', {'key': key})
        else:
            held = tx.get('terms', {'key': key})
            at = fields.get('address', held['address'] if held is not None else None)
            moved = held is None or at != held['address'] or not held['number']
            if at and moved:
                fields['number'] = tx.number(str(at))
            elif not at:
                fields['number'] = None
            if held is None:
                tx.insert('terms', {'key': key, **fields})
            else:
                tx.update('terms', {'key': key}, fields)
    if state == REMOVED:
        if ctx.surface == 'mcp':  # to an agent, one line: the write is done, MCP-037
            return _prompt('term_remove', term=words)
        return {'term': words, 'removed': True, 'why': fields.get('why')}
    row = next(one.row() for one in terms(store) if key_of(one.term) == key)
    if ctx.surface == 'mcp':  # the term is a read away, map_glossary term=, so it is not handed back whole
        return _prompt(f'term_{op}', term=str(row['term']), at=f" at {row['item']}" if row.get('item') else '')
    return row


def _now() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')



def item_read(store: Store, address: str, number: int) -> dict[str, Any] | None:
    """The term numbered `number` at `address`, MCP-037: its words as the title, its why, its definition and source."""
    with store.tables(write=False) as tx:
        found = tx.rows('terms', {'address': address, 'number': number}, limit=0).results
    if not found:
        return None
    row = found[0]
    body = '\n'.join(part for part in (_clean(row['definition']), f"source: {row['source']}" if row['source'] else '',
                                       f"by: {row['by']}" if row['by'] else '') if part)
    return {'kind': 'term', 'title': row['term'], 'why': row['why'], 'body': body, 'links': [],
            **({'removed': True} if row['state'] == REMOVED else {})}


def items_at(store: Store, address: str, before: int | None, limit: int) -> list[dict[str, Any]]:
    """The terms numbered at `address` below `before`, newest first, at most `limit`, as items are listed."""
    with store.tables(write=False) as tx:
        rows = [row for row in tx.rows('terms', {'address': address}, limit=0).results
                if row['number'] and (before is None or row['number'] < before)]
    rows.sort(key=lambda row: -int(row['number']))
    return [{'number': int(row['number']), 'kind': 'term', 'title': row['term'], 'why': row['why']}
            for row in rows[:limit]]


def at_node(store: Store, address: str) -> list[str]:
    """The terms added or edited at an Address, for the node's brief to name."""
    try:
        with store.tables(write=False) as tx:
            rows = tx.rows('terms', {'address': address}, limit=0).results
    except Exception:  # noqa: BLE001  a store without the table yet names no terms
        return []
    return [str(row['term']) for row in rows if row['state'] != REMOVED]


TERM_NOUNS = (
    Noun('op', 'add, the default; edit, which changes a term\'s definition, why, source or node, an element\'s term '
               'kept as an override of its EF and OP; or remove, which takes an added term out and hides an '
               'element\'s, both with a why.', required=False,
         schema={'type': 'string', 'enum': ['add', 'edit', 'remove']}),
    Noun('term', 'Required: the term, in the words the project uses for it.', required=False),
    Noun('definition', 'add, required, and edit: what the term means in this project, in a sentence.', required=False),
    Noun('why', 'Required: one line saying why the term is needed, or why it changes or goes.', required=False),
    Noun('source', 'add, required, and edit: where it comes from, a file and line, or who uses it.', required=False),
    Noun('node', 'add and edit: the Address where it was found; it takes the next number there, <address>#<n>.',
         required=False),
)
GLOSSARY_NOUNS = (
    Noun('format', 'block, the default, the glossary as an agent reads it; list, each term with its definition, '
                   'why, source and uses.', required=False, schema={'type': 'string', 'enum': ['block', 'list']}),
    Noun('term', 'One term to read, with where it comes from.', required=False),
    Noun('limit', 'list: how many terms, 0 for all.', kind='int', required=False),
    Noun('after', 'list: the cursor the previous page returned as next.', required=False),
)
VERBS = (
    Verb('glossary', glossary, "Read the project's glossary: its terms, from the map's element names and those added, "
                               'each defined in the project\'s words.',
         nouns=GLOSSARY_NOUNS, switches=('glossary_bytes', 'glossary_register'), effect='read', reads_layers=True,
         details="An element's name is a term defined by its EF and OP, read from the map each time, so a refined name "
                 'or a removed element is in step at once. Terms the person and agents add carry a definition, a why '
                 'and a source. The block is sized by the setting glossary_bytes, most-used terms first, and led by '
                 'the peer register standard while the setting glossary_register is peer.',
         examples=(('metaform map glossary', 'The glossary as an agent reads it.'),
                   ('metaform map glossary format=list', 'Every term with its definition, why, source and uses.'))),
    Verb('term', term, "Add, edit or remove a term of the project's glossary, with its definition, why and source.",
         nouns=TERM_NOUNS,
         details='A term found at a node is added there, node=<address>, and takes the next number at it. An '
                 "element's own name is its term already: edit gives it a definition of the project's own beside its "
                 'EF and OP, remove hides it. Nothing coins a replacement for a term the project uses.',
         examples=((('metaform map term term="kitchen timer" definition="The countdown a cook sets for one dish." '
                     'why="Cooks say timer, never countdown." source="src/timer.py:12" node=code.timer.kitchen'),
                    'Add a term found at the kitchen timer.'),)),
)
PANES = (
    Pane('glossary', 'Glossary', "Read the project's own terms, each with its definition, why and source.",
         icon='file', verb='glossary', arguments={'format': 'list'}, area='right', group='chat', order=120,
         min_width=320),
)
