"""The shared command line parser, CLI-001, CLI-003, CLI-004, CLI-015 and BASE-043.

Required nouns are positional, in order. Optional nouns are `name=value` words
in any order after them. A switch is a setting the verb reads: `--name` and
`--no-name` for a boolean, `--name value` or `--name=value` otherwise, or its
one-letter short form. `--confirm`, `--json` and `--help` are verb controls.
After `--`, every word is a plain noun.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import settings
from .errors import Stop
from .module import Noun, Verb

CONTROLS = ('--confirm', '--json', '--help', '-h')


@dataclass
class Parsed:
    nouns: dict[str, Any] = field(default_factory=dict)
    switches: dict[str, Any] = field(default_factory=dict)
    confirm: bool = False
    json: bool = False
    help: bool = False
    unknown: list[str] = field(default_factory=list)


def convert(noun: Noun, raw: str, where: str) -> Any:
    """One noun's value from its word, BASE-035."""
    if noun.kind == 'int':
        try:
            return int(raw)
        except ValueError:
            raise Stop(f'{noun.name} is a whole number, not {raw!r}.', f'{where} --help') from None
    if noun.kind == 'bool':
        if raw not in ('true', 'false'):
            raise Stop(f'{noun.name} is true or false, not {raw!r}.', f'{where} --help')
        return raw == 'true'
    if noun.kind == 'json':
        try:
            return json.loads(raw)
        except ValueError:
            raise Stop(f'{noun.name} is JSON, and {raw!r} does not parse.', f'{where} --help') from None
    return raw


def parse(module: str, verb: Verb, words: list[str]) -> Parsed:
    where = f'metaform {module} {verb.name}'
    parsed = Parsed()
    positional: list[str] = []
    optional = {noun.name: noun for noun in verb.nouns if not noun.required}
    ended = False
    index = 0
    while index < len(words):
        word = words[index]
        index += 1
        if ended:
            positional.append(word)
            continue
        if word == '--':
            ended = True
        elif word in ('--help', '-h'):
            parsed.help = True
        elif word == '--json':
            parsed.json = True
        elif word == '--confirm' and verb.caution:
            parsed.confirm = True
        elif word == '--all':
            raise Stop('--all is not a switch. all is an argument.', f'{where} all')
        elif word.startswith('-') and len(word) > 1:
            name, equals, inline = word.partition('=')
            if not name.startswith('--') and (len(name) != 2 or not name[1].isalpha()):
                raise Stop(f'{name} is not a switch; to pass it as a word, put -- before it.', f'{where} --help')
            found = settings.by_switch(name)
            if found is None or found[0].key not in verb.switches:
                raise Stop(f'{module} {verb.name} has no switch {name}.', f'{where} --help')
            setting, negative = found
            if setting.kind == 'bool':
                if equals:
                    raise Stop(f'{name} takes no value.', f'{where} --help')
                parsed.switches[setting.key] = not negative
                continue
            if not equals:
                if index >= len(words):
                    raise Stop(f'{name} needs a value.', f'{where} --help')
                inline = words[index]
                index += 1
            try:
                parsed.switches[setting.key] = settings.parse(setting, inline)
            except settings.SettingError as error:
                raise Stop(str(error), error.next_step or f'metaform help {setting.switch}') from None
        elif '=' in word and word.split('=', 1)[0] in optional:
            name, _, raw = word.partition('=')
            if not positional_complete(verb, positional):
                raise Stop(f'{name}= comes after the required nouns.', f'{where} --help')
            parsed.nouns[name] = convert(optional[name], raw, where)
        else:
            positional.append(word)
    if parsed.help:
        return parsed
    _place(verb, positional, parsed, where)
    return parsed


def positional_complete(verb: Verb, positional: list[str]) -> bool:
    required = [noun for noun in verb.nouns if noun.required]
    return len(positional) >= len([noun for noun in required if not noun.many])


def _place(verb: Verb, positional: list[str], parsed: Parsed, where: str) -> None:
    remaining = list(positional)
    for noun in verb.nouns:
        if noun.many:
            values = [convert(noun, word, where) for word in remaining]
            remaining = []
            if values:
                parsed.nouns[noun.name] = values
            elif noun.required:
                raise Stop(f'{verb.name} needs at least one {noun.name}.', f'{where} --help')
            continue
        if noun.name in parsed.nouns:
            continue
        if noun.required and remaining:
            parsed.nouns[noun.name] = convert(noun, remaining.pop(0), where)
        elif noun.required:
            raise Stop(f'{verb.name} needs {noun.usage()}.', f'{where} --help')
    if remaining:
        raise Stop(f'{verb.name} does not take {remaining[0]!r}.', f'{where} --help')


KIND_WORDS = {'str': 'text', 'int': 'a whole number', 'bool': 'true or false'}


def _typed(kind: str, value: Any) -> bool:
    if kind == 'str':
        return isinstance(value, str)
    if kind == 'int':
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == 'bool':
        return isinstance(value, bool)
    return True


def _noun_value(noun: Noun, value: Any, where: str) -> Any:
    """One noun from its JSON value, BASE-035. A noun with a schema, or of kind json, takes any JSON value."""
    if noun.schema is not None or noun.kind == 'json':
        return value
    if noun.many:
        if not isinstance(value, list) or not all(_typed(noun.kind, member) for member in value):
            raise Stop(f'{noun.name} is a list of {KIND_WORDS[noun.kind]} values.', f'{where} --help')
        return list(value)
    if not _typed(noun.kind, value):
        raise Stop(f'{noun.name} is {KIND_WORDS[noun.kind]}, not {json.dumps(value)}.', f'{where} --help')
    return value


def switch_value(setting: settings.Setting, value: Any, folder: Path | None = None) -> Any:
    """A setting's value from its JSON form over MCP, CLI-027, checked as `set` checks it."""
    if setting.kind == 'bool':
        if not isinstance(value, bool):
            raise settings.SettingError(f'{setting.key} is true or false, not {json.dumps(value)}.')
        return value
    if setting.kind == 'list':
        if not isinstance(value, list) or not all(isinstance(member, str) for member in value):
            raise settings.SettingError(f'{setting.key} is a list of text values.')
        return [member.strip() for member in value if member.strip()]
    if setting.kind == 'int':
        if not isinstance(value, int) or isinstance(value, bool):
            raise settings.SettingError(f'{setting.key} is a whole number, not {json.dumps(value)}.')
        return settings.parse(setting, str(value), folder)
    if not isinstance(value, str):
        raise settings.SettingError(f'{setting.key} is text, not {json.dumps(value)}.')
    return settings.parse(setting, value, folder)


def from_json(module: str, verb: Verb, arguments: dict[str, Any], *, ignore: tuple[str, ...] = (),
              folder: Path | None = None) -> Parsed:
    """The nouns and switches of one tool call, checked the way the command line checks them, MCP-005 and MCP-006.

    A required noun that is missing, or a value of the wrong kind, stops the call with the same next step the
    command line gives. A name that is neither a noun nor a switch of the verb is listed in `unknown`.
    """
    where = f'metaform {module} {verb.name}'
    parsed = Parsed()
    for noun in verb.nouns:
        if noun.name not in arguments:
            if noun.required:
                raise Stop(f'{verb.name} needs {noun.usage()}.', f'{where} --help')
            continue
        parsed.nouns[noun.name] = _noun_value(noun, arguments[noun.name], where)
    for key in verb.switches:
        setting = settings.SCHEMA.get(key)
        if setting is None or key not in arguments:
            continue
        try:
            parsed.switches[key] = switch_value(setting, arguments[key], folder)
        except settings.SettingError as error:
            raise Stop(str(error), error.next_step or f'metaform help {setting.switch}') from None
    known = {noun.name for noun in verb.nouns} | set(verb.switches) | set(ignore)
    parsed.unknown = sorted(name for name in arguments if name not in known)
    return parsed
