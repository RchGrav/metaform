"""hello: each chassis feature working once, BASE-019.

  settings  `greeting` and `loud`, declared in code; `loud` is also greet's switch,
            CLI-012; `favorite` is a select whose choices come from this module's data
  greet     a sync verb with a noun and a switch; it publishes hello.greeted
  wait      an async verb
  history   reads what the event subscriber recorded, a layer in the project store
  live      the chassis announces the subscriber's write as map.changed, so an open web GUI shows the greeting at once,
            VIEW-018; the module does nothing for it
  forget    a caution verb that acts only with --confirm
  todo      writes a work record, the condition of this module's own element kept apart from the map, MAP-046;
            done resolves it, and the status line counts what is still to do
  beep      a verb that runs on one system only, BASE-016
  status    a status hook that adds one line to `metaform` status
  visit     counts a name in hello's own table beside the map, which goes with the metaform, STORE-045
  note      keeps a note in hello's own project-level table, which a clear of the project's metaforms keeps;
            notes lists them in time order, through the table's index
  node_read adds how many names hello has greeted to `map where` and `map node` of its own element, BASE-035
  work_read todo keeps how many names hello had greeted when the task was written, in hello's own table keyed by the
            work id, and work_read shows it on that work record in `map work id=<id>`, BASE-035; the work table's
            layout is unchanged, STORE-045

Each public import a module can use, shown once:
  count           ctx.say, a message for a person beside the data the verb returns
  welcome         ctx.publish_async, publishing from an async verb
  later           ctx.spawn, a task hello owns that the chassis cancels when the process ends or hello unloads
  follow          ctx.listen, map.changed from another process heard in this one, BASE-053
  greet-favorite  Stop, a user error with the one command to run next
  uptime          start and stop, the hooks that run when hello loads and unloads
  history         Module.default, what `metaform hello` runs with no verb
  repeat          settings.number, `times`
  greet-friends   settings.items, `friends`
  report          save_report, a report file on hello's layer
  feedback        feedback, on the Metaform process
  reports         list_reports
  read-report     read_report

The greeting history is items in a layer this module declares, attached to an
element the layer creates for them, STORE-022 and D22.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from metaform import home, settings
from metaform import module as chassis
from metaform.data import (
    Column,
    Data,
    DataTx,
    Index,
    Layer,
    NewerStore,
    Node,
    Operation,
    Store,
    Table,
    Tables,
    WorkRecord,
    plain,
    query_read,
    query_reads,
)
from metaform.module import (
    AgentRoleDefinition,
    Context,
    Module,
    Noun,
    Provides,
    Status,
    Stop,
    Subscription,
    Verb,
    feedback,
    list_reports,
    read_report,
    save_report,
)

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = True
REMOTE_AGENT = False  # a demonstration of the module contract, with nothing for project work

LAYER = 'hello.greetings'
HOLDER = 'code.module.hello'
PROVENANCE = {'module': 'hello', 'workflow': 'greet', 'role': 'module'}


def _names(store: Store) -> list[str]:
    """The names greeted so far. No layer yet means no names yet; any other failure is real and raises."""
    if not any(layer.name == LAYER for layer in store.layers(limit=0).results):
        return []
    items = store.layer_items(LAYER, limit=0).results
    return [str(item.value) for item in items if getattr(item, 'id', None)]


def _favorite_choices(ctx: Context) -> list[str]:
    return sorted(set(_names(ctx.store))) if ctx.store is not None else []


settings.text('greeting', 'hello', help='The word hello greets with.')
settings.boolean('loud', False, help='Shout the greeting.')
settings.choice('favorite', choices=_favorite_choices,
                help="A name hello has greeted. Its choices come from the module's own data.")
settings.number('times', 1, min=1, max=10, help='How many times repeat says the greeting.')
settings.items('friends', help='The names greet-friends greets.')


def greet(ctx: Context) -> str:
    ctx.require_store()
    name = ctx.nouns['name']
    text = f"{ctx.setting('greeting')}, {name}"
    if ctx.setting('loud'):
        text = text.upper() + '!'
    ctx.publish('hello.greeted', {'name': name})
    return text + '\n'


async def wait(ctx: Context) -> str:
    seconds = ctx.nouns['seconds']
    await asyncio.sleep(seconds)
    return f'waited {seconds} s\n'


def basedemo(ctx: Context) -> dict[str, Any]:
    """Shared services are available to an ordinary module as they are to shipped servers, BASE-004."""
    chassis.refresh_modules()
    project = home.project(ctx.project) if ctx.project else None
    answer: dict[str, Any] = {
        'home': str(home.home()),
        'registered': [one.project_id for one in home.projects()],
        'project': project.to_dict() if project else None,
        'layers': settings.toggled_layers(ctx.folder),
        'reads': list(query_reads()),
        'newer_store_error': NewerStore.__name__,
        'code_print': chassis.code_print(),
    }
    if ctx.project:
        answer.update(backups=[one.to_dict() for one in home.backups(ctx.project)],
                      held=home.not_empty(ctx.project),
                      caution=home.removal_caution(ctx.project))
    if ctx.store is not None:
        answer['roots'] = plain(query_read(ctx.store, 'roots', {'limit': '0'}))
    return answer


def base_restore(ctx: Context) -> dict[str, Any]:
    """Restore the selected project's backup through the public base after verb confirmation, QUAL-016."""
    project = ctx.require_store().project().project_id
    return home.restore_project(project, ctx.nouns.get('name')).to_dict()


def base_remove(ctx: Context) -> dict[str, str]:
    """Remove the selected empty project's registration through the public base, QUAL-016."""
    project = ctx.require_store().project().project_id
    home.remove_project(project)
    return {'project': project}


def history(ctx: Context) -> list[str] | str:
    names = _names(ctx.require_store())
    return '\n'.join(names) + '\n' if names else 'No greetings yet. Try: metaform hello greet <name>\n'


def forget(ctx: Context) -> str:
    store = ctx.require_store()
    if any(layer.name == LAYER for layer in store.layers(limit=0).results):
        store.discard(LAYER)
    return 'Greeting history deleted.\n'


def beep(ctx: Context) -> str:
    return '\a'


def _own_element(store: Store) -> Layer:
    """The element the greetings hang from, made when no greeting has made it yet, and its layer."""
    with store.atomic():
        layer = store.layer(LAYER, 'hello', 'Who hello has greeted.', mutable=True, hideable=True,
                            provenance=PROVENANCE)
        store.add_element(LAYER, HOLDER)
    return layer


def todo(ctx: Context) -> str:
    """A work record on this module's own element: missing, with the task given, MAP-046 and STORE-042."""
    store = ctx.require_store()
    _own_element(store)
    record = store.add_work(Node('element', HOLDER), 'unbuilt', note='hello has more to do', task=ctx.nouns['task'])
    with store.tables() as tx:  # hello's own field on the record, in its own table, STORE-045
        tx.insert('todos', {'work_id': record.id, 'greeted': len(_names(store))})
    return f'To do: {ctx.nouns["task"]} ({record.id})\n'


def done(ctx: Context) -> str:
    """Mark one of this module's work records done, its resolution kept beside it."""
    record = ctx.require_store().finish_work(ctx.nouns['id'], ctx.nouns['resolution'])
    return f'Done: {record.task} ({record.resolution})\n'


def _to_do(store: Store) -> int:
    return len(store.work(Node('element', HOLDER), open=True, limit=0).results)


def record(payload: dict[str, Any], ctx: Context) -> None:
    """hello.greeted: remember the name as one item of this module's layer."""
    store = ctx.require_store()
    with store.atomic():
        layer = store.layer(LAYER, 'hello', 'Who hello has greeted.', mutable=True, hideable=True,
                            provenance=PROVENANCE)
        store.add_element(LAYER, HOLDER)
        store.add_item(LAYER, Node('element', HOLDER), payload['name'])
    if layer.ready is None:  # finished, it is seen in context and stays editable, STORE-032
        store.finish(LAYER)


def count(ctx: Context) -> dict[str, int]:
    """ctx.say writes a message for a person; the data an agent needs back is the return value, BASE-036."""
    greeted = len(_names(ctx.require_store()))
    ctx.say(f'hello has greeted {greeted} {"name" if greeted == 1 else "names"}.')
    return {'greeted': greeted}


async def welcome(ctx: Context) -> str:
    """An async verb publishes with ctx.publish_async; ctx.publish would block its loop, BASE-009 and BASE-010."""
    ctx.require_store()
    name = ctx.nouns['name']
    await ctx.publish_async('hello.greeted', {'name': name})
    return f'welcome, {name}\n'


async def _greet_after(ctx: Context, name: str, seconds: int) -> None:
    await asyncio.sleep(seconds)
    await ctx.publish_async('hello.greeted', {'name': name})


async def later(ctx: Context) -> str:
    """ctx.spawn starts a task hello owns: it runs on after the verb returns, as in the MCP server, and the chassis
    cancels it when the process ends or hello unloads, BASE-018. From the command line the process ends at once."""
    ctx.require_store()
    name, seconds = ctx.nouns['name'], ctx.nouns['seconds']
    ctx.spawn(_greet_after(ctx, name, seconds))
    return f'Greeting {name} in {seconds} s from a task hello owns; the chassis cancels the task if the process ends ' \
           'first.\n'


async def follow(ctx: Context) -> dict[str, Any]:
    """ctx.listen hears each map.changed published in another process of this home, BASE-053: the handler runs in the
    listener's own thread, so it hands the payload to this loop. hello waits for the next change and shows it."""
    loop = asyncio.get_running_loop()
    heard: asyncio.Future[dict[str, Any]] = loop.create_future()

    def told(payload: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(lambda: heard.done() or heard.set_result(payload))
    with ctx.listen(told):
        ctx.say('Waiting for the next change to the map made in another process.')
        payload = await heard
    ctx.say(f'{payload.get("project")} changed, metaform {payload.get("base_id") or "list"}.')
    return {'changed': [payload]}


def greet_favorite(ctx: Context) -> str:
    """A verb raises Stop for a user error: what happened and the one command to run next, CLI-009."""
    favorite = ctx.setting('favorite')
    if not favorite:
        raise Stop('No favorite is set.', 'metaform set --favorite <name>')
    ctx.nouns['name'] = favorite
    return greet(ctx)


_loaded: dict[str, float] = {}  # what start sets up for this process and stop takes down


def start(ctx: Context) -> None:
    """Runs once when hello loads, before its first verb, subscriber or tool call, BASE-018."""
    _loaded['at'] = time.monotonic()


def stop(ctx: Context) -> None:
    """Runs once when hello unloads or the process ends, after its spawned tasks are cancelled, BASE-018."""
    _loaded.clear()


def uptime(ctx: Context) -> str:
    return f'hello started {time.monotonic() - _loaded["at"]:.1f} s ago in this process.\n'


def repeat(ctx: Context) -> str:
    """Reads `times`, a number setting."""
    return f"{ctx.setting('greeting')}, {ctx.nouns['name']}\n" * ctx.setting('times')


def greet_friends(ctx: Context) -> str:
    """Reads `friends`, an items setting, and greets each name."""
    friends = ctx.setting('friends')
    if not friends:
        return 'No friends set. Try: metaform set --friends ada,bob\n'
    greetings: list[str] = []
    for friend in friends:
        ctx.nouns['name'] = friend
        greetings.append(greet(ctx))
    return ''.join(greetings)


def report(ctx: Context) -> str:
    """save_report writes a report file in the home, on hello's layer, whose provenance then carries it, BASE-045."""
    store = ctx.require_store()
    layer = _own_element(store)
    return save_report(store.project_id, layer.id, 'report', ctx.nouns['text'], store=store,
                       layer=layer.id) + '\n'


def send_feedback(ctx: Context) -> dict[str, Any]:
    """feedback saves feedback on the Metaform process, never refused for what it says, BASE-045."""
    return feedback(ctx.folder, ctx.nouns['text'], project=ctx.project)


def reports(ctx: Context) -> str:
    """list_reports lists the report, feedback and shape files of the folder's project, BASE-045."""
    names = [row.name for row in list_reports(ctx.folder, project=ctx.project, limit=0).results]
    return '\n'.join(names) + '\n' if names else 'No reports yet.\n'


def read_one_report(ctx: Context) -> str:
    """read_report returns one listed file's text exactly, BASE-045."""
    return read_report(ctx.folder, ctx.nouns['name'], project=ctx.project)


# hello's own tables, STORE-045: the chassis creates them on first use, versions them with this version, and
# carries them through backup, export, import and clear. `visits` is beside the map, in the metaform's store, and
# goes with the metaform; `notes` is in the project's store for hello and stays when the metaforms are cleared.
# `todos` keeps hello's own field on each work record todo writes, keyed by the work id, beside the map as the work
# records are; version 2 added it.
TABLES = Tables(version=2, tables=(
    Table('visits', place='metaform', key=('name',),
          columns=(Column('name', required=True), Column('times', 'int', required=True, default=0))),
    Table('todos', place='metaform', key=('work_id',),
          columns=(Column('work_id', required=True), Column('greeted', 'int', required=True))),
    Table('notes', place='project', key=('note_id',),
          columns=(Column('note_id', required=True), Column('text', required=True), Column('at', required=True)),
          indexes=(Index(('at',)),)),
))


def count_visit(tx: DataTx, name: str) -> str:
    """Count a visit in one transaction: read the name's row by its key, then add it or change it."""
    tables = tx.tables()
    held = tables.get('visits', {'name': name})
    if held is None:
        row = tables.insert('visits', {'name': name, 'times': 1})
    else:
        row = tables.update('visits', {'name': name}, {'times': held['times'] + 1}) or held
    return f'{name}: {row["times"]} visit{"" if row["times"] == 1 else "s"}\n'


def visit(ctx: Context) -> str:
    return ctx.require_store().count_visit(ctx.nouns['name'])


def note(ctx: Context) -> str:
    """Keep a note in the project-level table."""
    with ctx.require_store().tables() as tx:
        row = tx.insert('notes', {'note_id': uuid.uuid4().hex, 'text': ctx.nouns['text'],
                                  'at': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S.%fZ')})
    return f'Noted ({row["note_id"]}).\n'


def notes(ctx: Context) -> str:
    """The notes in time order: every read goes through an index, here the one on `at`, STORE-005."""
    with ctx.require_store().tables(write=False) as tx:
        found = tx.rows('notes', by=('at',), limit=0).results
    return ''.join(f'{row["text"]}\n' for row in found) or 'No notes yet. Try: metaform hello note <text>\n'


def node_read(ctx: Context, node: Node) -> dict[str, int] | None:
    """What hello adds to the read of a node: at its own element, how many names it has greeted; nothing elsewhere.
    The chassis puts it under `hello` in `map where` and `map node`, BASE-035."""
    if ctx.store is None or node != Node('element', HOLDER):
        return None
    return {'greeted': len(_names(ctx.store))}


def work_read(ctx: Context, record: WorkRecord) -> dict[str, int] | None:
    """What hello keeps on a work record todo wrote: how many names it had greeted then; nothing on any other
    record. The chassis puts it under `hello` in `map work id=<id>`, BASE-035."""
    if ctx.store is None:
        return None
    with ctx.store.tables(write=False) as tx:
        row = tx.get('todos', {'work_id': record.id})
    return None if row is None else {'greeted': row['greeted']}


def status(ctx: Context) -> Status:
    if ctx.store is None:
        return Status()
    count, open_work = len(_names(ctx.store)), _to_do(ctx.store)
    if not count and not open_work:
        return Status()
    return Status(lines=(f'Hello: {count} greeted' + (f', {open_work} to do' if open_work else ''),))


MODULE = Module(
    id='hello',
    summary='Hello World: a demonstration of every module feature.',
    purpose='Shows each Metaform module feature working once: it greets names, keeps them as a layer, '
            'publishes an event for each greeting, and keeps what it still has to do as work records. Use it to see '
            'how a module behaves. Details: metaform help hello.',
    details='Settings are declared in code and appear in set, unset and the settings screen. '
            'The favorite setting takes its choices from the names this module has greeted. '
            'metaform hello with no verb runs history, its default verb.',
    verbs=(
        Verb('greet', greet, 'Greet a name and publish hello.greeted.',
             nouns=(Noun('name', 'The name to greet.'),), switches=('loud',),
             examples=(('metaform hello greet world', 'Prints hello, world.'),
                       ('metaform hello greet world --loud', 'Prints HELLO, WORLD!'))),
        Verb('wait', wait, 'Wait a number of seconds. Shows an async verb, and a task over MCP.',
             nouns=(Noun('seconds', 'How long to wait.', kind='int'),), effect='read', task=True),
        Verb('basedemo', basedemo, 'Show the shared home, project, layer and query services.', effect='read'),
        Verb('base-restore', base_restore, 'Restore a clear backup through the public base.',
             nouns=(Noun('name', 'The backup name, newest when omitted.', required=False),),
             caution="This restores the selected project's clear backup, backing up what it holds now.", effect='remove',
             person_says=True),  # the person's decision: an agent's confirm never runs it, CLI-011
        Verb('base-remove', base_remove, "Remove the selected empty project's registration through the public base.",
             caution="This removes the selected empty project's registration, keeping its files and backups.", effect='remove'),
        Verb('history', history, 'List the names greeted so far.', effect='read'),
        Verb('forget', forget, 'Delete the greeting history.', caution='This deletes the greeting history.', effect='remove'),
        Verb('beep', beep, 'Sound the terminal bell. Shows a verb that runs on one system.',
             supported_os=('windows',), effect='read'),
        Verb('todo', todo, "Write a work record on this module's own element: something still to do.",
             nouns=(Noun('task', 'What it needs.'),),
             examples=(('metaform hello todo "greet in every language"', 'Records a missing work record.'),)),
        Verb('done', done, 'Mark one of those work records done, keeping its resolution.',
             nouns=(Noun('id', 'The work record id todo returned.'), Noun('resolution', 'How it was resolved.'))),
        Verb('count', count, 'Count the names greeted. Shows ctx.say beside the data a verb returns.', effect='read'),
        Verb('welcome', welcome, 'Greet a name from an async verb. Shows ctx.publish_async.',
             nouns=(Noun('name', 'The name to greet.'),)),
        Verb('later', later, 'Greet a name after some seconds, from a task hello owns. Shows ctx.spawn.',
             nouns=(Noun('name', 'The name to greet.'), Noun('seconds', 'How long to wait.', kind='int')),
             details='The task runs on after the verb returns for as long as the process runs, as the MCP server '
                     'does. The chassis cancels it when the process ends or hello unloads, so from the command line '
                     'the name is not greeted.'),
        Verb('follow', follow, 'Wait for the next map change made in another process and show it. Shows ctx.listen.',
             surfaces=('cli',),
             details='Run it in one terminal and change the map in another, such as with metaform map work op=add; it prints '
                     'the change and ends. A module whose process runs on, such as the web GUI\'s server, listens '
                     'the same way for as long as it runs.'),
        Verb('greet-favorite', greet_favorite, 'Greet the favorite name. Shows Stop when none is set.'),
        Verb('uptime', uptime, 'How long ago hello started in this process. Shows the start and stop hooks.', effect='read'),
        Verb('repeat', repeat, 'Say the greeting --times times. Shows a number setting.',
             nouns=(Noun('name', 'The name to greet.'),), switches=('times',),
             examples=(('metaform hello repeat world --times 3', 'Prints hello, world three times.'),), effect='read'),
        Verb('greet-friends', greet_friends, 'Greet each name in --friends. Shows an items setting.',
             switches=('friends',),
             examples=(('metaform hello greet-friends --friends ada,bob', 'Greets ada and bob.'),)),
        Verb('report', report, "Save a report on hello's layer. Shows save_report.",
             nouns=(Noun('text', 'The report.'),)),
        Verb('feedback', send_feedback, 'Save feedback on the Metaform process. Shows feedback.',
             nouns=(Noun('text', 'The feedback.'),)),
        Verb('reports', reports, "List this project's report, feedback and shape files. Shows list_reports.", effect='read'),
        Verb('read-report', read_one_report, 'Print one report file exactly. Shows read_report.',
             nouns=(Noun('name', 'The file name reports lists.'),), effect='read'),
        Verb('visit', visit, "Count a visit by a name in hello's own table beside the map. Shows Module.tables.",
             nouns=(Noun('name', 'The name visiting.'),)),
        Verb('note', note, "Keep a note in hello's own project-level table, which a clear keeps.",
             nouns=(Noun('text', 'The note.'),)),
        Verb('notes', notes, "List hello's notes in time order, read through the table's index.", effect='read'),
    ),
    subscriptions=(Subscription('hello.greeted', record),),
    start=start,
    stop=stop,
    status=status,
    default='history',
    tables=TABLES,
    data=Data(operations={'count_visit': Operation(count_visit, write=True)}),
    node_read=node_read,
    work_read=work_read,
    provides=(Provides('agent.roles', (
        AgentRoleDefinition('hello.greeter', 'Welcome an assigned visitor and return the greeting.',
                            ('hello:role_greeter',)),
    )),),
)
