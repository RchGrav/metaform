"""Who sits at a table. A seat is a kind and an id, written one of three ways:

- `acp:<agent>/<model>`, such as `acp:antigravity/argon`: Claude Code, Codex or Antigravity in its own ACP
  session started by this server, on the person's own login to it and never an API key, `harness`;
- a plain model id, `deepseek/deepseek-v4.1-flash` (or `openrouter:<model>`), called through OpenRouter with
  OPENROUTER_API_KEY, `openrouter`;
- `agent:<name>`, an outside agent that reads its turn with `turn` and answers with `submit`;
- `a2a:<peer name>` or `a2a:<card URL>`, a remote A2A agent the person names, `peers`.

Whoever opens a table names its seats, in the order they speak; there is no default line-up.
"""
from __future__ import annotations

import json
import re
import shlex
import shutil
from collections.abc import Mapping
from typing import Any, cast

from . import config, peers, store


class Refused(Exception):
    """A seat that cannot sit; the message says why and what to write instead."""


def parse(given: str) -> dict[str, str]:
    text = given.strip()
    kind, sep, rest = text.partition(':')
    if sep and kind == 'agent' and rest.strip():
        return {'kind': 'agent', 'id': f'agent:{rest.strip()}'}
    if sep and kind == 'a2a' and rest.strip():
        given = rest.strip()
        try:
            peer = peers.resolve(given)
        except peers.Refused as error:
            raise Refused(str(error)) from None
        return {'kind': 'a2a', 'id': f'a2a:{peer.name or peer.card}', 'agent': peer.name, 'model': peer.card}
    if sep and kind == 'acp':
        agent, slash, model = rest.strip().partition('/')
        if not (slash and re.fullmatch(r'[A-Za-z0-9._-]+', agent) and re.fullmatch(r'[A-Za-z0-9~._:\[\] -]+', model)):
            raise Refused(f'{text} is not a seat: write acp:<agent>/<model>, such as acp:claude/opus or '
                          'acp:codex/gpt-6-astra.')
        return {'kind': 'acp', 'id': f'acp:{agent}/{model}', 'agent': agent, 'model': model}
    model = rest if sep and kind == 'openrouter' else text
    if not re.fullmatch(r'[A-Za-z0-9~._-]+/[A-Za-z0-9._:-]+', model):
        raise Refused(f'{text} is not a seat: write an OpenRouter model id such as deepseek/deepseek-v4.1-flash, '
                      'acp:<agent>/<model>, or agent:<name>.')
    return {'kind': 'openrouter', 'id': model, 'model': model}


def words(value: Any) -> list[str]:
    """A list given as a JSON list, a list, or text separated by commas."""
    if value is None or value == '':
        return []
    if isinstance(value, str):
        text = value.strip()
        value = json.loads(text) if text.startswith('[') else text.split(',')
    if not isinstance(value, list):
        raise Refused('seats is a list of seats.')
    return [str(one).strip() for one in cast(list[Any], value) if str(one).strip()]


def chosen(given: Any) -> tuple[list[dict[str, str]], list[str]]:
    """The seats in order, each named once, with each ACP seat's agent checked and its model resolved to the value its
    agent offered at its latest session; and a notice for an agent whose models are not known yet."""
    agents = config.agents()
    seats: list[dict[str, str]] = []
    notices: list[str] = []
    for seat in (parse(one) for one in words(given)):
        if seat['kind'] == 'acp':
            agent, model = seat['agent'], seat['model']
            if agent not in agents:
                raise Refused(f'{seat["id"]}: {agent} is not an agent this server starts; it starts '
                              f'{", ".join(sorted(agents))}. Add one under [agents] in config.toml.')
            program = shlex.split(agents[agent])[0]
            if shutil.which(program) is None:
                raise Refused(f'{seat["id"]}: the command {program} that starts {agent} is not found.')
            choices = store.offered(agent)
            if choices:
                value = resolve(model, choices)
                if value is None:
                    listed = ', '.join(f'{one["value"]} ({one.get("name")})' for one in choices)
                    raise Refused(f'{seat["id"]}: {agent} offers no one model matching {model}; it offers {listed}.')
                seat = {**seat, 'id': f'acp:{agent}/{value}', 'model': value}
            else:
                notices.append(f'{agent} has not run here yet, so the model {model} is checked when its seat\'s '
                               'session starts; a model it does not offer takes the seat away.')
        if all(seat['id'] != held['id'] for held in seats):
            seats.append(seat)
    if not seats:
        raise Refused('A table needs one seat at least.')
    return seats, notices


def plain(text: str) -> str:
    return re.sub(r'[^a-z0-9]', '', text.lower())


def matches(given: str, value: str, label: str, way: int) -> bool:
    """Whether a model an agent offers, by its value and its name, is the one given, in the `way`th sense: the value
    itself, its name, either with only letters and digits compared, or a full id ending with the name."""
    if way == 0:
        return value == given
    if way == 1:
        return label.casefold() == given.casefold()
    if way == 2:
        return plain(value) == plain(given) or plain(label) == plain(given)
    return bool(plain(label)) and plain(given).endswith(plain(label))


def resolve(given: str, choices: list[dict[str, str]]) -> str | None:
    """The model value an agent offers for a seat's model: the value itself, its name, or a full id that ends with
    the name, so claude-opus-5-5 is Claude Code's opus, named Opus 5.5. A family's short name selects its newest
    offered version, as astra selects gpt-6.1-astra. An exact value wins; None when none or two match."""
    for way in range(4):
        if way == 1:
            released = [(tuple(int(part) for part in match[1].split('.')), one['value']) for one in choices
                        if (match := re.search(r'-(\d+(?:\.\d+)*)-([a-z]+)$', one['value']))
                        and match[2] == given.casefold()]
            # Claude Code's ids put the family first and the version after it, claude-fable-5-1 and claude-fable-5
            released += [(tuple(int(part) for part in match[2].split('-')), one['value']) for one in choices
                         if (match := re.fullmatch(r'[a-z]+-([a-z]+)-(\d+(?:-\d+)*)', one['value']))
                         and match[1] == given.casefold()]
            if released:
                newest = max(version for version, _ in released)
                values = {value for version, value in released if version == newest}
                return values.pop() if len(values) == 1 else None
        found = [str(one['value']) for one in choices
                 if matches(given, str(one['value']), str(one.get('name') or ''), way)]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            return None
    return None


def reporter(given: str | None, seated: list[dict[str, str]]) -> tuple[str, str | None]:
    """The seat that writes the report: the one asked for, or the `reporter` setting, when it sits at the table;
    else the first seat that can, an ACP seat before an OpenRouter one. Never Claude through OpenRouter, since a
    Claude seat runs on the person's own login. A notice when it is not the one asked for."""
    wanted = parse((given or config.value('reporter')).strip())
    if wanted['kind'] == 'acp':
        value = resolve(wanted['model'], store.offered(wanted['agent']))
        if value is not None:
            wanted = {**wanted, 'id': f'acp:{wanted["agent"]}/{value}', 'model': value}
    if claude_by_openrouter(wanted['id']):
        raise Refused('Claude through OpenRouter never writes the report; seat acp:claude/<model> for it.')

    def same(seat: dict[str, str]) -> bool:  # acp:claude/opus is the seat acp:claude/opus however its model resolved
        if seat['id'] == wanted['id']:
            return True
        return seat['kind'] == wanted['kind'] == 'acp' and seat['agent'] == wanted['agent'] and \
            plain(seat['model']) == plain(wanted['model'])

    found = next((seat for seat in seated if able(seat) and same(seat)), None)
    if found is not None:
        return found['id'], None
    if given:
        raise Refused(f'The reporter {given} does not sit at this table; a report is written by a seat at it.')
    fallback = next((seat for seat in seated if seat['kind'] == 'acp'), None) or \
        next((seat for seat in seated if able(seat)), None)
    if fallback is None:
        raise Refused(f'No seat at this table can write the report: seat {wanted["id"]}, another acp seat, or an '
                      'OpenRouter model other than Claude.')
    return fallback['id'], f'{wanted["id"]} does not sit at this table, so {fallback["id"]} writes the report.'


def able(seat: Mapping[str, Any]) -> bool:
    """Whether a seat can write the report: an ACP or A2A seat, or an OpenRouter model other than Claude."""
    return seat['kind'] in ('acp', 'a2a') or \
        (seat['kind'] == 'openrouter' and not claude_by_openrouter(str(seat['id'])))


def claude_by_openrouter(seat: str) -> bool:
    return seat.startswith(('anthropic/', 'openrouter:anthropic/'))
