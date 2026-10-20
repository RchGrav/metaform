"""agents: one record for each role an agent Metaform starts runs as, ticket 3a1306bd (2026-10-15).

A role names the prompts it is sent by their names in the prompt store, `<module>:<element>` for an element of a
module's prompts.xml, `<module>:<file>` for a prompt kept whole in a file and `skill:<name>` for a skill's procedure,
the names `metaform prompts review` gives them. Each prompt stays in its module, and the module still sends it,
through `prompt_files.served`, which serves the prompt store's version, STORE-044: the shipped text, or the edit
saved in its place with `agents override`. The roles are the code's, `settings.AGENT_ROLES`. What each session was
sent comes from dispatch's runner, which tells each turn's prompt versions on `prompt.sent`; this module keeps them in
its table `sent`, linked from its layer `agents`, LAYER-001. A name that no longer resolves is reported on the role,
never dropped.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, cast

from metaform import home, prompt_files, settings
from metaform.data import Column, Index, Store, StoreError, Table, Tables, prompts
from metaform.module import (
    Context,
    Module,
    Noun,
    Provides,
    Resource,
    Stop,
    Subscription,
    Verb,
    context,
    surface,
)

from . import roles as authored

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False  # what each session was sent is kept only while the module is on, so it is on from the start
REMOTE_AGENT = False  # the roles and what each session was sent belong to the home whose dispatch started them

LAYER = 'agents'
VARIABLE = 'Which role and which prompt versions each agent session in this project was sent.'


@dataclass(frozen=True)
class Sends:
    """One prompt a role is sent: its name in the prompt store and when it is sent; `opens` when it is sent only as a
    conversation begins, so an edit of it reaches the conversations begun after it and not one already running."""
    name: str
    when: str
    opens: bool = False


@dataclass(frozen=True)
class Role:
    """A role an agent Metaform starts runs as: what it is for, whether it may put a question to the person (dispatch
    starts it with system true, BASE-052) and the prompts it is sent, in the order they are sent."""
    name: str
    purpose: str
    asks_person: bool
    sends: tuple[Sends, ...]


# Sent to an agent of any role that dispatch runs, after its own.
ANY = (
    Sends('prompt.dispatch:context_retention', 'once per context epoch, to establish the retained startup key'),
    Sends('prompt.dispatch:context_checkpoint', 'on the first necessary turn of a start or resume'),
    Sends('prompt.dispatch:role_resource', 'when an authored role is assigned, and as a link after compaction'),
    Sends('prompt.dispatch:communication', 'once per context epoch, with the initial instructions'),
    Sends('prompt.dispatch:timer', 'as a turn when a timer the agent set with dispatch timer is due'),
    Sends('prompt.dispatch:workflow_answered', 'as a turn, or into the turn in flight, when a workflow run it paused is '
                                        'answered'),
)

# The roles in settings.AGENT_ROLES, in its order, each read from where dispatch's runner picks its first turn
# (runner.Session.begin) and the turns it adds later. BASE-054 names another six; the code is the reference.
ROLES = (
    Role('intake', 'Maps the AUE into its elements and purpose records from its source, when the person starts an '
                   'intake.', True, (
        Sends('prompt.intake:intake.axiom', 'first turn: the intake procedure, with what the person asked for; the '
                                     "folder's intake_file setting serves its own file in its place"),
        Sends('prompt.intake:schema_pointer', "added to the first turn when the intake does not name its schema's URI"),
        Sends('prompt.dispatch:intake_first_record', 'once, when the agent makes no Metaform call in time'),
    )),
    Role('system', "The person's own agent in the project's folder: talks with them and acts for them, owns the "
                   'board so every ticket moves, waits on a decision put to them, or is closed, and speaks as their '
                   'mascot when they chose one.', True, (
        Sends('prompt.dispatch:system', 'first turn, and again ahead of the next turn once an edit of it is saved'),
        Sends('prompt.dispatch:mascot', 'filled into the first turn while the person has a mascot and the web module is on, '
                                 'and again with dispatch:system once an edit of either is saved'),
        Sends('prompt.dispatch:system_changed', 'ahead of the next turn after an edit of dispatch:system or dispatch:mascot '
                                         'is saved while its conversation runs, with the prompt as it now reads'),
        Sends('prompt.dispatch:setup_trouble', 'as its next turn, for each feature a module says is not working'),
        Sends('prompt.dispatch:wave_ready', 'as its next turn, when tickets of the work the person\'s word covers are '
                                     'free to start'),
    )),
    Role('sentinel', 'Takes up an issue the person raised on a node, following the sentinel skill.', True, (
        Sends('prompt.skills:served', 'first turn: the skill whole, its libraries first', True),
        Sends('prompt.skill.sentinel', 'filled into the first turn: the skill\'s procedure', True),
        Sends('prompt.skills:assignment_input', 'filled into the first turn: the node, the ticket and the report, bound as '
                                         'data', True),
    )),
    Role('talk', 'Talks with the person about something they clicked on the map; it works no ticket.', True, (
        Sends('prompt.dispatch:talk', 'first turn', True),
        Sends('prompt.dispatch:eyes', 'filled into the first turn while the web module offers a body and eyes', True),
    )),
    Role('prep', 'Prepares a merge under review for the person, in its worktree.', False, (
        Sends('prompt.dispatch:prep', 'first turn', True),
        Sends('prompt.dispatch:decide', 'as the answer to a question it puts, since it may not ask the person'),
    )),
    Role('worker', 'Works one ticket at its node, handed to it by dispatch.', False, (
        Sends('prompt.dispatch:work', 'first turn, after the brief of its node', True),
        Sends('prompt.dispatch:work_record', 'filled into the first turn while the memory module is on', True),
        Sends('prompt.dispatch:retry', 'first turn of a session resumed to retry the ticket'),
        Sends('prompt.dispatch:on_ticket_done', 'as a turn when its ticket is done, as dispatch_record_on_finish says'),
        Sends('prompt.dispatch:on_stopped_open', 'as a turn when it stopped with its ticket open, as dispatch_record_on_stop '
                                          'says'),
        Sends('prompt.dispatch:on_failure', 'as a turn after a turn that ended in an error, as dispatch_record_on_failure '
                                     'says'),
        Sends('prompt.dispatch:decide', 'as the answer to a question it puts, since it may not ask the person'),
    )),
)
assert tuple(role.name for role in ROLES) == settings.AGENT_ROLES, 'one record for each of the code\'s roles'

# Version 1: what each session was sent, one row for each turn that carried a prompt, kept in the project so a clear
# keeps it; a session is read by its id or by its runner's, METAFORM_SESSION.
# Version 2 adds the authored-role tables of roles.py: definitions, their history, role sources, and each recipient
# context epoch with its receipts. It only adds tables, so version 1's code still reads and writes `sent`, STORE-029.
# Version 3 adds content fingerprints and startup context checks without changing the existing tables' fields.
TABLES = Tables(version=3, compatible_from=1, tables=(
    Table('sent', place='project', key=('session_id', 'seq'),
          columns=(Column('session_id', required=True), Column('seq', 'int', required=True),
                   Column('work_id', required=True), Column('runner'), Column('role', required=True),
                   Column('agent'), Column('at', required=True), Column('prompts', 'json', required=True)),
          indexes=(Index(('runner',)),)),
    *authored.TABLES,
))


# ------------------------------------------------------------------------------------------------ prompts by name

def _role(name: Any) -> Role:
    found = next((role for role in ROLES if role.name == str(name)), None)
    if found is None:
        raise Stop(f"No role {name}. Roles: {', '.join(role.name for role in ROLES)}.", 'metaform agents roles')
    return found


def _sends(role: Role) -> tuple[Sends, ...]:
    return (*role.sends, *ANY)


class Unread(Exception):
    """The prompt's shipped text cannot be read from here, though the name may resolve where it is sent."""


def _shipped(ctx: Context, name: str) -> tuple[str | None, str | None]:
    """The text a prompt's module ships now, as a version holds it, and None; or None and why the name does not
    resolve. Unread when it cannot be told from here."""
    owner, rest = prompt_files.split_address(name)
    if not rest:
        return None, f'{name} is not a prompt name: <module>:<element>, <module>:<file> or skill:<name>.'
    if owner == 'skill':  # a skill is read through the workflow module, never by importing the skill registry
        workflow = next((one for one in surface(ctx.folder) if one.id == 'workflow'), None)
        if workflow is None:
            raise Unread(f'The workflow module is off here, so the shipped text of the skill {rest} is not read; '
                         'dispatch still sends it from the skill registry.')
        verb = next(one for one in workflow.verbs if one.name == 'skill')
        try:
            return str(verb.run(context('workflow', ctx.folder, project=ctx.project, nouns={'name': rest}))), None
        except Stop:
            return None, f'There is no skill {rest}.'
    try:
        text = prompt_files.shipped(owner, rest)
    except (OSError, ValueError) as error:
        return None, f'{owner} cannot be read: {error}'
    if text is None:
        return None, f'{owner} ships no prompt {rest}.'
    return text, None


# Served as shipped and never kept in the prompt store or edited, STORE-044 and BASE-039: the chassis's list, which
# the gate every edit goes through refuses.
FIXED = prompt_files.FIXED


def _format(name: str) -> str:
    if name.startswith('prompt.agents:generated_'):
        try:
            return prompts.prompt_version(name).format
        except StoreError:
            return 'text'
    return 'xml' if '.' not in name.partition(':')[2] and not name.startswith('prompt.skill.') else 'text'


def _held(name: str, shipped: str) -> dict[str, Any]:
    """Where the prompt store holds a prompt, read only: the version sent next and its text, whether that is the
    shipped text or an edit, and an edit's shipped text it is behind."""
    if name in FIXED:
        return {'revision': None, 'origin': 'shipped', 'text': shipped, 'fixed': True,
                'note': f'Never stored or edited: {FIXED[name]}.'}
    try:
        versions = prompts.prompt_versions(name)
    except StoreError:
        return {'revision': None, 'origin': 'shipped', 'text': _readable(name, shipped),
                'note': 'Not in the prompt store yet: its shipped text becomes version 1 when it is next sent.'}
    newest = versions[0]
    held: dict[str, Any] = {'revision': newest.number, 'origin': newest.origin}
    if newest.origin == 'edited':
        held['text'] = prompt_files.readable(newest)
        if _format(name) == 'xml':
            try:
                prompt_files.rendered(newest.text)
            except ValueError as error:
                held['broken_edit'] = f'Version {newest.number} is {error}; the shipped text is sent in its place.'
        behind = prompts.behind(name)
        last = next((one.text for one in versions if one.origin == 'shipped'), None)
        if behind is not None and behind.text == shipped:
            held['behind'] = {'shipped': shipped, 'seen': behind.seen}
        elif shipped not in (newest.text, last):  # changed since it was last sent: kept when it is next sent
            held['behind'] = {'shipped': shipped, 'seen': None}
        if 'behind' in held:
            held['note'] = (f'Version {newest.number}, an edit, is sent in place of a newer shipped text. Merge the '
                            f'two with metaform agents override name={name}, or go back to the shipped text with '
                            f'metaform agents drop name={name}.')
        return held
    held['text'] = _readable(name, shipped)
    if newest.text != shipped:
        held['note'] = (f'The shipped text changed after version {newest.number}; it becomes version '
                        f'{newest.number + 1} when it is next sent.')
    return held


def _readable(name: str, text: str) -> str:
    """A prompt's text as the person reads and edits it, its fill places written <name />."""
    return prompt_files.plain(text) if _format(name) == 'xml' else text


def _prompt(ctx: Context, sends: Sends) -> dict[str, Any]:
    """One prompt of a role: whether its name resolves, True, False or None when it cannot be told from here, and
    where the prompt store holds it."""
    one: dict[str, Any] = {'name': sends.name, 'when': sends.when}
    try:
        shipped, problem = _shipped(ctx, sends.name)
    except Unread as unread:
        stored = _stored(sends.name)
        return {**one, 'resolves': None, 'problem': str(unread), **stored}
    if shipped is None:
        return {**one, 'resolves': False, 'problem': problem}
    owner, element = prompt_files.split_address(sends.name)
    written = prompt_files.problem_of(owner, element) if _format(sends.name) == 'xml' else None
    # a prompt written wrong in its file: still sent as it last read, and named until it is corrected
    return {**one, 'resolves': True, **_held(sends.name, shipped), **({'file_problem': written} if written else {})}


def _stored(name: str) -> dict[str, Any]:
    """The newest version the prompt store holds of a prompt, for one whose shipped text is not read here."""
    try:
        newest = prompts.prompt_version(name)
    except StoreError:
        return {'revision': None}
    return {'revision': newest.number, 'origin': newest.origin, 'text': newest.text}


# ------------------------------------------------------------------------------------------------ authority and agents

def _authority(ctx: Context, role: Role) -> dict[str, Any]:
    """What an agent of the role may do: all the tools on the folder's surface, less what the person withholds; the
    intake's server leaves out dispatch_intake_withheld; a role in roles_without_authority writes no tickets and starts,
    stops or messages no agents, MAP-050."""
    held = role.name in cast(list[str], ctx.setting('roles_without_authority') or [])
    withheld: list[str] = []
    if role.name == 'intake':
        try:
            withheld = [str(one) for one in cast(list[Any], settings.value('dispatch_intake_withheld', ctx.folder)
                                                 or [])]
        except Exception:  # noqa: BLE001  dispatch is off, and its settings with it: no intake agent is started
            withheld = []
    return {'tools': 'every tool on the folder\'s surface' + (f", less {', '.join(withheld)}" if withheld else ''),
            'withheld': withheld,
            'held_back': held,
            'authority': ('none: it writes no tickets and starts, stops or messages no agents, roles_without_authority'
                          if held else 'writes tickets and starts, stops and messages agents'),
            'asks_person': role.asks_person}


def _inferred(row: dict[str, Any], state: dict[str, Any]) -> str:
    """A session's role read from what dispatch keeps of it, for one started before its turns were recorded: an intake,
    a summoned agent (system or sentinel, or a talk), else a worker or a merge preparation."""
    if str(row.get('work_id') or '').startswith('intake-'):
        return 'intake'
    about = state.get('about')
    return 'system' if about == 'system' else 'talk' if about else 'worker'


def _running(ctx: Context) -> list[dict[str, Any]]:
    """The sessions dispatch is running now, each with its role: the one its turns were recorded with, else read from
    dispatch's state. None while dispatch is off here."""
    dispatch = next((one for one in surface(ctx.folder) if one.id == 'dispatch'), None)
    if dispatch is None:
        return []
    verb = next(one for one in dispatch.verbs if one.name == 'sessions')
    try:
        found = cast(dict[str, Any], verb.run(context('dispatch', ctx.folder, project=ctx.project,
                                                      nouns={'thread': False})))
    except (Stop, StoreError):  # no project here yet: no agent runs in it
        return []
    states = cast(dict[str, dict[str, Any]], found.get('states') or {})
    rows = [row for row in cast(list[dict[str, Any]], found.get('sessions') or []) if row.get('state') == 'running']
    if not rows:
        return []
    recorded = _recorded_roles(ctx, [str(row['session_id']) for row in rows])
    return [{'session_id': row['session_id'], 'work_id': row['work_id'], 'agent': row.get('agent'),
             'started': row.get('started'), 'runner': row.get('runner'),
             'role': recorded.get(str(row['session_id'])) or _inferred(row, states.get(str(row['session_id'])) or {}),
             'role_from': 'recorded' if str(row['session_id']) in recorded else 'inferred'}
            for row in rows]


def _recorded_roles(ctx: Context, session_ids: list[str]) -> dict[str, str]:
    try:
        with ctx.require_store().tables(write=False) as tx:
            return {session_id: str(found[0]['role']) for session_id in session_ids
                    if (found := tx.rows('sent', {'session_id': session_id}, by=('session_id', 'seq'),
                                         limit=1).results)}
    except StoreError:
        return {}


# ------------------------------------------------------------------------------------------------ verbs

def roles(ctx: Context) -> dict[str, Any]:
    running = _running(ctx)
    held = cast(list[str], ctx.setting('roles_without_authority') or [])
    listed: list[dict[str, Any]] = []
    for each in ROLES:
        named = [_prompt(ctx, sends) for sends in _sends(each)]
        listed.append({'role': each.name, 'purpose': each.purpose,
                       'prompts': [one['name'] for one in named],
                       'broken': [one['name'] for one in named if one['resolves'] is False],
                       'unread': [one['name'] for one in named if one['resolves'] is None],
                       'behind': [one['name'] for one in named if 'behind' in one],
                       'held_back': each.name in held,
                       'running': sum(1 for one in running if one['role'] == each.name)})
    return {'roles': listed,
            'authored': [{'role': role.name, 'uri': f'metaform://role/{role.name}', 'provider': owner,
                           'purpose': role.purpose, 'prompts': list(role.prompts)}
                          for owner, role in authored.definitions(ctx)],
            'next': 'metaform agents role name=<execution role>; metaform agents resolve name=<authored role>'}


def role(ctx: Context) -> dict[str, Any]:
    chosen = _role(ctx.nouns['name'])
    named = [_prompt(ctx, sends) for sends in _sends(chosen)]
    result: dict[str, Any] = {'role': chosen.name, 'purpose': chosen.purpose, 'prompts': named,
                              **_authority(ctx, chosen),
                              'running': [one for one in _running(ctx) if one['role'] == chosen.name]}
    broken = [one['name'] for one in named if one['resolves'] is False]
    if broken:
        result['broken'] = broken
        result['notice'] = (f"{len(broken)} prompt name(s) of {chosen.name} no longer resolve: {', '.join(broken)}. "
                            'The module no longer ships them under that name; the role record names them until it is '
                            'corrected.')
    return result


def sent(ctx: Context) -> dict[str, Any]:
    """Which role a session ran as and which prompt versions each of its turns carried, by its session id or its
    runner's (METAFORM_SESSION)."""
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
    for row in ordered:
        for one in cast(list[dict[str, Any]], row['prompts']):
            numbers = versions.setdefault(str(one['name']), [])
            if one.get('number') not in numbers:
                numbers.append(one.get('number'))
    return {'session_id': first['session_id'], 'role': first['role'], 'agent': first['agent'],
            'work_id': first['work_id'], 'runners': sorted({str(row['runner']) for row in ordered if row['runner']}),
            'prompts': [{'name': name, 'versions': numbers} for name, numbers in versions.items()],
            'turns': [{'at': row['at'], 'runner': row['runner'], 'prompts': row['prompts']} for row in ordered],
            'next': 'metaform prompt <name> <version> reads the exact text of a version'}


def updates(ctx: Context) -> dict[str, Any]:
    """Inspect version-preserving prompt merges and custom selections deliberately left untouched."""
    name = ctx.nouns.get('name')
    return {'updates': prompts.prompt_merges(str(name) if name else None)}


def _known(ctx: Context, name: str) -> str:
    """The shipped text of a prompt some role names; a name no role names is refused, so an edit goes nowhere unsent."""
    if not any(sends.name == name for role in ROLES for sends in _sends(role)) and not any(
            name in role.prompts for _, role in authored.definitions(ctx)):
        raise Stop(f'No role is sent a prompt {name}.', 'metaform agents roles')
    if name in FIXED:
        raise Stop(f'{name} is {FIXED[name]}.', 'metaform agents role name=intake')
    try:
        shipped, problem = _shipped(ctx, name)
    except Unread as unread:
        raise Stop(str(unread), 'metaform enable workflow') from None
    if shipped is None:
        try:
            return prompts.prompt_version(name).text
        except StoreError:
            pass
        raise Stop(str(problem), 'metaform agents roles')
    return shipped


def _reach(ctx: Context, name: str) -> tuple[list[str], list[str]]:
    """Who takes a change of the prompt `name` and when, one phrase for each role sent it, and the sessions running
    now that keep the text they began with: a prompt sent only as a conversation begins reaches the conversations
    begun after the change (UX review round 2, prompt-authoring F4)."""
    running = _running(ctx)
    said: list[str] = []
    kept: list[str] = []
    for role in ROLES:
        found = next((sends for sends in _sends(role) if sends.name == name), None)
        if found is None:
            continue
        ids = [str(one['session_id']) for one in running if one['role'] == role.name]
        if not found.opens:
            said.append(f'the {role.name} role from its next turn' + (f', the {len(ids)} running now included'
                                                                        if ids else ''))
            continue
        said.append(f'the {role.name} role from its next new conversation' + (
            f'; the {len(ids)} running now keep the text they began with' if ids else ''))
        kept += ids
    for _, role in authored.definitions(ctx):
        if name in role.prompts:
            said.append(f'the authored {role.name} role from its next turn')
    return said, kept


def _sent_caution(ctx: Context) -> str:
    """override's and drop's caution for this call: the prompt, the roles sent it and when each takes the change, with
    the sessions running as them now (UX review, person-consent F3, and prompt-authoring F4)."""
    name = str(ctx.nouns.get('name') or '')
    said, _ = _reach(ctx, name)
    if not said:
        return ''
    return f'{name} is sent to {"; ".join(said)}. metaform agents drop {name} goes back to the shipped text.'


def override(ctx: Context) -> dict[str, Any]:
    """Save an edit of a role's prompt in the prompt store, sent in place of the shipped text, STORE-044: written as
    plain text and encoded by `prompt_files.save_edit`, so what is saved is what is sent; each role that names it
    takes it from its next turn, or from its next conversation for a prompt sent only as one begins."""
    name, text = str(ctx.nouns['name']), str(ctx.nouns['text']).strip()
    shipped = _known(ctx, name)
    parent = ctx.nouns.get('parent')
    xml = _format(name) == 'xml'
    if not xml:
        prompts.shipped(name, _format(name), shipped)  # the shipped text is the version the edit is made from
    try:  # the one gate every surface saves through: plain text in, sent as written
        version, notices = prompt_files.save_edit(name, text, parent=int(parent) if parent is not None else None,
                                                  format=_format(name), shipped_text=shipped if xml else None)
    except ValueError as error:
        raise Stop(f'{error}.', f'metaform prompt {name}') from None
    reached, kept = _reach(ctx, name)
    result: dict[str, Any] = {'name': name, 'revision': version.number, 'origin': version.origin,
                              'sent': f'to {"; ".join(reached)}'}
    if kept:
        result['running_not_reached'] = kept
    said = [notice.message for notice in version.notices] + notices
    if said:  # in the result contract's shape, where and message, so every surface shows them (prompt-authoring F6)
        result['notices'] = [{'where': name, 'message': message} for message in said]
    return result


def drop(ctx: Context) -> dict[str, Any]:
    """Go back to the shipped text of a prompt whose edit is sent in its place: the shipped text becomes the newest
    version, so later shipped changes flow in again, STORE-044."""
    name = str(ctx.nouns['name'])
    shipped = _known(ctx, name)
    try:
        newest = prompts.prompt_version(name)
    except StoreError:
        raise Stop(f'{name} has no edit: its shipped text is sent.', f'metaform prompt {name}') from None
    if newest.origin != 'edited':
        raise Stop(f'{name} has no edit: version {newest.number}, its shipped text, is sent.',
                   f'metaform prompt {name}')
    version = prompts.add_prompt_version(name, shipped, newest.number, origin='shipped')
    reached, kept = _reach(ctx, name)
    return {'name': name, 'revision': version.number, 'origin': version.origin, 'dropped': newest.number,
            'sent': f'the shipped text, to {"; ".join(reached)}', **({'running_not_reached': kept} if kept else {})}


# ------------------------------------------------------------------------------------------------ what was sent

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


SESSION = Noun('session', 'The session id, or its runner\'s id (METAFORM_SESSION).')
NAME = Noun('name', 'The prompt, by its name in the prompt store, such as dispatch:system.')

MODULE = Module(
    id='agents',
    summary='The roles of the agents Metaform starts, the prompts each is sent, and what each session was sent.',
    purpose='One record for each role an agent Metaform starts runs as: what it is for, the prompts it is sent in '
            'order and when, with each prompt\'s text and version in the prompt store, its tools and authority, and '
            'the agents running as it now. An edit saved with override is sent in place of the shipped text. '
            'Details: metaform help agents.',
    details='The prompts stay in their modules\' prompts.xml and the modules still send them, through the prompt '
            'store (STORE-044). A prompt name that no longer resolves is reported on the role, never dropped.',
    verbs=(
        Verb('roles', roles, 'List the roles of the agents Metaform starts, with the prompts each is sent.',
             effect='read'),
        Verb('specialists', authored.SERVICE.specialists, 'List reusable expertise and role URLs, without duty bodies.',
             effect='read'),
        Verb('role', role, 'Read one role: what it is for, each prompt it is sent with its text and version, its '
                           'tools and authority, and the agents running as it.',
             nouns=(Noun('name', 'The role: intake, system, sentinel, talk, prep or worker.'),), effect='read'),
        Verb('resolve', authored.resolve, "Resolve a role's responsibilities and the prompt components actually selected "
                                          'without changing an agent assignment.',
             nouns=(Noun('name', 'The role name or URI from an enabled module provider.'),),
             effect='read'),
        Verb('receipts', authored.inspect_receipts, 'Read context delivery fingerprints and versions, without bodies.',
             nouns=(SESSION,), effect='read'),
        Verb('confirm', authored.confirm_context, 'Confirm a startup context checkpoint using your retained key; '
             'omit the key if it is unavailable. Missing proof makes only requested context eligible again.',
             nouns=(Noun('checkpoint', 'The checkpoint in the startup request.'),
                    Noun('key', 'The key retained from the context instructions; omit if lost.', required=False)),
             effect='write'),
        Verb('updates', updates, 'Read selected prompt merge evidence, exact parent versions and retained conflicts.',
             nouns=(Noun('name', 'An existing prompt component identity; omit to read every applied update.',
                         required=False),), effect='read'),
        Verb('sent', sent, 'Read which role a session ran as and which prompt versions each of its turns carried.',
             nouns=(SESSION,), effect='read'),
        Verb('override', override, "Save an edit of a role's prompt, sent in place of the shipped text; the result "
                                   'says which roles take it and when.',
             nouns=(NAME, Noun('text', 'The edited prompt as plain text, as the agent reads it: & and < are written '
                                       'as they are, and each fill place as <name/>, such as <work_id/>.'),
                    Noun('parent', 'The version this edit came from; the newest by default.', kind='int',
                         required=False)),
             caution='Every agent of the roles that name this prompt is sent the edit, each as its role takes it.',
             cautioned=_sent_caution, page='the Prompt tab'),
        Verb('drop', drop, "Go back to a prompt's shipped text, so its edit is no longer sent.", nouns=(NAME,),
             caution='Every agent of the roles that name this prompt is sent the shipped text, each as its role takes '
                     'it.',
             cautioned=_sent_caution, page='the Prompt tab'),
    ),
    subscriptions=(Subscription('prompt.sent', record), Subscription('session.compacted', authored.compacted)),
    provides=(Provides('agent.role', authored.SERVICE), Provides('agent.roles', authored.generated)),
    resources=(Resource('metaform://specialists', 'Specialist registry',
                        'Reusable specialist names, purposes and role URLs, without prompt bodies.', 'specialists'),
               Resource('metaform://role/{name}', 'Authored role',
                        'The authored responsibility, provider and resolved prompt versions.', 'resolve'),),
    tables=TABLES,
)
