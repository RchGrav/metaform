"""`metaform query`: the design's own questions on the command line, through the reads of STORE-025, STORE-028.

Each read's positional arguments are nouns in order; its named options are
`name=value` nouns. There is no general SQL surface.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .data import Node, Store
from .errors import Stop


def _node(text: str) -> Node:
    return Node.parse(text)


def _bool(text: str) -> bool:
    if text not in ('true', 'false'):
        raise Stop(f'{text!r} is not true or false.', 'metaform query')
    return text == 'true'


def _int(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise Stop(f'{text!r} is not a whole number.', 'metaform query') from None


def _list(text: str) -> list[str]:
    return [item for item in text.split(',') if item]


@dataclass(frozen=True)
class Read:
    method: str
    positional: tuple[tuple[str, Callable[[str], Any]], ...]
    optional: dict[str, Callable[[str], Any]]
    summary: str


PAGING = {'limit': _int, 'after': str}
CONTEXT = {'selection': _list, 'raw': _bool}

READS: dict[str, Read] = {
    'roots': Read('roots', (), {**CONTEXT, **PAGING}, "The map's entry: the CQU and the DE with their joins, and every "
                                                    'root element.'),
    'graph': Read('graph', (), {**CONTEXT, **PAGING}, 'A page of the outer map in address order, with parents, '
                                                      'joins and subtype joins.'),
    'messages': Read('messages', (), {'node': _node, 'kind': str, 'open': _bool, **PAGING},
                     'The questions and messages agents left the user, oldest first.'),
    'work': Read('work', (), {'node': _node, 'condition': str, 'open': _bool, **PAGING},
                 'The work records: the condition of an element or a join, apart from the map.'),
    'element': Read('element', (('ref', str),), dict(CONTEXT), 'One element by address or id.'),
    'joins': Read('joins', (('element', str),), {'as': str, **CONTEXT, **PAGING},
                  'The joins an element owns, or with as=provider those it serves.'),
    'identity': Read('identity', (('element', str),), {**CONTEXT, **PAGING}, 'Every join an element provides for.'),
    'subtypes': Read('subtypes', (('join', str),), {**CONTEXT, **PAGING},
                     'The subtype joins in a join, each with the element it holds.'),
    'where': Read('where', (('address', str),), dict(CONTEXT),
                  'The element at an address, with the subtype join and join holding it when those are its only joins.'),
    'children': Read('children', (('address', str),), dict(PAGING), 'The next types toward the leaves.'),
    'layer-items': Read('layer_items', (('layer', str),), {'node': _node, 'in_context': _bool, **PAGING},
                        'A whole layer, or it at one node; in_context=true reads it as the context sees it.'),
    'node': Read('node', (('target', _node),), dict(CONTEXT), "Every layer's items at one node."),
    'context': Read('context', (('address', str),), {'selection': _list, **PAGING},
                    'The properties that apply at an address and those visible there.'),
    'links-to': Read('links_to', (('target', _node),), {'layer': str, **CONTEXT, **PAGING}, 'Items linking to a node.'),
    'citing': Read('citing', (('key', str), ('value', str)), dict(PAGING), 'Everything whose refs hold a key and value.'),
    'history': Read('history', (('thing', str),), dict(PAGING), 'Every version of a thing.'),
    'layers': Read('layers', (), {'tag': str, 'kind': str, 'module': str, **PAGING}, 'The layers.'),
    'provenance': Read('provenance', (('layer', str),), {}, "One layer's provenance."),
    'effective-selection': Read('effective_selection', (('address', str),), {'root': _list},
                                'The layers that reach an address.'),
    'search': Read('search', (('text', str),), {'layer': str, 'selection': _list, **PAGING}, 'Items by their words.'),
    'has-intake': Read('has_intake', (), {}, 'Whether the active metaform has an intake.'),
    'intake-recording': Read('intake_recording', (), {}, 'The intake being recorded, its metaform and its layer.'),
    'layer-graph': Read('layer_graph', (('layer', str),), {}, "One layer's own elements, joins and subtype joins, "
                                                              'building or finished.'),
    'metaforms': Read('metaforms', (), dict(PAGING), "The project's metaforms."),
    'active-metaform': Read('active_metaform', (), {}, "The project's active metaform."),
    'project': Read('project', (), {}, 'The project record with its target.'),
}


def listing() -> str:
    width = max(len(name) for name in READS)
    lines = ['Reads'] + [f'  {name:<{width}}  {read.summary}' for name, read in READS.items()]
    lines += ['', "Use 'metaform query <read> <arguments> [name=value] [--json]'."]
    return '\n'.join(lines) + '\n'


def _read(name: str) -> Read:
    read = READS.get(name)
    if read is None:
        raise Stop(f'No read {name}.', 'metaform query')
    return read


def run(store: Store, name: str, words: list[str]) -> Any:
    read = _read(name)
    positional: list[str] = []
    given: dict[str, str] = {}
    for word in words:
        key, equals, raw = word.partition('=')
        if equals and key in read.optional:
            given[key] = raw
        else:
            positional.append(word)
    if len(positional) != len(read.positional):
        usage = ' '.join(f'<{noun}>' for noun, _ in read.positional)
        raise Stop(f'query {name} takes {usage or "no arguments"}.', f'metaform query {name} {usage}'.rstrip())
    given.update({noun: word for word, (noun, _) in zip(positional, read.positional)})
    return call(store, name, given)


def call(store: Store, name: str, given: Mapping[str, str]) -> Any:
    """One read by name, its arguments given by their names, as `run` and the web GUI's endpoints give them, VIEW-004.
    Names the read does not take are left out."""
    read = _read(name)
    missing = [noun for noun, _ in read.positional if noun not in given]
    if missing:
        usage = ' '.join(f'<{noun}>' for noun, _ in read.positional)
        raise Stop(f'{name} needs {", ".join(missing)}.', f'metaform query {name} {usage}'.rstrip())
    arguments = [convert(given[noun]) for noun, convert in read.positional]
    named = {('as_' if key == 'as' else key): convert(given[key]) for key, convert in read.optional.items()
             if key in given}
    if 'node' in named:
        arguments.append(named.pop('node'))
    return getattr(store, read.method)(*arguments, **named)
