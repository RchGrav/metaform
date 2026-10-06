"""Persisted call transport for the agent that interprets Axiom.

Frames carry authored logic unchanged. The agent interprets Choice, Map,
Retry and Catch; this module transports their calls and results.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

from metaform import nonce
from metaform.module import Stop

from .binding import Call, Logic, Lookup, prepare, receive, returned
from .element import ElementValue, Value


def pack(value: Any) -> Any:
    """Keep element views and tuples intact across the nonce's JSON boundary."""
    if isinstance(value, Value):
        return {'kind': 'element' if isinstance(value, ElementValue) else 'value',
                'value': {key: pack(value[key]) for key in value}}
    if isinstance(value, Mapping):
        return {'kind': 'dict', 'value': {key: pack(one) for key, one in cast(Mapping[str, Any], value).items()}}
    if isinstance(value, (list, tuple)):
        return {'kind': 'tuple' if isinstance(value, tuple) else 'list',
                'value': [pack(one) for one in cast(Sequence[Any], value)]}
    return value


def unpack(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    held = cast(dict[str, Any], value)
    kind, data = held['kind'], held['value']
    if kind in ('dict', 'element', 'value'):
        fields = {key: unpack(one) for key, one in cast(dict[str, Any], data).items()}
        return ElementValue(fields) if kind == 'element' else Value(fields) if kind == 'value' else fields
    values = [unpack(one) for one in cast(list[Any], data)]
    return tuple(values) if kind == 'tuple' else values


def _call(data: dict[str, Any]) -> Call:
    logic = data['logic']
    return Call(data['address'], Logic(**logic), unpack(data['arguments']), unpack(data['this']),
                tuple(data['targets']), data['unpack'])


def _frame(call: Call, context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {'call': {'address': call.address, 'logic': call.logic.to_dict(),
                     'arguments': pack(call.arguments), 'this': pack(call.this),
                     'targets': list(call.targets), 'unpack': call.unpack},
            'variables': pack(call.arguments), 'context': context}


def held(word: str) -> nonce.Nonce:
    found = nonce.read(word)
    if found is None or not found.open or found.module != 'workflow':
        raise Stop('Invalid or Unknown Nonce', 'metaform help workflow')
    return found


def start(text: str, variables: Mapping[str, Any], this: Any, lookup: Lookup,
          context: dict[str, Any], resolve: Callable[[str], Any] | None = None) -> str:
    call = prepare(text, variables, this, lookup, resolve)
    return nonce.request('workflow', 'resume', {'context': context, 'frames': [_frame(call, context)],
                                               'caller': pack(dict(variables)), 'parent': None})


def view(word: str) -> dict[str, Any]:
    """Expose the callee alone, including when its nonce holds a private caller stack."""
    state = held(word).value
    frame = state['frames'][-1]
    call = _call(frame['call'])
    result: dict[str, Any] = {
        'nonce': word, 'state': 'waiting' if state.get('waiting') else 'running',
        'context': frame.get('context') or state['context'], 'address': call.address,
        'logic': {'type': call.logic.type, 'name': call.logic.name, 'content': call.logic.content},
        'arguments': call.arguments, 'this': call.this, 'variables': unpack(frame['variables'])}
    if 'returned' in frame:
        result['returned'] = unpack(frame['returned'])
    if 'error' in frame:
        result['error'] = frame['error']
    if 'branches' in frame:
        result['branches'] = [
            {'nonce': branch['nonce'], **({'error': branch['error']} if branch['error'] is not None
                                         else {'value': unpack(branch['value'])})}
            for branch in frame['branches']]
    return result


def call(word: str, text: str, variables: Mapping[str, Any], lookup: Lookup, *, fresh: bool = False,
         resolve: Callable[[str], Any] | None = None, context: dict[str, Any] | None = None) -> str:
    state = held(word).value
    if state.get('waiting'):
        raise Stop('This call is waiting for its handoff to return.', f'metaform {word}')
    frame = state['frames'][-1]
    child = prepare(text, variables, _call(frame['call']).this, lookup, resolve)
    child_context = context or frame.get('context') or state['context']
    frame['variables'] = pack(dict(variables))
    frame.pop('returned', None)
    frame.pop('error', None)
    if fresh:
        child_word = nonce.request('workflow', 'resume', {
            'context': child_context, 'frames': [_frame(child, child_context)], 'parent': word})
        state['waiting'] = [child_word]
        nonce.update(word, value=state)
        return child_word
    state['frames'].append(_frame(child, child_context))
    nonce.update(word, value=state)
    return word


def parallel(word: str, texts: Sequence[str], variables: Mapping[str, Any], lookup: Lookup,
             resolve: Callable[[str], Any] | None = None, context: dict[str, Any] | None = None) -> list[str]:
    """Register the independent calls selected by the interpreting agent."""
    state = held(word).value
    if state.get('waiting'):
        raise Stop('This call is waiting for its handoffs to return.', f'metaform {word}')
    frame = state['frames'][-1]
    calls = [prepare(text, variables, _call(frame['call']).this, lookup, resolve) for text in texts]
    child_context = context or frame.get('context') or state['context']
    frame['variables'] = pack(dict(variables))
    frame.pop('returned', None)
    frame.pop('error', None)
    words = [nonce.request('workflow', 'resume', {'context': child_context, 'frames': [_frame(child, child_context)],
                                                'parent': word}) for child in calls]
    state['waiting'] = words
    state['branches'] = {child_word: {'call': _frame(child)['call']} for child_word, child in zip(words, calls)}
    nonce.update(word, value=state)
    return words


def complete(word: str, expression: str, variables: Mapping[str, Any]) -> dict[str, Any]:
    state = held(word).value
    frame = state['frames'][-1]
    return _finish(word, returned(expression, variables, _call(frame['call']).this))


def fail(word: str, name: str, message: str) -> dict[str, Any]:
    return _finish(word, error={'name': name, 'message': message})


def _deliver(frame: dict[str, Any], child: Call, value: Any, error: dict[str, str] | None) -> None:
    if error is None:
        frame['variables'] = pack(receive(child, value, unpack(frame['variables'])))
        frame['returned'] = pack(value)
        frame.pop('error', None)
    else:
        frame['error'] = error
        frame.pop('returned', None)


def _finish(word: str, value: Any = None, *, error: dict[str, str] | None = None) -> dict[str, Any]:
    state = held(word).value
    if state.get('waiting'):
        raise Stop('This call is waiting for its handoffs to return.', f'metaform {word}')
    child = _call(state['frames'][-1]['call'])
    if len(state['frames']) > 1:
        state['frames'].pop()
        _deliver(state['frames'][-1], child, value, error)
        nonce.update(word, value=state)
        return {'resume': word, **view(word)}
    parent_word = state['parent']
    if parent_word is not None:
        def deliver(parent: dict[str, Any]) -> dict[str, Any]:
            if 'branches' in parent:
                if error is None:
                    receive(child, value, unpack(parent['frames'][-1]['variables']))
                branches = parent['branches']
                branches[word].update({'value': pack(value), 'error': error})
                if any('value' not in branches[one] for one in parent['waiting']):
                    return parent
                for branch_word in parent['waiting']:
                    branch = branches[branch_word]
                    _deliver(parent['frames'][-1], _call(branch['call']), unpack(branch['value']), branch['error'])
                parent['frames'][-1]['branches'] = [
                    {'nonce': one, 'value': branches[one]['value'], 'error': branches[one]['error']}
                    for one in parent['waiting']]
                parent.pop('branches')
            else:
                _deliver(parent['frames'][-1], child, value, error)
            parent.pop('waiting', None)
            return parent
        parent = nonce.mutate(parent_word, deliver).value
        nonce.close(word)
        if parent.get('waiting'):
            return {'caller': parent_word, 'state': 'waiting'}
        return {'resume': parent_word}
    result = {'error': error} if error is not None else {
        'value': value, 'variables': receive(child, value, unpack(state['caller']))}
    nonce.close(word)
    return result
