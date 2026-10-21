"""The settings, the person's own: a TOML file in the home, each key overridden by an environment variable.

The home is ROUNDTABLE_HOME, `~/.roundtable` by default; it holds the store, `roundtable.sqlite3`, the runners' logs
under `logs/`, the config file `config.toml`, and the reports under `reports/` unless `reports` names another folder.
Every key below can be set in `config.toml` or as `ROUNDTABLE_<KEY>` in the environment, which wins. An agent's
command is set under `[agents]` in the file, or as `ROUNDTABLE_AGENT_<NAME>`; an A2A peer under `[peers.<name>]`, or
as `ROUNDTABLE_PEER_<NAME>`. Tokens are never written anywhere: the file names the variables that hold them.

No tool changes a setting: they decide which models are called on the person's account and how much a table may
spend, so only the person, who owns the file and the environment, sets them. A chair may open a table with lower
limits than these, never higher.

Settings are read afresh on every call. A discussion keeps the rules, judgment questions and the bars captured when
it opened, `keep` and for a table with topics each noul's own (`keep_new`, `keep_on_topic`, `keep_covered`,
`keep_round_added`); changes to those apply to new discussions. Other changes take effect at the next turn.
"""
from __future__ import annotations

import os
import re
import secrets
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

DEFAULTS: dict[str, Any] = {
    'keep': 0.83,  # the bar each of Jev's four nouls must reach for a submission to enter the discussion
    'keep_new': '',  # on a table with topics, the bar Jev's new_context noul must reach; empty is keep
    'keep_on_topic': '',  # on a table with topics, the bar Jev's on_topic noul must reach; empty is keep
    'keep_covered': '',  # the bar covered must reach after a round for it to count as settled; empty is keep
    'keep_round_added': '',  # the bar round_added must fall below for a round to count as settled; empty is keep
    'rounds': 8,  # the most rounds a table runs, or a table with topics runs on each topic
    'min_rounds': 3,  # the fewest rounds a topic runs before Jev, a round that kept nothing or its budget end it
    'topic_tokens': 12000,  # a topic's discussion goes to synthesis once Jev's state for it reaches this estimate
    'spend': 2.0,  # the most US dollars a table spends through OpenRouter: its seats, Jev and an OpenRouter reporter
    'agent_wait': 300,  # seconds a seat's agent has for its turn, and an outside agent seat to submit
    'jev_wait': 300,  # seconds one of Jev's judgments has for every attempt and the waits between them
    'degraded_after': 2,  # failures of one kind in a row, empty replies among them, that mark a seat degraded
    'unavailable_after': 4,  # failures of one kind in a row that make a seat unavailable, asked again after a probe
    'probe_wait': 300,  # seconds before an unavailable seat is first probed, doubling after each failure to an hour
    'reporter': 'acp:claude/opus',  # the seat at the table that writes the report
    'reports': '',  # the folder reports and exports are written to; empty is <home>/reports
    'jev_model': 'typesafe/jev-1.13',  # a fixed Jev version, never an alias, captured with the floors at open
    'openrouter_url': 'https://openrouter.ai/api',  # chat completions at /v1/chat/completions, Jev at /alpha/decisions
    'seat_tokens': 1024,  # a discussion turn's output: 512 characters are about 130 tokens, the rest low reasoning
    'seat_reasoning': 'low',  # the reasoning effort a seat's turn asks for where its model allows; empty asks none
    'report_tokens': 12000,
    'report_model': 'deepseek/deepseek-v4.1-flash',  # the OpenRouter model that writes the report when no seat does
    'cache_ttl': '1h',  # an hour's cache for Anthropic and Qwen in place of five minutes, at a higher write; empty is 5m
    'host': '127.0.0.1',  # where `roundtable serve --http` listens; always a loopback address
    'port': 7435,
    'web_port': 7436,  # where the web page listens, on the same host, with `roundtable web` or `serve --http`
    'a2a_any_url': False,  # true lets a seat be any A2A card URL, not only a peer the person named
    'a2a_tokens': 'ROUNDTABLE_A2A_TOKEN',  # the variables, comma-separated, whose values may call this A2A server
}
AGENTS: dict[str, str] = {  # the ACP adapters, at the versions Metaform's dispatch pins
    'claude': 'npx -y @agentclientprotocol/claude-agent-acp@0.89.1',
    'codex': 'npx -y @agentclientprotocol/codex-acp@2.2.2',
    'antigravity': 'metaform dispatch adapter antigravity-acp@1.4.1',
}
KEY = 'OPENROUTER_API_KEY'


def home() -> Path:
    found = Path(os.environ.get('ROUNDTABLE_HOME') or Path.home() / '.roundtable').expanduser()
    found.mkdir(parents=True, exist_ok=True)
    return found


def file() -> dict[str, Any]:
    path = home() / 'config.toml'
    if not path.is_file():
        return {}
    with path.open('rb') as held:
        return tomllib.load(held)


def value(key: str) -> Any:
    """One setting: the environment's, else the file's, else the default, as the default's type."""
    default = DEFAULTS[key]
    given: Any = os.environ.get(f'ROUNDTABLE_{key.upper()}')
    if given is None:
        given = file().get(key, default)
    if isinstance(default, bool):
        return str(given).strip().lower() in ('1', 'true', 'yes', 'on')
    if isinstance(default, int):
        return int(given)
    if isinstance(default, float):
        return float(given)
    return str(given)


def keep() -> float:
    """The bar, given as a fraction (0.83) or as per cent (83)."""
    found = value('keep')
    return found / 100 if found > 1 else found


def floor(key: str) -> float:
    """One noul's own bar, `keep_new` and the others, given as `keep` is; `keep` itself when it is left empty."""
    given = str(value(key)).strip()
    if not given:
        return keep()
    found = float(given)
    return found / 100 if found > 1 else found


FLOORS = ('keep_new', 'keep_on_topic', 'keep_covered', 'keep_round_added')


def reports() -> Path:
    folder = Path(value('reports') or home() / 'reports').expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def agents() -> dict[str, str]:
    """Each ACP agent a seat can be, by name, with the command that starts it."""
    own = cast(dict[str, Any], file().get('agents') or {})
    found = {**AGENTS, **{str(name): str(command) for name, command in own.items()}}
    for name, command in os.environ.items():  # ROUNDTABLE_AGENT_WAIT is the agent_wait setting, not an agent
        if name.startswith('ROUNDTABLE_AGENT_') and command.strip() and \
                name.removeprefix('ROUNDTABLE_').lower() not in DEFAULTS:
            found[name.removeprefix('ROUNDTABLE_AGENT_').lower()] = command
    return found


@dataclass(frozen=True)
class Peer:
    """An A2A agent the person names: its short name, its Agent Card's URL, and the variable holding its token."""
    name: str
    card: str
    token_env: str | None

    @property
    def token(self) -> str | None:
        return (os.environ.get(self.token_env) or None) if self.token_env else None


PEER_NAME = re.compile(r'^[a-z0-9][a-z0-9_-]*$')
VARIABLE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def card_url(given: str) -> str:
    """An Agent Card's URL: as given when it names a file, else the well-known card under it."""
    url = given.strip()
    return url if url.endswith('.json') else url.rstrip('/') + '/.well-known/agent-card.json'


def peer(name: str, url: str, token_env: str | None) -> Peer:
    if not PEER_NAME.fullmatch(name) or not url.startswith(('http://', 'https://')) or \
            (token_env and not VARIABLE.fullmatch(token_env)):
        raise ValueError(f'The peer {name!r} is not a name, an http(s) card URL and a token variable: '
                         f'{url!r} {token_env!r}.')
    return Peer(name, card_url(url), token_env or None)


def peers() -> dict[str, Peer]:
    """The A2A peers the person names: `[peers.<name>]` with `card` and `token_env` in the file, or
    ROUNDTABLE_PEER_<NAME>="<card URL> <token variable>" in the environment. A token itself is never stored, only the
    name of the variable that holds it."""
    found: dict[str, Peer] = {}
    for name, entry in cast(dict[str, Any], file().get('peers') or {}).items():
        held = cast(dict[str, Any], entry) if isinstance(entry, dict) else {}
        found[str(name)] = peer(str(name), str(held.get('card') or ''), str(held.get('token_env') or '') or None)
    for variable, value in os.environ.items():
        if variable.startswith('ROUNDTABLE_PEER_') and value.strip():
            url, _, token_env = value.strip().partition(' ')
            name = variable.removeprefix('ROUNDTABLE_PEER_').lower().replace('_', '-')
            found[name] = peer(name, url, token_env.strip() or None)
    return found


def a2a_tokens() -> list[str]:
    """The bearer tokens that may call this server's A2A endpoints, read from the variables `a2a_tokens` names."""
    names = [one.strip() for one in str(value('a2a_tokens')).split(',') if one.strip()]
    return [token for token in (os.environ.get(one, '').strip() for one in names) if token]


def web_token() -> str:
    """The token in the web page's URL: ROUNDTABLE_WEB_TOKEN, else the one kept in the home's `web-token`, made on
    first use and readable only by the person, so a bookmarked address keeps working."""
    given = os.environ.get('ROUNDTABLE_WEB_TOKEN', '').strip()
    if given:
        return given
    path = home() / 'web-token'
    if path.is_file() and path.read_text().strip():
        return path.read_text().strip()
    made = secrets.token_urlsafe(24)
    path.write_text(made + '\n')
    path.chmod(0o600)
    return made


def openrouter_key() -> str:
    return os.environ.get(KEY, '').strip()


def shown() -> dict[str, Any]:
    """Every setting in force, for `status` and the README's check; never a key."""
    return {**{key: value(key) for key in DEFAULTS}, 'keep': keep(), **{key: floor(key) for key in FLOORS},
            'reports': str(reports()),
            'agents': agents(), 'openrouter_key': bool(openrouter_key()), 'a2a_tokens_set': len(a2a_tokens()),
            'peers': {name: {'card': one.card, 'token_env': one.token_env, 'token_set': bool(one.token)}
                      for name, one in peers().items()}}
