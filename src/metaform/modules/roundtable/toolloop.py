"""A model seat's turn with its controls, BASE-066: OpenRouter chat completions with tools, in a loop.

A seat through OpenRouter is given its controls as tools on every call of its turn and of its time to explore: it may
call them, each call is run for its own seat and answered, and it is asked again, up to STEPS rounds of calls; then
it is asked once more with the tools withheld, and its text is its answer. A look's picture is given to a model that
takes pictures, image among its OpenRouter input modalities, as image content in a message after the tool's answer;
every model gets what is in view as a list. A model that takes no tools is asked without them.

The conversation the seat keeps, in its row, holds every call and answer of its turns, each picture as a line saying
it was seen from the start, so a picture is sent once, as the newest message of one request, and nothing before a
request's newest message is ever changed: each request's prefix is the last one's, which the provider's prompt cache
holds.

The tools are a registry: `register(Tool(...))` adds one, its description a prompt of `resources/prompts.xml`, its
parameters a JSON schema, and its `run` the control for the seat at hand.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from metaform.data import Store
from metaform.module import Stop

from . import controls, seats
from .render import said

STEPS = 6  # rounds of tool calls a seat may make in one turn before it is asked for its answer
PLAINLY = 'none'


@dataclass(frozen=True)
class At:
    """The seat a tool acts for: its table, its position, and how its eye view is drawn."""
    held: Store
    number: int
    position: int
    picture: controls.Picture


@dataclass(frozen=True)
class Tool:
    name: str
    prompt: str  # the prompt in resources/prompts.xml that describes it to the model
    run: Callable[[At, Mapping[str, Any]], dict[str, Any]]
    parameters: dict[str, Any] = field(default_factory=lambda: {'type': 'object', 'properties': {}})


TOOLS: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    TOOLS[tool.name] = tool


def number(given: Any) -> float | None:
    return None if given in (None, '') else float(given)


register(Tool('turn', 'tool_turn', lambda at, args: controls.rotate(
    at.held, at.number, at.position, number(args.get('degrees')), number(args.get('to'))), {
        'type': 'object', 'properties': {
            'degrees': {'type': 'number', 'description': said('tool_turn_degrees')},
            'to': {'type': 'number', 'description': said('tool_turn_to')}}}))
register(Tool('look', 'tool_look', lambda at, args: controls.look(at.held, at.number, at.position, at.picture)))
register(Tool('look_at', 'tool_look_at', lambda at, args: controls.look_at(
    at.held, at.number, at.position, str(args.get('name') or ''), at.picture), {
        'type': 'object', 'properties': {'name': {'type': 'string', 'description': said('tool_look_at_name')}},
        'required': ['name']}))


def schema() -> list[dict[str, Any]]:
    return [{'type': 'function', 'function': {'name': tool.name, 'description': said(tool.prompt),
                                              'parameters': tool.parameters}} for tool in TOOLS.values()]


def call(at: At, asked: Mapping[str, Any]) -> tuple[str, str | None]:
    """One tool call run for the seat: its answer as JSON text, and the picture it drew, if any."""
    function = cast(dict[str, Any], asked.get('function') or {})
    tool = TOOLS.get(str(function.get('name')))
    if tool is None:
        return json.dumps({'error': said('tool_unknown', tool=function.get('name'))}), None
    try:
        given: Any = json.loads(str(function.get('arguments') or '{}') or '{}')
        found = tool.run(at, cast(dict[str, Any], given) if isinstance(given, dict) else {})
    except Stop as error:
        return json.dumps({'error': error.message}), None
    except (ValueError, TypeError) as error:
        return json.dumps({'error': str(error)}), None
    picture = found.pop('png', None)
    return json.dumps(found), (str(picture) if picture else None)


def plain(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The conversation for a model that takes no tools: every call and answer as plain text."""
    found: list[dict[str, Any]] = []
    for one in messages:
        content: Any = one.get('content')
        text = content if isinstance(content, str) else ' '.join(
            str(part.get('text') or '') for part in cast(list[dict[str, Any]], content or []))
        if one.get('role') == 'tool':
            found.append({'role': 'user', 'content': text})
        elif text:
            found.append({'role': str(one.get('role')), 'content': text})
    return found


def session(at: At) -> str:
    """The seat's own OpenRouter session, sent with every request it makes, so they stay on one provider endpoint."""
    return f'roundtable:{at.number}:{at.position}'


def turn(model: str, at: At, messages: list[dict[str, Any]], *, deadline: float | None = None,
         vision: bool | None = None, paid: seats.Paid | None = None,
         use: seats.Use | None = None) -> tuple[str, list[dict[str, Any]]]:
    """The model's answer to the conversation, after the tool calls it makes; and the conversation to keep, with its
    answer last. Each call's cost is told to `paid` and its usage added to `use`. Silent when the model fails or says
    nothing.

    The conversation only grows: every request is the conversation kept so far, so each one's prefix is the last
    one's and the provider's cache holds it. A picture is the one exception, sent only in the newest message of the
    request after the look; the conversation keeps its line from the start, and every later request sends that."""
    sees = seats.sees(model) if vision is None else vision
    kept = list(messages)
    pictures: list[str] = []
    tools = schema()
    for step in range(STEPS + 1):
        last = step == STEPS or (deadline is not None and time.time() > deadline)
        sent = [*kept[:-1], {'role': 'user', 'content': [
            {'type': 'text', 'text': said('view_image')},
            *({'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{one}'}} for one in pictures)]}
        ] if pictures else kept
        try:
            reply = seats.complete(model, sent, tools=tools, tool_choice=PLAINLY if last else 'auto', paid=paid,
                                   session=session(at), use=use)
        except seats.Untooled:
            text = seats.chat(model, plain(kept), paid=paid, session=session(at), use=use)
            return text, [*plain(kept), {'role': 'assistant', 'content': text}]
        asked = cast(list[dict[str, Any]], reply.get('tool_calls') or [])
        if not asked or last:
            text = str(reply.get('content') or '').strip()
            if not text:
                raise seats.Silent('the reply was empty.')
            return text, [*kept, {'role': 'assistant', 'content': text}]
        kept.append({'role': 'assistant', 'content': reply.get('content') or '', 'tool_calls': asked})
        pictures = []
        for one in asked:
            answer, picture = call(at, one)
            kept.append({'role': 'tool', 'tool_call_id': one.get('id'), 'content': answer})
            if picture and sees:
                pictures.append(picture)
        if pictures:
            kept.append({'role': 'user', 'content': said('view_image_kept')})
    raise seats.Silent('the reply was empty.')
