"""Persisted call transport for the agent that interprets Axiom.

Frames carry authored logic unchanged. The agent interprets Choice, Map,
Retry and Catch; this module transports their calls and results. Each run's
state is kept in its run record, `runs`, reached by its run id.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

from metaform.data import Store
from metaform.module import Stop

from . import runs
from .binding import Call, Logic, Lookup, prepare, receive, returned
from .element import ElementValue, Value


def pack(value: Any) -> Any:
    """Keep element views and tuples intact across the run record's JSON boundary."""
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


def held(store: Store, word: str) -> runs.Run:
    return runs.held(store, word)


def working(store: Store, word: str) -> dict[str, Any]:
    """The state of a run that can take its next step: not waiting on its handoffs, nor paused on the person. The
    paused refusal names the person's answer command, which refuses every agent, so an agent told the answer in a
    message hands it to the person instead of answering itself."""
    found = held(store, word)
    if found.state == 'waiting':
        raise Stop('This call is waiting for its handoffs to return.', f'metaform workflow resume run={word}')
    if found.state == 'input_required':
        stopped = (found.message or '').rstrip('.')
        raise Stop(f'This run is paused on the person, who has not yet answered: {stopped}. The person answers it '
                   f'with metaform workflow answer run={word} <answer>; if they gave you their answer in a message, '
                   'tell them to run that, then end your turn.', f'metaform workflow resume run={word}')
    return found.value


def start(store: Store, text: str, variables: Mapping[str, Any], this: Any, lookup: Lookup,
          context: dict[str, Any], resolve: Callable[[str], Any] | None = None) -> str:
    call = prepare(text, variables, this, lookup, resolve)
    return runs.start(store, 'call', {'context': context, 'frames': [_frame(call, context)],
                                      'caller': pack(dict(variables)), 'parent': None})


def view(store: Store, word: str) -> dict[str, Any]:
    """Expose the callee alone, including when its run holds a private caller stack."""
    found = held(store, word)
    state = found.value
    frame = state['frames'][-1]
    call = _call(frame['call'])
    result: dict[str, Any] = {
        'run': word, 'state': found.state, **({'message': found.message} if found.message else {}),
        'context': frame.get('context') or state['context'], 'address': call.address,
        'logic': {'type': call.logic.type, 'name': call.logic.name, 'content': call.logic.content},
        'arguments': call.arguments, 'this': call.this, 'variables': unpack(frame['variables'])}
    if 'returned' in frame:
        result['returned'] = unpack(frame['returned'])
    if 'error' in frame:
        result['error'] = frame['error']
    if 'answer' in frame:
        result['answer'] = frame['answer']
    if 'branches' in frame:
        result['branches'] = [
            {'run': branch['run'], **({'error': branch['error']} if branch['error'] is not None
                                         else {'value': unpack(branch['value'])})}
            for branch in frame['branches']]
    return result


def call(store: Store, word: str, text: str, variables: Mapping[str, Any], lookup: Lookup, *, fresh: bool = False,
         resolve: Callable[[str], Any] | None = None, context: dict[str, Any] | None = None) -> str:
    state = working(store, word)
    frame = state['frames'][-1]
    child = prepare(text, variables, _call(frame['call']).this, lookup, resolve)
    child_context = context or frame.get('context') or state['context']
    frame['variables'] = pack(dict(variables))
    for spent in ('returned', 'error', 'answer'):
        frame.pop(spent, None)
    if fresh:
        child_word = runs.start(store, 'call', {
            'context': child_context, 'frames': [_frame(child, child_context)], 'parent': word})
        state['waiting'] = [child_word]
        runs.save(store, word, state)
        return child_word
    state['frames'].append(_frame(child, child_context))
    runs.save(store, word, state)
    return word


def parallel(store: Store, word: str, texts: Sequence[str], variables: Mapping[str, Any], lookup: Lookup,
             resolve: Callable[[str], Any] | None = None, context: dict[str, Any] | None = None) -> list[str]:
    """Register the independent calls selected by the interpreting agent."""
    state = working(store, word)
    frame = state['frames'][-1]
    calls = [prepare(text, variables, _call(frame['call']).this, lookup, resolve) for text in texts]
    child_context = context or frame.get('context') or state['context']
    frame['variables'] = pack(dict(variables))
    for spent in ('returned', 'error', 'answer'):
        frame.pop(spent, None)
    words = [runs.start(store, 'call', {'context': child_context, 'frames': [_frame(child, child_context)],
                                        'parent': word}) for child in calls]
    state['waiting'] = words
    state['branches'] = {child_word: {'call': _frame(child)['call']} for child_word, child in zip(words, calls)}
    runs.save(store, word, state)
    return words


def complete(store: Store, word: str, expression: str, variables: Mapping[str, Any]) -> dict[str, Any]:
    state = working(store, word)
    frame = state['frames'][-1]
    return _finish(store, word, returned(expression, variables, _call(frame['call']).this))


def fail(store: Store, word: str, name: str, message: str) -> dict[str, Any]:
    return _finish(store, word, error={'name': name, 'message': message})


def _deliver(frame: dict[str, Any], child: Call, value: Any, error: dict[str, str] | None) -> None:
    if error is None:
        frame['variables'] = pack(receive(child, value, unpack(frame['variables'])))
        frame['returned'] = pack(value)
        frame.pop('error', None)
    else:
        frame['error'] = error
        frame.pop('returned', None)


def _delivery(parent_word: str, word: str, child: Call, value: Any, error: dict[str, str] | None) -> runs.Delivery:
    """How a fresh-agent run's return, or its error, reaches the run it was handed from: that run's id and the change
    to its state, applied in the transaction that ends the child, so nothing can end the child between the two."""
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
                {'run': one, 'value': branches[one]['value'], 'error': branches[one]['error']}
                for one in parent['waiting']]
            parent.pop('branches')
        else:
            _deliver(parent['frames'][-1], child, value, error)
        parent.pop('waiting', None)
        return parent
    return parent_word, deliver


def _caller(parent_word: str, parent: runs.Run | None) -> dict[str, Any]:
    """Where the caller stands once a child has returned to it: still waiting on other branches, or to resume."""
    if parent is None:
        return {}
    return {'caller': parent_word, 'state': 'waiting'} if parent.value.get('waiting') else {'resume': parent_word}


def _finish(store: Store, word: str, value: Any = None, *, error: dict[str, str] | None = None) -> dict[str, Any]:
    state = working(store, word)
    child = _call(state['frames'][-1]['call'])
    if len(state['frames']) > 1:
        state['frames'].pop()
        _deliver(state['frames'][-1], child, value, error)
        runs.save(store, word, state)
        return {'resume': word, **view(store, word)}
    parent_word = state['parent']
    if parent_word is not None:
        parent = runs.close(store, word, result={'error': error} if error is not None else {'value': pack(value)},
                            failed=error is not None, delivery=_delivery(parent_word, word, child, value, error))
        return _caller(parent_word, parent)
    result = {'error': error} if error is not None else {
        'value': value, 'variables': receive(child, value, unpack(state['caller']))}
    runs.close(store, word, result={'error': error} if error is not None else
               {'value': pack(value), 'variables': pack(result['variables'])}, failed=error is not None)
    return result


def pause(store: Store, word: str, found: str, *, ticket: str | None = None,
          session: str | None = None) -> dict[str, Any]:
    """Pause a call or an assignment on the person, `input_required`, with what stopped it and the ticket and session
    of the agent that paused it, until they answer."""
    working(store, word)
    paused = runs.pause(store, word, found, ticket=ticket, session=session)
    return {'run': word, 'state': paused.state, 'message': found}


def answer(store: Store, word: str, given: str) -> runs.Run:
    """The person's answer, beside what stopped the run: in a call's current frame, or on an assignment, which has
    none. The run is running again, and its agent reads the answer when it resumes the run."""
    def place(state: dict[str, Any], found: str) -> dict[str, Any]:
        (state['frames'][-1] if 'frames' in state else state['assignment'])['answer'] = {
            'question': found, 'answer': given}
        return state
    return runs.answer(store, word, place)


CANCELLED = 'cancelled'  # the error a cancelled fresh-agent run delivers to its caller, for the caller's Catch


def cancel(store: Store, word: str, reason: str) -> dict[str, Any]:
    """Cancel a run and every open run below it. A run handed from another delivers the error `cancelled` to its
    caller in the same transaction, as a failed call would, so the caller's authored Catch decides what follows."""
    def delivery(found: runs.Run) -> runs.Delivery | None:
        parent_word = found.value.get('parent')
        if parent_word is None or found.kind != 'call':
            return None
        return _delivery(parent_word, word, _call(found.value['frames'][0]['call']), None,
                         {'name': CANCELLED, 'message': reason})
    cancelled, parent = runs.cancel(store, word, reason, delivery=delivery)
    parent_word = None if parent is None else parent.run_id
    return {'run': word, 'state': CANCELLED, 'cancelled': cancelled,
            **({} if parent_word is None else _caller(parent_word, parent))}
